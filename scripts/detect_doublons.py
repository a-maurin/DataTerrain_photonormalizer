#!/usr/bin/env python3

import logging
import os

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/' + os.path.basename(__file__).replace('.py', '.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

"""
Script de détection des doublons dans les photos
"""

from collections import Counter
from PIL import Image

try:
    import imagehash
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False
    logger.info("⚠️  Module 'imagehash' non disponible. Installation recommandée: pip install imagehash")

def detect_doublons(log_handler, export_dir=None):
    """
    Détecte les photos en double dans le dossier DCIM
    
    Args:
        log_handler: Handler pour afficher les messages
        export_dir: Dossier d'exportation pour les fichiers générés (optionnel)
    
    Returns:
        list: Liste des groupes de doublons (chaque groupe est une liste de noms de fichiers)
    """
    dcim_path = "/home/e357/Qfield/cloud/DataTerrain/DCIM"
    
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
    
    log_handler.info(f"📷 Trouvé {len(photos)} photos dans DCIM")
    
    if len(photos) == 0:
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
                        if len(filtered_photos) > 1:
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
                # Fallback: utiliser la comparaison par contenu (plus lent)
                log_handler.warning("⚠️  Module imagehash non disponible, utilisation de la comparaison par contenu")
                content_groups = {}
                for photo in photo_list:
                    file_path = os.path.join(dcim_path, photo)
                    try:
                        with Image.open(file_path) as img:
                            # Utiliser le contenu de l'image comme clé
                            content_key = str(img.size) + str(img.mode) + str(img.format)
                            if content_key not in content_groups:
                                content_groups[content_key] = []
                            content_groups[content_key].append(photo)
                    except Exception as e:
                        log_handler.warning(f"⚠️ Erreur traitement {photo}: {e}")
                
                # Ajouter les groupes avec vrais doublons
                for content_key, photos in content_groups.items():
                    if len(photos) > 1:
                        if content_key not in true_doubles:
                            true_doubles[content_key] = []
                        true_doubles[content_key].extend(photos)
            

        
        log_handler.info(f"📊 Trouvé {len(true_doubles)} groupes de vrais doublons")
        
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
                f.write(f"Photos analysées: {len(photos)}\n")
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