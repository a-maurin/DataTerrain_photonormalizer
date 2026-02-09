#!/usr/bin/env python3
"""
Version simplifiée pour la console QGIS - Exécuter avec :
# Fichier obsolète - ne pas exécuter
print("⚠️  Ce fichier est obsolète et ne doit pas être exécuté directement")
"""

import os
import re
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import QgsVectorLayer

def detect_unreferenced_photos():
    """Détecte les photos non référencées et affiche les résultats."""
    
    # Chemins par défaut
    dcim_path = "/home/e357/Qfield/cloud/DataTerrain/DCIM"
    gpkg_file = "/home/e357/Qfield/cloud/DataTerrain/donnees_terrain.gpkg"
    layer_name = "saisies_terrain"  # Nom correct de la table trouvé dans l'analyse
    layer_path = f"{gpkg_file}|layername={layer_name}"
    
    # Vérifier le dossier DCIM
    if not os.path.exists(dcim_path):
        QMessageBox.warning(None, "Erreur", f"Dossier DCIM introuvable : {dcim_path}")
        return
    
    # Vérifier le fichier GeoPackage
    if not os.path.exists(gpkg_file):
        QMessageBox.warning(None, "Erreur", f"Fichier GeoPackage introuvable : {gpkg_file}")
        return
    
    # Lister les photos dans DCIM
    dcim_photos = []
    for file in os.listdir(dcim_path):
        if file.lower().endswith('.jpg') or file.lower().endswith('.jpeg'):
            dcim_photos.append(file)
    
    if not dcim_photos:
        QMessageBox.information(None, "Résultat", "Aucune photo trouvée dans DCIM")
        return
    
    # Lire les photos référencées depuis la couche
    try:
        print(f"Tentative de chargement de la couche: {layer_path}")
        layer = QgsVectorLayer(layer_path, "donnees_terrain_layer", "ogr")
        
        if not layer.isValid():
            # Essayer de lister les couches disponibles dans le GeoPackage
            print(f"La couche {layer_name} n'est pas valide, tentative de liste des couches disponibles...")
            
            # Essayer de charger le GeoPackage sans spécifier de couche
            gpkg_layer = QgsVectorLayer(gpkg_file, "gpkg_test", "ogr")
            if gpkg_layer.isValid():
                sublayers = gpkg_layer.dataProvider().subLayers()
                available_layers = []
                for sublayer in sublayers:
                    layer_info = QgsVectorLayer(sublayer.split('!!::!!')[1], "temp", "ogr")
                    if layer_info.isValid():
                        available_layers.append(layer_info.name())
                
                error_msg = f"Couche '{layer_name}' introuvable. Couches disponibles:\n\n"
                error_msg += "\n".join(available_layers)
                QMessageBox.warning(None, "Erreur", error_msg)
            else:
                QMessageBox.warning(None, "Erreur", f"Impossible de charger le GeoPackage : {gpkg_file}")
            
            return
        
        referenced_photos = set()
        for feature in layer.getFeatures():
            photo_field = feature['photo']
            if photo_field and isinstance(photo_field, str):
                photo_name = photo_field.split('/')[-1]
                if photo_name.lower().endswith('.jpg') or photo_name.lower().endswith('.jpeg'):
                    referenced_photos.add(photo_name)
    
    except Exception as e:
        QMessageBox.warning(None, "Erreur", f"Erreur lors de la lecture de la couche : {e}")
        return
    
    # Trouver les photos non référencées
    unreferenced = [p for p in dcim_photos if p not in referenced_photos]
    
    if not unreferenced:
        QMessageBox.information(None, "Résultat", "Toutes les photos sont référencées !")
        return
    
    # Créer le message de résultat
    message = f"Photos non référencées : {len(unreferenced)}\n\n"
    message += f"Total dans DCIM: {len(dcim_photos)}\n"
    message += f"Photos référencées: {len(referenced_photos)}\n"
    message += f"Photos non référencées: {len(unreferenced)}\n\n"
    
    # Ajouter quelques exemples
    examples = unreferenced[:5]
    message += "Exemples :\n" + "\n".join(f"• {p}" for p in examples)
    
    if len(unreferenced) > 5:
        message += f"\n... et {len(unreferenced) - 5} autres"
    
    # Sauvegarder la liste complète
    report_file = "photos_non_referencées.txt"
    with open(report_file, 'w') as f:
        f.write("Photos non référencées\n")
        f.write("=" * 40 + "\n\n")
        for photo in sorted(unreferenced):
            f.write(f"{photo}\n")
    
    message += f"\n\nListe complète sauvegardée dans :\n{os.path.abspath(report_file)}"
    
    # Afficher les résultats
    msg_box = QMessageBox()
    msg_box.setWindowTitle("Photos non référencées")
    msg_box.setText(f"Trouvé {len(unreferenced)} photos non référencées")
    msg_box.setInformativeText(f"Voir détails dans {report_file}")
    msg_box.setDetailedText(message)
    msg_box.setIcon(QMessageBox.Information)
    msg_box.exec_()

# Exécuter la détection
detect_unreferenced_photos()