#!/usr/bin/env python3
"""
Script pour détecter les photos non rattachées à une entité dans DataTerrain.
Ce script analyse les photos dans le dossier DCIM et les compare avec les entités
existantes dans la base de données QGIS.

Utilisation depuis QGIS Python Console:
    from detect_unreferenced_photos import run_detection
    run_detection()

Le script génère un rapport des photos non référencées.
"""

import os
import re
from typing import List, Dict, Set

# Vérifier si on est dans QGIS
try:
    from qgis.PyQt.QtWidgets import QMessageBox, QApplication
    from qgis.core import QgsVectorLayer
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False

def get_dcim_photos(dcim_path: str) -> List[str]:
    """
    Récupère la liste des photos dans le dossier DCIM.
    
    Args:
        dcim_path: Chemin vers le dossier DCIM
        
    Returns:
        Liste des noms de fichiers photo
    """
    if not os.path.exists(dcim_path):
        print(f"⚠️  Le dossier DCIM n'existe pas : {dcim_path}")
        return []
    
    photo_files = []
    for file in os.listdir(dcim_path):
        if file.lower().endswith('.jpg') or file.lower().endswith('.jpeg'):
            photo_files.append(file)
    
    print(f"📷 Trouvé {len(photo_files)} photos dans {dcim_path}")
    return photo_files

def get_referenced_photos_from_layer(layer_path: str) -> Set[str]:
    """
    Récupère les photos référencées dans la couche QGIS.
    
    Args:
        layer_path: Chemin vers le fichier de couche QGIS
        
    Returns:
        Ensemble des noms de fichiers photo référencés
    """
    if not QGIS_AVAILABLE:
        print("❌ QGIS n'est pas disponible. Impossible de lire la couche directement.")
        return set()
    
    try:
        # Charger la couche
        layer = QgsVectorLayer(layer_path, "photos_layer", "ogr")
        
        if not layer.isValid():
            print(f"❌ Impossible de charger la couche : {layer_path}")
            return set()
        
        referenced_photos = set()
        
        # Parcourir les entités et extraire les noms de photos
        for feature in layer.getFeatures():
            photo_field = feature['photo']
            if photo_field and isinstance(photo_field, str):
                # Extraire le nom de fichier de la photo
                photo_name = photo_field.split('/')[-1]  # Prendre la dernière partie du chemin
                if photo_name.lower().endswith('.jpg') or photo_name.lower().endswith('.jpeg'):
                    referenced_photos.add(photo_name)
        
        print(f"📋 Trouvé {len(referenced_photos)} photos référencées dans la couche")
        return referenced_photos
        
    except Exception as e:
        print(f"❌ Erreur lors de la lecture de la couche : {e}")
        return set()

def analyze_photo_formats(photos: List[str]) -> Dict[str, List[str]]:
    """
    Analyse les formats des photos.
    
    Args:
        photos: Liste des noms de fichiers photo
        
    Returns:
        Dictionnaire avec les photos classées par format
    """
    formats = {
        'standard': [],
        'ancien': [], 
        'inconnu': []
    }
    
    # Patterns pour la détection des formats
    standard_pattern = r'DT_\d{4}-\d{2}-\d{2}_\d+_[^_]+(?:_[^_]+)*_[^_]+_[-+]?\d+\.?\d*_[-+]?\d+\.?\d*\.jpg'
    ancien_pattern = r'\d{8}_\d+\.jpg'
    
    for photo in photos:
        if re.match(standard_pattern, photo):
            formats['standard'].append(photo)
        elif re.match(ancien_pattern, photo):
            formats['ancien'].append(photo)
        else:
            formats['inconnu'].append(photo)
    
    return formats

def run_detection():
    """
    Fonction principale pour l'exécution depuis QGIS.
    Affiche les résultats dans une boîte de dialogue.
    """
    print("🔍 Détection des photos non rattachées à une entité")
    print("=" * 60)
    
    # Chemins par défaut (à adapter selon votre configuration)
    dcim_path = "/home/e357/Qfield/cloud/DataTerrain/DCIM"
    layer_path = "/home/e357/Qfield/cloud/DataTerrain/DataTerrain.gpkg|layername=photos"
    
    print(f"📁 Dossier DCIM : {dcim_path}")
    print(f"🗂️ Couche QGIS : {layer_path}")
    print()
    
    # Récupérer les photos dans DCIM
    dcim_photos = get_dcim_photos(dcim_path)
    
    if not dcim_photos:
        message = "❌ Aucune photo trouvée dans le dossier DCIM."
        print(message)
        if QGIS_AVAILABLE:
            QMessageBox.warning(None, "Détection photos", message)
        return
    
    # Récupérer les photos référencées
    referenced_photos = get_referenced_photos_from_layer(layer_path)
    
    if not referenced_photos:
        message = "⚠️  Aucune photo référencée trouvée ou impossible de lire la couche.\n\nToutes les photos dans DCIM sont potentiellement non référencées."
        print(message)
        
        # Analyser les formats quand même
        formats = analyze_photo_formats(dcim_photos)
        
        format_info = "\n📈 Analyse des formats :\n"
        for format_type, photo_list in formats.items():
            format_info += f"  {format_type.upper()}: {len(photo_list)} photos\n"
            if photo_list:
                format_info += f"    Exemples: {', '.join(photo_list[:3])}\n"
        
        print(format_info)
        message += format_info
        
        if QGIS_AVAILABLE:
            QMessageBox.information(None, "Détection photos", message)
        return
    
    # Trouver les photos non référencées
    unreferenced_photos = [photo for photo in dcim_photos if photo not in referenced_photos]
    
    result_message = f"🔍 Résultat de l'analyse :\n"
    result_message += f"  Photos dans DCIM: {len(dcim_photos)}\n"
    result_message += f"  Photos référencées: {len(referenced_photos)}\n"
    result_message += f"  Photos non référencées: {len(unreferenced_photos)}\n"
    
    print(result_message)
    
    if unreferenced_photos:
        # Analyser les formats
        formats = analyze_photo_formats(unreferenced_photos)
        
        detailed_message = f"📋 Photos non référencées ({len(unreferenced_photos)}) :\n\n"
        
        for format_type, photo_list in formats.items():
            if photo_list:
                detailed_message += f"📌 {format_type.upper()} ({len(photo_list)} photos):\n"
                for photo in sorted(photo_list):
                    detailed_message += f"  • {photo}\n"
                detailed_message += "\n"
        
        print(detailed_message)
        
        # Générer un fichier de rapport
        report_file = "photos_non_referencées.txt"
        with open(report_file, 'w') as f:
            f.write("Photos non référencées\n")
            f.write("=" * 50 + "\n\n")
            
            for format_type, photo_list in formats.items():
                if photo_list:
                    f.write(f"{format_type.upper()} ({len(photo_list)} photos):\n")
                    for photo in sorted(photo_list):
                        f.write(f"  {photo}\n")
                    f.write("\n")
        
        final_message = result_message + "\n" + detailed_message
        final_message += f"📄 Rapport détaillé sauvegardé dans : {os.path.abspath(report_file)}\n"
        final_message += f"💡 Vous pouvez utiliser ces informations pour créer des entités avec le plugin PhotoNormalizer."
        
        print(f"📄 Rapport sauvegardé dans : {os.path.abspath(report_file)}")
        print(f"💡 Vous pouvez utiliser ces informations pour créer des entités avec le plugin PhotoNormalizer.")
        
        if QGIS_AVAILABLE:
            # Créer une boîte de dialogue avec les résultats
            msg_box = QMessageBox()
            msg_box.setWindowTitle("Résultats détection photos non référencées")
            msg_box.setText(f"Trouvé {len(unreferenced_photos)} photos non référencées")
            msg_box.setInformativeText(f"Voir le rapport détaillé dans : {os.path.abspath(report_file)}")
            msg_box.setDetailedText(detailed_message)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.exec_()
    else:
        message = "✅ Toutes les photos dans DCIM sont référencées dans la base de données."
        print(message)
        if QGIS_AVAILABLE:
            QMessageBox.information(None, "Détection photos", message)

def main():
    """
    Fonction principale pour l'exécution en ligne de commande.
    """
    run_detection()

if __name__ == "__main__":
    main()