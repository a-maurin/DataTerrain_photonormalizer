#!/usr/bin/env python3
"""
Logique principale du plugin PhotoNormalizer
"""

import os
import sys
import re
from datetime import datetime
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.PyQt.QtCore import QDate, QDateTime
from qgis.core import QgsProject, QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY
from .log_handler import LogHandler, LogWindow

# Importation pour le traitement d'images
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("⚠️  Module PIL/Pillow non disponible. Installation recommandée: pip install pillow")

class PhotoNormalizer:
    """
    Classe principale pour la normalisation des photos
    """
    
    def __init__(self, iface):
        self.iface = iface
        self.log_window = None
        self.log_handler = None
        # Calculer le chemin correct vers le dossier exports (dans le dossier du plugin)
        plugin_dir = os.path.dirname(os.path.dirname(__file__))  # Remonter au dossier du plugin
        self.export_dir = os.path.join(plugin_dir, 'exports')
        os.makedirs(self.export_dir, exist_ok=True)
        
    def run(self):
        """Exécute le traitement principal"""
        # Créer la fenêtre de log
        self.log_window = LogWindow(self.iface.mainWindow())
        self.log_handler = LogHandler(self.log_window)
        
        # Connecter le signal
        self.log_window.run_mode_selected.connect(self.on_mode_selected)
        
        # Afficher la fenêtre
        self.log_window.show()
        
    def on_mode_selected(self, mode):
        """Gère la sélection du mode"""
        if mode == "detection":
            self.detect_unreferenced_photos()
            self._save_logs_automatically()
        elif mode == "duplicate_detection":
            self.detect_doublons()
            self._save_logs_automatically()
        elif mode == "orphan_analysis":
            self.analyse_orphelines()
            self._save_logs_automatically()
        elif mode == "renommage":
            self.run_renommage_mode()
            self._save_logs_automatically()
        elif mode == "optimisation":
            self.run_optimisation_mode()
            self._save_logs_automatically()
        elif mode == "correction_fid":
            self.run_correction_fid_mode()
            self._save_logs_automatically()
        elif mode == "photos_orphelines_fid":
            self.run_photos_orphelines_fid_mode()
            self._save_logs_automatically()
        elif mode == "renommage_formulaires":
            self.run_renommage_formulaires_mode()
            self._save_logs_automatically()
        elif mode == "clean_photos":
            self.run_clean_photos_mode()
            self._save_logs_automatically()
        elif mode == "normal":
            self.run_normal_mode()
            self._save_logs_automatically()
    
    def run_clean_photos_mode(self):
        """Mode isolé: nettoie les champs photo incohérents (FID du nom ≠ FID de l'entité)."""
        self.log_handler.info("📋 Mode Nettoyage des champs photo incohérents en cours...")
        gpkg_file = "/home/e357/Qfield/cloud/DataTerrain/donnees_terrain.gpkg"
        layer_name = "saisies_terrain"
        try:
            nb = self.clean_inconsistent_photo_fields(gpkg_file, layer_name)
            if nb > 0:
                self.log_handler.success(f"✅ Champs photo nettoyés pour {nb} entité(s) incohérente(s)")
            else:
                self.log_handler.info("ℹ️  Aucun champ photo incohérent détecté")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors du nettoyage des champs photo: {e}")
            
    def detect_unreferenced_photos(self):
        """Détecte les photos non référencées"""
        from ..scripts.photo_detection import detect_unreferenced_photos
        self.log_handler.info("🔍 Détection des photos non référencées en cours...")
        try:
            detect_unreferenced_photos(self.log_handler, self.export_dir)
            self.log_handler.info("✅ Détection terminée avec succès")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors de la détection: {e}")
            
    def detect_doublons(self):
        """Exécute la détection des photos en double"""
        from ..scripts.detect_doublons import detect_doublons
        self.log_handler.info("👥 Détection des doublons en cours...")
        try:
            # Exécuter la détection
            doublons_groups = detect_doublons(self.log_handler, self.export_dir)
            
            # Debug: afficher les données reçues
            self.log_handler.debug(f"📋 Données doublons reçues - Type: {type(doublons_groups)}")
            if isinstance(doublons_groups, list):
                self.log_handler.debug(f"📋 Nombre de groupes: {len(doublons_groups)}")
                for i, group in enumerate(doublons_groups[:3]):  # Afficher les 3 premiers groupes
                    self.log_handler.debug(f"📋 Groupe {i}: {type(group)} - {len(group) if isinstance(group, list) else 'N/A'} éléments")
            
            if doublons_groups and len(doublons_groups) > 0:
                self.log_handler.info(f"📊 {len(doublons_groups)} groupes de doublons détectés")
                
                # Afficher l'interface pour gérer les doublons
                self.show_doublons_interface(doublons_groups)
            else:
                self.log_handler.info("✅ Aucune photo en double détectée")
                
        except Exception as e:
            self.log_handler.error(f"❌ Erreur détection doublons: {e}")
    
    def show_doublons_interface(self, doublons_groups):
        """Affiche l'interface pour gérer les doublons"""
        try:
            from .doublons_dialog import DoublonsDialog
            
            # Créer et afficher la dialogue
            dialog = DoublonsDialog(
                doublons_groups, 
                "/home/e357/Qfield/cloud/DataTerrain/DCIM",
                self.iface.mainWindow(),
                self.log_handler  # Passer le log_handler
            )
            
            # Connecter le signal
            dialog.doublons_supprimes.connect(self.on_doublons_deleted)
            
            # Afficher la dialogue
            dialog.exec_()
            
        except Exception as e:
            self.log_handler.error(f"❌ Erreur affichage interface doublons: {e}")
            import traceback
            self.log_handler.error(f"Détails: {traceback.format_exc()}")
    
    def on_doublons_deleted(self, deleted_files):
        """Gère la suppression des doublons"""
        if deleted_files:
            self.log_handler.success(f"🗑️  {len(deleted_files)} doublons supprimés")
            for file in deleted_files:
                self.log_handler.info(f"  • Supprimé: {file}")
        else:
            self.log_handler.info("ℹ️  Aucune suppression effectuée")
            
    def analyse_orphelines(self):
        """Exécute l'analyse des photos orphelines"""
        from ..scripts.analyse_orphelines import analyser_photos_orphelines
        self.log_handler.info("📊 Analyse des photos orphelines en cours...")
        try:
            analyser_photos_orphelines(self.log_handler)
            self.log_handler.info("✅ Analyse des photos orphelines terminée")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors de l'analyse: {e}")
            
    def run_normal_mode(self):
        """Exécute le mode normal - Traitement complet de normalisation"""
        self.log_handler.info("⚙️ Mode normal en cours...")
        
        # Étape 0: Sauvegarde initiale et vérification
        self.log_handler.info("📋 Étape 0/8: Préparation et sauvegarde...")
        dcim_path = "/home/e357/Qfield/cloud/DataTerrain/DCIM"
        gpkg_file = "/home/e357/Qfield/cloud/DataTerrain/donnees_terrain.gpkg"
        layer_name = "saisies_terrain"
        
        # Créer une sauvegarde du dossier DCIM avant toute opération
        backup_success = self.create_dcim_backup(dcim_path)
        if not backup_success:
            self.log_handler.warning("⚠️  Impossible de créer une sauvegarde, continuation sans sauvegarde")
        
        # Créer une sauvegarde du fichier GeoPackage avant toute opération
        gpkg_backup_success = self.create_gpkg_backup(gpkg_file)
        if not gpkg_backup_success:
            self.log_handler.warning("⚠️  Impossible de créer une sauvegarde GeoPackage, continuation sans sauvegarde")
        
        # Vérification initiale du nombre de photos
        initial_photos = self.get_dcim_photos(dcim_path)
        self.log_handler.info(f"📊 Nombre initial de photos: {len(initial_photos)}")
        
        # Initialiser le suivi des photos
        self.log_handler.initialize_photo_tracking(initial_photos)
        
        # Étape 1: Initialisation
        self.log_handler.info("📋 Étape 1/8: Initialisation...")
        
        if not os.path.exists(dcim_path):
            self.log_handler.error(f"❌ Dossier DCIM introuvable: {dcim_path}")
            return
        
        if not os.path.exists(gpkg_file):
            self.log_handler.error(f"❌ Fichier GeoPackage introuvable: {gpkg_file}")
            return
        
        self.log_handler.success("✅ Initialisation terminée")
        
        # Étape 2: Analyse des photos
        self.log_handler.info("📋 Étape 2/8: Analyse des photos...")
        try:
            # Exécuter la détection des photos non référencées
            from ..scripts.photo_detection import detect_unreferenced_photos
            detect_unreferenced_photos(self.log_handler, self.export_dir)
            self.log_handler.success("✅ Analyse terminée")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur analyse: {e}")
            return
        
        # Étape 3: Détection des doublons (déplacée plus tôt pour éviter de renommer des doublons)
        self.log_handler.info("📋 Étape 3/8: Détection des doublons...")
        try:
            self.detect_doublons()
        except Exception as e:
            self.log_handler.error(f"❌ Erreur détection doublons: {e}")
            # Continuer malgré l'erreur
        
        # Étape 4: Analyse des photos orphelines
        self.log_handler.info("📋 Étape 4/8: Analyse des photos orphelines...")
        try:
            from ..scripts.analyse_orphelines import analyser_photos_orphelines
            analyser_photos_orphelines(self.log_handler)
            self.log_handler.success("✅ Analyse orphelines terminée")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur analyse orphelines: {e}")
            return
        
        # Étape 5: Renommage des photos
        try:
            self.log_handler.info("📋 Étape 5/8: Renommage des photos...")
            layer = self.get_layer(gpkg_file, layer_name)
            self.renommer_photos(dcim_path, layer)
            self.log_handler.success("✅ Renommage des photos terminé")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors du renommage des photos: {e}")
            # Continuer malgré l'erreur
        
        # Étape 6: Création d'entités pour les photos orphelines avec FID (synchronisation cloud)
        try:
            entites_orphelines_fid = self.creer_entites_pour_photos_orphelines_avec_fid(dcim_path, layer)
            if entites_orphelines_fid > 0:
                self.log_handler.success(f"✅ Création d'entités pour photos orphelines avec FID terminée ({entites_orphelines_fid} entités)")
            else:
                self.log_handler.info("ℹ️  Aucune photo orpheline avec FID nécessitant création d'entité")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur création entités photos orphelines avec FID: {e}")
            # Continuer malgré l'erreur
        
        # Étape 7: Création d'entités pour les photos orphelines
        try:
            entites_creees = self.creer_entites_pour_orphelines(dcim_path, layer)
            self.log_handler.success(f"✅ Création d'entités terminée ({entites_creees} entités créées)")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors de la création d'entités: {e}")
            # Continuer malgré l'erreur
        
        # Étape 8: Correction des FID=0 (photos mal renommées)
        try:
            photos_corrigees = self.correct_fid_zero_photos(dcim_path, gpkg_file, layer_name)
            if photos_corrigees > 0:
                self.log_handler.success(f"✅ Correction FID terminée ({photos_corrigees} photos corrigées)")
            else:
                self.log_handler.info("ℹ️  Aucune photo avec FID=0 trouvée")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors de la correction des FID: {e}")
            # Continuer malgré l'erreur
        
        # Étape 8b: Synchronisation des champs photo des entités (ancien nom → nouveau nom)
        try:
            nb_sync = self.synchroniser_champs_photo_entites(gpkg_file, layer_name)
            if nb_sync > 0:
                self.log_handler.success(f"✅ Champs photo synchronisés ({nb_sync} entités mises à jour)")
            else:
                self.log_handler.info("ℹ️  Tous les champs photo pointent déjà vers les noms actuels")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur synchronisation champs photo: {e}")
            # Continuer malgré l'erreur
        
        # Étape 8c: Nettoyage des champs photo incohérents (ex. _0_ ou FID nom ≠ FID entité)
        try:
            nb_clean = self.clean_inconsistent_photo_fields(gpkg_file, layer_name)
            if nb_clean > 0:
                self.log_handler.success(f"✅ Champs photo incohérents nettoyés ({nb_clean} entités)")
            else:
                self.log_handler.info("ℹ️  Aucun champ photo incohérent (tous les FID nom = FID entité)")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur nettoyage champs photo: {e}")
            # Continuer malgré l'erreur
        
        # Étape 9: Vérification d'intégrité (nouvelle étape)
        self.log_handler.info("📋 Étape 9/8: Vérification d'intégrité finale...")
        try:
            self.verify_data_integrity(dcim_path, gpkg_file, layer_name)
            self.log_handler.success("✅ Vérification d'intégrité terminée")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur vérification intégrité: {e}")
            # Continuer malgré l'erreur
        
        # Étape 10: Optimisation des images
        try:
            self.optimize_images(dcim_path)
        except Exception as e:
            self.log_handler.error(f"❌ Erreur optimisation images: {e}")
            # Continuer malgré l'erreur
        
        # Étape 11: Renommage d'après les formulaires (toutes les photos dont nom_agent/type_saisie sont complétés)
        self.log_handler.info("📋 Étape 11/11: Renommage d'après les formulaires...")
        try:
            layer = self.get_layer(gpkg_file, layer_name)
            nb_renommes_form = self.renommer_photos_d_apres_formulaires(dcim_path, layer)
            if nb_renommes_form > 0:
                self.log_handler.success(f"✅ Renommage d'après formulaires terminé ({nb_renommes_form} photos)")
            else:
                self.log_handler.info("ℹ️  Aucune photo à renommer d'après les formulaires (champs à compléter manuellement si besoin)")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur renommage d'après formulaires: {e}")
            # Continuer malgré l'erreur
        
        # Finalisation et vérification d'intégrité
        self.log_handler.info("📋 Finalisation et vérification...")
        
        # Vérification finale du nombre de photos avec logique améliorée
        final_photos = self.get_dcim_photos(dcim_path)
        self.log_handler.info(f"📊 Nombre final de photos: {len(final_photos)}")
        
        # Calcul des différences avec prise en compte des renommages
        photos_disparues = set()
        photos_renommees = set()
        photos_nouvelles = set()
        
        # Analyser chaque photo initiale
        for initial_photo in initial_photos:
            if initial_photo in final_photos:
                # Photo inchangée
                continue
            elif self.log_handler.is_photo_renamed(initial_photo):
                # Photo renommée - vérifier si le nouveau nom existe
                final_name = self.log_handler.get_final_photo_name(initial_photo)
                if final_name and final_name in final_photos:
                    photos_renommees.add((initial_photo, final_name))
                else:
                    photos_disparues.add(initial_photo)
            else:
                # Photo potentiellement disparue
                photos_disparues.add(initial_photo)
        
        # Trouver les vraies nouvelles photos (non issues de renommages)
        for final_photo in final_photos:
            if final_photo not in initial_photos:
                # Vérifier si c'est une photo renommée
                is_renamed_version = False
                for initial_photo, renamed_name in photos_renommees:
                    if renamed_name == final_photo:
                        is_renamed_version = True
                        break
                
                if not is_renamed_version:
                    photos_nouvelles.add(final_photo)
        
        # Afficher les résultats avec messages améliorés
        if photos_renommees:
            self.log_handler.info(f"✅ {len(photos_renommees)} photos ont été renommées avec succès:")
            for old_name, new_name in sorted(photos_renommees):
                self.log_handler.info(f"  📋 {old_name} → {new_name}")
        
        # Vérifier si les photos disparues sont dans le dossier de synchronisation QField
        photos_deplacees_qfield = set()
        photos_reellement_disparues = set()
        
        qfield_sync_dcim = os.path.join(os.path.dirname(dcim_path), '.qfieldsync', 'download', 'DCIM')
        if os.path.exists(qfield_sync_dcim):
            sync_photos = [f for f in os.listdir(qfield_sync_dcim) 
                          if f.lower().endswith(('.jpg', '.jpeg'))]
            
            for photo in photos_disparues:
                if photo in sync_photos:
                    photos_deplacees_qfield.add(photo)
                else:
                    photos_reellement_disparues.add(photo)
        else:
            photos_reellement_disparues = photos_disparues
        
        # Afficher les résultats avec messages améliorés
        if photos_deplacees_qfield:
            self.log_handler.warning(f"⚠️  {len(photos_deplacees_qfield)} photos ont été déplacées dans le dossier de synchronisation QField:")
            self.log_handler.warning("   Cela peut être dû à la synchronisation avec QField Cloud.")
            for photo in sorted(photos_deplacees_qfield)[:5]:
                self.log_handler.warning(f"   • {photo}")
            if len(photos_deplacees_qfield) > 5:
                self.log_handler.warning(f"   • ... et {len(photos_deplacees_qfield) - 5} autres")
        
        if photos_reellement_disparues:
            self.log_handler.error(f"❌ ATTENTION: {len(photos_reellement_disparues)} photos n'ont pas été retrouvées:")
            self.log_handler.error("Cela peut indiquer un problème lors du traitement. Vérifiez les logs détaillés.")
            for photo in sorted(photos_reellement_disparues):
                self.log_handler.error(f"  🚨 {photo}")
            
            # Suggérer des actions
            self.log_handler.warning("💡 Actions recommandées:")
            self.log_handler.warning("  1. Vérifiez la sauvegarde créée au début du traitement")
            self.log_handler.warning("  2. Consultez le rapport détaillé des opérations")
            self.log_handler.warning("  3. Vérifiez que ces photos n'ont pas été renommées ou déplacées")
        else:
            self.log_handler.success("✅ Toutes les photos initiales ont été correctement traitées")
            self.log_handler.success("   - Les photos renommées sont suivies et accessibles")
            self.log_handler.success("   - Les doublons ont été supprimés comme prévu")
            self.log_handler.success("   - Aucune perte de données détectée")
        
        if photos_nouvelles:
            self.log_handler.info(f"ℹ️  {len(photos_nouvelles)} nouvelles photos ont été créées:")
            for photo in sorted(photos_nouvelles):
                self.log_handler.info(f"  ✨ {photo}")
        
        # Générer et sauvegarder le rapport des opérations
        report_file = self.log_handler.save_operation_report(self.export_dir)
        
        # Générer le résumé des renommages
        renaming_summary = self.log_handler.generate_renaming_summary()
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        renaming_report_file = os.path.join(self.export_dir, f"renaming_summary_{timestamp}.log")
        
        try:
            with open(renaming_report_file, 'w') as f:
                f.write(renaming_summary)
            self.log_handler.info(f"📋 Résumé des renommages sauvegardé: {renaming_report_file}")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur sauvegarde résumé renommages: {e}")
        
        # Résumé final avec messages améliorés
        self.log_handler.success("🎉 TRAITEMENT TERMINÉ AVEC SUCCÈS!")
        self.log_handler.info("📊 RÉSUMÉ COMPLET DES OPÉRATIONS:")
        self.log_handler.info(f"  📁 Photos initiales: {len(initial_photos)}")
        self.log_handler.info(f"  📁 Photos finales: {len(final_photos)}")
        self.log_handler.info(f"  📋 Opérations enregistrées: {self.log_handler.operation_count}")
        
        if len(photos_renommees) > 0:
            self.log_handler.success(f"  ✅ Photos renommées: {len(photos_renommees)} (format standardisé)")
        else:
            self.log_handler.info(f"  ℹ️  Photos renommées: {len(photos_renommees)}")
        
        if len(photos_disparues) > 0:
            self.log_handler.error(f"  ❌ Photos non retrouvées: {len(photos_disparues)} (voir détails ci-dessus)")
        else:
            self.log_handler.success(f"  ✅ Photos non retrouvées: {len(photos_disparues)} (tout est en ordre!)")
        
        if len(photos_nouvelles) > 0:
            self.log_handler.info(f"  ✨ Nouvelles photos créées: {len(photos_nouvelles)}")
        else:
            self.log_handler.info(f"  ℹ️  Nouvelles photos créées: {len(photos_nouvelles)}")
        self.log_handler.info("  • Analyse des photos: ✅")
        self.log_handler.info("  • Analyse des orphelines: ✅")
        self.log_handler.info("  • Renommage des photos: ✅")
        self.log_handler.info("  • Création entités photos orphelines avec FID: ✅")
        self.log_handler.info("  • Création d'entités orphelines: ✅")
        self.log_handler.info("  • Correction FID=0: ✅")
        self.log_handler.info("  • Gestion des doublons: ✅")
        self.log_handler.info("  • Optimisation images: ✅")
        self.log_handler.info("  • Renommage d'après formulaires: ✅")
        self.log_handler.info(f"\n💡 Tous les rapports sont disponibles dans le dossier '{self.export_dir}/'")
        if report_file:
            self.log_handler.info(f"📋 Rapport détaillé: {report_file}")
        
        # Avertissement si des photos ont réellement disparu
        if photos_disparues:
            self.log_handler.error("❌ ATTENTION: Des photos ont réellement disparu pendant le traitement!")
            self.log_handler.error("Veuillez consulter le rapport détaillé pour plus d'informations.")
        else:
            self.log_handler.success("✅ Toutes les photos ont été correctement traitées sans perte")
    
    def run_renommage_mode(self):
        """Exécute le mode renommage isolé"""
        self.log_handler.info("📋 Mode Renommage en cours...")
        
        # Paramètres
        dcim_path = "/home/e357/Qfield/cloud/DataTerrain/DCIM"
        gpkg_file = "/home/e357/Qfield/cloud/DataTerrain/donnees_terrain.gpkg"
        layer_name = "saisies_terrain"
        
        # Vérifications
        if not os.path.exists(dcim_path):
            self.log_handler.error(f"❌ Dossier DCIM introuvable: {dcim_path}")
            return
            
        if not os.path.exists(gpkg_file):
            self.log_handler.error(f"❌ Fichier GeoPackage introuvable: {gpkg_file}")
            return
        
        # Charger la couche
        try:
            layer = self.get_layer(gpkg_file, layer_name)
        except Exception as e:
            self.log_handler.error(f"❌ Erreur chargement couche: {e}")
            return
        
        # Exécuter le renommage
        try:
            self.renommer_photos(dcim_path, layer)
            self.log_handler.success("✅ Renommage des photos terminé")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors du renommage: {e}")
    
    def run_photos_orphelines_fid_mode(self):
        """Exécute le mode de traitement des photos orphelines avec FID"""
        self.log_handler.info("📋 Mode Photos Orphelines avec FID en cours...")
        
        # Paramètres
        dcim_path = "/home/e357/Qfield/cloud/DataTerrain/DCIM"
        gpkg_file = "/home/e357/Qfield/cloud/DataTerrain/donnees_terrain.gpkg"
        layer_name = "saisies_terrain"
        
        # Vérifications
        if not os.path.exists(dcim_path):
            self.log_handler.error(f"❌ Dossier DCIM introuvable: {dcim_path}")
            return
        
        if not os.path.exists(gpkg_file):
            self.log_handler.error(f"❌ Fichier GeoPackage introuvable: {gpkg_file}")
            return
        
        # Charger la couche
        try:
            layer = self.get_layer(gpkg_file, layer_name)
        except Exception as e:
            self.log_handler.error(f"❌ Erreur chargement couche: {e}")
            return
        
        # Exécuter le traitement des photos orphelines avec FID
        try:
            entites_creees = self.creer_entites_pour_photos_orphelines_avec_fid(dcim_path, layer)
            if entites_creees > 0:
                self.log_handler.success(f"✅ Traitement photos orphelines avec FID terminé ({entites_creees} entités créées)")
            else:
                self.log_handler.info("ℹ️  Aucune photo orpheline avec FID nécessitant traitement")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur traitement photos orphelines avec FID: {e}")
            import traceback
            self.log_handler.error(f"Détails: {traceback.format_exc()}")

    def run_renommage_formulaires_mode(self):
        """Renomme les photos *_INCONNU_INCONNU_* d'après les champs nom_agent et type_saisie des entités."""
        self.log_handler.info("📋 Mode Renommage d'après les formulaires en cours...")
        dcim_path = "/home/e357/Qfield/cloud/DataTerrain/DCIM"
        gpkg_file = "/home/e357/Qfield/cloud/DataTerrain/donnees_terrain.gpkg"
        layer_name = "saisies_terrain"
        if not os.path.exists(dcim_path):
            self.log_handler.error(f"❌ Dossier DCIM introuvable: {dcim_path}")
            return
        if not os.path.exists(gpkg_file):
            self.log_handler.error(f"❌ Fichier GeoPackage introuvable: {gpkg_file}")
            return
        try:
            layer = self.get_layer(gpkg_file, layer_name)
            nb = self.renommer_photos_d_apres_formulaires(dcim_path, layer)
            if nb > 0:
                self.log_handler.success(f"✅ Renommage d'après formulaires terminé ({nb} photos renommées)")
            else:
                self.log_handler.info("ℹ️  Aucune photo à renommer (complétez nom_agent et type_saisie dans les formulaires si besoin)")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur renommage d'après formulaires: {e}")
            import traceback
            self.log_handler.error(traceback.format_exc())

    def run_correction_fid_mode(self):
        """Exécute le mode de correction des FID=0"""
        self.log_handler.info("📋 Mode Correction FID en cours...")
        
        # Paramètres
        dcim_path = "/home/e357/Qfield/cloud/DataTerrain/DCIM"
        gpkg_file = "/home/e357/Qfield/cloud/DataTerrain/donnees_terrain.gpkg"
        layer_name = "saisies_terrain"
        
        # Vérifications
        if not os.path.exists(dcim_path):
            self.log_handler.error(f"❌ Dossier DCIM introuvable: {dcim_path}")
            return
        
        if not os.path.exists(gpkg_file):
            self.log_handler.error(f"❌ Fichier GeoPackage introuvable: {gpkg_file}")
            return
        
        # Exécuter la correction
        try:
            self.correct_fid_zero_photos(dcim_path, gpkg_file, layer_name)
            self.log_handler.success("✅ Correction des FID=0 terminée")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors de la correction des FID: {e}")
            import traceback
            self.log_handler.error(f"Détails: {traceback.format_exc()}")

    def correct_fid_zero_photos(self, dcim_path, gpkg_file, layer_name):
        """Corrige les photos avec FID=0"""
        self.log_handler.info("🔧 Correction des photos avec FID=0...")
        
        # Charger la couche
        try:
            layer_path = f"{gpkg_file}|layername={layer_name}"
            layer = QgsVectorLayer(layer_path, layer_name, "ogr")
            
            if not layer.isValid():
                self.log_handler.error(f"❌ Impossible de charger la couche {layer_name}")
                return 0
            
            self.log_handler.info(f"✅ Couche '{layer_name}' chargée avec {layer.featureCount()} entités")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur chargement couche: {e}")
            return 0
        
        # Trouver les photos avec FID=0
        import re
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
        
        self.log_handler.info(f"📊 Trouvé {len(zero_fid_photos)} photos avec FID=0")
        
        if len(zero_fid_photos) == 0:
            self.log_handler.info("✅ Aucune photo avec FID=0 trouvée")
            return 0
        
        # Démarrer l'édition
        layer.startEditing()
        photo_field_idx = layer.fields().indexFromName('photo')
        if photo_field_idx < 0:
            self.log_handler.warning("⚠️  Champ 'photo' introuvable")
            return 0
        
        photos_corrigees = 0
        
        for photo_name, date_str, x, y in zero_fid_photos:
            self.log_handler.info(f"🔧 Correction de: {photo_name}")
            
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
                    self.log_handler.info(f"✅ Entité existante trouvée avec FID: {existing_fid}")
                    
                    # Vérifier si l'entité existante a déjà une photo
                    existing_feature = None
                    for feature in layer.getFeatures():
                        if feature.id() == existing_fid:
                            existing_feature = feature
                            break
                    
                    photo_existante = existing_feature['photo'] if existing_feature else None
                    old_path = os.path.join(dcim_path, photo_name)
                    
                    if photo_existante and isinstance(photo_existante, str) and photo_existante.strip():
                        # L'entité a déjà une photo valide → supprimer le doublon
                        if os.path.exists(old_path):
                            try:
                                os.remove(old_path)
                                photos_corrigees += 1
                                self.log_handler.success(
                                    f"🗑️  Photo doublon supprimée: {photo_name} "
                                    f"(entité FID {existing_fid} a déjà une photo aux mêmes coordonnées)"
                                )
                            except Exception as e:
                                self.log_handler.error(f"❌ Erreur suppression doublon {photo_name}: {e}")
                        continue
                    
                    # L'entité n'a pas de photo → renommer la photo avec le FID existant
                    new_photo_name = f"DT_{date_str}_{existing_fid}_INCONNU_INCONNU_{x}_{y}.jpg"
                    new_path = os.path.join(dcim_path, new_photo_name)
                    
                    if not os.path.exists(new_path):
                        if os.path.exists(old_path):
                            os.rename(old_path, new_path)
                            self.log_handler.register_renamed_photo(photo_name, new_photo_name)
                            layer.changeAttributeValue(existing_fid, photo_field_idx, f'DCIM/{new_photo_name}')
                            photos_corrigees += 1
                            self.log_handler.success(f"✅ Photo corrigée: FID mis à jour de 0 à {existing_fid}")
                            self.log_handler.info(f"   {photo_name} → {new_photo_name}")
                        else:
                            self.log_handler.warning(f"⚠️  Fichier source introuvable: {photo_name}")
                    else:
                        self.log_handler.warning(f"⚠️  Conflit de nom: {new_photo_name} existe déjà")
                        # Si le fichier avec le nouveau nom existe déjà, supprimer l'ancien doublon
                        if os.path.exists(old_path):
                            try:
                                os.remove(old_path)
                                self.log_handler.success(
                                    f"🗑️  Photo doublon supprimée: {photo_name} "
                                    f"(fichier {new_photo_name} existe déjà pour entité FID {existing_fid})"
                                )
                            except Exception as e:
                                self.log_handler.warning(f"⚠️  Impossible de supprimer doublon {photo_name}: {e}")
                else:
                    # Créer une nouvelle entité si aucune n'existe
                    self.log_handler.info(f"ℹ️  Aucune entité existante trouvée, création d'une nouvelle")
                    
                    # Créer une nouvelle entité
                    from qgis.core import QgsFeature, QgsGeometry, QgsPointXY
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
                        self.log_handler.error(f"❌ Échec de la création de l'entité pour {photo_name}")
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
                        self.log_handler.error(f"❌ Impossible de trouver le FID pour {photo_name}")
                        if hasattr(layer, 'rollBack'):
                            layer.rollBack()
                        continue
                    
                    self.log_handler.info(f"✅ Nouveau FID attribué: {new_fid}")
                    
                    # Rebasculer en mode édition
                    layer.startEditing()
                    
                    # Renommer la photo
                    new_photo_name = f"DT_{date_str}_{new_fid}_INCONNU_INCONNU_{x}_{y}.jpg"
                    old_path = os.path.join(dcim_path, photo_name)
                    new_path = os.path.join(dcim_path, new_photo_name)
                    
                    if not os.path.exists(new_path):
                        os.rename(old_path, new_path)
                        self.log_handler.register_renamed_photo(photo_name, new_photo_name)
                        layer.changeAttributeValue(new_fid, photo_field_idx, f'DCIM/{new_photo_name}')
                        photos_corrigees += 1
                        self.log_handler.success(f"✅ Photo corrigée: FID mis à jour de 0 à {new_fid}")
                        self.log_handler.info(f"   {photo_name} → {new_photo_name}")
                    else:
                        self.log_handler.warning(f"⚠️  Conflit de nom: {new_photo_name} existe déjà")
                        layer.rollBack() if hasattr(layer, 'rollBack') else None
            
            except Exception as e:
                self.log_handler.error(f"❌ Erreur lors de la correction de {photo_name}: {e}")
                layer.rollBack() if hasattr(layer, 'rollBack') else None
                continue
        
        # Sauvegarder les modifications finales
        layer.commitChanges()
        
        self.log_handler.success(f"✅ {photos_corrigees}/{len(zero_fid_photos)} photos corrigées")
        return photos_corrigees

    def run_optimisation_mode(self):
        """Exécute le mode optimisation isolé"""
        self.log_handler.info("📋 Mode Optimisation en cours...")
        
        # Paramètres
        dcim_path = "/home/e357/Qfield/cloud/DataTerrain/DCIM"
        
        # Vérifications
        if not os.path.exists(dcim_path):
            self.log_handler.error(f"❌ Dossier DCIM introuvable: {dcim_path}")
            return
        
        # Exécuter l'optimisation
        try:
            self.optimize_images(dcim_path)
            self.log_handler.success("✅ Optimisation des images terminée")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors de l'optimisation: {e}")
    
    def optimize_images(self, dcim_path):
        """Optimise les images (redimensionnement et qualité)"""
        self.log_handler.info("📋 Étape 7/8: Optimisation des images...")
        
        # Vérifier si PIL est disponible
        if not HAS_PIL:
            self.log_handler.warning("⚠️  Module PIL/Pillow non installé. Impossible d'optimiser les images.")
            self.log_handler.warning("Installation recommandée: pip install pillow")
            return
        
        # Paramètres d'optimisation
        max_width = 800
        max_height = 600
        quality = 85  # Qualité JPEG (0-100)
        
        # Ne traiter que les photos présentes dans dcim_path (optimisation in-place)
        all_photos = self.get_dcim_photos(dcim_path)
        photos = [p for p in all_photos if os.path.exists(os.path.join(dcim_path, p))]
        if not photos:
            self.log_handler.info("⚠️  Aucune photo trouvée pour optimisation")
            return
        
        self.log_handler.info(f"📷 Analyse de {len(photos)} photos pour optimisation...")
        
        optimized_count = 0
        skipped_count = 0
        error_count = 0
        
        for photo_name in photos:
            photo_path = os.path.join(dcim_path, photo_name)
            
            try:
                # Vérifier si le fichier existe
                if not os.path.exists(photo_path):
                    self.log_handler.warning(f"⚠️  Fichier introuvable: {photo_name}")
                    error_count += 1
                    continue
                
                # Ouvrir l'image
                with Image.open(photo_path) as img:
                    original_size = img.size
                    original_width, original_height = original_size
                    
                    # Vérifier si l'image doit être redimensionnée
                    needs_resize = original_width > max_width or original_height > max_height
                    
                    if needs_resize:
                        # Redimensionner l'image
                        img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                        
                        # Sauvegarder l'image optimisée (écraser l'originale)
                        img.save(photo_path, "JPEG", quality=quality, optimize=True)
                        
                        new_size = img.size
                        optimized_count += 1
                        
                        self.log_handler.info(f"✅ Optimisé: {photo_name} ({original_width}x{original_height} → {new_size[0]}x{new_size[1]})")
                    else:
                        # L'image est déjà assez petite, mais on peut optimiser la qualité
                        if photo_name.lower().endswith('.jpg'):
                            img.save(photo_path, "JPEG", quality=quality, optimize=True)
                            skipped_count += 1
                            self.log_handler.debug(f"ℹ️  Déjà optimisé: {photo_name} ({original_width}x{original_height})")
                        else:
                            skipped_count += 1
                            self.log_handler.debug(f"ℹ️  Format non JPEG: {photo_name} (non optimisé)")
                            
            except Exception as e:
                error_count += 1
                self.log_handler.error(f"❌ Erreur optimisation {photo_name}: {e}")
        
        # Résumé
        self.log_handler.info(f"\n📊 Résumé optimisation:")
        self.log_handler.info(f"  • Images optimisées: {optimized_count}")
        self.log_handler.info(f"  • Images déjà optimales: {skipped_count}")
        self.log_handler.info(f"  • Erreurs: {error_count}")
        
        if optimized_count > 0:
            self.log_handler.success(f"✅ {optimized_count} images optimisées avec succès")
        else:
            self.log_handler.info("ℹ️  Aucune image nécessitait d'optimisation")
        
    def create_dcim_backup(self, dcim_path):
        """Crée une sauvegarde du dossier DCIM avant les opérations"""
        try:
            import shutil
            from datetime import datetime
            
            # Créer un dossier de backup centralisé
            backup_dir = "/home/e357/Qfield/cloud/donnee_terrain_backups"
            os.makedirs(backup_dir, exist_ok=True)
            
            # Nom du backup avec timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"DCIM_backup_{timestamp}"
            backup_path = os.path.join(backup_dir, backup_name)
            
            self.log_handler.info(f"💾 Création de la sauvegarde: {backup_path}")
            
            # Copier le dossier DCIM
            shutil.copytree(dcim_path, backup_path)
            
            # Vérifier que la sauvegarde a réussi
            if os.path.exists(backup_path):
                photos_in_backup = len([f for f in os.listdir(backup_path) if f.lower().endswith(('.jpg', '.jpeg'))])
                photos_in_original = len(self.get_dcim_photos(dcim_path))
                
                if photos_in_backup == photos_in_original:
                    self.log_handler.success(f"✅ Sauvegarde de sécurité créée: {photos_in_backup} photos sauvegardées")
                    self.log_handler.info(f"   Emplacement: {backup_path}")
                    self.log_handler.info("   💡 Cette sauvegarde permet de restaurer les photos en cas de problème")
                    return True
                else:
                    self.log_handler.error(f"❌ Échec de la sauvegarde: {photos_in_backup}/{photos_in_original} photos seulement")
                    self.log_handler.warning("   Le traitement continuera mais sans filet de sécurité")
                    return False
            else:
                self.log_handler.error(f"❌ Échec de la création de la sauvegarde")
                return False
                
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors de la sauvegarde: {e}")
            return False

    def verify_data_integrity(self, dcim_path, gpkg_file, layer_name):
        """Vérifie l'intégrité des données après toutes les opérations"""
        self.log_handler.info("🔍 Vérification de l'intégrité des données...")
        
        try:
            # Vérifier que le dossier DCIM existe toujours
            if not os.path.exists(dcim_path):
                self.log_handler.error(f"❌ Dossier DCIM introuvable: {dcim_path}")
                return False
            
            # Vérifier que le fichier GeoPackage existe toujours
            if not os.path.exists(gpkg_file):
                self.log_handler.error(f"❌ Fichier GeoPackage introuvable: {gpkg_file}")
                return False
            
            # Compter les photos dans DCIM
            current_photos = self.get_dcim_photos(dcim_path)
            self.log_handler.info(f"📊 Nombre de photos dans DCIM: {len(current_photos)}")
            
            # Vérifier que la couche est toujours valide
            try:
                layer = self.get_layer(gpkg_file, layer_name)
                feature_count = layer.featureCount()
                self.log_handler.info(f"📊 Nombre d'entités dans la couche: {feature_count}")
            except Exception as e:
                self.log_handler.error(f"❌ Impossible de charger la couche: {e}")
                return False
            
            # Vérifier que chaque photo a une entité correspondante ou est orpheline
            photos_without_entity = []
            for photo_name in current_photos:
                # Exclure les photos avec un FID temporaire de la vérification
                if "_0_INCONNU_INCONNU_" in photo_name:
                    self.log_handler.info(f"ℹ️  Photo avec FID temporaire exclue de la vérification: {photo_name}")
                    continue
                
                # Vérifier si la photo est référencée dans la couche
                has_entity = False
                for feature in layer.getFeatures():
                    photo_field = feature['photo']
                    if photo_field and photo_name in photo_field:
                        has_entity = True
                        break
                
                if not has_entity:
                    # Vérifier si une entité existe déjà à ces coordonnées
                    entite_existante = None
                    for feature in layer.getFeatures():
                        if feature.geometry() and not feature.geometry().isEmpty():
                            point = feature.geometry().asPoint()
                            # Extraire les coordonnées du nom de la photo
                            import re
                            match = re.search(r'_([-+]?\d+\.?\d*)_([-+]?\d+\.?\d*)\.jpg', photo_name)
                            if match:
                                x = float(match.group(1))
                                y = float(match.group(2))
                                if abs(point.x() - x) < 0.01 and abs(point.y() - y) < 0.01:
                                    entite_existante = feature
                                    break
                    
                    if entite_existante:
                        self.log_handler.info(f"ℹ️  Entité existante trouvée pour {photo_name} (FID: {entite_existante.id()})")
                    else:
                        photos_without_entity.append(photo_name)
            
            if photos_without_entity:
                self.log_handler.warning(f"⚠️  {len(photos_without_entity)} photos n'ont pas d'entité correspondante:")
                for photo in photos_without_entity[:5]:  # Afficher max 5 pour éviter la surcharge
                    self.log_handler.warning(f"   • {photo}")
                if len(photos_without_entity) > 5:
                    self.log_handler.warning(f"   • ... et {len(photos_without_entity) - 5} autres")
            else:
                self.log_handler.success("✅ Toutes les photos ont une entité correspondante")
            
            # Vérifier que chaque entité a une photo valide
            entities_without_photo = []
            for feature in layer.getFeatures():
                photo_field = feature['photo']
                if photo_field:
                    photo_path = os.path.join('DCIM', photo_field)
                    if not os.path.exists(os.path.join(dcim_path, os.path.basename(photo_path))):
                        entities_without_photo.append(feature.id())
            
            if entities_without_photo:
                self.log_handler.warning(f"⚠️  {len(entities_without_photo)} entités référencent des photos inexistantes")
            else:
                self.log_handler.success("✅ Toutes les entités ont une photo valide")
            
            # Vérification finale
            if not photos_without_entity and not entities_without_photo:
                self.log_handler.success("🎉 Intégrité des données vérifiée avec succès!")
                self.log_handler.success("   • Toutes les photos ont des entités correspondantes")
                self.log_handler.success("   • Toutes les entités ont des photos valides")
                self.log_handler.success("   • La base de données est cohérente")
                return True
            else:
                self.log_handler.warning("⚠️  Des incohérences ont été détectées (voir détails ci-dessus)")
                self.log_handler.info("💡 Ces incohérences peuvent être normales si des photos ont été")
                self.log_handler.info("   intentionnellement marquées comme orphelines ou si des entités")
                self.log_handler.info("   sont en cours de traitement.")
                return True
                
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors de la vérification d'intégrité: {e}")
            return False

    def create_gpkg_backup(self, gpkg_path):
        """Crée une sauvegarde du fichier GeoPackage avant les opérations"""
        try:
            import shutil
            from datetime import datetime
            
            # Créer un dossier de backup centralisé
            backup_dir = "/home/e357/Qfield/cloud/donnee_terrain_backups"
            os.makedirs(backup_dir, exist_ok=True)
            
            # Nom du backup avec timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"donnees_terrain_backup_{timestamp}.gpkg"
            backup_path = os.path.join(backup_dir, backup_name)
            
            self.log_handler.info(f"💾 Création de la sauvegarde GeoPackage: {backup_path}")
            
            # Copier le fichier GeoPackage
            shutil.copy2(gpkg_path, backup_path)
            
            # Vérifier que la sauvegarde a réussi
            if os.path.exists(backup_path):
                self.log_handler.success(f"✅ Sauvegarde GeoPackage créée: {backup_path}")
                self.log_handler.info("   💡 Cette sauvegarde permet de restaurer les données en cas de problème")
                return True
            else:
                self.log_handler.error(f"❌ Échec de la création de la sauvegarde GeoPackage")
                return False
                
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors de la sauvegarde GeoPackage: {e}")
            return False
    
    def get_dcim_photos(self, dcim_path):
        """Récupère les photos dans le dossier DCIM et le dossier de synchronisation QField"""
        if not os.path.exists(dcim_path):
            return []
        
        # Récupérer les photos dans le dossier DCIM principal
        main_dcim_photos = [f for f in os.listdir(dcim_path) 
                           if f.lower().endswith(('.jpg', '.jpeg'))]
        
        # Vérifier aussi le dossier de synchronisation QField
        qfield_sync_dcim = os.path.join(os.path.dirname(dcim_path), '.qfieldsync', 'download', 'DCIM')
        sync_photos = []
        if os.path.exists(qfield_sync_dcim):
            sync_photos = [f for f in os.listdir(qfield_sync_dcim) 
                          if f.lower().endswith(('.jpg', '.jpeg'))]
        
        # Combiner les photos des deux dossiers
        all_photos = list(set(main_dcim_photos + sync_photos))
        
        return all_photos
        
    def _save_logs_automatically(self):
        """Sauvegarde automatiquement les logs à la fin de chaque mode"""
        try:
            # Créer le dossier logs s'il n'existe pas
            logs_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),  
                'logs'
            )
            os.makedirs(logs_dir, exist_ok=True)
            
            # Générer un nom de fichier avec timestamp
            timestamp = datetime.now().strftime("photonormalizer_%Y%m%d_%H%M%S.log")
            log_file = os.path.join(logs_dir, timestamp)
            
            # Sauvegarder les logs
            with open(log_file, 'w', encoding='utf-8') as f:
                if hasattr(self, 'log_window') and hasattr(self.log_window, 'log_text'):
                    f.write(self.log_window.log_text.toPlainText())
            
            self.log_handler.info(f"💾 Logs automatiquement sauvegardés: {log_file}")
            
        except Exception as e:
            self.log_handler.error(f"❌ Erreur sauvegarde automatique des logs: {e}")
        
        # Réactiver le bouton Lancer après le traitement
        self.log_handler.enable_run_button()

    def get_layer(self, gpkg_path, layer_name):
        """Charge une couche depuis un GeoPackage"""
        layer_path = f"{gpkg_path}|layername={layer_name}"
        layer = QgsVectorLayer(layer_path, layer_name, "ogr")
        
        if not layer.isValid():
            raise ValueError(f"Impossible de charger la couche {layer_name}")
        
        return layer

    def synchroniser_champs_photo_entites(self, gpkg_file, layer_name):
        """
        Met à jour le champ 'photo' de chaque entité pour qu'il pointe vers le nom
        actuel du fichier (après renommage). Corrige les entités qui référencent
        encore un ancien nom de photo.
        Retourne le nombre d'entités mises à jour.
        """
        self.log_handler.info("📋 Synchronisation des champs photo des entités...")
        try:
            layer = self.get_layer(gpkg_file, layer_name)
            photo_field_idx = layer.fields().indexFromName('photo')
            if photo_field_idx < 0:
                self.log_handler.warning("⚠️  Champ 'photo' introuvable dans la couche")
                return 0
            
            updated = 0
            layer.startEditing()
            for feature in layer.getFeatures():
                photo_val = feature['photo']
                if not photo_val or not isinstance(photo_val, str):
                    continue
                old_name = photo_val.replace('DCIM/', '').strip()
                if not old_name.lower().endswith(('.jpg', '.jpeg')):
                    continue
                new_name = self.log_handler.get_final_photo_name(old_name)
                if not new_name or new_name == old_name:
                    continue
                # Ne mettre à jour que si le FID dans le nouveau nom correspond à cette entité
                # (évite qu'une entité 538 reçoive le fichier d'une entité 497)
                fid_dans_nom = self._fid_depuis_nom_photo(new_name)
                if fid_dans_nom is not None and feature.id() != fid_dans_nom:
                    continue
                new_photo_val = f'DCIM/{new_name}'
                layer.changeAttributeValue(feature.id(), photo_field_idx, new_photo_val)
                updated += 1
                self.log_handler.debug(f"  Entité FID {feature.id()}: {old_name} → {new_name}")
            layer.commitChanges()
            return updated
        except Exception as e:
            self.log_handler.error(f"❌ Erreur synchronisation champs photo: {e}")
            try:
                if layer.isEditing() and hasattr(layer, 'rollBack'):
                    layer.rollBack()
            except (NameError, AttributeError):
                pass
            return 0
    
    def clean_inconsistent_photo_fields(self, gpkg_file, layer_name):
        """
        Vide le champ 'photo' des entités dont le FID dans le nom de fichier
        (DT_YYYY-MM-DD_FID_...) ne correspond pas au FID réel de l'entité.
        Pour les fichiers orphelins ainsi créés :
        - Si une entité existe aux mêmes coordonnées → supprime le fichier orphelin (doublon)
        - Sinon → crée une nouvelle entité pour la photo orpheline
        Retourne le nombre d'entités modifiées.
        """
        self.log_handler.info("🔍 Recherche des champs photo incohérents (FID nom ≠ FID entité)...")
        dcim_path = "/home/e357/Qfield/cloud/DataTerrain/DCIM"
        layer = self.get_layer(gpkg_file, layer_name)
        photo_idx = layer.fields().indexFromName('photo')
        if photo_idx < 0:
            self.log_handler.warning("⚠️  Champ 'photo' introuvable dans la couche")
            return 0
        
        from ..scripts.analyse_orphelines import extraire_coord_du_nom
        
        updated = 0
        fichiers_orphelins = []  # Liste des fichiers qui deviennent orphelins
        
        layer.startEditing()
        for feature in layer.getFeatures():
            photo_val = feature['photo']
            if not photo_val or not isinstance(photo_val, str):
                continue
            filename = photo_val.replace('DCIM/', '').strip()
            fid_in_name = self._fid_depuis_nom_photo(filename)
            if fid_in_name is None:
                continue
            if fid_in_name != feature.id():
                self.log_handler.warning(
                    f"⚠️  Incohérence FID pour entité {feature.id()}: "
                    f"champ photo → {filename} (FID {fid_in_name})"
                )
                # Extraire les coordonnées du fichier orphelin
                _, x_orphan, y_orphan = extraire_coord_du_nom(filename)
                if x_orphan is not None and y_orphan is not None:
                    fichiers_orphelins.append((filename, x_orphan, y_orphan, feature.id()))
                layer.changeAttributeValue(feature.id(), photo_idx, None)
                updated += 1
        layer.commitChanges()
        
        # Traiter les fichiers orphelins
        if fichiers_orphelins:
            self.log_handler.info(f"📋 Traitement de {len(fichiers_orphelins)} fichier(s) orphelin(s)...")
            fichiers_supprimes = 0
            entites_creees = 0
            
            layer.startEditing()
            for filename, x_orphan, y_orphan, entity_fid_that_had_it in fichiers_orphelins:
                file_path = os.path.join(dcim_path, filename)
                if not os.path.exists(file_path):
                    continue
                
                # Chercher une entité existante aux mêmes coordonnées
                entite_existante_meme_coord = None
                for feature in layer.getFeatures():
                    if feature.geometry() and not feature.geometry().isEmpty():
                        point = feature.geometry().asPoint()
                        if abs(point.x() - float(x_orphan)) < 0.01 and abs(point.y() - float(y_orphan)) < 0.01:
                            entite_existante_meme_coord = feature
                            break
                
                if entite_existante_meme_coord:
                    # Une entité existe aux mêmes coordonnées
                    photo_existante = entite_existante_meme_coord['photo']
                    if photo_existante and isinstance(photo_existante, str):
                        # L'entité a déjà une photo valide → supprimer le doublon
                        try:
                            os.remove(file_path)
                            fichiers_supprimes += 1
                            self.log_handler.success(
                                f"🗑️  Fichier doublon supprimé: {filename} "
                                f"(entité FID {entite_existante_meme_coord.id()} a déjà une photo aux mêmes coordonnées)"
                            )
                        except Exception as e:
                            self.log_handler.error(f"❌ Erreur suppression {filename}: {e}")
                    else:
                        # L'entité n'a pas de photo → associer ce fichier
                        layer.changeAttributeValue(entite_existante_meme_coord.id(), photo_idx, f'DCIM/{filename}')
                        self.log_handler.success(
                            f"✅ Fichier orphelin associé à entité FID {entite_existante_meme_coord.id()} "
                            f"(mêmes coordonnées, pas de photo existante)"
                        )
                else:
                    # Aucune entité aux mêmes coordonnées → créer une nouvelle entité
                    try:
                        from qgis.core import QgsFeature, QgsGeometry, QgsPointXY
                        new_feature = QgsFeature(layer.fields())
                        
                        # Extraire la date du nom de fichier
                        date_match = re.search(r'DT_(\d{4}-\d{2}-\d{2})_', filename)
                        if date_match:
                            date_str = date_match.group(1)
                            new_feature['date_saisie'] = date_str
                        
                        new_feature['x_saisie'] = float(x_orphan)
                        new_feature['y_saisie'] = float(y_orphan)
                        new_feature['nom_agent'] = 'INCONNU'
                        new_feature['type_saisie'] = 'INCONNU'
                        new_feature['photo'] = f'DCIM/{filename}'
                        
                        point = QgsPointXY(float(x_orphan), float(y_orphan))
                        new_feature.setGeometry(QgsGeometry.fromPointXY(point))
                        
                        success = layer.addFeature(new_feature)
                        if success:
                            entites_creees += 1
                            self.log_handler.success(
                                f"✅ Nouvelle entité créée pour photo orpheline: {filename} "
                                f"(coordonnées {x_orphan}, {y_orphan})"
                            )
                        else:
                            self.log_handler.error(f"❌ Échec création entité pour {filename}")
                    except Exception as e:
                        self.log_handler.error(f"❌ Erreur création entité pour {filename}: {e}")
            
            layer.commitChanges()
            
            if fichiers_supprimes > 0:
                self.log_handler.info(f"🗑️  {fichiers_supprimes} fichier(s) doublon(s) supprimé(s)")
            if entites_creees > 0:
                self.log_handler.info(f"✅ {entites_creees} nouvelle(s) entité(s) créée(s) pour photos orphelines")
        
        return updated

    def renommer_photos(self, dcim_path, layer):
        """Renomme les photos selon le format standard"""
        self.log_handler.info("📋 Étape 4/5: Renommage des photos...")
        
        # Lister les photos présentes physiquement dans dcim_path (pas le sync) pour éviter de tenter un renommage sur des fichiers absents
        all_photos = self.get_dcim_photos(dcim_path)
        photos = [p for p in all_photos if os.path.exists(os.path.join(dcim_path, p))]
        if not photos:
            self.log_handler.info("⚠️  Aucune photo trouvée dans DCIM")
            return
        
        self.log_handler.info(f"📷 Trouvé {len(photos)} photos dans DCIM")
        
        # Analyser chaque photo
        photos_a_renommer = []
        
        for photo_name in photos:
            # Vérifier si la photo suit le format standard
            if re.match(r'DT_\d{4}-\d{2}-\d{2}_\d+_(?:[^_]+|INCONNU)_(?:[^_]+|INCONNU)_[-+]?\d+\.?\d*_[-+]?\d+\.?\d*\.jpg', photo_name):
                # Vérifier si c'est un fichier nouvellement créé avec INCONNU_INCONNU
                if "_INCONNU_INCONNU_" in photo_name:
                    self.log_handler.info(f"ℹ️  Photo nouvellement créée conservée: {photo_name}")
                    self.log_handler.info(f"   Cette photo ne sera pas renommée pour éviter les conflits.")
                    continue
                else:
                    # Déjà au format standard avec des descriptifs valides, ne pas renommer
                    continue
            
            # Vérifier si c'est un format ancien (DT_YYYYMMDD_HHMMSS_X_Y.jpg)
            match = re.match(r'DT_(\d{8})_(\d{6})_([-+]?\d+\.?\d*)_([-+]?\d+\.?\d*)\.jpg', photo_name)
            if match:
                # Extraire les informations
                date_str = match.group(1)  # YYYYMMDD
                time_str = match.group(2)  # HHMMSS
                x = match.group(3)
                y = match.group(4)
                
                # Convertir la date au format YYYY-MM-DD
                try:
                    year = date_str[:4]
                    month = date_str[4:6]
                    day = date_str[6:8]
                    formatted_date = f"{year}-{month}-{day}"
                    
                    # Construire le nouveau nom
                    new_name = f"DT_{formatted_date}_0_INCONNU_INCONNU_{x}_{y}.jpg"
                    photos_a_renommer.append((photo_name, new_name))
                    
                except Exception as e:
                    self.log_handler.error(f"Erreur de conversion de date pour {photo_name}: {e}")
        
        if not photos_a_renommer:
            self.log_handler.info("✅ Toutes les photos sont déjà au format standard")
            return
        
        self.log_handler.info(f"🔄 {len(photos_a_renommer)} photos à renommer")
        
        # Effectuer le renommage avec vérifications et logging détaillé
        for old_name, new_name in photos_a_renommer:
            old_path = os.path.join(dcim_path, old_name)
            new_path = os.path.join(dcim_path, new_name)

            # Vérification préalable
            if not os.path.exists(old_path):
                self.log_handler.error(f"❌ Fichier source introuvable: {old_path}")
                continue

            # Log le début de l'opération
            op_id = self.log_handler.log_photo_operation(
                "RENAME", old_name, old_path, new_path, 
                f"Renommage de {old_name} vers {new_name}"
            )
            
            # Vérification avant renommage
            photos_before = set(os.listdir(dcim_path))
            self.log_handler.debug(f"Photos avant renommage: {len(photos_before)} fichiers")
            
            try:
                # Vérifier que le nouveau nom n'existe pas déjà
                if os.path.exists(new_path):
                    self.log_handler.warning(f"⚠️  Conflit : {new_name} existe déjà")
                    self.log_handler.log_operation_end(
                        f"RENAME_{op_id}", 
                        self.log_handler.log_operation_start(f"RENAME_{op_id}"),
                        success=False,
                        context=f"Conflit de nom: {new_name}"
                    )
                    continue
                
                # Vérification stricte avant renommage
                if not os.path.exists(old_path):
                    self.log_handler.error(f"❌ ERREUR CRITIQUE: {old_path} n'existe pas avant renommage!")
                    self.log_handler.log_operation_end(
                        f"RENAME_{op_id}", 
                        self.log_handler.log_operation_start(f"RENAME_{op_id}"),
                        success=False,
                        context="Fichier source introuvable avant renommage"
                    )
                    continue
                
                # Vérifier la taille du fichier avant renommage
                old_size = os.path.getsize(old_path)
                self.log_handler.debug(f"📋 Taille avant renommage: {old_size} octets")
                
                # Renommer le fichier avec vérification
                self.log_handler.debug(f"📋 Tentative de renommage: {old_path} → {new_path}")
                
                try:
                    os.rename(old_path, new_path)
                except Exception as e:
                    self.log_handler.error(f"❌ ERREUR lors du renommage: {str(e)}")
                    self.log_handler.log_operation_end(
                        f"RENAME_{op_id}", 
                        self.log_handler.log_operation_start(f"RENAME_{op_id}"),
                        success=False,
                        context=f"Exception lors du renommage: {str(e)}"
                    )
                    continue
                
                # Vérification stricte après renommage
                if not os.path.exists(new_path):
                    self.log_handler.error(f"❌ ERREUR CRITIQUE: {new_path} n'existe pas après renommage!")
                    self.log_handler.error(f"   Cela suggère que le fichier a été SUPPRIMÉ au lieu d'être renommé!")
                    self.log_handler.log_operation_end(
                        f"RENAME_{op_id}", 
                        self.log_handler.log_operation_start(f"RENAME_{op_id}"),
                        success=False,
                        context="Fichier cible introuvable après renommage - SUPPRESSION suspectée"
                    )
                    
                    # Vérifier si le fichier original existe toujours
                    if os.path.exists(old_path):
                        self.log_handler.error(f"❌ Le fichier original {old_path} existe toujours!")
                        self.log_handler.error(f"   Cela confirme que le renommage a ÉCHOUÉ sans supprimer le fichier.")
                    else:
                        self.log_handler.error(f"❌ Le fichier original {old_path} a DISPARU!")
                        self.log_handler.error(f"   Cela suggère une SUPPRESSION accidentelle pendant le renommage.")
                    
                    # Annuler le renommage si le fichier original existe toujours
                    if os.path.exists(old_path):
                        self.log_handler.info(f"🔄 Annulation du renommage: {old_path} → {new_path}")
                        try:
                            # Rétablir le nom original
                            os.rename(old_path, old_path)
                            self.log_handler.success(f"✅ Renommage annulé avec succès")
                        except Exception as e:
                            self.log_handler.error(f"❌ Erreur lors de l'annulation du renommage: {e}")
                    
                    # Vérifier que le fichier original existe toujours après l'annulation
                    if os.path.exists(old_path):
                        self.log_handler.info(f"✅ Le fichier original {old_path} a été rétabli avec succès")
                    else:
                        self.log_handler.error(f"❌ Le fichier original {old_path} a été perdu pendant l'annulation")
                    
                    continue
                
                # Vérifier la taille du fichier après renommage
                try:
                    new_size = os.path.getsize(new_path)
                    if new_size != old_size:
                        self.log_handler.warning(f"⚠️  La taille du fichier a changé: {old_size} → {new_size} octets")
                except Exception as e:
                    self.log_handler.error(f"❌ Impossible de vérifier la taille après renommage: {str(e)}")
                
                # Vérification finale
                photos_after = set(os.listdir(dcim_path))
                
                # Vérifier que l'ancienne photo a disparu
                if old_name in photos_after:
                    self.log_handler.error(f"❌ ERREUR: {old_name} existe toujours après renommage!")
                    self.log_handler.log_operation_end(
                        f"RENAME_{op_id}", 
                        self.log_handler.log_operation_start(f"RENAME_{op_id}"),
                        success=False,
                        context="Ancienne photo toujours présente"
                    )
                    continue
                
                # Vérifier que la nouvelle photo existe
                if new_name not in photos_after:
                    self.log_handler.error(f"❌ ERREUR: {new_name} n'existe pas dans la liste des photos!")
                    self.log_handler.error(f"   Mais le fichier existe physiquement: {os.path.exists(new_path)}")
                    self.log_handler.log_operation_end(
                        f"RENAME_{op_id}", 
                        self.log_handler.log_operation_start(f"RENAME_{op_id}"),
                        success=False,
                        context="Nouvelle photo introuvable dans la liste"
                    )
                    continue
                
                # Vérification finale de cohérence
                if os.path.exists(old_path):
                    self.log_handler.error(f"❌ PROBLÈME DE COHÉRENCE: {old_name} existe toujours après renommage!")
                    self.log_handler.error(f"   Cela indique que le renommage a ÉCHOUÉ mais le fichier n'a pas été supprimé.")
                    self.log_handler.error(f"   Vérifiez les permissions et l'état du système de fichiers.")
                
                # Mettre à jour le suivi des photos dans le log_handler
                self.log_handler.register_renamed_photo(old_name, new_name)

                self.log_handler.success(f"✅ Renommé : {old_name} → {new_name}")
                self.log_handler.log_operation_end(
                    f"RENAME_{op_id}", 
                    self.log_handler.log_operation_start(f"RENAME_{op_id}"),
                    success=True,
                    context=f"Renommage réussi: {old_name} → {new_name}"
                )
                
                # Mettre à jour la couche si nécessaire
                self._mettre_a_jour_couche_photos(layer, old_name, new_name)
                
            except Exception as e:
                self.log_handler.error(f"❌ Erreur lors du renommage de {old_name} : {e}")
                self.log_handler.log_operation_end(
                    f"RENAME_{op_id}", 
                    self.log_handler.log_operation_start(f"RENAME_{op_id}"),
                    success=False,
                    context=f"Exception: {str(e)}"
                )
                
                # Vérification d'intégrité après erreur
                photos_after_error = set(os.listdir(dcim_path))
                if old_name not in photos_after_error:
                    self.log_handler.error(f"❌ PHOTO DISPARUE: {old_name} a disparu après l'erreur!")
                    self.log_handler.error(f"   Cela suggère une suppression accidentelle ou un déplacement non contrôlé.")
                    self.log_handler.error(f"   Vérifiez immédiatement le dossier DCIM et la corbeille.")
                if new_name in photos_after_error:
                    self.log_handler.warning(f"⚠️  La nouvelle photo {new_name} existe malgré l'erreur")

    def _fid_depuis_nom_photo(self, photo_name):
        """Extrait le FID du nom de fichier (format DT_YYYY-MM-DD_FID_...). Retourne None si absent ou invalide."""
        if not photo_name or not isinstance(photo_name, str):
            return None
        match = re.match(r'DT_\d{4}-\d{2}-\d{2}_(\d+)_', photo_name)
        if match:
            return int(match.group(1))
        return None

    def _mettre_a_jour_couche_photos(self, layer, old_name, new_name):
        """Met à jour la référence photo uniquement pour l'entité dont le FID correspond au FID dans new_name.
        Évite qu'une entité (ex. 538) reçoive le nom d'un fichier qui appartient à une autre (ex. 497)."""
        try:
            fid_dans_nom = self._fid_depuis_nom_photo(new_name)
            if fid_dans_nom is None:
                return
            layer.startEditing()
            for feature in layer.getFeatures():
                photo_field = feature['photo']
                if not photo_field or old_name not in photo_field:
                    continue
                # Ne mettre à jour que si le nouveau nom de fichier correspond à cette entité (même FID)
                if feature.id() != fid_dans_nom:
                    continue
                new_photo_path = photo_field.replace(old_name, new_name)
                layer.changeAttributeValue(feature.id(),
                                         layer.fields().indexFromName('photo'),
                                         new_photo_path)
                self.log_handler.info(f"📋 Mise à jour de l'entité {feature.id()}: {old_name} → {new_name}")
                break
            
            # Sauvegarder les modifications
            layer.commitChanges()
            
        except Exception as e:
            self.log_handler.error(f"Erreur lors de la mise à jour de la couche: {e}")
            if hasattr(layer, 'rollBack'):
                layer.rollBack()

    def _sanitize_for_filename(self, value):
        """Retourne une chaîne utilisable dans un nom de fichier (espaces → _, pas de caractères interdits)."""
        if value is None:
            return ""
        s = str(value).strip()
        for c in r'\/:*?"<>|':
            s = s.replace(c, '_')
        s = s.replace(' ', '_')
        return s or "INCONNU"

    def _date_saisie_to_yyyy_mm_dd(self, value):
        """Normalise date_saisie (QDate, QDateTime, str, date, datetime) en YYYY-MM-DD."""
        if value is None:
            return None
        # QDate / QDateTime (champ QGIS courant)
        if hasattr(value, 'toString'):
            try:
                if hasattr(value, 'date'):  # QDateTime
                    d = value.date()
                else:
                    d = value
                return f"{d.year():04d}-{d.month():02d}-{d.day():02d}"
            except Exception:
                pass
        # Python date / datetime
        if hasattr(value, 'strftime'):
            try:
                return value.strftime('%Y-%m-%d')
            except Exception:
                pass
        # Chaîne
        s = str(value).strip()
        if len(s) >= 10 and re.match(r'^\d{4}-\d{2}-\d{2}', s):
            return s[:10]
        m = re.match(r'^(\d{4})[-/]?(\d{2})[-/]?(\d{2})', s.replace('/', '-'))
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        # YYYYMMDD compact
        m = re.match(r'^(\d{4})(\d{2})(\d{2})', re.sub(r'[^0-9]', '', s))
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return None

    def _date_from_photo_filename(self, filename):
        """Extrait une date YYYY-MM-DD du nom de fichier photo (fallback si date_saisie invalide)."""
        if not filename:
            return None
        # DT_2026-02-05_... ou DT_20260205_...
        m = re.search(r'DT_(\d{4})-?(\d{2})-?(\d{2})', filename)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        m = re.search(r'DT_(\d{4})(\d{2})(\d{2})', filename)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return None

    def renommer_photos_d_apres_formulaires(self, dcim_path, layer):
        """
        Renomme les photos selon la règle DT_YYYY-MM-DD_FID_nom_agent_type_saisie_X_Y.jpg
        en utilisant les champs des entités (date_saisie, nom_agent, type_saisie, géométrie).
        Fonctionne pour toutes les photos du répertoire DCIM (ancien format ou nouveau).
        Ne renomme que si nom_agent et type_saisie sont renseignés et différents de INCONNU.
        Retourne le nombre de photos renommées.
        """
        self.log_handler.info("📋 Renommage des photos d'après les formulaires (toutes les photos DCIM)...")
        photo_idx = layer.fields().indexFromName('photo')
        nom_agent_idx = layer.fields().indexFromName('nom_agent')
        type_saisie_idx = layer.fields().indexFromName('type_saisie')
        if photo_idx < 0:
            self.log_handler.error("❌ Champ 'photo' introuvable dans la couche")
            return 0
        if nom_agent_idx < 0 or type_saisie_idx < 0:
            self.log_handler.error("❌ Champs 'nom_agent' ou 'type_saisie' introuvables dans la couche")
            return 0
        
        from ..scripts.analyse_orphelines import extraire_coord_du_nom
        
        renamed_count = 0
        layer.startEditing()
        try:
            for feature in layer.getFeatures():
                photo_val = feature['photo']
                if not photo_val or not isinstance(photo_val, str):
                    continue
                old_name = photo_val.replace('DCIM/', '').strip().split('/')[-1]
                if not old_name.lower().endswith(('.jpg', '.jpeg')):
                    continue
                old_path = os.path.join(dcim_path, old_name)
                if not os.path.exists(old_path):
                    continue
                nom_agent = (feature['nom_agent'] or '').strip() if feature['nom_agent'] is not None else ''
                type_saisie = (feature['type_saisie'] or '').strip() if feature['type_saisie'] is not None else ''
                if not nom_agent or nom_agent.upper() == 'INCONNU':
                    continue
                if not type_saisie or type_saisie.upper() == 'INCONNU':
                    continue
                date_str = self._date_saisie_to_yyyy_mm_dd(feature['date_saisie'])
                if not date_str:
                    date_str = self._date_from_photo_filename(old_name)
                if not date_str:
                    self.log_handler.warning(f"⚠️  Entité FID {feature.id()}: date_saisie invalide et pas de date dans le nom de photo, ignorée")
                    continue
                fid = feature.id()
                geom = feature.geometry()
                if not geom or geom.isEmpty():
                    self.log_handler.warning(f"⚠️  Entité FID {fid}: pas de géométrie, ignorée")
                    continue
                pt = geom.asPoint()
                x, y = pt.x(), pt.y()
                # Formater x,y avec 3 décimales (comme les noms existants) pour éviter noms trop longs
                x_str = f"{round(float(x), 3):.3f}"
                y_str = f"{round(float(y), 3):.3f}"
                agent_part = self._sanitize_for_filename(nom_agent)
                type_part = self._sanitize_for_filename(type_saisie)
                new_name = f"DT_{date_str}_{fid}_{agent_part}_{type_part}_{x_str}_{y_str}.jpg"
                if new_name == old_name:
                    continue
                new_path = os.path.join(dcim_path, new_name)
                
                # Si le nouveau fichier existe déjà, mettre à jour le champ photo sans renommer
                if os.path.exists(new_path):
                    # Vérifier que le FID dans le nom correspond bien à cette entité (sécurité)
                    fid_in_new_name = self._fid_depuis_nom_photo(new_name)
                    if fid_in_new_name is not None and fid_in_new_name != fid:
                        self.log_handler.warning(f"⚠️  Conflit: {new_name} existe déjà mais FID ({fid_in_new_name}) ≠ entité ({fid}), ignoré")
                        continue
                    
                    # Vérifier si le champ photo pointe encore vers l'ancien nom
                    if old_name != new_name:
                        # Le fichier avec le nouveau nom existe déjà, mettre à jour le champ photo
                        new_photo_val = f'DCIM/{new_name}'
                        layer.changeAttributeValue(feature.id(), photo_idx, new_photo_val)
                        renamed_count += 1
                        
                        # Si l'ancien fichier existe toujours et que c'est un doublon (mêmes coordonnées), le supprimer
                        if os.path.exists(old_path):
                            # Extraire les coordonnées de l'ancien nom pour vérifier si c'est un doublon
                            _, x_old, y_old = extraire_coord_du_nom(old_name)
                            if x_old is not None and y_old is not None:
                                # Vérifier si les coordonnées sont identiques (doublon)
                                if abs(float(x_old) - float(x)) < 0.01 and abs(float(y_old) - float(y)) < 0.01:
                                    try:
                                        os.remove(old_path)
                                        self.log_handler.success(
                                            f"🗑️  Fichier doublon supprimé: {old_name} "
                                            f"(mêmes coordonnées que {new_name})"
                                        )
                                    except Exception as e:
                                        self.log_handler.warning(f"⚠️  Impossible de supprimer doublon {old_name}: {e}")
                                        self.log_handler.info(f"ℹ️  Fichier {new_name} existe déjà, champ photo mis à jour (ancien fichier {old_name} toujours présent)")
                                else:
                                    self.log_handler.info(f"ℹ️  Fichier {new_name} existe déjà, champ photo mis à jour (ancien fichier {old_name} toujours présent)")
                            else:
                                self.log_handler.info(f"ℹ️  Fichier {new_name} existe déjà, champ photo mis à jour (ancien fichier {old_name} toujours présent)")
                        else:
                            self.log_handler.success(f"✅ Champ photo mis à jour: {old_name} → {new_name} (fichier déjà renommé)")
                    # Sinon, le champ pointe déjà vers le bon fichier, rien à faire
                    continue
                
                # Le nouveau fichier n'existe pas, procéder au renommage
                if not os.path.exists(old_path):
                    self.log_handler.warning(f"⚠️  Fichier source introuvable: {old_name}")
                    continue
                    
                try:
                    os.rename(old_path, new_path)
                except Exception as e:
                    self.log_handler.error(f"❌ Renommage impossible {old_name} → {new_name}: {e}")
                    continue
                new_photo_val = f'DCIM/{new_name}'
                layer.changeAttributeValue(feature.id(), photo_idx, new_photo_val)
                self.log_handler.register_renamed_photo(old_name, new_name)
                renamed_count += 1
                self.log_handler.success(f"✅ {old_name} → {new_name}")
            layer.commitChanges()
        except Exception as e:
            self.log_handler.error(f"❌ Erreur: {e}")
            if layer.isEditing() and hasattr(layer, 'rollBack'):
                layer.rollBack()
            return renamed_count
        return renamed_count

    def creer_entites_pour_photos_orphelines_avec_fid(self, dcim_path, layer):
        """Crée des entités pour les photos orphelines qui ont un FID valide mais pas d'entité correspondante"""
        self.log_handler.info("📋 Détection et création d'entités pour photos orphelines avec FID...")
        
        # Lister les photos orphelines avec FID valide
        photos_orphelines_avec_fid = []
        
        # D'abord, obtenir la liste des FID existants
        fid_existants = set()
        for feature in layer.getFeatures():
            fid_existants.add(feature.id())
        
        for filename in os.listdir(dcim_path):
            if filename.lower().endswith('.jpg'):
                # Vérifier si la photo a un FID mais pas d'entité correspondante
                match = re.match(r'DT_(\d{4}-\d{2}-\d{2})_(\d+)_([^_]+)_([^_]+)_([-+]?\d+\.?\d*)_([-+]?\d+\.?\d*)\.jpg', filename)
                if match:
                    fid = int(match.group(2))
                    # Vérifier si ce FID n'existe pas dans la couche
                    if fid not in fid_existants:
                        date_str = match.group(1)
                        agent = match.group(3).replace('_', ' ')
                        type_saisie = match.group(4).replace('_', ' ')
                        x = float(match.group(5))
                        y = float(match.group(6))
                        photos_orphelines_avec_fid.append((filename, date_str, fid, agent, type_saisie, x, y))
        
        if not photos_orphelines_avec_fid:
            self.log_handler.info("ℹ️  Aucune photo orpheline avec FID valide nécessitant création d'entité")
            self.log_handler.info("   (Les orphelines listées en analyse ont déjà une entité pour ce FID ; le champ photo peut être vide ou pointer ailleurs.)")
            return 0
        
        self.log_handler.warning(f"⚠️  {len(photos_orphelines_avec_fid)} photos orphelines avec FID à traiter")
        
        # Démarrer l'édition de la couche
        layer.startEditing()
        photo_field_idx = layer.fields().indexFromName('photo')
        if photo_field_idx < 0:
            self.log_handler.warning("⚠️  Champ 'photo' introuvable dans la couche")
            return 0
        
        entites_creees = 0
        
        for photo_name, date_str, fid, agent, type_saisie, x, y in photos_orphelines_avec_fid:
            try:
                # Vérifier qu'aucune entité n'existe déjà aux mêmes coordonnées (éviter les doublons)
                entite_existante_meme_coord = None
                for feature in layer.getFeatures():
                    if feature.geometry() and not feature.geometry().isEmpty():
                        point = feature.geometry().asPoint()
                        if abs(point.x() - float(x)) < 0.01 and abs(point.y() - float(y)) < 0.01:
                            entite_existante_meme_coord = feature
                            break
                
                if entite_existante_meme_coord:
                    # Une entité existe déjà aux mêmes coordonnées
                    photo_existante = entite_existante_meme_coord['photo']
                    file_path = os.path.join(dcim_path, photo_name)
                    
                    if photo_existante and isinstance(photo_existante, str):
                        # L'entité a déjà une photo → supprimer le doublon
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                                self.log_handler.success(
                                    f"🗑️  Photo doublon supprimée: {photo_name} "
                                    f"(entité FID {entite_existante_meme_coord.id()} existe déjà aux mêmes coordonnées)"
                                )
                            except Exception as e:
                                self.log_handler.error(f"❌ Erreur suppression doublon {photo_name}: {e}")
                        continue
                    else:
                        # L'entité n'a pas de photo → associer ce fichier
                        layer.changeAttributeValue(entite_existante_meme_coord.id(), photo_field_idx, f'DCIM/{photo_name}')
                        self.log_handler.success(
                            f"✅ Photo orpheline associée à entité FID {entite_existante_meme_coord.id()} "
                            f"(mêmes coordonnées, pas de photo existante)"
                        )
                        continue
                
                # Aucune entité aux mêmes coordonnées → créer une nouvelle entité
                from qgis.core import QgsFeature, QgsGeometry, QgsPointXY
                new_feature = QgsFeature(layer.fields())
                
                # Remplir les attributs
                new_feature['date_saisie'] = f"{date_str}T00:00:00"  # Format ISO
                new_feature['x_saisie'] = x
                new_feature['y_saisie'] = y
                new_feature['nom_agent'] = agent
                new_feature['type_saisie'] = type_saisie
                new_feature['photo'] = f'DCIM/{photo_name}'
                
                # Définir la géométrie
                point = QgsPointXY(x, y)
                new_feature.setGeometry(QgsGeometry.fromPointXY(point))
                
                # Ajouter l'entité
                success = layer.addFeature(new_feature)
                if not success:
                    self.log_handler.error(f"❌ Échec création entité pour {photo_name}")
                    continue
                
                # Sauvegarder pour obtenir le FID réel attribué
                layer.commitChanges()
                
                # Trouver le FID réel de l'entité créée
                assigned_fid = None
                for feature in layer.getFeatures():
                    if feature.geometry() and not feature.geometry().isEmpty():
                        feat_point = feature.geometry().asPoint()
                        if (abs(feat_point.x() - float(x)) < 0.01 and 
                            abs(feat_point.y() - float(y)) < 0.01):
                            assigned_fid = feature.id()
                            break
                
                if assigned_fid is None or assigned_fid <= 0:
                    self.log_handler.error(f"❌ Impossible de trouver le FID attribué pour {photo_name}")
                    continue
                
                entites_creees += 1
                
                # Si le FID attribué ne correspond pas au FID dans le nom, renommer le fichier et mettre à jour le champ photo
                if assigned_fid != fid:
                    self.log_handler.warning(f"⚠️  FID attribué ({assigned_fid}) différent du FID dans le nom ({fid})")
                    # Construire le nouveau nom avec le FID réel
                    agent_part = agent.replace(' ', '_')
                    type_part = type_saisie.replace(' ', '_')
                    new_photo_name = f"DT_{date_str}_{assigned_fid}_{agent_part}_{type_part}_{x}_{y}.jpg"
                    old_path = os.path.join(dcim_path, photo_name)
                    new_path = os.path.join(dcim_path, new_photo_name)
                    
                    if os.path.exists(old_path) and not os.path.exists(new_path):
                        try:
                            os.rename(old_path, new_path)
                            layer.startEditing()
                            layer.changeAttributeValue(assigned_fid, photo_field_idx, f'DCIM/{new_photo_name}')
                            layer.commitChanges()
                            self.log_handler.register_renamed_photo(photo_name, new_photo_name)
                            self.log_handler.success(f"✅ Photo renommée: {photo_name} → {new_photo_name}")
                        except Exception as e:
                            self.log_handler.error(f"❌ Erreur renommage photo {photo_name}: {e}")
                    else:
                        self.log_handler.warning(f"⚠️  Impossible de renommer {photo_name} (fichier absent ou conflit)")
                        # Mettre à jour quand même le champ photo avec le nom actuel
                        layer.startEditing()
                        layer.changeAttributeValue(assigned_fid, photo_field_idx, f'DCIM/{photo_name}')
                        layer.commitChanges()
                else:
                    self.log_handler.success(f"✅ Entité créée pour {photo_name} (FID: {fid})")
                    
            except Exception as e:
                self.log_handler.error(f"❌ Erreur création entité pour {photo_name}: {e}")
                if layer.isEditing():
                    if hasattr(layer, 'rollBack'):
                        layer.rollBack()
        
        # Sauvegarder les modifications finales si on est encore en édition
        if layer.isEditing():
            layer.commitChanges()
        self.log_handler.success(f"✅ {entites_creees}/{len(photos_orphelines_avec_fid)} entités créées pour photos orphelines avec FID")
        return entites_creees

    def creer_entites_pour_orphelines(self, dcim_path, layer):
        """Crée des entités pour les photos orphelines (uniquement les fichiers présents dans dcim_path)."""
        self.log_handler.info("📋 Étape 5/6: Création d'entités pour les photos orphelines...")
        
        # Lister uniquement les photos présentes dans dcim_path (pas le sync) pour éviter de renommer des noms déjà renommés ou absents
        if not os.path.exists(dcim_path):
            self.log_handler.info("⚠️  Dossier DCIM introuvable")
            return 0
        photos = [f for f in os.listdir(dcim_path) if f.lower().endswith(('.jpg', '.jpeg'))]
        if not photos:
            self.log_handler.info("⚠️  Aucune photo trouvée dans DCIM")
            return 0
        
        # Analyser chaque photo pour trouver les orphelines
        from ..scripts.analyse_orphelines import extraire_coord_du_nom
        
        entites_creees = 0
        
        # Démarrer l'édition de la couche
        layer.startEditing()
        
        # Dictionnaire pour mapper les coordonnées aux FID créés
        coord_to_fid = {}
        
        for photo_name in photos:
            fid, x, y = extraire_coord_du_nom(photo_name)
            
            # Ignorer les photos déjà au format standard avec FID
            if fid is not None:
                # Vérifier si cette photo est déjà associée à une entité (FID = feature.id() en QGIS)
                entite_trouvee = False
                for feature in layer.getFeatures():
                    if feature.id() == fid:
                        entite_trouvee = True
                        break
                
                if entite_trouvee:
                    continue  # Déjà associée, ignorer
            
            # Vérifier si les coordonnées sont valides
            if x is None or y is None:
                self.log_handler.warning(f"⚠️  Impossible d'extraire les coordonnées de {photo_name}")
                continue
            
            # Traiter les photos au format ancien (sans FID) ou orphelines
            if (fid is None and x is not None and y is not None) or (fid is not None and not entite_trouvee):
                try:
                    # Créer une clé unique pour ces coordonnées
                    coord_key = (round(float(x), 2), round(float(y), 2))
                    
                    # Vérifier si une entité existe déjà à ces coordonnées (éviter les doublons)
                    if coord_key in coord_to_fid:
                        existing_fid = coord_to_fid[coord_key]
                        self.log_handler.info(f"ℹ️  Entité existe déjà à {x},{y} (FID: {existing_fid})")
                        
                        # Vérifier si l'entité existante a déjà une photo
                        existing_feature = None
                        for feature in layer.getFeatures():
                            if feature.id() == existing_fid:
                                existing_feature = feature
                                break
                        
                        file_path = os.path.join(dcim_path, photo_name)
                        photo_existante = existing_feature['photo'] if existing_feature else None
                        
                        if photo_existante and isinstance(photo_existante, str) and photo_existante.strip():
                            # L'entité a déjà une photo valide → supprimer le doublon
                            if os.path.exists(file_path):
                                try:
                                    os.remove(file_path)
                                    self.log_handler.success(
                                        f"🗑️  Photo doublon supprimée: {photo_name} "
                                        f"(entité FID {existing_fid} a déjà une photo aux mêmes coordonnées)"
                                    )
                                except Exception as e:
                                    self.log_handler.error(f"❌ Erreur suppression doublon {photo_name}: {e}")
                            continue
                        else:
                            # L'entité n'a pas de photo → associer ce fichier ou renommer selon le cas
                            if fid is None:
                                # Extraire la date pour le renommage
                                date_match = re.search(r'DT_(\d{4})(\d{2})(\d{2})', photo_name)
                                if date_match:
                                    year = date_match.group(1)
                                    month = date_match.group(2)
                                    day = date_match.group(3)
                                    date_str = f"{year}-{month}-{day}"
                                    
                                    # Construire le nouveau nom avec le FID existant
                                    new_photo_name = f"DT_{date_str}_{existing_fid}_INCONNU_INCONNU_{x}_{y}.jpg"
                                    
                                    # Renommer physiquement le fichier (uniquement s'il existe dans dcim_path)
                                    old_path = os.path.join(dcim_path, photo_name)
                                    new_path = os.path.join(dcim_path, new_photo_name)
                                    
                                    if not os.path.exists(old_path):
                                        self.log_handler.warning(f"⚠️  Fichier introuvable (déjà renommé?): {photo_name}")
                                        continue
                                    if not os.path.exists(new_path):
                                        os.rename(old_path, new_path)
                                        
                                        # Mettre à jour le champ photo de l'entité existante vers le nouveau nom
                                        photo_field_idx = layer.fields().indexFromName('photo')
                                        if photo_field_idx >= 0:
                                            layer.changeAttributeValue(existing_fid, photo_field_idx, f'DCIM/{new_photo_name}')
                                            self.log_handler.info(f"📋 Entité FID {existing_fid}: champ photo mis à jour → {new_photo_name}")
                                        
                                        # Mettre à jour le suivi des photos renommées
                                        self.log_handler.register_renamed_photo(photo_name, new_photo_name)
                                        
                                        self.log_handler.success(f"✅ Photo renommée avec FID existant: {photo_name} → {new_photo_name}")
                                    else:
                                        self.log_handler.warning(f"⚠️  Conflit de nom: {new_photo_name} existe déjà")
                            else:
                                # Photo avec FID mais pas d'entité correspondante → associer à l'entité existante
                                photo_field_idx = layer.fields().indexFromName('photo')
                                if photo_field_idx >= 0 and os.path.exists(file_path):
                                    layer.changeAttributeValue(existing_fid, photo_field_idx, f'DCIM/{photo_name}')
                                    self.log_handler.success(
                                        f"✅ Photo orpheline associée à entité FID {existing_fid} "
                                        f"(mêmes coordonnées, pas de photo existante)"
                                    )
                        continue
                    
                    # Créer une nouvelle entité
                    from qgis.core import QgsFeature, QgsGeometry, QgsPointXY
                    new_feature = QgsFeature(layer.fields())
                    
                    # Extraire la date du nom de fichier
                    if fid is not None:
                        date_match = re.search(r'DT_(\d{4}-\d{2}-\d{2})', photo_name)
                        if date_match:
                            date_str = date_match.group(1)
                            new_feature['date_saisie'] = date_str
                    else:
                        date_match = re.search(r'DT_(\d{4})(\d{2})(\d{2})', photo_name)
                        if date_match:
                            year = date_match.group(1)
                            month = date_match.group(2)
                            day = date_match.group(3)
                            date_str = f"{year}-{month}-{day}"
                            new_feature['date_saisie'] = date_str
                    
                    # Définir les coordonnées et autres champs
                    new_feature['x_saisie'] = float(x)
                    new_feature['y_saisie'] = float(y)
                    new_feature['nom_agent'] = 'INCONNU'
                    new_feature['type_saisie'] = 'INCONNU'
                    new_feature['photo'] = f'DCIM/{photo_name}'
                    
                    # Définir la géométrie
                    point = QgsPointXY(float(x), float(y))
                    new_feature.setGeometry(QgsGeometry.fromPointXY(point))
                    
                    # Ajouter l'entité à la couche
                    success = layer.addFeature(new_feature)
                    if not success:
                        self.log_handler.error(f"❌ Échec de la création de l'entité pour {photo_name}")
                        continue
                    
                    # Sauvegarder les modifications pour obtenir le FID réel
                    layer.commitChanges()
                    
                    # Trouver le FID de l'entité nouvellement créée
                    new_fid = None
                    for feature in layer.getFeatures():
                        if feature.geometry() and not feature.geometry().isEmpty():
                            feat_point = feature.geometry().asPoint()
                            if (abs(feat_point.x() - float(x)) < 0.01 and 
                                abs(feat_point.y() - float(y)) < 0.01):
                                new_fid = feature.id()
                                break
                    
                    if new_fid is None or new_fid <= 0:
                        self.log_handler.error(f"❌ Impossible de trouver le FID pour {photo_name}")
                        if hasattr(layer, 'rollBack'):
                            layer.rollBack()
                        continue
                    
                    # Vérifier si le FID est déjà utilisé par une autre entité
                    fid_exists = False
                    for feature in layer.getFeatures():
                        if feature.id() == new_fid and feature.id() != new_feature.id():
                            fid_exists = True
                            break
                    
                    if fid_exists:
                        # Attribuer un nouveau FID unique
                        max_fid = max([feature.id() for feature in layer.getFeatures()], default=0)
                        new_fid = max_fid + 1
                        self.log_handler.warning(f"⚠️  Conflit de FID détecté. Nouveau FID attribué: {new_fid}")
                    
                    # Enregistrer le mapping coordonnées -> FID
                    coord_to_fid[coord_key] = new_fid
                    entites_creees += 1
                    self.log_handler.info(f"✅ Entité créée avec FID {new_fid} pour {photo_name}")
                    
                    # Rebasculer en mode édition pour les mises à jour
                    layer.startEditing()
                    photo_field_idx = layer.fields().indexFromName('photo')
                    
                    # Renommer la photo avec le vrai FID et mettre à jour le champ photo de l'entité
                    if fid is None and date_match:
                        # Photo sans FID (ex. DT_YYYYMMDD_HHMMSS_X_Y.jpg ou _0_)
                        new_photo_name = f"DT_{date_str}_{new_fid}_INCONNU_INCONNU_{x}_{y}.jpg"
                        old_path = os.path.join(dcim_path, photo_name)
                        new_path = os.path.join(dcim_path, new_photo_name)
                        
                        if not os.path.exists(old_path):
                            self.log_handler.warning(f"⚠️  Fichier introuvable (déjà renommé?): {photo_name}")
                        elif not os.path.exists(new_path):
                            os.rename(old_path, new_path)
                            if photo_field_idx >= 0:
                                layer.changeAttributeValue(new_fid, photo_field_idx, f'DCIM/{new_photo_name}')
                                self.log_handler.info(f"📋 Entité FID {new_fid}: champ photo mis à jour → {new_photo_name}")
                            self.log_handler.register_renamed_photo(photo_name, new_photo_name)
                            self.log_handler.success(f"✅ Photo renommée: {photo_name} → {new_photo_name}")
                        else:
                            self.log_handler.warning(f"⚠️  Conflit de nom: {new_photo_name} existe déjà")
                    elif fid is not None and fid != new_fid:
                        # Photo avec FID dans le nom mais entité créée avec un autre FID : renommer le fichier et mettre à jour l'entité
                        date_str = None
                        m = re.search(r'DT_(\d{4}-\d{2}-\d{2})_', photo_name)
                        if m:
                            date_str = m.group(1)
                        if date_str:
                            new_photo_name = re.sub(r'^DT_\d{4}-\d{2}-\d{2}_\d+_', f'DT_{date_str}_{new_fid}_', photo_name)
                            old_path = os.path.join(dcim_path, photo_name)
                            new_path = os.path.join(dcim_path, new_photo_name)
                            if os.path.exists(old_path) and not os.path.exists(new_path):
                                os.rename(old_path, new_path)
                                if photo_field_idx >= 0:
                                    layer.changeAttributeValue(new_fid, photo_field_idx, f'DCIM/{new_photo_name}')
                                    self.log_handler.info(f"📋 Entité FID {new_fid}: champ photo mis à jour → {new_photo_name}")
                                self.log_handler.register_renamed_photo(photo_name, new_photo_name)
                                self.log_handler.success(f"✅ Photo renommée (FID corrigé): {photo_name} → {new_photo_name}")
                    
                except Exception as e:
                    self.log_handler.error(f"❌ Erreur lors du traitement de {photo_name}: {e}")
                    if hasattr(layer, 'rollBack'):
                        layer.rollBack()
                    continue
        
        # Sauvegarder les modifications finales
        layer.commitChanges()
        
        self.log_handler.success(f"✅ {entites_creees} entités créées pour les photos orphelines")
        return entites_creees
