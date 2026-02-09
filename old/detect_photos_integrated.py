#!/usr/bin/env python3
"""
Version intégrée du script de détection des photos non référencées.
Conçu pour être utilisé avec le système de logging du plugin PhotoNormalizer.
"""

import os
from qgis.core import QgsVectorLayer

def detect_unreferenced_photos_integrated(log_handler, export_dir=None):
    """
    Détecte les photos non référencées et utilise le log_handler du plugin.
    
    Args:
        log_handler: L'objet LogHandler du plugin pour afficher les messages
        export_dir: Dossier d'exportation pour les fichiers générés (optionnel)
    """
    
    # Chemins par défaut
    dcim_path = "/home/e357/Qfield/cloud/DataTerrain/DCIM"
    gpkg_file = "/home/e357/Qfield/cloud/DataTerrain/donnees_terrain.gpkg"
    layer_name = "saisies_terrain"
    layer_path = f"{gpkg_file}|layername={layer_name}"
    
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
        layer = QgsVectorLayer(layer_path, "saisies_terrain_layer", "ogr")
        
        if not layer.isValid():
            log_handler.error(f"❌ Impossible de charger la couche : {layer_path}")
            return False
        
        referenced_photos = set()
        photos_with_null = 0
        
        # Parcourir les entités et extraire les noms de photos
        for feature in layer.getFeatures():
            photo_field = feature['photo']
            if photo_field and isinstance(photo_field, str):
                # Extraire le nom de fichier de la photo
                photo_name = photo_field.split('/')[-1]  # Prendre la dernière partie du chemin
                if photo_name.lower().endswith('.jpg') or photo_name.lower().endswith('.jpeg'):
                    referenced_photos.add(photo_name)
            else:
                photos_with_null += 1
        
        log_handler.info(f"📋 Trouvé {len(referenced_photos)} photos référencées dans la couche")
        if photos_with_null > 0:
            log_handler.info(f"⚠️  {photos_with_null} entités ont un champ photo vide ou null")
        
    except Exception as e:
        log_handler.error(f"❌ Erreur lors de la lecture de la couche : {e}")
        return False
    
    # Trouver les photos non référencées
    unreferenced = [p for p in dcim_photos if p not in referenced_photos]
    
    log_handler.info(f"🔍 Résultat de l'analyse :")
    log_handler.info(f"  • Photos dans DCIM: {len(dcim_photos)}")
    log_handler.info(f"  • Photos référencées: {len(referenced_photos)}")
    log_handler.info(f"  • Photos non référencées: {len(unreferenced)}")
    
    if unreferenced:
        log_handler.info(f"📋 Liste des photos non référencées ({len(unreferenced)}):")
        
        # Afficher quelques exemples
        examples = unreferenced[:5]
        for photo in examples:
            log_handler.info(f"  • {photo}")
        
        if len(unreferenced) > 5:
            log_handler.info(f"  • ... et {len(unreferenced) - 5} autres")
        
        # Sauvegarder la liste complète
        report_file = "photos_non_referencées.txt"
        
        # Utiliser le dossier d'exportation si disponible, sinon le dossier du script
        if export_dir:
            report_path = os.path.join(export_dir, report_file)
        else:
            report_path = os.path.join(os.path.dirname(__file__), report_file)
        
        try:
            with open(report_path, 'w') as f:
                f.write("Photos non référencées\n")
                f.write("=" * 50 + "\n\n")
                for photo in sorted(unreferenced):
                    f.write(f"{photo}\n")
            
            log_handler.info(f"📄 Rapport complet sauvegardé dans : {report_path}")
            log_handler.info(f"💡 Vous pouvez utiliser ces informations pour créer des entités avec le plugin PhotoNormalizer.")
            
        except Exception as e:
            log_handler.error(f"❌ Impossible de sauvegarder le rapport : {e}")
            return False
    else:
        log_handler.info("✅ Toutes les photos dans DCIM sont référencées dans la base de données.")
    
    return True