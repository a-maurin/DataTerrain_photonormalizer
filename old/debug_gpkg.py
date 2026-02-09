#!/usr/bin/env python3
"""
Script de débogage pour analyser le GeoPackage.
Approche alternative pour lire la structure du GeoPackage.
"""

import os
import sqlite3
from qgis.PyQt.QtWidgets import QMessageBox, QMessageBox

def log_message(message, show_in_dialog=False):
    """Journalise les messages et les affiche éventuellement dans une boîte de dialogue."""
    print(message)
    
    # Écrire dans un fichier de log
    with open("debug_gpkg.log", "a") as f:
        f.write(message + "\n")
    
    if show_in_dialog:
        QMessageBox.information(None, "Debug", message)

def debug_geopackage():
    """Analyse détaillée du GeoPackage."""
    
    # Effacer le fichier de log précédent
    with open("debug_gpkg.log", "w") as f:
        f.write("=== Début de l'analyse du GeoPackage ===\n\n")
    
    gpkg_path = "/home/e357/Qfield/cloud/DataTerrain/donnees_terrain.gpkg"
    
    log_message(f"🔍 Analyse détaillée de : {gpkg_path}")
    
    # Vérifier que le fichier existe
    if not os.path.exists(gpkg_path):
        error_msg = f"❌ Fichier introuvable : {gpkg_path}"
        log_message(error_msg, True)
        return
    
    log_message(f"✅ Fichier trouvé : {gpkg_path}")
    
    try:
        # Approche 1: Utiliser SQLite pour lire directement le GeoPackage
        print("\n📊 Lecture directe avec SQLite...")
        conn = sqlite3.connect(gpkg_path)
        cursor = conn.cursor()
        
        # Lister toutes les tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = cursor.fetchall()
        
        log_message(f"Tables trouvées : {len(tables)}")
        
        found_photo_tables = []
        
        for table in tables:
            table_name = table[0]
            log_message(f"  • {table_name}")
            
            # Vérifier si c'est une table de données (pas une table système)
            if not table_name.startswith('gpkg_') and not table_name.startswith('sqlite_'):
                try:
                    # Lister les colonnes
                    cursor.execute(f"PRAGMA table_info({table_name});")
                    columns = cursor.fetchall()
                    
                    column_names = []
                    columns_str = ""
                    for col in columns:
                        col_name = col[1]
                        column_names.append(col_name)
                        if col_name == 'photo':
                            columns_str += f"🔍 {col_name} (trouvé!), "
                        else:
                            columns_str += f"{col_name}, "
                    
                    log_message(f"    Colonnes: {columns_str}")
                    
                    if 'photo' in column_names:
                        log_message(f"    ✅ Cette table contient un champ 'photo'!")
                        found_photo_tables.append(table_name)
                        
                        # Compter le nombre d'enregistrements
                        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                        count = cursor.fetchone()[0]
                        log_message(f"    📈 Nombre d'enregistrements: {count}")
                        
                        # Voir quelques exemples de valeurs du champ photo
                        cursor.execute(f"SELECT photo FROM {table_name} LIMIT 5;")
                        photos = cursor.fetchall()
                        log_message(f"    📷 Exemples de photos: {photos}")
                        
                except Exception as e:
                    log_message(f"    ❌ Erreur lors de la lecture de {table_name}: {e}")
        
        conn.close()
        
        # Approche 2: Essayer avec QGIS
        print("\n🎯 Tentative avec QGIS...")
        try:
            from qgis.core import QgsVectorLayer
            
            # Essayer de charger le GeoPackage
            layer = QgsVectorLayer(gpkg_path, "debug_layer", "ogr")
            
            if layer.isValid():
                log_message("✅ GeoPackage chargé avec succès via QGIS")
                
                # Lister les sous-couches
                sublayers = layer.dataProvider().subLayers()
                log_message(f"Sous-couches trouvées: {len(sublayers)}")
                
                for sublayer in sublayers:
                    log_message(f"  • {sublayer}")
            else:
                log_message("❌ Impossible de charger le GeoPackage via QGIS")
                
        except Exception as e:
            print(f"❌ Erreur avec QGIS: {e}")
        
    except Exception as e:
        error_msg = f"❌ Erreur générale: {e}"
        log_message(error_msg, True)
        return
    
    # Afficher un résumé final
    if found_photo_tables:
        summary = f"🎉 Analyse terminée avec succès!\n\n"
        summary += f"Tables avec champ 'photo' trouvées:\n"
        for table in found_photo_tables:
            summary += f"  • {table}\n"
        summary += f"\n📄 Rapport complet sauvegardé dans: {os.path.abspath('debug_gpkg.log')}"
        log_message(summary, True)
    else:
        summary = f"⚠️ Analyse terminée\n\n"
        summary += f"Aucune table avec champ 'photo' trouvée.\n"
        summary += f"📄 Rapport complet sauvegardé dans: {os.path.abspath('debug_gpkg.log')}"
        log_message(summary, True)

# Exécuter le débogage
debug_geopackage()