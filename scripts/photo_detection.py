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
Script de détection des photos non référencées
"""

from qgis.core import QgsVectorLayer

def detect_unreferenced_photos(log_handler, export_dir):
    """
    Détecte les photos non référencées dans le dossier DCIM
    
    Args:
        log_handler: Handler pour afficher les messages
        export_dir: Dossier pour exporter les résultats
    """
    # Chemins par défaut
    dcim_path = "/home/e357/Qfield/cloud/DataTerrain/DCIM"
    gpkg_file = "/home/e357/Qfield/cloud/DataTerrain/donnees_terrain.gpkg"
    layer_name = "saisies_terrain"
    
    log_handler.info(f"🔍 Détection des photos non référencées")
    log_handler.info(f"📁 Dossier DCIM : {dcim_path}")
    log_handler.info(f"🗂️ Couche QGIS : {layer_name} dans {gpkg_file}")
    
    # Vérifier le dossier DCIM
    if not os.path.exists(dcim_path):
        log_handler.error(f"❌ Dossier DCIM introuvable : {dcim_path}")
        return False
    
    # Vérifier le fichier GeoPackage
    if not os.path.exists(gpkg_file):
        log_handler.error(f"❌ Fichier GeoPackage introuvable : {gpkg_file}")
        return False
    
    # Lister les photos dans DCIM
    log_handler.info("📷 Analyse des photos dans DCIM...")
    dcim_photos = []
    for file in os.listdir(dcim_path):
        if file.lower().endswith('.jpg') or file.lower().endswith('.jpeg'):
            dcim_photos.append(file)
    
    if not dcim_photos:
        log_handler.info("⚠️  Aucune photo trouvée dans DCIM")
        return True
    
    log_handler.info(f"📷 Trouvé {len(dcim_photos)} photos dans DCIM")
    
    # Lire les photos référencées depuis la couche
    try:
        log_handler.info("📋 Lecture des photos référencées depuis la base de données...")
        layer = QgsVectorLayer(f"{gpkg_file}|layername={layer_name}", layer_name, "ogr")
        
        if not layer.isValid():
            log_handler.error(f"❌ Impossible de charger la couche : {layer_name}")
            return False
        
        referenced_photos = set()
        photos_with_null = 0
        
        for feature in layer.getFeatures():
            photo_field = feature['photo']
            if photo_field and isinstance(photo_field, str):
                photo_name = photo_field.split('/')[-1]
                if photo_name.lower().endswith(('.jpg', '.jpeg')):
                    referenced_photos.add(photo_name)
            else:
                photos_with_null += 1
        
        log_handler.info(f"📋 Trouvé {len(referenced_photos)} photos référencées")
        if photos_with_null > 0:
            log_handler.info(f"⚠️  {photos_with_null} entités ont un champ photo vide")
        
    except Exception as e:
        log_handler.error(f"❌ Erreur lecture couche : {e}")
        return False
    
    # Trouver les photos non référencées (présentes dans DCIM mais pas dans le champ photo des entités)
    set_referenced = set(referenced_photos)
    unreferenced = [p for p in dcim_photos if p not in set_referenced]
    
    # Photos référencées en base mais absentes du DCIM (entités pointant vers un fichier supprimé/renommé)
    referenced_but_missing = set_referenced - set(dcim_photos)
    
    debug_info = f"DEBUG: Photos uniques dans referenced_photos: {len(set_referenced)}"
    log_handler.debug(debug_info)
    
    log_handler.info(f"🔍 Résultat:")
    log_handler.info(f"  • Photos dans DCIM: {len(dcim_photos)}")
    log_handler.info(f"  • Photos référencées (uniques): {len(set_referenced)}")
    log_handler.info(f"  • Photos non référencées: {len(unreferenced)}")
    if referenced_but_missing:
        log_handler.info(f"  • Référencées en base mais absentes du DCIM: {len(referenced_but_missing)}")
    
    if unreferenced:
        log_handler.info(f"📋 Photos non référencées ({len(unreferenced)}):")
        for photo in unreferenced[:5]:
            log_handler.info(f"  • {photo}")
        if len(unreferenced) > 5:
            log_handler.info(f"  • ... et {len(unreferenced) - 5} autres")
        
        # Sauvegarder la liste complète
        report_file = os.path.join(export_dir, "photos_non_referencées.txt")
        try:
            with open(report_file, 'w') as f:
                f.write("Photos non référencées\n")
                f.write("=" * 50 + "\n\n")
                for photo in sorted(unreferenced):
                    f.write(f"{photo}\n")
            log_handler.info(f"📄 Rapport sauvegardé: {report_file}")
        except Exception as e:
            log_handler.error(f"❌ Erreur sauvegarde rapport: {e}")
            return False
    else:
        log_handler.info("✅ Toutes les photos sont référencées")
    
    return True