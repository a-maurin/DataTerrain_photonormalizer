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
Script pour corriger les photos avec FID=0
Ce script trouve les photos avec FID=0 et les renomme avec un FID valide
"""

import re
import sys
from qgis.core import QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY

try:
    from ..core.project_config import get_dcim_path, get_gpkg_path
except ImportError:
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from core.project_config import get_dcim_path, get_gpkg_path


def correct_fid_zero_photos():
    """Corrige les photos avec FID=0"""
    logger.info("=== CORRECTION DES PHOTOS AVEC FID=0 ===")
    
    # Configuration (config centralisée Linux / Windows)
    dcim_path = get_dcim_path()
    gpkg_file = get_gpkg_path()
    layer_name = "saisies_terrain"
    
    # Vérifier les chemins
    if not os.path.exists(dcim_path):
        logger.info(f"❌ Dossier DCIM introuvable: {dcim_path}")
        return False
    
    if not os.path.exists(gpkg_file):
        logger.info(f"❌ Fichier GeoPackage introuvable: {gpkg_file}")
        return False
    
    # Charger la couche
    try:
        layer_path = f"{gpkg_file}|layername={layer_name}"
        layer = QgsVectorLayer(layer_path, layer_name, "ogr")
        
        if not layer.isValid():
            logger.info(f"❌ Impossible de charger la couche {layer_name}")
            return False
        
        logger.info(f"✅ Couche '{layer_name}' chargée avec {layer.featureCount()} entités")
    except Exception as e:
        logger.info(f"❌ Erreur chargement couche: {e}")
        return False
    
    # Trouver les photos avec FID=0
    zero_fid_photos = []
    for filename in os.listdir(dcim_path):
        if filename.lower().endswith('.jpg'):
            # Vérifier le format DT_YYYY-MM-DD_0_INCONNU_INCONNU_X_Y.jpg
            match = re.match(r'DT_(\d{4}-\d{2}-\d{2})_0_INCONNU_INCONNU_([-+]?\d+\.?\d*)_([-+]?\d+\.?\d*)\.jpg', filename)
            if match:
                date_str = match.group(1)
                x = match.group(2)
                y = match.group(3)
                zero_fid_photos.append((filename, date_str, x, y))
    
    logger.info(f"📊 Trouvé {len(zero_fid_photos)} photos avec FID=0")
    
    if len(zero_fid_photos) == 0:
        logger.info("✅ Aucune photo avec FID=0 trouvée")
        return True
    
    # Démarrer l'édition
    layer.startEditing()
    photo_field_idx = layer.fields().indexFromName('photo')
    if photo_field_idx < 0:
        logger.info("⚠️  Champ 'photo' introuvable")
        return False
    
    photos_corrigees = 0
    
    for photo_name, date_str, x, y in zero_fid_photos:
        logger.info(f"\n🔧 Correction de: {photo_name}")
        
        try:
            # Vérifier si une entité existe déjà à ces coordonnées
            existing_fid = None
            for feature in layer.getFeatures():
                if feature.geometry() and not feature.geometry().isEmpty():
                    point = feature.geometry().asPoint()
                    if abs(point.x() - float(x)) < 0.01 and abs(point.y() - float(y)) < 0.01:
                        existing_fid = feature.id()
                        break
            
            if existing_fid is not None:
                logger.info(f"✅ Entité existante trouvée avec FID: {existing_fid}")
                
                # Renommer la photo avec le FID existant
                new_photo_name = f"DT_{date_str}_{existing_fid}_INCONNU_INCONNU_{x}_{y}.jpg"
                old_path = os.path.join(dcim_path, photo_name)
                new_path = os.path.join(dcim_path, new_photo_name)
                
                if not os.path.exists(new_path):
                    os.rename(old_path, new_path)
                    layer.changeAttributeValue(existing_fid, photo_field_idx, f'DCIM/{new_photo_name}')
                    photos_corrigees += 1
                    logger.info(f"✅ Photo corrigée: {photo_name} → {new_photo_name}")
                else:
                    logger.info(f"⚠️  Conflit de nom: {new_photo_name} existe déjà")
            else:
                # Créer une nouvelle entité si aucune n'existe
                logger.info(f"ℹ️  Aucune entité existante trouvée, création d'une nouvelle")
                
                # Créer une nouvelle entité
                new_feature = QgsFeature(layer.fields())
                new_feature['date_saisie'] = date_str
                new_feature['x_saisie'] = float(x)
                new_feature['y_saisie'] = float(y)
                new_feature['nom_agent'] = 'INCONNU'
                new_feature['type_saisie'] = 'INCONNU'
                new_feature['photo'] = f'DCIM/{photo_name}'
                
                # Définir la géométrie
                point = QgsPointXY(float(x), float(y))
                new_feature.setGeometry(QgsGeometry.fromPointXY(point))
                
                # Ajouter l'entité
                success = layer.addFeature(new_feature)
                if not success:
                    logger.info(f"❌ Échec de la création de l'entité pour {photo_name}")
                    continue
                
                # Sauvegarder pour obtenir le FID
                layer.commitChanges()
                
                # Trouver le FID
                new_fid = None
                for feature in layer.getFeatures():
                    if feature.geometry() and not feature.geometry().isEmpty():
                        feat_point = feature.geometry().asPoint()
                        if abs(feat_point.x() - float(x)) < 0.01 and abs(feat_point.y() - float(y)) < 0.01:
                            new_fid = feature.id()
                            break
                
                if new_fid is None or new_fid <= 0:
                    logger.info(f"❌ Impossible de trouver le FID pour {photo_name}")
                    if hasattr(layer, 'rollBack'):
                        layer.rollBack()
                    continue
                
                logger.info(f"✅ Nouveau FID attribué: {new_fid}")
                
                # Rebasculer en mode édition
                layer.startEditing()
                
                # Renommer la photo
                new_photo_name = f"DT_{date_str}_{new_fid}_INCONNU_INCONNU_{x}_{y}.jpg"
                old_path = os.path.join(dcim_path, photo_name)
                new_path = os.path.join(dcim_path, new_photo_name)
                
                if not os.path.exists(new_path):
                    os.rename(old_path, new_path)
                    layer.changeAttributeValue(new_fid, photo_field_idx, f'DCIM/{new_photo_name}')
                    photos_corrigees += 1
                    logger.info(f"✅ Photo corrigée: {photo_name} → {new_photo_name}")
                else:
                    logger.info(f"⚠️  Conflit de nom: {new_photo_name} existe déjà")
                    if hasattr(layer, 'rollBack'):
                        layer.rollBack()
        
        except Exception as e:
            logger.info(f"❌ Erreur lors de la correction de {photo_name}: {e}")
            if hasattr(layer, 'rollBack'):
                layer.rollBack()
            continue
    
    # Sauvegarder les modifications finales
    layer.commitChanges()
    
    logger.info(f"\n=== RÉSUMÉ ===")
    logger.info(f"📊 Photos avec FID=0 analysées: {len(zero_fid_photos)}")
    logger.info(f"✅ Photos corrigées: {photos_corrigees}")
    logger.info(f"🎯 Taux de succès: {photos_corrigees}/{len(zero_fid_photos)} ({photos_corrigees/len(zero_fid_photos)*100:.1f}%)")
    
    return True

if __name__ == "__main__":
    correct_fid_zero_photos()
