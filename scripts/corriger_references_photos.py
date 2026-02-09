#!/usr/bin/env python3
"""
Script pour corriger les références de photos avec "INCONNU" dans les entités
Ce script parcourt toutes les entités et corrige les champs photo qui contiennent "INCONNU"
en les faisant correspondre aux fichiers physiques réels.
"""

import os
import re
import logging
from datetime import datetime
from qgis.core import QgsProject, QgsVectorLayer
from qgis.PyQt.QtWidgets import QMessageBox

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/corriger_references_photos.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def corriger_references_photos():
    """
    Corrige les références de photos contenant "INCONNU" dans les entités
    """
    logger.info("=== CORRECTION DES RÉFÉRENCES DE PHOTOS ===")
    
    # Configuration
    layer_name = "donnees_terrain"
    base_path = "/home/e357/Qfield/cloud/DataTerrain"
    dcim = os.path.join(base_path, "DCIM")
    
    # Vérification du dossier DCIM
    if not os.path.exists(dcim):
        QMessageBox.critical(None, "Erreur", f"Dossier DCIM introuvable : {dcim}")
        return False
    
    # Récupération de la couche
    try:
        layers = QgsProject.instance().mapLayersByName(layer_name)
        if not layers:
            QMessageBox.critical(None, "Erreur", f"La couche '{layer_name}' est introuvable.")
            return False
            
        layer = layers[0]
        if not isinstance(layer, QgsVectorLayer):
            logger.error("La couche n'est pas une couche vectorielle.")
            QMessageBox.critical(None, "Erreur", "La couche n'est pas une couche vectorielle.")
            return False
            
        logger.info(f"✓ Couche '{layer_name}' trouvée avec {layer.featureCount()} entités")
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la couche : {e}")
        QMessageBox.critical(None, "Erreur", f"Erreur lors de la récupération de la couche : {e}")
        return False
    
    # Vérification du mode édition
    if not layer.isEditable():
        if not layer.startEditing():
            QMessageBox.critical(None, "Erreur", "Impossible de démarrer le mode édition.")
            return False
        logger.info("✓ Mode édition démarré")
    
    # Récupération de toutes les photos dans DCIM
    all_photos = [f for f in os.listdir(dcim) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    logger.info(f"✓ {len(all_photos)} photos trouvées dans DCIM")
    
    # Statistiques
    entites_corrigées = 0
    entites_avec_problemes = 0
    entites_sans_correction = 0
    
    # Parcourir toutes les entités
    for feature in layer.getFeatures():
        photo_path = feature['photo']
        
        if not photo_path:
            continue
            
        # Extraire le nom de fichier
        photo_name = os.path.basename(photo_path)
        
        # Vérifier si le nom contient "INCONNU"
        if "INCONNU" in photo_name:
            logger.info(f"\n🔍 Entité FID {feature.id()} avec photo problématique : {photo_name}")
            
            # Extraire les coordonnées du nom de fichier
            # Pattern: DT_YYYY-MM-DD_FID_nom_agent_type_saisie_X_Y.jpg
            pattern = r'DT_(\d{4}-\d{2}-\d{2})_(\d+)_[^_]+_[^_]+_([-+]?\d+\.?\d*)_([-+]?\d+\.?\d*)\.jpg'
            match = re.search(pattern, photo_name)
            
            if match:
                date_str = match.group(1)
                fid = match.group(2)
                x = match.group(3)
                y = match.group(4)
                
                logger.info(f"  Coordonnées extraites: FID={fid}, X={x}, Y={y}")
                
                # Chercher le fichier physique correspondant
                # Nous cherchons un fichier avec les mêmes coordonnées
                corresponding_photos = []
                
                for physical_photo in all_photos:
                    # Extraire les coordonnées du fichier physique
                    physical_match = re.search(pattern, physical_photo)
                    if physical_match:
                        physical_x = physical_match.group(3)
                        physical_y = physical_match.group(4)
                        
                        # Comparer les coordonnées (avec une marge d'erreur)
                        if (abs(float(x) - float(physical_x)) < 0.1 and 
                            abs(float(y) - float(physical_y)) < 0.1):
                            corresponding_photos.append(physical_photo)
                
                if corresponding_photos:
                    logger.info(f"  ✓ Fichiers physiques correspondants trouvés: {len(corresponding_photos)}")
                    
                    # Choisir le fichier avec le FID correspondant si possible
                    best_match = None
                    
                    # D'abord chercher un fichier avec le même FID
                    for photo in corresponding_photos:
                        if f"_{fid}_" in photo:
                            best_match = photo
                            break
                    
                    # Si pas trouvé, prendre le premier
                    if not best_match:
                        best_match = corresponding_photos[0]
                    
                    logger.info(f"  ✓ Meilleur correspondance: {best_match}")
                    
                    # Mettre à jour le champ photo
                    new_photo_path = f"DCIM/{best_match}"
                    
                    try:
                        layer.changeAttributeValue(feature.id(), 
                                                  layer.fields().indexFromName('photo'),
                                                  new_photo_path)
                        entites_corrigées += 1
                        logger.info(f"  ✅ Entité FID {feature.id()} corrigée: {photo_name} → {best_match}")
                        
                    except Exception as e:
                        entites_avec_problemes += 1
                        logger.info(f"  ❌ Erreur lors de la mise à jour: {e}")
                        
                else:
                    entites_sans_correction += 1
                    logger.info(f"  ⚠️  Aucun fichier physique correspondant trouvé pour {photo_name}")
                    
            else:
                entites_sans_correction += 1
                logger.info(f"  ⚠️  Impossible d'extraire les coordonnées de {photo_name}")
    
    # Sauvegarde des modifications
    logger.info(f"\n=== SAUVEGARDE DES MODIFICATIONS ===")
    
    if layer.isEditable():
        if not layer.commitChanges():
            QMessageBox.critical(None, "Erreur", "Impossible de sauvegarder les modifications.")
            return False
        logger.info("✓ Modifications sauvegardées avec succès")
    
    # Résumé
    logger.info(f"\n=== RÉSUMÉ ===")
    logger.info(f"📊 Entités analysées: {layer.featureCount()}")
    logger.info(f"✅ Entités corrigées: {entites_corrigées}")
    logger.info(f"⚠️  Entités avec problèmes: {entites_avec_problemes}")
    logger.info(f"ℹ️  Entités sans correction possible: {entites_sans_correction}")
    
    # Message de confirmation
    QMessageBox.information(
        None,
        "Correction terminée",
        f"Résultat de la correction:\n\n"
        f"- {entites_corrigées} entités corrigées\n"
        f"- {entites_avec_problemes} entités avec problèmes\n"
        f"- {entites_sans_correction} entités sans correction possible\n\n"
        f"Les références de photos contenant 'INCONNU' ont été mises à jour\n"
        f"pour correspondre aux fichiers physiques réels."
    )
    
    return True

if __name__ == "__main__":
    corriger_references_photos()