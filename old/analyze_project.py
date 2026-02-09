#!/usr/bin/env python3
"""
Script pour analyser la structure du projet DataTerrain.
Ce script examine le dossier du projet et trouve automatiquement les couches disponibles.
"""

import os
from qgis.core import QgsVectorLayer, QgsProject
from qgis.PyQt.QtWidgets import QMessageBox

def analyze_project_structure():
    """Analyse la structure du projet DataTerrain."""
    
    project_dir = "/home/e357/Qfield/cloud/DataTerrain"
    
    if not os.path.exists(project_dir):
        QMessageBox.warning(None, "Erreur", f"Dossier projet introuvable : {project_dir}")
        return
    
    print(f"🔍 Analyse du projet DataTerrain dans : {project_dir}")
    
    # Chercher les fichiers GeoPackage
    gpkg_files = []
    for file in os.listdir(project_dir):
        if file.lower().endswith('.gpkg'):
            gpkg_files.append(file)
    
    print(f"📁 Fichiers GeoPackage trouvés : {gpkg_files}")
    
    if not gpkg_files:
        QMessageBox.warning(None, "Erreur", "Aucun fichier GeoPackage trouvé dans le dossier du projet")
        return
    
    # Analyser chaque GeoPackage
    results = []
    for gpkg_file in gpkg_files:
        gpkg_path = os.path.join(project_dir, gpkg_file)
        print(f"\n📦 Analyse de {gpkg_file}...")
        
        try:
            # Charger le GeoPackage
            gpkg_layer = QgsVectorLayer(gpkg_path, "gpkg_analysis", "ogr")
            
            if not gpkg_layer.isValid():
                print(f"❌ Impossible de charger {gpkg_file}")
                continue
            
            # Lister les sous-couches
            sublayers = gpkg_layer.dataProvider().subLayers()
            print(f"📋 Couches trouvées dans {gpkg_file}:")
            
            for sublayer in sublayers:
                layer_info = sublayer.split('!!::!!')
                if len(layer_info) > 1:
                    layer_name = layer_info[1].split('|')[0]  # Extraire le nom de la couche
                    layer_type = layer_info[0]  # Type de couche
                    
                    # Charger la couche pour vérifier ses champs
                    temp_layer = QgsVectorLayer(sublayer.split('!!::!!')[1], "temp", "ogr")
                    if temp_layer.isValid():
                        fields = [field.name() for field in temp_layer.fields()]
                        
                        result = {
                            'gpkg': gpkg_file,
                            'layer': layer_name,
                            'type': layer_type,
                            'fields': fields,
                            'has_photo_field': 'photo' in fields
                        }
                        results.append(result)
                        
                        print(f"  • {layer_name} (type: {layer_type})")
                        print(f"    Champs: {', '.join(fields)}")
                        if 'photo' in fields:
                            print(f"    ✅ Contient un champ 'photo'!")
                        else:
                            print(f"    ❌ Pas de champ 'photo'")
        
        except Exception as e:
            print(f"❌ Erreur lors de l'analyse de {gpkg_file}: {e}")
    
    # Afficher les résultats
    if results:
        print(f"\n📊 Résumé des couches avec champ 'photo':")
        photo_layers = [r for r in results if r['has_photo_field']]
        
        if photo_layers:
            for layer in photo_layers:
                print(f"  ✅ {layer['gpkg']} > {layer['layer']}")
        else:
            print("  ❌ Aucune couche avec champ 'photo' trouvée")
        
        # Créer un message pour l'utilisateur
        message = "Structure du projet DataTerrain:\n\n"
        
        for gpkg_file in gpkg_files:
            message += f"📁 {gpkg_file}\n"
            
            gpkg_layers = [r for r in results if r['gpkg'] == gpkg_file]
            for layer in gpkg_layers:
                photo_info = " ✅" if layer['has_photo_field'] else " ❌"
                message += f"  • {layer['layer']}{photo_info}\n"
        
        if photo_layers:
            message += f"\n💡 Couches recommandées pour la détection de photos:\n"
            for layer in photo_layers:
                message += f"  • {layer['gpkg']} | layername={layer['layer']}\n"
        
        QMessageBox.information(None, "Structure du projet", message)
    else:
        QMessageBox.warning(None, "Erreur", "Aucune couche valide trouvée dans les GeoPackage")

# Exécuter l'analyse
analyze_project_structure()