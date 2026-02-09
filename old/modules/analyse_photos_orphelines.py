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
Script d'analyse des photos orphelines
Ce script compare les photos du dossier DCIM avec les entités de la couche donnees_terrain
pour identifier pourquoi certaines photos sont considérées comme orphelines.
"""

import re
from qgis.core import QgsProject

def extraire_coord_du_nom(nom_fichier):
    """
    Extraire les coordonnées d'un nom de fichier au format DT_YYYY-MM-DD_FID_agent_type_X_Y.jpg
    """
    # Pattern pour extraire les coordonnées du nom de fichier
    pattern = r'DT_\d{4}-\d{2}-\d{2}_(\d+)_[^_]+_[^_]+_([-+]?\d+\.?\d*)_([-+]?\d+\.?\d*)\.jpg'
    match = re.match(pattern, nom_fichier)
    
    if match:
        fid = int(match.group(1))
        x = float(match.group(2))
        y = float(match.group(3))
        return fid, x, y
    return None, None, None

def analyser_photos_orphelines():
    """
    Analyser les photos orphelines et comparer avec les entités
    """
    
    # Configuration
    layer_name = "donnees_terrain"
    
    # Récupération de la couche
    try:
        layers = QgsProject.instance().mapLayersByName(layer_name)
        if not layers:
            logger.info(f"Erreur : La couche '{layer_name}' est introuvable dans le projet.")
            return
        
        layer = layers[0]
    except Exception as e:
        logger.info(f"Erreur lors de la récupération de la couche : {e}")
        return
    
    # Utilisation du chemin fixe pour QField Cloud
    base_path = "/home/e357/Qfield/cloud/DataTerrain"
    dcim = os.path.join(base_path, "DCIM")
    
    logger.info(f"Chemin QField Cloud : {base_path}")
    logger.info(f"Dossier DCIM : {dcim}")
    
    if not os.path.exists(dcim):
        logger.info(f"Erreur : Le dossier DCIM est introuvable : {dcim}")
        return
    
    # Récupération des photos dans le dossier DCIM
    all_photos = [f for f in os.listdir(dcim) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    logger.info(f"Nombre total de photos dans DCIM : {len(all_photos)}")
    
    # Récupération des photos référencées dans la couche
    used_photos = {}
    for f in layer.getFeatures():
        photo = f['photo']
        if photo:
            photo_name = os.path.basename(photo)
            used_photos[photo_name] = f
    
    logger.info(f"Nombre de photos référencées dans la couche : {len(used_photos)}")
    
    # Identification des photos orphelines
    orphelines = [p for p in all_photos if p not in used_photos]
    logger.info(f"Nombre de photos orphelines : {len(orphelines)}")
    
    # Analyse détaillée des photos orphelines
    logger.info("\n=== ANALYSE DÉTAILLÉE DES PHOTOS ORPHELINES ===")
    
    for photo_name in orphelines:
        logger.info(f"\nAnalyse de : {photo_name}")
        
        # Extraire les coordonnées du nom de fichier
        fid, x, y = extraire_coord_du_nom(photo_name)
        
        if fid is not None:
            logger.info(f"  FID extrait : {fid}")
            logger.info(f"  Coordonnées extraites : X={x}, Y={y}")
            
            # Rechercher une entité correspondante
            entite_trouvee = None
            for f in layer.getFeatures():
                if f.id() == fid:
                    entite_trouvee = f
                    break
            
            if entite_trouvee:
                photo_attribut = entite_trouvee['photo']
                logger.info(f"  Entité FID {fid} trouvée dans la couche")
                logger.info(f"  Photo référencée dans l'entité : {photo_attribut}")
                
                if photo_attribut and photo_attribut != f"DCIM/{photo_name}":
                    logger.info(f"  ⚠️  PROBLÈME : Le nom de la photo dans l'entité ne correspond pas !")
                    logger.info(f"     Attendu : DCIM/{photo_name}")
                    logger.info(f"     Actuel : {photo_attribut}")
                elif not photo_attribut:
                    logger.info(f"  ⚠️  PROBLÈME : L'attribut photo est vide pour cette entité")
                else:
                    logger.info(f"  ✓ Correspondance normale")
            else:
                logger.info(f"  ⚠️  PROBLÈME : Aucune entité avec FID {fid} trouvée dans la couche")
        else:
            logger.info(f"  ⚠️  PROBLÈME : Impossible d'extraire les coordonnées du nom de fichier")
            logger.info(f"  Format attendu : DT_YYYY-MM-DD_FID_agent_type_X_Y.jpg")

if __name__ == "__main__":
    analyser_photos_orphelines()
