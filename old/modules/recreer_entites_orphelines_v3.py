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
Script pour recréer les entités manquantes à partir des photos au format ancien
Version 3 - Traite directement les photos DT_YYYYMMDD_HHMMSS_X_Y.jpg
"""

import re
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import QgsProject, QgsFeature, QgsGeometry, QgsPointXY, QgsVectorLayer

def recreer_entites_orphelines_v3():
    """
    Recrée les entités manquantes à partir des photos au format ancien
    """
    logger.info("=== RECREATION DES ENTITES A PARTIR DES PHOTOS ANCIENNES ===")
    
    # Configuration
    layer_name = "donnees_terrain"
    
    try:
        # Vérification de la couche
        layers = QgsProject.instance().mapLayersByName(layer_name)
        if not layers:
            QMessageBox.critical(None, "Erreur", f"La couche '{layer_name}' est introuvable.")
            return False
        
        layer = layers[0]
        logger.info(f"✓ Couche '{layer_name}' trouvée avec {layer.featureCount()} entités")
        
        # Vérification du type de couche
        if not isinstance(layer, QgsVectorLayer):
            QMessageBox.critical(None, "Erreur", "La couche n'est pas une couche vectorielle.")
            return False
        
        # Utilisation du chemin fixe pour QField Cloud
        base_path = "/home/e357/Qfield/cloud/DataTerrain"
        dcim = os.path.join(base_path, "DCIM")
        
        if not os.path.exists(dcim):
            QMessageBox.critical(None, "Erreur", f"Dossier DCIM introuvable : {dcim}")
            return False
        
        # Récupérer toutes les photos au format ancien (DT_YYYYMMDD_HHMMSS_X_Y.jpg)
        all_photos = [f for f in os.listdir(dcim) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        
        # Filtrer les photos au format ancien
        old_format_photos = []
        for photo_name in all_photos:
            # Format ancien : DT_YYYYMMDD_HHMMSS_X_Y.jpg
            if re.match(r'DT_\d{8}_\d{6}_[-+]?\d+\.?\d*_[-+]?\d+\.?\d*\.jpg', photo_name):
                old_format_photos.append(photo_name)
        
        logger.info(f"Photos au format ancien trouvées : {len(old_format_photos)}")
        
        if len(old_format_photos) == 0:
            QMessageBox.information(None, "Information", "Aucune photo au format ancien trouvée.")
            return True
        
        # Vérifier que la couche est en mode édition
        if not layer.isEditable():
            if not layer.startEditing():
                QMessageBox.critical(None, "Erreur", "Impossible de démarrer le mode édition.")
                return False
        
        # Compter les entités avant traitement
        initial_feature_count = layer.featureCount()
        logger.info(f"\nNombre d'entités avant traitement : {initial_feature_count}")
        
        entites_creees = 0
        entites_existantes = 0
        entites_avec_conflit = 0
        
        for photo_name in old_format_photos:
            logger.info(f"\n🔍 Traitement de : {photo_name}")
            
            # Extraire les informations du nom de la photo
            match = re.match(r'DT_(\d{8})_(\d{6})_([-+]?\d+\.?\d*)_([-+]?\d+\.?\d*)\.jpg', photo_name)
            
            if not match:
                continue
            
            date_str = match.group(1)  # YYYYMMDD
            time_str = match.group(2)  # HHMMSS
            x = float(match.group(3))
            y = float(match.group(4))
            
            # Convertir la date au format ISO
            try:
                date_iso = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}T{time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}"
            except (IndexError, ValueError) as e:
                logger.info(f"⚠️  Erreur de conversion de date pour {photo_name}: {e}")
                date_iso = None
            
            # Vérifier si une entité existe déjà à ces coordonnées
            entite_existante = None
            for f in layer.getFeatures():
                geom = f.geometry()
                if geom and not geom.isEmpty():
                    point = geom.asPoint()
                    # Vérifier si les coordonnées correspondent (avec une marge de 0.1 unité)
                    if abs(point.x() - x) < 0.1 and abs(point.y() - y) < 0.1:
                        entite_existante = f
                        break
            
            if entite_existante:
                entites_existantes += 1
                continue
            
            # Créer une nouvelle entité
            logger.info(f"✓ Création d'une nouvelle entité pour {photo_name}")
            
            # Créer la géométrie
            try:
                point = QgsPointXY(x, y)
                if not point.isEmpty():
                    geom = QgsGeometry.fromPointXY(point)
                    if not geom or geom.isEmpty():
                        continue
                else:
                    continue
            except Exception as e:
                continue
            
            # Créer la feature
            try:
                feature = QgsFeature(layer.fields())
                if not feature.isValid():
                    continue
                
                feature.setGeometry(geom)
                
                # Remplir les attributs
                if 'photo' in [field.name() for field in layer.fields()]:
                    feature['photo'] = f"DCIM/{photo_name}"
                
                if date_iso and 'date_saisie' in [field.name() for field in layer.fields()]:
                    feature['date_saisie'] = date_iso
                
                # Les autres champs avec des valeurs par défaut
                if 'nom_agent' in [field.name() for field in layer.fields()]:
                    feature['nom_agent'] = "Inconnu"
                if 'type_saisie' in [field.name() for field in layer.fields()]:
                    feature['type_saisie'] = "a_renseigner"
                
                if not feature.isValid():
                    continue
                
                success = layer.addFeature(feature)
                
                if success:
                    if feature.id() >= 0:
                        entites_creees += 1
                        logger.info(f"  ✓ Entité créée avec FID {feature.id()}")
                    else:
                        logger.info(f"  ⚠️  Feature ajoutée mais FID invalide pour {photo_name}")
                else:
                    logger.info(f"  ❌ Échec de l'ajout de la feature pour {photo_name}")
                    
            except Exception as e:
                logger.info(f"  ❌ Erreur création feature : {e}")
        
        # Vérification finale du nombre d'entités
        final_feature_count = layer.featureCount()
        logger.info(f"\nNombre d'entités après traitement : {final_feature_count}")
        
        logger.info("\nSauvegarde des modifications...")
        if layer.isEditable():
            if not layer.commitChanges():
                QMessageBox.critical(None, "Erreur", "Impossible de sauvegarder les modifications.")
                return False
            logger.info("✓ Modifications sauvegardées avec succès")
        
        logger.info(f"\n=== RÉSUMÉ ===")
        logger.info(f"📊 Photos au format ancien analysées : {len(old_format_photos)}")
        logger.info(f"✅ Entités créées : {entites_creees}")
        logger.info(f"ℹ️  Entités existantes trouvées : {entites_existantes}")
        logger.info(f"📈 Entités totales : {initial_feature_count} → {final_feature_count} (+{entites_creees})")
        
        if entites_creees > 0:
            logger.info(f"\n📋 Instructions pour finaliser :")
            logger.info(f"1. Vérifiez les {entites_creees} nouvelles entités créées")
            logger.info(f"2. Complétez manuellement les champs 'nom_agent' et 'type_saisie'")
            logger.info(f"3. Les photos ont été associées automatiquement")
        
        QMessageBox.information(
            None,
            "Recréation terminée",
            f"Résultat :\n"
            f"- {len(old_format_photos)} photos au format ancien analysées\n"
            f"- {entites_creees} nouvelles entités créées\n"
            f"- {entites_existantes} entités existantes trouvées\n"
            f"- {entites_avec_conflit} conflits détectés\n\n"
            f"Les nouvelles entités ont été créées avec les coordonnées des photos.\n"
            f"Vous devez compléter manuellement les autres champs."
        )
        
        return True
        
    except Exception as e:
        if layer.isEditable():
            if hasattr(layer, 'rollBack'):
                layer.rollBack()
        
        QMessageBox.critical(None, "Erreur", f"Erreur critique : {e}\n\nToutes les modifications ont été annulées.")
        return False

if __name__ == "__main__":
    recreer_entites_orphelines_v3()
