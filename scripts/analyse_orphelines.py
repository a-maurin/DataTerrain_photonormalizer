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
Script d'analyse des photos orphelines intégré au nouveau système
"""

import re
import sys
from qgis.core import QgsVectorLayer

try:
    from ..core.project_config import (
        get_dcim_path,
        get_gpkg_path,
        get_layer_name,
        get_photo_field_name,
        get_coord_tolerance,
    )
except ImportError:
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from core.project_config import (
        get_dcim_path,
        get_gpkg_path,
        get_layer_name,
        get_photo_field_name,
        get_coord_tolerance,
    )


def extraire_coord_du_nom(nom_fichier):
    """
    Extraire les coordonnées d'un nom de fichier
    Formats supportés:
    - DT_YYYY-MM-DD_FID_agent_type_X_Y.jpg
    - DT_YYYYMMDD_HHMMSS_X_Y.jpg
    """
    # Pattern pour extraire les coordonnées du nom de fichier
    # Format 1: DT_YYYY-MM-DD_FID_..._X_Y.jpg (avec agent et type multi-parties)
    pattern1 = r'DT_\d{4}-\d{2}-\d{2}_(\d+)_(.+?)_([-+]?\d+\.?\d*)_([-+]?\d+\.?\d*)\.jpg'
    # Format 2: DT_YYYYMMDD_HHMMSS_X_Y.jpg
    pattern2 = r'DT_\d{8}_\d{6}_([-+]?\d+\.?\d*)_([-+]?\d+\.?\d*)\.jpg'
    
    match = re.match(pattern1, nom_fichier) or re.match(pattern2, nom_fichier)
    
    if match:
        if match.re.pattern == pattern1:
            # Format avec FID
            fid = int(match.group(1))
            x = float(match.group(3))
            y = float(match.group(4))
            return fid, x, y
        else:
            # Format sans FID (seulement coordonnées)
            x = float(match.group(1))
            y = float(match.group(2))
            return None, x, y  # FID est None pour ce format
    return None, None, None

def analyser_photos_orphelines(log_handler):
    """
    Analyser les photos orphelines et comparer avec les entités
    
    Args:
        log_handler: Handler pour afficher les messages et logs
    """
    
    # Configuration (config centralisée Linux / Windows)
    gpkg_file = get_gpkg_path()
    layer_name = get_layer_name()
    pfn = get_photo_field_name()
    tol = get_coord_tolerance()
    dcim = get_dcim_path()
    
    log_handler.info("🔍 Analyse des photos orphelines en cours...")
    
    # Récupération de la couche depuis le GeoPackage
    try:
        layer = QgsVectorLayer(f"{gpkg_file}|layername={layer_name}", layer_name, "ogr")
        if not layer.isValid():
            log_handler.error(f"❌ La couche '{layer_name}' est introuvable dans {gpkg_file}.")
            log_handler.error(
                f"💡 Vérifiez que le fichier GeoPackage existe et contient la table '{layer_name}'."
            )
            return False
        log_handler.info(f"✅ Couche '{layer_name}' chargée avec succès")
    except Exception as e:
        log_handler.error(f"❌ Erreur lors de la récupération de la couche : {e}")
        return False
    
    if not os.path.exists(dcim):
        log_handler.error(f"Dossier DCIM introuvable : {dcim}")
        return False
    
    log_handler.info(f"📁 Analyse du dossier : {dcim}")
    
    # Lister les photos dans DCIM
    photos = []
    
    for file in os.listdir(dcim):
        if file.lower().endswith('.jpg'):
            photos.append(file)
    
    log_handler.info(f"📷 Trouvé {len(photos)} photos dans DCIM")
    
    # Analyser chaque photo
    photos_orphelines = []
    photos_avec_entite = []
    
    for photo in photos:
        fid, x, y = extraire_coord_du_nom(photo)
        
        if fid is None and x is not None and y is not None:
            # Format ancien (DT_YYYYMMDD_HHMMSS_X_Y.jpg) - pas de FID
            log_handler.info(f"ℹ️  Format ancien (sans FID) : {photo}")
            photos_orphelines.append((photo, None, False))
            continue
        elif fid is None:
            log_handler.debug(f"🐞 Format non reconnu : {photo}")
            continue
        
        # Exclure les photos avec un FID temporaire (0)
        if fid == 0:
            log_handler.info(f"ℹ️  Photo avec FID temporaire exclue: {photo}")
            continue
        
        # Rechercher l'entité correspondante (FID = feature.id() en QGIS)
        entite_trouvee = False
        for feature in layer.getFeatures():
            if feature.id() == fid:
                entite_trouvee = True
                # Vérifier si la photo est associée
                photo_field = feature[pfn]
                if photo_field and photo in photo_field:
                    photos_avec_entite.append((photo, fid, True))
                else:
                    photos_orphelines.append((photo, fid, False))
                break
        
        if not entite_trouvee:
            # Vérifier si une entité existe déjà à ces coordonnées
            entite_existante = None
            for feature in layer.getFeatures():
                if feature.geometry() and not feature.geometry().isEmpty():
                    point = feature.geometry().asPoint()
                    if abs(point.x() - x) < tol and abs(point.y() - y) < tol:
                        entite_existante = feature
                        break
            
            if entite_existante:
                log_handler.info(f"ℹ️  Entité existante trouvée à {x},{y} (FID: {entite_existante.id()})")
                photos_avec_entite.append((photo, entite_existante.id(), True))
            else:
                photos_orphelines.append((photo, fid, False))
    
    # Afficher les résultats
    log_handler.info(f"\n📊 Résultats de l'analyse:")
    log_handler.info(f"  • Photos avec entité associée: {len(photos_avec_entite)}")
    log_handler.info(f"  • Photos orphelines: {len(photos_orphelines)}")
    
    if photos_orphelines:
        log_handler.info(f"\n📋 Photos orphelines ({len(photos_orphelines)}):")
        for photo, fid, _ in photos_orphelines[:10]:  # Afficher les 10 premières
            if fid is not None:
                log_handler.info(f"  • {photo} (FID: {fid})")
            else:
                log_handler.info(f"  • {photo} (Format ancien - pas de FID)")
        if len(photos_orphelines) > 10:
            log_handler.info(f"  • ... et {len(photos_orphelines) - 10} autres")
    
    # Sauvegarder les résultats
    try:
        # Calculer le chemin correct vers le dossier exports (dans le dossier du plugin)
        plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        export_dir = os.path.join(plugin_dir, 'exports')
        
        # Créer le dossier s'il n'existe pas
        os.makedirs(export_dir, exist_ok=True)
        
        report_path = os.path.join(export_dir, 'analyse_orphelines.txt')
        
        with open(report_path, 'w') as f:
            f.write("Analyse des photos orphelines\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Photos analysées: {len(photos)}\n")
            f.write(f"Photos avec entité: {len(photos_avec_entite)}\n")
            f.write(f"Photos orphelines: {len(photos_orphelines)}\n\n")
            
            for photo, fid, _ in photos_orphelines:
                if fid is not None:
                    f.write(f"{photo} (FID: {fid})\n")
                else:
                    f.write(f"{photo} (Format ancien - pas de FID)\n")
        
        log_handler.info(f"📄 Rapport sauvegardé: {report_path}")
        return True
    except Exception as e:
        log_handler.error(f"❌ Erreur sauvegarde rapport: {e}")
        return False