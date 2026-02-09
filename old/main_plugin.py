#!/usr/bin/env python3
"""
Photo Normalizer v0.0.4 - Plugin QGIS pour la normalisation complète des photos
Version unifiée avec toutes les améliorations :
- Normalisation des photos
- Détection des photos orphelines
- Création d'entités manquantes
- Analyse complète et rapport détaillé
- Fenêtre de log pour le suivi des opérations
"""

import os
import re
import sys
from PIL import Image, ExifTags
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsProject,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsVectorLayer,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem
)
from qgis.PyQt.QtCore import QSettings
from .log_window import LogWindow, LogHandler
from .detect_photos_integrated import detect_unreferenced_photos_integrated

class PhotoNormalizerUnifie:
    """
    Version unifiée du plugin de normalisation des photos
    """
    
    def __init__(self, log_handler=None):
        self.layer_name = "donnees_terrain"
        self.max_w, self.max_h = 800, 600
        self.quality = 85
        self.crs_3857 = QgsCoordinateReferenceSystem('EPSG:3857')
        self.stats = {
            'photos_analysees': 0,
            'photos_standard': 0,
            'photos_ancien_format': 0,
            'photos_renommees': 0,
            'photos_associees': 0,
            'entites_creees': 0,
            'conflits': 0
        }
        self.transform = None
        self.log_handler = log_handler
        self.export_dir = None
        # Initialiser le dossier d'exportation après l'initialisation du log handler
        if self.log_handler is not None:
            self._initialize_export_directory()
    
    def _initialize_export_directory(self):
        """
        Initialise le dossier d'exportation dans le répertoire du plugin.
        Crée le dossier s'il n'existe pas.
        """
        try:
            # Obtenir le chemin du répertoire du plugin
            plugin_dir = os.path.dirname(os.path.abspath(__file__))
            export_dir = os.path.join(plugin_dir, "exports")
            
            # Créer le dossier s'il n'existe pas
            if not os.path.exists(export_dir):
                os.makedirs(export_dir)
                if self.log_handler is not None:
                    self.log_handler.info(f"📁 Dossier d'exportation créé : {export_dir}")
            else:
                if self.log_handler is not None:
                    self.log_handler.info(f"📁 Dossier d'exportation existant : {export_dir}")
            
            self.export_dir = export_dir
            
        except Exception as e:
            if self.log_handler is not None:
                self.log_handler.error(f"❌ Impossible de créer le dossier d'exportation : {e}")
            else:
                print(f"❌ Impossible de créer le dossier d'exportation : {e}")
            self.export_dir = None
    
    def get_export_path(self, filename):
        """
        Retourne le chemin complet pour un fichier d'exportation.
        
        Args:
            filename: Nom du fichier à exporter
            
        Returns:
            Chemin complet ou None si le dossier d'exportation n'est pas disponible
        """
        if not self.export_dir:
            return None
        
        return os.path.join(self.export_dir, filename)
        
    def run_photo_detection(self):
        """
        Exécute le script de détection des photos non référencées
        avec la console intégrée au plugin.
        """
        try:
            self.log_handler.log_message("🔍 Détection des photos non référencées en cours...")
            
            # Exécuter la version intégrée qui utilise directement notre système de log
            success = detect_unreferenced_photos_integrated(self.log_handler, self.export_dir)
            
            if success:
                self.log_handler.log_message("✅ Détection des photos non référencées terminée avec succès")
            else:
                self.log_handler.log_message("⚠️  Détection des photos non référencées terminée avec des erreurs")
                
        except Exception as e:
            self.log_handler.log_message(f"❌ Erreur lors de la détection des photos: {e}", level="ERROR")
            import traceback
            self.log_handler.log_message(f"Détails: {traceback.format_exc()}", level="ERROR")
        self.log_file = None
        
        # Initialisation de la journalisation dans un fichier
        self._init_log_file()
        
        # Si aucun log_handler n'est fourni, créer un log_handler qui écrit dans le fichier
        if self.log_handler is None:
            self.log_handler = self._create_file_log_handler()
    
    def _create_file_log_handler(self):
        """Crée un log handler qui écrit dans le fichier de log"""
        class FileLogHandler:
            def __init__(self, log_file, photonormalizer_instance):
                self.log_file = log_file
                self.photonormalizer = photonormalizer_instance
                
            def debug(self, msg):
                self.photonormalizer._log_to_file(f"DEBUG: {msg}")
                
            def info(self, msg):
                self.photonormalizer._log_to_file(f"INFO: {msg}")
                
            def warning(self, msg):
                self.photonormalizer._log_to_file(f"WARNING: {msg}")
                
            def error(self, msg):
                self.photonormalizer._log_to_file(f"ERROR: {msg}")
                
            def success(self, msg):
                self.photonormalizer._log_to_file(f"SUCCESS: {msg}")
            
            def log_message(self, msg, level="INFO"):
                """Méthode générique pour logger des messages avec différents niveaux"""
                prefix = level.upper() if level.upper() in ["DEBUG", "INFO", "WARNING", "ERROR", "SUCCESS"] else "INFO"
                self.photonormalizer._log_to_file(f"{prefix}: {msg}")
        
        return FileLogHandler(self.log_file, self)
    
    def _init_log_file(self):
        """Initialise le fichier de log"""
        import datetime
        import os
        
        # Obtenir le chemin du plugin
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Utiliser le dossier d'exportation si disponible, sinon créer un dossier logs
        if self.export_dir:
            log_dir = self.export_dir
        else:
            # Utiliser le dossier du plugin pour les logs
            log_dir = os.path.join(plugin_dir, "logs")
        
        os.makedirs(log_dir, exist_ok=True)
        
        # Créer un nom de fichier avec timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"photonormalizer_{timestamp}.log"
        log_path = os.path.join(log_dir, log_filename)
        
        self.log_file = log_path
        
        # Écrire l'en-tête du log
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write(f"=== PHOTO NORMALIZER LOG - {timestamp} ===\n")
                f.write("Version: 0.0.4 - Version unifiée\n")
                f.write(f"Chemin du plugin : {plugin_dir}\n")
                f.write("==========================================\n\n")
            self._log_to_file("Fichier de log initialisé avec succès")
        except Exception as e:
            print(f"❌ Erreur lors de l'initialisation du fichier de log : {e}")
            # En cas d'erreur, utiliser un chemin alternatif
            if self.export_dir:
                self.log_file = os.path.join(self.export_dir, "photonormalizer_fallback.log")
            else:
                # Vérifier que plugin_dir est défini
                if 'plugin_dir' not in locals():
                    plugin_dir = os.path.dirname(os.path.abspath(__file__))
                self.log_file = os.path.join(plugin_dir, "photonormalizer_fallback.log")
            try:
                with open(self.log_file, 'w', encoding='utf-8') as f:
                    f.write(f"=== PHOTO NORMALIZER LOG - FALLBACK ===\n")
                    f.write(f"Erreur initiale : {e}\n")
                    f.write(f"Chemin du plugin : {plugin_dir}\n")
                    f.write("==========================================\n\n")
            except Exception as e:
                print(f"❌ Impossible de créer le fichier de log de secours: {e}")
                self.log_file = None
    
    def _log_to_file(self, message):
        """Écrit un message dans le fichier de log"""
        import datetime
        
        if self.log_file:
            try:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(f"[{timestamp}] {message}\n")
            except Exception as e:
                print(f"❌ Erreur lors de l'écriture dans le fichier de log : {e}")
                # En cas d'erreur, essayer d'écrire dans un fichier de secours
                fallback_path = os.path.join(os.path.expanduser("~"), "photonormalizer_error.log")
                try:
                    with open(fallback_path, 'a', encoding='utf-8') as f:
                        f.write(f"[{timestamp}] ERREUR LOG: {e}\n")
                        f.write(f"[{timestamp}] MESSAGE ORIGINAL: {message}\n")
                except Exception as log_error:
                    print(f"❌ Impossible d'écrire dans le fichier de log de secours: {log_error}")
        

    
    def execute(self):
        """
        Exécute le traitement complet unifié
        """
        # Le menu est maintenant géré par l'interface unifiée, donc cette méthode
        # est appelée directement lorsque l'utilisateur sélectionne le mode normal
        # dans l'interface graphique.
        
        # Vérification du fichier de log
        if self.log_file:
            try:
                self._log_to_file("=== DEBUT DU TRAITEMENT ===")
                self._log_to_file(f"Fichier de log : {self.log_file}")
            except Exception as e:
                self.log_handler.error(f"Erreur lors de l'écriture dans le fichier de log : {e}")

        self.log_handler.info("=== PHOTO NORMALIZER v0.0.4 - VERSION UNIFIÉE ===")
        self.log_handler.info("Traitement complet avec détection et création d'entités")
        
        try:
            # Étape 1 : Initialisation
            layer, dcim = self._initialisation()
            if not layer or not dcim:
                return False
            
            # Étape 2 : Analyse complète
            try:
                all_photos = self._get_all_photos(dcim)
                photo_analysis = self._analyser_photos(layer, all_photos)
            except Exception as e:
                self.log_handler.error(f"Erreur lors de l'analyse des photos : {e}")
                import traceback
                self.log_handler.error(traceback.format_exc())
                return False
            
            # Étape 3 : Traitement des photos standard
            try:
                self._traiter_photos_standard(layer, photo_analysis)
            except Exception as e:
                self.log_handler.error(f"Erreur lors du traitement des photos standard : {e}")
                import traceback
                self.log_handler.error(traceback.format_exc())
                # Continuer malgré l'erreur
            
            # Étape 4 : Association des photos anciennes
            try:
                self._associer_photos_anciennes(layer, photo_analysis)
            except Exception as e:
                self.log_handler.error(f"Erreur lors de l'association des photos anciennes : {e}")
                import traceback
                self.log_handler.error(traceback.format_exc())
                # Continuer malgré l'erreur
            
            # Étape 5 : Création d'entités manquantes
            try:
                self._creer_entites_manquantes(layer, photo_analysis)
            except Exception as e:
                self.log_handler.error(f"Erreur lors de la création des entités manquantes : {e}")
                import traceback
                self.log_handler.error(traceback.format_exc())
                # Continuer malgré l'erreur
            
            # Étape 6 : Mise à jour des noms de photos pour les entités modifiées
            try:
                photos_mises_a_jour = self._mettre_a_jour_noms_photos(layer)
                self.stats['photos_renommees'] += photos_mises_a_jour
            except Exception as e:
                self.log_handler.error(f"Erreur lors de la mise à jour des noms de photos : {e}")
                import traceback
                self.log_handler.error(traceback.format_exc())
                # Continuer malgré l'erreur
            
            # Étape 7 : Rapport final
            try:
                self._generer_rapport()
            except Exception as e:
                self.log_handler.error(f"Erreur lors de la génération du rapport : {e}")
                import traceback
                self.log_handler.error(traceback.format_exc())
            
            return True
            
        except Exception as e:
            self.log_handler.error(f"❌ Erreur critique : {e}")
            import traceback
            self.log_handler.error(traceback.format_exc())
            if self.log_file:
                try:
                    self._log_to_file(f"❌ ERREUR CRITIQUE : {e}")
                    self._log_to_file(traceback.format_exc())
                except Exception as log_error:
                    self.log_handler.error(f"Erreur lors de l'écriture de l'erreur dans le fichier de log : {log_error}")
            QMessageBox.critical(None, "Erreur", f"Erreur critique : {e}")
            return False
        
    def _initialisation(self):
        """Initialisation du plugin"""
        try:
            # Vérification de la couche
            layers = QgsProject.instance().mapLayersByName(self.layer_name)
            if not layers:
                QMessageBox.critical(None, "Erreur", f"La couche '{self.layer_name}' est introuvable.")
                return None, None
            
            layer = layers[0]
            self.log_handler.success(f"Couche '{self.layer_name}' trouvée avec {layer.featureCount()} entités")
            
            # Utilisation du chemin fixe pour QField Cloud
            base_path = "/home/e357/Qfield/cloud/DataTerrain"
            dcim = os.path.join(base_path, "DCIM")
            
            if not os.path.exists(dcim):
                QMessageBox.critical(None, "Erreur", f"Dossier DCIM introuvable : {dcim}")
                return None, None
            
            self.log_handler.info(f"Dossier DCIM : {dcim}")
            
            # Initialisation de la transformation
            try:
                self.transform = QgsCoordinateTransform(
                    layer.crs(),
                    self.crs_3857,
                    QgsProject.instance()
                )
            except Exception as e:
                self.log_handler.error(f"Erreur lors de la création de la transformation : {e}")
                # Utiliser une transformation identité en cas d'échec
                self.transform = None
            
            return layer, dcim
            
        except Exception as e:
            self.log_handler.error(f"Erreur lors de l'initialisation : {e}")
            import traceback
            self.log_handler.error(traceback.format_exc())
            return None, None
        
    def _get_all_photos(self, dcim_path):
        """Récupère toutes les photos du dossier DCIM"""
        all_photos = [f for f in os.listdir(dcim_path)
                     if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        self.log_handler.info(f"Photos trouvées : {len(all_photos)}")
        return all_photos
        
    def _analyser_photos(self, layer, all_photos):
        """Analyse complète de toutes les photos"""
        self.log_handler.info("\n--- Analyse des photos ---")
        
        photo_analysis = {}
        photos_referenced = set()
        
        # Indexer les entités existantes
        entities_by_fid = {}
        for f in layer.getFeatures():
            fid = f.id()
            photo = f['photo']
            entities_by_fid[fid] = f
            if photo:
                photo_name = os.path.basename(photo)
                photos_referenced.add(photo_name)
        
        # Analyser chaque photo
        for photo_name in all_photos:
            self.stats['photos_analysees'] += 1
            
            # Déterminer le format
            format_type = self._determiner_format(photo_name)
            
            # Vérifier si référencée
            is_referenced = photo_name in photos_referenced
            
            photo_analysis[photo_name] = {
                'format': format_type,
                'referenced': is_referenced,
                'entity_id': None,
                'coordinates': None,
                'date': None,
                'time': None
            }
            
            # Extraire les informations selon le format
            if format_type == 'standard':
                self.stats['photos_standard'] += 1
            elif format_type == 'ancien':
                self.stats['photos_ancien_format'] += 1
                self._extraire_info_ancien_format(photo_name, photo_analysis[photo_name])
            else:
                # Format inconnu - probablement un format intermédiaire à corriger
                self.stats['photos_ancien_format'] += 1
                self.log_handler.info(f"Format inconnu (à corriger) : {photo_name}")
            
            if is_referenced:
                self.log_handler.success(f"{photo_name} - Format: {format_type} - Référencée")
            else:
                self.log_handler.warning(f"{photo_name} - Format: {format_type} - Non référencée")
        
        return photo_analysis
        
    def _determiner_format(self, photo_name):
        """Détermine le format de la photo"""
        # Format standard : DT_YYYY-MM-DD_FID_agent_type_X_Y.jpg
        # Modifié pour accepter les noms avec prénom (ex: cuenin_chris)
        if re.match(r'DT_\d{4}-\d{2}-\d{2}_\d+_[^_]+(?:_[^_]+)*_[^_]+_[-+]?\d+\.?\d*_[-+]?\d+\.?\d*\.jpg', photo_name):
            return 'standard'
        
        # Format ancien : DT_YYYYMMDD_HHMMSS_X_Y.jpg
        elif re.match(r'DT_\d{8}_\d{6}_[-+]?\d+\.?\d*_[-+]?\d+\.?\d*\.jpg', photo_name):
            return 'ancien'
        
        return 'inconnu'
        
    def _extraire_info_ancien_format(self, photo_name, analysis):
        """Extraire les informations des photos au format ancien"""
        match = re.match(r'DT_(\d{8})_(\d{6})_([-+]?\d+\.?\d*)_([-+]?\d+\.?\d*)\.jpg', photo_name)
        if match:
            analysis['date'] = match.group(1)
            analysis['time'] = match.group(2)
            analysis['coordinates'] = (float(match.group(3)), float(match.group(4)))
            
    def _traiter_photos_standard(self, layer, photo_analysis):
        """Traitement des photos référencées (standard ou à corriger)"""
        self.log_handler.info("\n--- Traitement des photos référencées ---")
        
        layer.startEditing()
        
        for photo_name, analysis in photo_analysis.items():
            # Traiter toutes les photos référencées qui ne sont pas déjà normalisées
            if not analysis['referenced']:
                continue
            
            # Vérifier si déjà normalisée
            if self._est_deja_normalisee(photo_name):
                self.log_handler.success(f"{photo_name} - Déjà normalisée")
                continue
            
            # Vérifier si la photo existe physiquement
            photo_path = os.path.join("/home/e357/Qfield/cloud/DataTerrain", "DCIM", photo_name)
            if not os.path.exists(photo_path):
                self.log_handler.warning(f"Photo manquante : {photo_name}")
                continue
            
            # Trouver l'entité correspondante
            entity = None
            for f in layer.getFeatures():
                if f['photo'] and os.path.basename(f['photo']) == photo_name:
                    entity = f
                    break
            
            if not entity:
                continue
            
            # Vérifier si la photo est déjà au bon format
            if self._est_deja_normalisee(photo_name):
                self.log_handler.success(f"{photo_name} - Déjà normalisée")
                continue
            
            # Renommage et traitement
            new_name = self._construire_nom_standard(entity, layer)
            if new_name is None:
                self.log_handler.warning(f"Impossible de construire un nom valide pour {photo_name}")
                self.stats['conflits'] += 1
                continue
                
            new_path = os.path.join(os.path.dirname(photo_path), new_name)
            
            if os.path.exists(new_path) and photo_path.lower() != new_path.lower():
                self.log_handler.warning(f"Conflit : {new_name} existe déjà")
                self.stats['conflits'] += 1
                continue
            
            try:
                self._traiter_image(photo_path, new_path)
                
                # Mise à jour de l'entité
                layer.changeAttributeValue(entity.id(), 
                                         layer.fields().indexFromName('photo'),
                                         f"DCIM/{new_name}")
                
                if photo_path.lower() != new_path.lower():
                    os.remove(photo_path)
                    self.stats['photos_renommees'] += 1
                    self.log_handler.success(f"Renommée : {photo_name} → {new_name}")
                else:
                    self.stats['photos_associees'] += 1
                    self.log_handler.success(f"Corrigée : {photo_name}")
                    
            except Exception as e:
                self.log_handler.error(f"Erreur traitement {photo_name}: {e}")
        
        layer.commitChanges()
        
    def _est_deja_normalisee(self, photo_name):
        """Vérifie si une photo est déjà au format standard"""
        return re.match(r'DT_\d{4}-\d{2}-\d{2}_\d+_[^_]+_[^_]+_[-+]?\d+\.?\d*_[-+]?\d+\.?\d*\.jpg', photo_name)
        
    def _construire_nom_standard(self, entity, layer):
        """Construit un nom standard pour une photo"""
        # Accès sécurisé aux champs avec méthode attribute()
        try:
            date_saisie = entity.attribute('date_saisie')
            if not date_saisie:
                self.log_handler.warning(f"Champ 'date_saisie' manquant ou vide pour l'entité {entity.id()}")
                return None
            
            # Vérification du format de la date - gestion de différents formats
            date_str = str(date_saisie)
            date_parts = None
            
            # Gestion des dates au format QDate comme PyQt5.QtCore.QDate(2026, 1, 15)
            if date_str.startswith('PyQt5.QtCore.QDate('):
                # Extraire les valeurs de la date
                import re
                match = re.search(r'QDate\((\d+), (\d+), (\d+)\)', date_str)
                if match:
                    year, month, day = match.groups()
                    # Validation des valeurs de date
                    try:
                        year = int(year)
                        month = int(month)
                        day = int(day)
                        
                        # Vérification que la date est valide
                        if month < 1 or month > 12:
                            self.log_handler.warning(f"Mois invalide ({month}) pour l'entité {entity.id()}: {date_str}")
                            return None
                        if day < 1 or day > 31:
                            self.log_handler.warning(f"Jour invalide ({day}) pour l'entité {entity.id()}: {date_str}")
                            return None
                        
                        date_parts = [str(year), str(month).zfill(2), str(day).zfill(2)]
                        date_str_formatted = f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}T00:00:00"
                        
                        # Mettre à jour l'entité avec le bon format de date
                        date_saisie_index = entity.fields().indexFromName('date_saisie')
                        if date_saisie_index != -1:
                            entity.setAttribute(date_saisie_index, date_str_formatted)
                    except ValueError as ve:
                        self.log_handler.warning(f"Erreur de conversion de date pour l'entité {entity.id()}: {ve}")
                        return None
                else:
                    self.log_handler.warning(f"Format de date QDate invalide pour l'entité {entity.id()}: {date_str}")
                    return None
            # Gestion des dates au format ISO standard
            elif 'T' in date_str and len(date_str.split('T')[0].split('-')) == 3:
                date_parts = date_str.split('T')[0].split('-')
                # Validation des parties de la date
                try:
                    year, month, day = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
                    if month < 1 or month > 12:
                        self.log_handler.warning(f"Mois invalide ({month}) pour l'entité {entity.id()}: {date_str}")
                        return None
                    if day < 1 or day > 31:
                        self.log_handler.warning(f"Jour invalide ({day}) pour l'entité {entity.id()}: {date_str}")
                        return None
                except ValueError:
                    self.log_handler.warning(f"Format de date ISO invalide pour l'entité {entity.id()}: {date_str}")
                    return None
            # Gestion des dates au format AAAA-MM-JJ
            elif len(date_str.split('-')) == 3:
                date_parts = date_str.split('-')
                # Validation des parties de la date
                try:
                    year, month, day = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
                    if month < 1 or month > 12:
                        self.log_handler.warning(f"Mois invalide ({month}) pour l'entité {entity.id()}: {date_str}")
                        return None
                    if day < 1 or day > 31:
                        self.log_handler.warning(f"Jour invalide ({day}) pour l'entité {entity.id()}: {date_str}")
                        return None
                    date_str = f"{date_str}T00:00:00"
                except ValueError:
                    self.log_handler.warning(f"Format de date AAAA-MM-JJ invalide pour l'entité {entity.id()}: {date_str}")
                    return None
            else:
                self.log_handler.warning(f"Format de date invalide pour l'entité {entity.id()}: {date_str}")
                return None
            
            if not date_parts or len(date_parts) != 3:
                self.log_handler.warning(f"Impossible d'extraire les parties de la date pour l'entité {entity.id()}: {date_str}")
                return None
            
            # Accès sécurisé aux champs avec valeurs par défaut
            # Utiliser les noms de champs corrects
            agent = entity.attribute('nom_agent') or "INCONNU"
            type_photo = entity.attribute('type_saisie') or "INCONNU"
            
            # Nettoyage des noms d'agent et type_photo pour éviter les caractères problématiques
            agent = re.sub(r'[^\w\-]', '_', str(agent))
            type_photo = re.sub(r'[^\w\-]', '_', str(type_photo))
            
        except Exception as e:
            self.log_handler.error(f"Erreur lors de la construction du nom pour l'entité {entity.id()} : {e}")
            import traceback
            self.log_handler.error(traceback.format_exc())
            return None
        
        # Extraction des coordonnées
        geom = entity.geometry()
        if geom:
            point = geom.asPoint()
            x, y = point.x(), point.y()
            # Transformation en EPSG:3857 si nécessaire
            # Note: crs() doit être appelé sur la couche, pas sur la géométrie
            if layer.crs() != self.crs_3857 and self.transform:
                try:
                    point_3857 = self.transform.transform(point.x(), point.y())
                    x, y = point_3857.x(), point_3857.y()
                except Exception as e:
                    self.log_handler.warning(f"Erreur de transformation de coordonnées pour l'entité {entity.id()}: {e}")
                    # Utiliser les coordonnées originales en cas d'échec
                    x, y = point.x(), point.y()
        else:
            x, y = 0, 0
        
        # Format correct : DT_YYYY-MM-DD_FID_agent_type_X_Y.jpg
        date_with_dashes = f"{date_parts[0]}-{date_parts[1]}-{date_parts[2]}"
        return f"DT_{date_with_dashes}_{entity.id()}_{agent}_{type_photo}_{x:.3f}_{y:.3f}.jpg"
        
    def _traiter_image(self, old_path, new_path):
        """Traite l'image (redimensionnement, orientation, etc.)"""
        try:
            with Image.open(old_path) as img:
                # Correction de l'orientation
                img = self._corriger_orientation(img)
                
                # Redimensionnement
                img.thumbnail((self.max_w, self.max_h), Image.Resampling.LANCZOS)
                
                # Sauvegarde
                img.save(new_path, "JPEG", quality=self.quality)
        except Exception as e:
            self.log_handler.error(f"Erreur lors du traitement de l'image {old_path} : {e}")
            import traceback
            self.log_handler.error(traceback.format_exc())
            # En cas d'erreur, essayer de copier le fichier directement
            try:
                import shutil
                shutil.copy2(old_path, new_path)
                self.log_handler.warning(f"Image copiée directement sans traitement : {old_path} → {new_path}")
            except Exception as copy_error:
                self.log_handler.error(f"Échec de la copie directe de l'image : {copy_error}")
                raise
            
    def _corriger_orientation(self, img):
        """Corrige l'orientation de l'image"""
        try:
            exif = img._getexif()
            if exif:
                orientation = exif.get(0x0112)
                if orientation == 3:
                    img = img.rotate(180, expand=True)
                elif orientation == 6:
                    img = img.rotate(270, expand=True)
                elif orientation == 8:
                    img = img.rotate(90, expand=True)
        except Exception as e:
            # En cas d'erreur, ignorer et retourner l'image originale
            self.log_handler.debug(f"Erreur lors de la correction d'orientation : {e}")
            pass
        return img
        
    def _mettre_a_jour_noms_photos(self, layer):
        """Met à jour les noms des photos pour les entités existantes qui ont été modifiées"""
        self.log_handler.info("\n--- Mise à jour des noms de photos pour les entités modifiées ---")
        
        layer.startEditing()
        
        photos_mises_a_jour = 0
        
        for entity in layer.getFeatures():
            if not entity['photo']:
                continue
            
            # Vérifier si l'entité a tous les champs nécessaires
            if not entity.attribute('date_saisie') or not entity.attribute('nom_agent') or not entity.attribute('type_saisie'):
                continue
            
            # Construire le nouveau nom basé sur les attributs actuels
            new_name = self._construire_nom_standard(entity, layer)
            if new_name is None:
                continue
            
            # Extraire le nom de fichier actuel
            current_photo_path = entity['photo']
            if 'DCIM/' in current_photo_path:
                current_photo_name = current_photo_path.split('DCIM/')[1]
            else:
                current_photo_name = current_photo_path
            
            # Vérifier si le nom doit être mis à jour
            if current_photo_name != new_name:
                old_path = os.path.join("/home/e357/Qfield/cloud/DataTerrain", "DCIM", current_photo_name)
                new_path = os.path.join("/home/e357/Qfield/cloud/DataTerrain", "DCIM", new_name)
                
                if os.path.exists(old_path) and not os.path.exists(new_path):
                    try:
                        self._traiter_image(old_path, new_path)
                        
                        # Mettre à jour le champ photo de l'entité
                        layer.changeAttributeValue(entity.id(),
                                                 layer.fields().indexFromName('photo'),
                                                 f"DCIM/{new_name}")
                        
                        os.remove(old_path)
                        photos_mises_a_jour += 1
                        self.log_handler.success(f"Mise à jour : {current_photo_name} → {new_name}")
                        
                    except Exception as e:
                        self.log_handler.error(f"Erreur mise à jour {current_photo_name}: {e}")
        
        layer.commitChanges()
        return photos_mises_a_jour

    def _associer_photos_anciennes(self, layer, photo_analysis):
        """Associe les photos au format ancien aux entités existantes"""
        self.log_handler.info("\n--- Association des photos anciennes ---")
        
        layer.startEditing()
        
        for photo_name, analysis in photo_analysis.items():
            if analysis['format'] != 'ancien' or analysis['coordinates'] is None:
                continue
            
            # Rechercher une entité proche
            x, y = analysis['coordinates']
            point = QgsPointXY(x, y)
            
            # Transformation inverse si nécessaire
            if layer.crs() != self.crs_3857:
                inv_transform = QgsCoordinateTransform(self.crs_3857, layer.crs(), QgsProject.instance())
                point = inv_transform.transform(point)
            
            # Rechercher l'entité la plus proche
            closest_entity = None
            min_distance = float('inf')
            
            for entity in layer.getFeatures():
                if not entity.geometry():
                    continue
                
                entity_point = entity.geometry().asPoint()
                distance = ((point.x() - entity_point.x())**2 + (point.y() - entity_point.y())**2)**0.5
                
                if distance < min_distance and distance < 10:  # Seuil de 10 mètres
                    min_distance = distance
                    closest_entity = entity
            
            if closest_entity and not closest_entity['photo']:
                # Construire le nouveau nom
                new_name = self._construire_nom_standard(closest_entity, layer)
                if new_name is None:
                    self.log_handler.warning(f"Impossible de construire un nom valide pour l'association de {photo_name}")
                    continue
                
                # Renommer la photo
                old_path = os.path.join("/home/e357/Qfield/cloud/DataTerrain", "DCIM", photo_name)
                new_path = os.path.join("/home/e357/Qfield/cloud/DataTerrain", "DCIM", new_name)
                
                if os.path.exists(new_path):
                    self.log_handler.warning(f"Conflit : {new_name} existe déjà")
                    self.stats['conflits'] += 1
                    continue
                
                try:
                    self._traiter_image(old_path, new_path)
                    
                    # Mise à jour de l'entité
                    layer.changeAttributeValue(closest_entity.id(),
                                             layer.fields().indexFromName('photo'),
                                             f"DCIM/{new_name}")
                    
                    os.remove(old_path)
                    self.stats['photos_renommees'] += 1
                    self.log_handler.success(f"Associée : {photo_name} → {new_name} (distance: {min_distance:.2f}m)")
                    
                except Exception as e:
                    self.log_handler.error(f"Erreur association {photo_name}: {e}")
        
        layer.commitChanges()
        
    def _creer_entites_manquantes(self, layer, photo_analysis):
        """Crée des entités pour les photos orphelines (format ancien ou standard non référencé)"""
        self.log_handler.info("\n--- Création d'entités manquantes ---")
        
        layer.startEditing()
        
        new_features = []  # Liste pour stocker toutes les nouvelles entités
        
        for photo_name, analysis in photo_analysis.items():
            # Traiter les photos non référencées qui ont des coordonnées valides
            # (format ancien OU format standard marqué comme inconnu mais avec des coordonnées)
            if (analysis['referenced'] or 
                analysis['coordinates'] is None):
                continue
            
            # Accepter aussi les formats standard qui ont été marqués comme "inconnus"
            # mais qui ont des coordonnées extraites
            if analysis['format'] not in ['ancien', 'inconnu']:
                continue
            
            # Extraire les informations
            if analysis['format'] == 'ancien':
                # Format ancien : DT_YYYYMMDD_HHMMSS_X_Y.jpg
                date_str = analysis['date']
                time_str = analysis['time']
                x, y = analysis['coordinates']
            else:
                # Format standard/inconnu : extraire les infos du nom de fichier
                # Exemple : DT_2026-01-19_454_cuenin_chris_eau_tas_fumier_548204.953_6007547.819.jpg
                match = re.match(r'DT_(\d{4}-\d{2}-\d{2})_(\d+)_([^_]+(?:_[^_]+)*)_([^_]+)_([-+]?\d+\.?\d*)_([-+]?\d+\.?\d*)\.jpg', photo_name)
                if not match:
                    self.log_handler.error(f"Impossible d'extraire les informations de {photo_name}")
                    continue
                    
                date_str = match.group(1)  # YYYY-MM-DD
                # Pour le format standard, on n'a pas l'heure, utiliser 000000
                time_str = "000000"
                agent_part = match.group(3)  # "cuenin_chris"
                type_saisie = match.group(4)  # "eau_tas_fumier"
                x = float(match.group(5))
                y = float(match.group(6))
                
                # Mettre à jour l'analyse pour les champs spécifiques
                analysis['agent'] = agent_part
                analysis['type_saisie'] = type_saisie
            
            # Créer une nouvelle entité
            new_feature = QgsFeature(layer.fields())
            
            # Remplir les attributs de manière sécurisée
            try:
                date_saisie_index = layer.fields().indexFromName('date_saisie')
                agent_index = layer.fields().indexFromName('nom_agent')
                type_photo_index = layer.fields().indexFromName('type_saisie')
                
                # Vérifier que les index sont valides
                if date_saisie_index == -1 or agent_index == -1 or type_photo_index == -1:
                    self.log_handler.error(f"Champs manquants dans la couche : date_saisie={date_saisie_index}, nom_agent={agent_index}, type_saisie={type_photo_index}")
                    return
                
                # Validation des données de date et heure
                if len(date_str) < 8 or len(time_str) < 6:
                    self.log_handler.error(f"Format de date/heure invalide : date={date_str}, time={time_str}")
                    return
                
                # Validation des valeurs de date
                try:
                    year = int(date_str[:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])
                    
                    if month < 1 or month > 12:
                        self.log_handler.error(f"Mois invalide ({month}) pour la date {date_str}")
                        return
                    if day < 1 or day > 31:
                        self.log_handler.error(f"Jour invalide ({day}) pour la date {date_str}")
                        return
                except ValueError as ve:
                    self.log_handler.error(f"Erreur de conversion de date : {ve}")
                    return
                
                # Validation des valeurs de temps
                try:
                    hour = int(time_str[:2])
                    minute = int(time_str[2:4])
                    second = int(time_str[4:6])
                    
                    if hour < 0 or hour > 23:
                        self.log_handler.error(f"Heure invalide ({hour}) pour le temps {time_str}")
                        return
                    if minute < 0 or minute > 59:
                        self.log_handler.error(f"Minute invalide ({minute}) pour le temps {time_str}")
                        return
                    if second < 0 or second > 59:
                        self.log_handler.error(f"Seconde invalide ({second}) pour le temps {time_str}")
                        return
                except ValueError as ve:
                    self.log_handler.error(f"Erreur de conversion de temps : {ve}")
                    return
                
                new_feature.setAttribute(date_saisie_index, f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}T{time_str[:2]}:{time_str[2:4]}:{time_str[4:6]}")
                if analysis['format'] == 'ancien':
                    new_feature.setAttribute(agent_index, "INCONNU")
                    new_feature.setAttribute(type_photo_index, "INCONNU")
                else:
                    # Pour le format standard, utiliser les infos extraites du nom
                    new_feature.setAttribute(agent_index, analysis.get('agent', "INCONNU"))
                    new_feature.setAttribute(type_photo_index, analysis.get('type_saisie', "INCONNU"))
                
                # Ajouter les coordonnées dans les champs x_saisie et y_saisie
                # Forcer le type float pour garantir la compatibilité avec QGIS
                x_saisie_index = layer.fields().indexFromName('x_saisie')
                y_saisie_index = layer.fields().indexFromName('y_saisie')
                
                if x_saisie_index != -1:
                    # Convertir explicitement en float et vérifier la valeur
                    try:
                        x_float = float(x)
                        new_feature.setAttribute(x_saisie_index, x_float)
                    except (ValueError, TypeError) as e:
                        self.log_handler.error(f"Erreur de conversion de x_saisie {x} : {e}")
                        new_feature.setAttribute(x_saisie_index, 0.0)  # Valeur par défaut
                
                if y_saisie_index != -1:
                    # Convertir explicitement en float et vérifier la valeur
                    try:
                        y_float = float(y)
                        new_feature.setAttribute(y_saisie_index, y_float)
                    except (ValueError, TypeError) as e:
                        self.log_handler.error(f"Erreur de conversion de y_saisie {y} : {e}")
                        new_feature.setAttribute(y_saisie_index, 0.0)  # Valeur par défaut
            except Exception as e:
                self.log_handler.error(f"Erreur lors de la définition des attributs : {e}")
                import traceback
                self.log_handler.error(traceback.format_exc())
                return
            
            # Créer la géométrie
            point = QgsPointXY(x, y)
            if layer.crs() != self.crs_3857:
                inv_transform = QgsCoordinateTransform(self.crs_3857, layer.crs(), QgsProject.instance())
                point = inv_transform.transform(point)
            
            new_feature.setGeometry(QgsGeometry.fromPointXY(point))
            
            # Ajouter l'entité à la liste (sans valider tout de suite)
            new_features.append(new_feature)
            
        
        # Créer les entités une par une pour pouvoir récupérer leurs FID immédiatement
        if new_features:
            layer.startEditing()
            
            for new_feature in new_features:
                # Extraire les informations avant la création
                feature_date = new_feature['date_saisie']
                feature_agent = new_feature['nom_agent']
                feature_type = new_feature['type_saisie']
                x = new_feature.geometry().asPoint().x()
                y = new_feature.geometry().asPoint().y()
                
                # Créer l'entité individuellement
                success = layer.addFeature(new_feature)
                if success:
                    # Récupérer le FID immédiatement après la création
                    # Dans QGIS, après addFeature, nous pouvons obtenir le FID de la feature
                    new_fid = new_feature.id()
                    
                    if new_fid != -1:  # Vérifier que le FID est valide
                        # Trouver le nom de photo original correspondant
                        photo_name = None
                        for p_name, p_analysis in photo_analysis.items():
                            if not p_analysis['referenced'] and p_analysis['coordinates'] == (x, y):
                                photo_name = p_name
                                break
                        
                        if photo_name:
                            # Extraire les informations pour construire le nouveau nom
                            agent_part = new_feature['nom_agent']
                            type_saisie = new_feature['type_saisie']
                            
                            # Construire le nouveau nom de photo selon le format standard
                            # Extraire la date au format YYYY-MM-DD
                            date_str = feature_date[:10].replace('-', '')  # YYYYMMDD
                            
                            new_photo_name = f"DT_{date_str}_{new_fid}_{agent_part}_{type_saisie}_{x:.3f}_{y:.3f}.jpg"
                            
                            # Renommer la photo et l'associer à l'entité
                            self.log_handler.success(f"Renommage : {photo_name} → {new_photo_name}")
                            
                            # Renommage physique du fichier
                            dcim_path = "/home/e357/Qfield/cloud/DataTerrain/DCIM"
                            old_path = os.path.join(dcim_path, photo_name)
                            new_path = os.path.join(dcim_path, new_photo_name)
                            
                            try:
                                # Vérifier que l'ancien fichier existe
                                if os.path.exists(old_path):
                                    # Vérifier que le nouveau nom n'existe pas déjà
                                    if not os.path.exists(new_path):
                                        # Renommer le fichier
                                        os.rename(old_path, new_path)
                                        
                                        # Mettre à jour le champ photo de l'entité
                                        layer.changeAttributeValue(new_fid, 
                                                                 layer.fields().indexFromName('photo'),
                                                                 f"DCIM/{new_photo_name}")
                                        
                                        # Associer la photo à l'entité (si nécessaire)
                                        self._associer_photo_a_entite(layer, new_fid, new_photo_name)
                                        
                                        self.log_handler.success(f"✅ Photo renommée et associée : {photo_name} → {new_photo_name}")
                                    else:
                                        self.log_handler.warning(f"Conflit : {new_photo_name} existe déjà")
                                        self.stats['conflits'] += 1
                                else:
                                    self.log_handler.error(f"Fichier source introuvable : {old_path}")
                            except Exception as e:
                                self.log_handler.error(f"Erreur lors du renommage de {photo_name} : {e}")
                            
                            # Mettre à jour les statistiques
                            self.stats['photos_renommees'] += 1
                            self.stats['entites_creees'] += 1
                        else:
                            self.log_handler.error(f"Impossible de trouver la photo originale pour l'entité {new_fid}")
                    else:
                        self.log_handler.error(f"FID invalide (-1) pour une entité créée")
                else:
                    self.log_handler.error(f"Échec de la création d'une entité")
            
            layer.commitChanges()
            self.log_handler.success(f"✅ {len(new_features)} entités créées avec succès")
        else:
            self.log_handler.info("Aucune nouvelle entité à créer")
        
    def _generer_rapport(self):
        """Génère un rapport final"""
        self.log_handler.info("\n=== RAPPORT FINAL ===")
        self.log_handler.info(f"Photos analysées : {self.stats['photos_analysees']}")
        self.log_handler.info(f"Photos au format standard : {self.stats['photos_standard']}")
        self.log_handler.info(f"Photos au format ancien : {self.stats['photos_ancien_format']}")
        self.log_handler.info(f"Photos renommées : {self.stats['photos_renommees']}")
        self.log_handler.info(f"Photos associées : {self.stats['photos_associees']}")
        self.log_handler.info(f"Entités créées : {self.stats['entites_creees']}")
        self.log_handler.info(f"Conflits de noms : {self.stats['conflits']}")
        
        # Vérification finale du fichier de log
        if self.log_file:
            try:
                import os
                if os.path.exists(self.log_file):
                    file_size = os.path.getsize(self.log_file)
                    self._log_to_file(f"Fichier de log final : {self.log_file} ({file_size} octets)")
                    self._log_to_file("=== FIN DU TRAITEMENT ===")
                else:
                    self._log_to_file("❌ Fichier de log introuvable à la fin du traitement")
            except Exception as e:
                self._log_to_file(f"❌ Erreur lors de la vérification du fichier de log : {e}")
        
        # Afficher un message de résumé
        message = (
            f"Traitement terminé avec succès !\n\n"
            f"Photos analysées : {self.stats['photos_analysees']}\n"
            f"Photos standard : {self.stats['photos_standard']}\n"
            f"Photos anciennes : {self.stats['photos_ancien_format']}\n"
            f"Photos renommées : {self.stats['photos_renommees']}\n"
            f"Photos associées : {self.stats['photos_associees']}\n"
            f"Entités créées : {self.stats['entites_creees']}\n"
            f"Conflits : {self.stats['conflits']}"
        )
        
        # Ajouter l'information sur le fichier de log
        if self.log_file:
            message += f"\n\nFichier de log disponible à :\n{self.log_file}"
            try:
                import os
                if os.path.exists(self.log_file):
                    file_size = os.path.getsize(self.log_file)
                    message += f"\nTaille du fichier : {file_size} octets"
                else:
                    message += f"\n❌ Fichier de log introuvable"
            except Exception as e:
                message += f"\n⚠️ Impossible de vérifier la taille du fichier: {e}"
        
        QMessageBox.information(None, "Traitement terminé", message)
    
    def test_log_file(self):
        """Méthode de test pour vérifier que la journalisation fonctionne"""
        try:
            # Créer une instance de test
            test_normalizer = PhotoNormalizerUnifie()
            
            # Écrire des messages de test
            test_normalizer.log_handler.info("Test de journalisation - Message INFO")
            test_normalizer.log_handler.warning("Test de journalisation - Message WARNING")
            test_normalizer.log_handler.error("Test de journalisation - Message ERROR")
            test_normalizer.log_handler.success("Test de journalisation - Message SUCCESS")
            
            # Vérifier le fichier de log
            if test_normalizer.log_file:
                import os
                if os.path.exists(test_normalizer.log_file):
                    with open(test_normalizer.log_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    return True, f"Fichier de log créé avec succès\nChemin : {test_normalizer.log_file}\nTaille : {len(content)} caractères"
                else:
                    return False, f"Fichier de log introuvable : {test_normalizer.log_file}"
            else:
                return False, "Aucun fichier de log initialisé"
        except Exception as e:
            return False, f"Erreur lors du test de journalisation : {e}"
    
    def read_latest_log(self):
        """Lit et retourne le contenu du log le plus récent"""
        import os
        import glob
        
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(plugin_dir, "logs")
        
        # Vérifier si le dossier de logs existe
        if not os.path.exists(log_dir):
            return None, f"Dossier de logs introuvable : {log_dir}"
        
        # Trouver tous les fichiers de log
        log_files = glob.glob(os.path.join(log_dir, "photonormalizer_*.log"))
        
        if not log_files:
            # Vérifier s'il y a un fichier de secours
            fallback_log = os.path.join(plugin_dir, "photonormalizer_fallback.log")
            if os.path.exists(fallback_log):
                return fallback_log, "Fichier de log de secours"
            else:
                return None, "Aucun fichier de log trouvé"
        
        # Trouver le fichier le plus récent
        latest_log = max(log_files, key=os.path.getmtime)
        
        return latest_log, "Fichier de log le plus récent"
    
    def get_latest_log_content(self):
        """Retourne le contenu du log le plus récent"""
        log_path, status = self.read_latest_log()
        
        if log_path and os.path.exists(log_path):
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                return True, content, log_path
            except Exception as e:
                return False, f"Erreur lors de la lecture du fichier : {e}", log_path
        else:
            return False, status, None

class PhotoNormalizerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.log_window = None
        self.log_handler = None
        self.normalizer = None  # Initialisé plus tard après la création du log_handler

    def initGui(self):
        # Action principale
        self.action = QAction(
            QIcon(os.path.join(os.path.dirname(__file__), "icon.png")),
            "Normaliser les photos QField",
            self.iface.mainWindow()
        )
        self.action.triggered.connect(self.run)
        
        # Actions pour les fonctionnalités avancées
        self.analyse_action = QAction("Analyser photos orphelines", self.iface.mainWindow())
        self.analyse_action.triggered.connect(self.run_analyse_orphelines)
        
        self.recreer_action = QAction("Recréer entités manquantes", self.iface.mainWindow())
        self.recreer_action.triggered.connect(self.run_recreer_entites)
        
        self.identifier_action = QAction("Identifier photos orphelines", self.iface.mainWindow())
        self.identifier_action.triggered.connect(self.run_identifier_orphelines)
        
        # Action de test de journalisation
        self.test_log_action = QAction("Tester la journalisation", self.iface.mainWindow())
        self.test_log_action.triggered.connect(self.run_test_log)
        
        # Action pour lire le dernier log
        self.read_log_action = QAction("Lire le dernier log", self.iface.mainWindow())
        self.read_log_action.triggered.connect(self.run_read_latest_log)
        
        # Ajout à l'interface
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&QField Tools", self.action)
        self.iface.addPluginToMenu("&QField Tools", self.analyse_action)
        self.iface.addPluginToMenu("&QField Tools", self.recreer_action)
        self.iface.addPluginToMenu("&QField Tools", self.identifier_action)
        self.iface.addPluginToMenu("&QField Tools", self.test_log_action)
        self.iface.addPluginToMenu("&QField Tools", self.read_log_action)

    def unload(self):
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu("&QField Tools", self.action)
        self.iface.removePluginMenu("&QField Tools", self.analyse_action)
        self.iface.removePluginMenu("&QField Tools", self.recreer_action)
        self.iface.removePluginMenu("&QField Tools", self.identifier_action)
        self.iface.removePluginMenu("&QField Tools", self.test_log_action)
        self.iface.removePluginMenu("&QField Tools", self.read_log_action)

    def run(self):
        """Exécute le traitement complet"""
        # Créer et afficher la fenêtre de log unifiée
        self.log_window = LogWindow(self.iface.mainWindow())
        self.log_handler = LogHandler(self.log_window)
        
        # Connecter le signal du bouton d'exécution
        self.log_window.run_mode_selected.connect(self.on_mode_selected)
        
        # Créer un log handler combiné qui écrit à la fois dans la fenêtre et dans le fichier
        class CombinedLogHandler:
            def __init__(self, window_handler, file_handler):
                self.window_handler = window_handler
                self.file_handler = file_handler
                
            def debug(self, msg):
                self.window_handler.debug(msg)
                self.file_handler.debug(msg)
                
            def info(self, msg):
                self.window_handler.info(msg)
                self.file_handler.info(msg)
                
            def warning(self, msg):
                self.window_handler.warning(msg)
                self.file_handler.warning(msg)
                
            def error(self, msg):
                self.window_handler.error(msg)
                self.file_handler.error(msg)
                
            def success(self, msg):
                self.window_handler.success(msg)
                self.file_handler.success(msg)
            
            def log_message(self, msg, level="INFO"):
                """Méthode générique pour logger des messages avec différents niveaux"""
                if level == "DEBUG":
                    self.debug(msg)
                elif level == "INFO":
                    self.info(msg)
                elif level == "WARNING":
                    self.warning(msg)
                elif level == "ERROR":
                    self.error(msg)
                elif level == "SUCCESS":
                    self.success(msg)
                else:
                    self.info(msg)
        
        # Créer le normalizer principal avec le log_handler
        self.normalizer = PhotoNormalizerUnifie(self.log_handler)
        
        # Initialiser le dossier d'exportation pour le normalizer
        self.normalizer._initialize_export_directory()
        
        # Initialiser le fichier de log pour le normalizer
        self.normalizer._init_log_file()
        
        # Créer le file handler pour le normalizer
        file_handler = self.normalizer._create_file_log_handler()
        
        # Créer le log handler combiné
        combined_handler = CombinedLogHandler(self.log_handler, file_handler)
        
        # Mettre à jour le normalizer avec le log_handler combiné
        self.normalizer.log_handler = combined_handler
        
        # Rediriger la sortie standard vers le log handler
        sys.stdout = self.log_handler
        
        # Afficher la fenêtre de log
        self.log_window.show()
    
    def on_mode_selected(self, mode):
        """
        Méthode appelée lorsque l'utilisateur sélectionne un mode dans l'interface unifiée
        """
        if mode == "detection":
            # Exécuter le mode détection des photos non référencées
            self.normalizer.run_photo_detection()
        elif mode == "normal":
            # Exécuter le mode normal
            self.normalizer.execute()
        
        # Exécuter le traitement
        self.normalizer.execute()
        
        # Restaurer la sortie standard
        sys.stdout = sys.__stdout__

    def run_analyse_orphelines(self):
        """Analyse des photos orphelines"""
        # Créer et afficher la fenêtre de log
        self.log_window = LogWindow(self.iface.mainWindow())
        self.log_handler = LogHandler(self.log_window)
        
        # Rediriger la sortie standard vers le log handler
        sys.stdout = self.log_handler
        
        # Afficher la fenêtre de log
        self.log_window.show()
        
        try:
            self.log_handler.info("Début de l'analyse des photos orphelines...")
            from .modules.analyse_photos_orphelines import analyser_photos_orphelines
            analyser_photos_orphelines()
            self.log_handler.success("Analyse des photos orphelines terminée avec succès.")
            QMessageBox.information(None, "Succès", "Analyse des photos orphelines terminée.")
        except Exception as e:
            self.log_handler.error(f"Erreur lors de l'analyse : {str(e)}")
            QMessageBox.critical(None, "Erreur", f"Erreur lors de l'analyse : {str(e)}")
        finally:
            # Restaurer la sortie standard
            sys.stdout = sys.__stdout__

    def run_recreer_entites(self):
        """Recréation des entités manquantes"""
        # Créer et afficher la fenêtre de log
        self.log_window = LogWindow(self.iface.mainWindow())
        self.log_handler = LogHandler(self.log_window)
        
        # Rediriger la sortie standard vers le log handler
        sys.stdout = self.log_handler
        
        # Afficher la fenêtre de log
        self.log_window.show()
        
        try:
            self.log_handler.info("Début de la création des entités manquantes...")
            from .modules.recreer_entites_orphelines_v3 import recreer_entites_orphelines_v3
            recreer_entites_orphelines_v3()
            self.log_handler.success("Création des entités manquantes terminée avec succès.")
            QMessageBox.information(None, "Succès", "Création des entités manquantes terminée.")
        except Exception as e:
            self.log_handler.error(f"Erreur lors de la création : {str(e)}")
            QMessageBox.critical(None, "Erreur", f"Erreur lors de la création : {str(e)}")
        finally:
            # Restaurer la sortie standard
            sys.stdout = sys.__stdout__

    def run_identifier_orphelines(self):
        """Identification précise des photos orphelines"""
        # Créer et afficher la fenêtre de log
        self.log_window = LogWindow(self.iface.mainWindow())
        self.log_handler = LogHandler(self.log_window)
        
        # Rediriger la sortie standard vers le log handler
        sys.stdout = self.log_handler
        
        # Afficher la fenêtre de log
        self.log_window.show()
        
        try:
            self.log_handler.info("Début de l'identification des photos orphelines...")
            from .modules.identifier_orphelines import identifier_orphelines
            identifier_orphelines()
            self.log_handler.success("Identification des photos orphelines terminée avec succès.")
            QMessageBox.information(None, "Succès", "Identification des photos orphelines terminée.")
        except Exception as e:
            self.log_handler.error(f"Erreur lors de l'identification : {str(e)}")
            QMessageBox.critical(None, "Erreur", f"Erreur lors de l'identification : {str(e)}")
        finally:
            # Restaurer la sortie standard
            sys.stdout = sys.__stdout__
    
    def run_test_log(self):
        """Teste la fonctionnalité de journalisation"""
        try:
            # Créer une instance de test
            test_normalizer = PhotoNormalizerUnifie()
            
            # Exécuter le test
            success, message = test_normalizer.test_log_file()
            
            if success:
                QMessageBox.information(None, "Test de journalisation", 
                                      f"Test réussi !\n\n{message}")
            else:
                QMessageBox.warning(None, "Test de journalisation", 
                                  f"Test échoué :\n\n{message}")
                
        except Exception as e:
            QMessageBox.critical(None, "Erreur de test", 
                                f"Erreur lors du test de journalisation : {e}")
    
    def run_read_latest_log(self):
        """Lit et affiche le contenu du log le plus récent"""
        try:
            # Créer une instance pour accéder aux méthodes
            log_reader = PhotoNormalizerUnifie()
            
            # Lire le contenu du log le plus récent
            success, content, log_path = log_reader.get_latest_log_content()
            
            if success:
                # Créer une boîte de dialogue pour afficher le contenu
                from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout, QLabel
                
                dialog = QDialog()
                dialog.setWindowTitle(f"Contenu du log - {os.path.basename(log_path)}")
                dialog.resize(800, 600)
                
                layout = QVBoxLayout()
                
                # Ajouter une étiquette avec le chemin du fichier
                path_label = QLabel(f"Chemin du fichier : {log_path}")
                layout.addWidget(path_label)
                
                # Ajouter la zone de texte pour le contenu
                text_edit = QTextEdit()
                text_edit.setPlainText(content)
                text_edit.setReadOnly(True)
                layout.addWidget(text_edit)
                
                # Ajouter des boutons
                button_layout = QHBoxLayout()
                
                copy_button = QPushButton("Copier dans le presse-papiers")
                copy_button.clicked.connect(lambda: text_edit.selectAll() or text_edit.copy())
                button_layout.addWidget(copy_button)
                
                close_button = QPushButton("Fermer")
                close_button.clicked.connect(dialog.accept)
                button_layout.addWidget(close_button)
                
                layout.addLayout(button_layout)
                dialog.setLayout(layout)
                
                dialog.exec_()
            else:
                QMessageBox.warning(None, "Aucun log trouvé", 
                                  f"Aucun fichier de log disponible :\n\n{content}")
                
        except Exception as e:
            QMessageBox.critical(None, "Erreur de lecture", 
                                f"Erreur lors de la lecture du log : {e}")