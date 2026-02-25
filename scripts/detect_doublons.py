#!/usr/bin/env python3

import logging
import os

# Configuration du logging (sans FileHandler pour éviter ResourceWarning de fichier non fermé)
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

"""
Script de détection des doublons dans les photos
"""

import re
import sys
import hashlib
from collections import Counter

try:
    from ..core.project_config import get_dcim_path, get_gpkg_path
except ImportError:
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from core.project_config import get_dcim_path, get_gpkg_path

from PIL import Image

try:
    import imagehash
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False
    logger.info("⚠️  Module 'imagehash' non disponible. Installation recommandée: pip install imagehash")


def _fid_depuis_nom_photo(photo_name):
    """Extrait le FID du nom de fichier (format DT_YYYY-MM-DD_FID_...). Retourne None si absent."""
    if not photo_name or not isinstance(photo_name, str):
        return None
    match = re.match(r'DT_\d{4}-\d{2}-\d{2}_(\d+)_', photo_name)
    return int(match.group(1)) if match else None


def _groupe_contient_doublon_meme_fid(photo_list):
    """
    Vérifie si le groupe contient deux photos ou plus avec le même FID dans le nom.
    Deux photos avec le même FID = sessions différentes (utilisateurs, dates, lieux différents) → pas des doublons.
    """
    fids = [f for f in (_fid_depuis_nom_photo(p) for p in photo_list) if f is not None]
    return len(fids) != len(set(fids))


def _extraire_coord_du_nom(nom_fichier):
    """Extrait les coordonnées d'un nom de fichier (format DT_YYYY-MM-DD_FID_..._X_Y.jpg)."""
    # Pattern pour capturer les deux derniers nombres avant .jpg comme coordonnées
    # Format: DT_YYYY-MM-DD_FID_agent_type_X_Y.jpg
    pattern = r'DT_\d{4}-\d{2}-\d{2}_\d+_.+_([-+]?\d+\.?\d*)_([-+]?\d+\.?\d*)\.jpg$'
    match = re.match(pattern, nom_fichier)
    if match:
        try:
            return float(match.group(1)), float(match.group(2))
        except (ValueError, IndexError):
            return None, None
    return None, None


def _calculer_hash_fichier(file_path):
    """Calcule le hash MD5 d'un fichier pour comparaison."""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return None


def _detecter_doublons_par_metadonnees(dcim_path, log_handler):
    """
    Détecte les doublons basés sur les métadonnées : photos orphelines avec même FID et coordonnées
    qu'une photo déjà attachée à une entité.
    """
    try:
        from qgis.core import QgsVectorLayer
        gpkg_file = get_gpkg_path()
        layer_name = "saisies_terrain"
        layer = QgsVectorLayer(f"{gpkg_file}|layername={layer_name}", layer_name, "ogr")
        
        if not layer.isValid():
            return []
        
        # Collecter les photos attachées avec leur FID et coordonnées
        photos_attachees = {}  # {(fid, x, y): [noms_photos]}
        for feature in layer.getFeatures():
            photo_field = feature['photo']
            if photo_field and isinstance(photo_field, str):
                photo_name = photo_field.split('/')[-1]
                if photo_name.lower().endswith(('.jpg', '.jpeg')):
                    fid = feature.id()
                    if feature.geometry() and not feature.geometry().isEmpty():
                        pt = feature.geometry().asPoint()
                        key = (fid, round(pt.x(), 2), round(pt.y(), 2))
                        if key not in photos_attachees:
                            photos_attachees[key] = []
                        photos_attachees[key].append(photo_name)
        
        # Chercher les photos orphelines qui correspondent à des photos attachées
        doublons_metadonnees = []
        for file in os.listdir(dcim_path):
            if not file.lower().endswith(('.jpg', '.jpeg')):
                continue
            
            fid = _fid_depuis_nom_photo(file)
            if fid is None or fid == 0:
                continue
            
            x, y = _extraire_coord_du_nom(file)
            if x is None or y is None:
                continue
            
            # Vérifier si cette photo est déjà attachée
            photo_field = None
            for feature in layer.getFeatures():
                pf = feature['photo']
                if pf and file in pf:
                    photo_field = pf
                    break
            
            if photo_field:
                continue  # Photo déjà attachée, pas une orpheline
            
            # Chercher si une photo attachée a le même FID et coordonnées
            key = (fid, round(x, 2), round(y, 2))
            if key in photos_attachees:
                # Doublon détecté : photo orpheline avec même FID et coordonnées qu'une photo attachée
                groupe = [file] + photos_attachees[key]
                doublons_metadonnees.append(groupe)
        
        return doublons_metadonnees
    except Exception as e:
        log_handler.warning(f"⚠️ Erreur détection doublons par métadonnées: {e}")
        return []


def detect_doublons(log_handler, export_dir=None):
    """
    Détecte les photos en double dans le dossier DCIM
    
    Args:
        log_handler: Handler pour afficher les messages
        export_dir: Dossier d'exportation pour les fichiers générés (optionnel)
    
    Returns:
        list: Liste des groupes de doublons (chaque groupe est une liste de noms de fichiers)
    """
    dcim_path = get_dcim_path()
    
    log_handler.info("🔍 Détection des doublons en cours...")
    
    # Vérifier la disponibilité de imagehash
    if not HAS_IMAGEHASH:
        log_handler.warning("⚠️  Module 'imagehash' non installé. Pour une meilleure détection, installez-le avec: pip install imagehash")
        log_handler.warning("📋 Utilisation du mode fallback (comparaison par contenu)")
    
    if not os.path.exists(dcim_path):
        log_handler.error(f"❌ Dossier DCIM introuvable: {dcim_path}")
        return False
    
    # Lister les photos
    photos = []
    for file in os.listdir(dcim_path):
        if file.lower().endswith(('.jpg', '.jpeg', '.png')):
            photos.append(file)
    
    total_photos = len(photos)
    log_handler.info(f"📷 Trouvé {total_photos} photos dans DCIM")
    
    if total_photos == 0:
        log_handler.info("ℹ️ Aucune photo trouvée")
        return True
    
    # Détection des doublons par taille
    log_handler.info("📊 Analyse par taille de fichier...")
    size_groups = {}
    for photo in photos:
        file_path = os.path.join(dcim_path, photo)
        try:
            file_size = os.path.getsize(file_path)
            if file_size not in size_groups:
                size_groups[file_size] = []
            size_groups[file_size].append(photo)
        except Exception as e:
            log_handler.warning(f"⚠️ Erreur lecture {photo}: {e}")
    
    # Filtrer les groupes avec plusieurs photos
    potential_doubles = {k: v for k, v in size_groups.items() if len(v) > 1}
    
    log_handler.info(f"📊 Trouvé {len(potential_doubles)} groupes de photos avec même taille")
    
    # Initialiser true_doubles
    true_doubles = {}
    
    if potential_doubles:
        log_handler.info("🔍 Analyse par hash visuel pour confirmation...")
        
        # Détection des vrais doublons par hash ou comparaison simple
        for size, photo_list in potential_doubles.items():
            if HAS_IMAGEHASH:
                # Utiliser imagehash si disponible
                hash_groups = {}
                for photo in photo_list:
                    file_path = os.path.join(dcim_path, photo)
                    try:
                        with Image.open(file_path) as img:
                            img_hash = str(imagehash.average_hash(img))
                            if img_hash not in hash_groups:
                                hash_groups[img_hash] = []
                            hash_groups[img_hash].append(photo)
                    except Exception as e:
                        log_handler.warning(f"⚠️ Erreur traitement {photo}: {e}")
                
                # Ajouter une vérification supplémentaire pour confirmer que les photos sont réellement identiques
                for hash_val, photos in hash_groups.items():
                    if len(photos) > 1:
                        # Vérifier que les photos sont réellement identiques en comparant leur contenu
                        base_photo = photos[0]
                        base_path = os.path.join(dcim_path, base_photo)
                        
                        for photo in photos[1:]:
                            photo_path = os.path.join(dcim_path, photo)
                            
                            # Comparer les images pixel par pixel
                            try:
                                with Image.open(base_path) as base_img, Image.open(photo_path) as compare_img:
                                    if base_img.size != compare_img.size or base_img.mode != compare_img.mode:
                                        log_handler.info(f"ℹ️  {photo} n'est pas un doublon de {base_photo} (taille ou mode différent)")
                                        hash_groups[hash_val].remove(photo)
                                        continue
                                    
                                    # Comparer les pixels
                                    if list(base_img.getdata()) != list(compare_img.getdata()):
                                        log_handler.info(f"ℹ️  {photo} n'est pas un doublon de {base_photo} (contenu différent)")
                                        hash_groups[hash_val].remove(photo)
                            except Exception as e:
                                log_handler.warning(f"⚠️ Erreur comparaison {photo}: {e}")
                
                # Ajouter les groupes avec vrais doublons
                for hash_val, photos in hash_groups.items():
                    if len(photos) > 1:
                        # Filtrer les photos avec INCONNU_INCONNU (optionnel)
                        filtered_photos = [p for p in photos if "_INCONNU_INCONNU_" not in p]
                        
                        # Si après filtrage il reste des doublons, les ajouter
                        # SAUF si le groupe contient deux photos avec le même FID (sessions différentes → pas des doublons)
                        if len(filtered_photos) > 1:
                            if _groupe_contient_doublon_meme_fid(filtered_photos):
                                log_handler.info(
                                    f"ℹ️  Groupe exclu (même FID, sessions différentes): "
                                    f"{[p for p in filtered_photos[:3]]}{'...' if len(filtered_photos) > 3 else ''}"
                                )
                            else:
                                if hash_val not in true_doubles:
                                    true_doubles[hash_val] = []
                                true_doubles[hash_val].extend(filtered_photos)
                                
                                # AVERTISSEMENT: Ne plus supprimer automatiquement
                                log_handler.warning(f"⚠️  DOUBLONS DÉTECTÉS (non supprimés automatiquement):")
                                for photo in filtered_photos:
                                    log_handler.warning(f"   • {photo}")
                                log_handler.warning(f"📋 Ces photos ont le même contenu visuel mais NE SERONT PAS supprimées automatiquement.")
                                log_handler.warning(f"💡 Pour supprimer des doublons, utilisez l'interface de gestion des doublons avec prudence.")
            else:
                # Fallback: utiliser la comparaison par hash MD5 du contenu du fichier
                log_handler.warning("⚠️  Module imagehash non disponible, utilisation de la comparaison par hash MD5")
                hash_groups = {}
                for photo in photo_list:
                    file_path = os.path.join(dcim_path, photo)
                    try:
                        file_hash = _calculer_hash_fichier(file_path)
                        if file_hash:
                            if file_hash not in hash_groups:
                                hash_groups[file_hash] = []
                            hash_groups[file_hash].append(photo)
                        else:
                            log_handler.warning(f"⚠️ Impossible de calculer le hash pour {photo}")
                    except Exception as e:
                        log_handler.warning(f"⚠️ Erreur traitement {photo}: {e}")
                
                # Ajouter les groupes avec vrais doublons (exclure si même FID = sessions différentes)
                for file_hash, photos in hash_groups.items():
                    if len(photos) > 1 and not _groupe_contient_doublon_meme_fid(photos):
                        if file_hash not in true_doubles:
                            true_doubles[file_hash] = []
                        true_doubles[file_hash].extend(photos)
            
        # Détection supplémentaire : doublons basés sur métadonnées (FID + coordonnées)
        log_handler.info("🔍 Détection des doublons par métadonnées (FID + coordonnées)...")
        doublons_metadonnees = _detecter_doublons_par_metadonnees(dcim_path, log_handler)
        if doublons_metadonnees:
            log_handler.info(f"📊 Trouvé {len(doublons_metadonnees)} groupes de doublons par métadonnées")
            for i, groupe in enumerate(doublons_metadonnees, 1):
                # Utiliser une clé unique pour les doublons métadonnées
                meta_key = f"meta_{i}"
                true_doubles[meta_key] = groupe
                log_handler.info(f"  📋 Groupe métadonnées {i}: {len(groupe)} photos (même FID + coordonnées)")
        
        log_handler.info(f"📊 Trouvé {len(true_doubles)} groupes de vrais doublons au total")
        
        # Sauvegarder les résultats
        try:
            # Utiliser le dossier d'exportation si disponible, sinon le dossier par défaut
            if export_dir:
                os.makedirs(export_dir, exist_ok=True)
            else:
                # Calculer le chemin correct vers le dossier exports (dans le dossier du plugin)
                plugin_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                export_dir = os.path.join(plugin_dir, 'exports')
                os.makedirs(export_dir, exist_ok=True)
            
            report_path = os.path.join(export_dir, 'doublons_detection.txt')
            with open(report_path, 'w') as f:
                f.write("Détection de doublons\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Photos analysées: {total_photos}\n")
                f.write(f"Groupes de doublons: {len(true_doubles)}\n\n")
                
                for i, (hash_val, photo_list) in enumerate(true_doubles.items(), 1):
                    f.write(f"Groupe {i} (hash: {hash_val}):\n")
                    for photo in photo_list:
                        f.write(f"  • {photo}\n")
                    f.write("\n")
            
            log_handler.info(f"📄 Rapport sauvegardé: {report_path}")
            
            # Afficher un résumé
            if len(true_doubles) > 0:
                log_handler.info("📋 Résumé des doublons:")
                for i, (hash_val, photo_list) in enumerate(true_doubles.items(), 1):
                    if i <= 5:  # Afficher max 5 groupes
                        log_handler.info(f"  Groupe {i}: {len(photo_list)} photos")
            
        except Exception as e:
            log_handler.error(f"❌ Erreur sauvegarde rapport: {e}")
            return []
    else:
        log_handler.info("✅ Aucune photo en double détectée")
        return []
    
    log_handler.info("✅ Détection des doublons terminée")
    
    # Debug: afficher le format des données retournées
    if true_doubles:
        log_handler.debug(f"📋 Format des données: {type(true_doubles)}")
        log_handler.debug(f"📋 Nombre de groupes: {len(true_doubles)}")
        for i, (key, photos) in enumerate(list(true_doubles.items())[:3]):  # Afficher les 3 premiers
            log_handler.debug(f"📋 Groupe {i}: clé='{key}', {len(photos)} photos")
    
    return list(true_doubles.values()) if true_doubles else []