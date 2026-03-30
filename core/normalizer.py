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
from qgis.core import QgsFeature, QgsGeometry, QgsPointXY
from .log_handler import LogHandler, LogWindow
from .project_config import (
    get_dcim_path,
    get_gpkg_path,
    get_cloud_base,
    get_project_base,
    get_backup_dir,
    get_layer_name,
    get_photo_field_name,
    get_coord_tolerance,
    refresh_paths_from_qgis,
    set_runtime_project_base,
    persist_project_base,
    is_valid_dataterrain_root,
)

_STEPS_MODE_COMPLET = 13

# Importation pour le traitement d'images
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("⚠️  Module PIL/Pillow non disponible. Installation recommandée: pip install pillow")

# Mode sécurisé : si False, les "doublons" détectés automatiquement (mêmes coordonnées)
# sont déplacés vers ARCHIVE_DOUBLONS_DIR au lieu d'être supprimés.
# Mettre True pour retrouver l'ancien comportement (suppression directe).
SUPPRESSION_AUTO_DOUBLONS = False

# Dossier d'archive des doublons (sous le répertoire cloud, défini dans project_config)
ARCHIVE_DOUBLONS_DIR_NAME = "DataTerrain_DCIM_archive_doublons"

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

    def _get_archive_doublons_dir(self, dcim_path=None):
        """Retourne le chemin du dossier d'archive des doublons (sous le répertoire cloud)."""
        return os.path.join(get_cloud_base(), ARCHIVE_DOUBLONS_DIR_NAME)

    def _supprimer_ou_archiver_doublon(self, file_path, raison, dcim_path=None):
        """
        Supprime le fichier (si SUPPRESSION_AUTO_DOUBLONS) ou le déplace vers
        (répertoire cloud)/DataTerrain_DCIM_archive_doublons/ pour éviter de perdre des photos par erreur.
        Retourne True si l'action a réussi (suppression ou archivage).
        """
        if not file_path or not os.path.exists(file_path):
            return False
        nom = os.path.basename(file_path)
        archive_dir = self._get_archive_doublons_dir(dcim_path)
        try:
            if SUPPRESSION_AUTO_DOUBLONS:
                os.remove(file_path)
                if self.log_handler:
                    self.log_handler.success(f"🗑️  Photo doublon supprimée: {nom} ({raison})")
                return True
            else:
                os.makedirs(archive_dir, exist_ok=True)
                dest = os.path.join(archive_dir, nom)
                if os.path.exists(dest):
                    base, ext = os.path.splitext(nom)
                    for i in range(1, 1000):
                        dest = os.path.join(archive_dir, f"{base}_{i}{ext}")
                        if not os.path.exists(dest):
                            break
                os.rename(file_path, dest)
                if self.log_handler:
                    self.log_handler.success(
                        f"📦  Doublon archivé (non supprimé): {nom} → {ARCHIVE_DOUBLONS_DIR_NAME}/ ({raison})"
                    )
                return True
        except Exception as e:
            if self.log_handler:
                self.log_handler.error(f"❌ Erreur pour {nom}: {e}")
            return False
        
    def run(self):
        """Exécute le traitement principal"""
        refresh_paths_from_qgis()
        # Créer la fenêtre de log
        self.log_window = LogWindow(self.iface.mainWindow())
        self.log_handler = LogHandler(self.log_window)
        self.log_window.set_configure_paths_callback(self._prompt_dataterrain_folder)

        # Connecter le signal
        self.log_window.run_mode_selected.connect(self.on_mode_selected)
        
        # Afficher la fenêtre
        self.log_window.show()

    def _prompt_dataterrain_folder(self):
        """Permet de choisir le dossier racine DataTerrain (DCIM + GPKG)."""
        from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox

        start = get_project_base() if os.path.isdir(get_project_base()) else ""
        d = QFileDialog.getExistingDirectory(
            self.iface.mainWindow(),
            "Sélectionner le dossier DataTerrain (contient DCIM/ et donnees_terrain.gpkg)",
            start,
        )
        if not d:
            return
        if is_valid_dataterrain_root(d):
            set_runtime_project_base(d)
            persist_project_base(d)
            self.log_handler.success(f"✅ Dossier DataTerrain configuré : {d}")
        else:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Dossier invalide",
                "Le dossier doit contenir un sous-dossier « DCIM » et le fichier « donnees_terrain.gpkg ».",
            )

    def on_mode_selected(self, mode):
        """Gère la sélection du mode"""
        refresh_paths_from_qgis()
        if mode == "detection":
            self.detect_unreferenced_photos()
            self._save_logs_automatically()
        elif mode == "duplicate_detection":
            self.detect_doublons()
            self._save_logs_automatically()
        elif mode == "orphan_analysis":
            self.analyse_orphelines()
            self._save_logs_automatically()
        elif mode == "analyse_table":
            self.run_analyse_table_attributaire_mode()
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
        elif mode == "reconcilier_photos":
            self.run_reconcilier_photos_mode()
            self._save_logs_automatically()
        elif mode == "normal":
            self.run_normal_mode()
            self._save_logs_automatically()
    
    def run_clean_photos_mode(self):
        """Mode isolé: synchronise les champs photo (ancien nom → nouveau), restaure depuis l'archive si besoin, puis nettoie les incohérences."""
        self.log_handler.info("📋 Mode Nettoyage des champs photo incohérents en cours...")
        gpkg_file = get_gpkg_path()
        layer_name = get_layer_name()
        dcim_path = get_dcim_path()
        try:
            nb_sync = self.synchroniser_champs_photo_entites(gpkg_file, layer_name, dcim_path)
            if nb_sync > 0:
                self.log_handler.success(f"✅ Champs photo synchronisés ({nb_sync} entités)")
            nb_repares = self.reparer_photos_manquantes_depuis_archive(gpkg_file, layer_name, dcim_path)
            if nb_repares > 0:
                self.log_handler.success(f"✅ {nb_repares} photo(s) restaurée(s) depuis l'archive")
            nb = self.clean_inconsistent_photo_fields(gpkg_file, layer_name)
            if nb > 0:
                self.log_handler.success(f"✅ Champs photo nettoyés pour {nb} entité(s) incohérente(s)")
            else:
                self.log_handler.info("ℹ️  Aucun champ photo incohérent détecté")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors du nettoyage des champs photo: {e}")

    def run_reconcilier_photos_mode(self):
        """
        Parcourt chaque photo dans DCIM :
        - Si attachée à une entité : vérifie que les coordonnées correspondent (bonne photo pour bonne entité).
        - Si non attachée : cherche une entité correspondante (FID ou coordonnées) ou crée une entité.
        """
        self.log_handler.info("📋 Mode Réconcilier photos et entités en cours...")
        gpkg_file = get_gpkg_path()
        layer_name = get_layer_name()
        dcim_path = get_dcim_path()
        try:
            nb_verif, nb_attachees, nb_creees = self.reconcilier_photos_avec_entites(gpkg_file, layer_name, dcim_path)
            self.log_handler.success(
                f"✅ Réconciliation terminée : {nb_verif} vérifiées, {nb_attachees} attachées, {nb_creees} entités créées"
            )
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors de la réconciliation: {e}")
            
    def detect_unreferenced_photos(self):
        """Détecte les photos non référencées"""
        from ..scripts.photo_detection import detect_unreferenced_photos
        self.log_handler.info("🔍 Détection des photos non référencées en cours...")
        try:
            ok = detect_unreferenced_photos(self.log_handler, self.export_dir)
            if ok:
                self.log_handler.info("✅ Détection terminée avec succès")
            else:
                self.log_handler.error("❌ Détection terminée avec erreurs (voir messages ci-dessus)")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors de la détection: {e}")
            
    def detect_doublons(self):
        """Exécute la détection des photos en double"""
        from ..scripts.detect_doublons import detect_doublons
        self.log_handler.info("👥 Détection des doublons en cours...")
        try:
            # Exécuter la détection
            doublons_groups = detect_doublons(self.log_handler, self.export_dir)
            
            # Debug (repr: évite que QTextEdit interprète <class 'list'> comme balise HTML)
            self.log_handler.debug(
                f"📋 Données doublons reçues - Type: {repr(type(doublons_groups))}"
            )
            if isinstance(doublons_groups, list):
                self.log_handler.debug(f"📋 Nombre de groupes: {len(doublons_groups)}")
                for i, group in enumerate(doublons_groups[:3]):
                    self.log_handler.debug(
                        f"📋 Groupe {i}: {repr(type(group))} - "
                        f"{len(group) if isinstance(group, list) else 'N/A'} éléments"
                    )
            
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
                get_dcim_path(),
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
    
    def run_analyse_table_attributaire_mode(self):
        """Mode isolé: analyse complète de la table attributaire"""
        from ..scripts.analyse_table_attributaire import analyser_table_attributaire
        self.log_handler.info("📊 Analyse de la table attributaire en cours...")
        try:
            analyser_table_attributaire(self.log_handler, self.export_dir)
            self.log_handler.info("✅ Analyse complète de la table attributaire terminée")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors de l'analyse de la table attributaire: {e}")
            
    def run_normal_mode(self):
        """Exécute le mode normal - Traitement complet de normalisation"""
        self.log_handler.info("⚙️ Mode normal en cours...")
        
        # Étape 0: Sauvegarde initiale et vérification
        self.log_handler.info(f"📋 Étape 1/{_STEPS_MODE_COMPLET}: Préparation et sauvegarde...")
        dcim_path = get_dcim_path()
        gpkg_file = get_gpkg_path()
        layer_name = get_layer_name()
        
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
        self.log_handler.info(f"📋 Étape 2/{_STEPS_MODE_COMPLET}: Initialisation...")
        
        if not os.path.exists(dcim_path):
            self.log_handler.error(f"❌ Dossier DCIM introuvable: {dcim_path}")
            return
        
        if not os.path.exists(gpkg_file):
            self.log_handler.error(f"❌ Fichier GeoPackage introuvable: {gpkg_file}")
            return
        
        # Créer le dossier d'archive des doublons (DataTerrain_DCIM_archive_doublons sous Qfield/cloud)
        archive_dir = self._get_archive_doublons_dir(dcim_path)
        try:
            os.makedirs(archive_dir, exist_ok=True)
            self.log_handler.info(f"📁 Dossier d'archive doublons: {archive_dir}")
        except Exception as e:
            self.log_handler.warning(f"⚠️  Impossible de créer le dossier d'archive: {archive_dir} — {e}")
        
        # Migrer l'ancien dossier _archive_plugin (sous DCIM) vers le nouveau chemin si il existe
        old_archive = os.path.join(dcim_path, "_archive_plugin")
        if os.path.isdir(old_archive):
            try:
                old_files = [f for f in os.listdir(old_archive) if f.lower().endswith(('.jpg', '.jpeg'))]
                if old_files:
                    for f in old_files:
                        src = os.path.join(old_archive, f)
                        dst = os.path.join(archive_dir, f)
                        if os.path.isfile(src):
                            if os.path.exists(dst):
                                base, ext = os.path.splitext(f)
                                for i in range(1, 1000):
                                    dst = os.path.join(archive_dir, f"{base}_{i}{ext}")
                                    if not os.path.exists(dst):
                                        break
                            os.rename(src, dst)
                    self.log_handler.success(f"📦 {len(old_files)} photo(s) migrée(s) de _archive_plugin vers {ARCHIVE_DOUBLONS_DIR_NAME}")
                # Supprimer l'ancien dossier s'il est vide
                if not os.listdir(old_archive):
                    os.rmdir(old_archive)
                    self.log_handler.info("📁 Ancien dossier _archive_plugin supprimé (vide)")
            except Exception as e:
                self.log_handler.warning(f"⚠️  Migration _archive_plugin → {ARCHIVE_DOUBLONS_DIR_NAME} non effectuée: {e}")
        
        self.log_handler.success("✅ Initialisation terminée")
        
        # Étape 2: Analyse des photos
        self.log_handler.info(f"📋 Étape 3/{_STEPS_MODE_COMPLET}: Analyse des photos...")
        try:
            from ..scripts.photo_detection import detect_unreferenced_photos

            ok = detect_unreferenced_photos(self.log_handler, self.export_dir)
            if not ok:
                self.log_handler.error(
                    "❌ Mode complet interrompu : la détection des photos non référencées a échoué (voir ci-dessus)."
                )
                return
            self.log_handler.success("✅ Analyse terminée")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur analyse: {e}")
            self.log_handler.error(
                "❌ Mode complet interrompu : corrigez le problème (chemins, GPKG) puis relancez."
            )
            return

        # Étape 3: Détection des doublons (déplacée plus tôt pour éviter de renommer des doublons)
        self.log_handler.info(f"📋 Étape 4/{_STEPS_MODE_COMPLET}: Détection des doublons...")
        try:
            self.detect_doublons()
        except Exception as e:
            self.log_handler.error(f"❌ Erreur détection doublons: {e}")
            # Continuer malgré l'erreur
        
        # Étape 4: Analyse des photos orphelines
        self.log_handler.info(f"📋 Étape 5/{_STEPS_MODE_COMPLET}: Analyse des photos orphelines...")
        try:
            from ..scripts.analyse_orphelines import analyser_photos_orphelines
            analyser_photos_orphelines(self.log_handler)
            self.log_handler.success("✅ Analyse orphelines terminée")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur analyse orphelines: {e}")
            self.log_handler.error(
                "❌ Mode complet interrompu : corrigez le problème puis relancez le mode complet."
            )
            return

        # Étape 5: Renommage des photos
        try:
            self.log_handler.info(f"📋 Étape 6/{_STEPS_MODE_COMPLET}: Renommage des photos...")
            layer = self.get_layer(gpkg_file, layer_name)
            self.renommer_photos(dcim_path, layer)
            self.log_handler.success("✅ Renommage des photos terminé")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors du renommage des photos: {e}")
            # Continuer malgré l'erreur
        
        # Étape 6: Création d'entités pour les photos orphelines avec FID (synchronisation cloud)
        try:
            self.log_handler.info(
                f"📋 Étape 7/{_STEPS_MODE_COMPLET}: Création d'entités (photos orphelines avec FID)..."
            )
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
            self.log_handler.info(
                f"📋 Étape 8/{_STEPS_MODE_COMPLET}: Création d'entités pour les photos orphelines..."
            )
            entites_creees = self.creer_entites_pour_orphelines(dcim_path, layer)
            self.log_handler.success(f"✅ Création d'entités terminée ({entites_creees} entités créées)")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors de la création d'entités: {e}")
            # Continuer malgré l'erreur
        
        # Étape 8: Correction des FID=0 (photos mal renommées)
        try:
            self.log_handler.info(
                f"📋 Étape 9/{_STEPS_MODE_COMPLET}: Correction des photos avec FID=0..."
            )
            photos_corrigees = self.correct_fid_zero_photos(dcim_path, gpkg_file, layer_name)
            if photos_corrigees > 0:
                self.log_handler.success(f"✅ Correction FID terminée ({photos_corrigees} photos corrigées)")
            else:
                self.log_handler.info("ℹ️  Aucune photo avec FID=0 trouvée")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur lors de la correction des FID: {e}")
            # Continuer malgré l'erreur
        
        # Étape 8b–8c: Synchronisation, archive, nettoyage des champs photo
        try:
            self.log_handler.info(
                f"📋 Étape 10/{_STEPS_MODE_COMPLET}: Synchronisation des champs photo, archive et nettoyage..."
            )
            nb_sync = self.synchroniser_champs_photo_entites(gpkg_file, layer_name, dcim_path)
            if nb_sync > 0:
                self.log_handler.success(f"✅ Champs photo synchronisés ({nb_sync} entités mises à jour)")
            else:
                self.log_handler.info("ℹ️  Tous les champs photo pointent déjà vers les noms actuels")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur synchronisation champs photo: {e}")
            # Continuer malgré l'erreur
        
        # Étape 8b bis: Réparer les entités dont la photo est dans l'archive (restaurer vers DCIM)
        try:
            nb_repares = self.reparer_photos_manquantes_depuis_archive(gpkg_file, layer_name, dcim_path)
            if nb_repares > 0:
                self.log_handler.success(f"✅ {nb_repares} photo(s) restaurée(s) depuis l'archive vers DCIM")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur réparation photos depuis archive: {e}")
        
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
        self.log_handler.info(f"📋 Étape 11/{_STEPS_MODE_COMPLET}: Vérification d'intégrité finale...")
        try:
            self.verify_data_integrity(dcim_path, gpkg_file, layer_name)
            self.log_handler.success("✅ Vérification d'intégrité terminée")
        except Exception as e:
            self.log_handler.error(f"❌ Erreur vérification intégrité: {e}")
            # Continuer malgré l'erreur
        
        # Étape 12: Optimisation des images
        try:
            self.log_handler.info(f"📋 Étape 12/{_STEPS_MODE_COMPLET}: Optimisation des images...")
            self.optimize_images(dcim_path)
        except Exception as e:
            self.log_handler.error(f"❌ Erreur optimisation images: {e}")
            # Continuer malgré l'erreur
        
        # Étape 11: Renommage d'après les formulaires (toutes les photos dont nom_agent/type_saisie sont complétés)
        self.log_handler.info(f"📋 Étape 13/{_STEPS_MODE_COMPLET}: Renommage d'après les formulaires...")
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
        
        # Vérifier où sont les photos "disparues" : QField sync, archive doublons (mode sécurisé), ou vraiment perdues
        photos_deplacees_qfield = set()
        photos_archivees = set()
        photos_reellement_disparues = set()
        
        archive_dir = self._get_archive_doublons_dir(dcim_path)
        archive_list = set()
        if os.path.exists(archive_dir):
            archive_list = {f for f in os.listdir(archive_dir) if f.lower().endswith(('.jpg', '.jpeg'))}
        
        # Déterminer le nom sous lequel la photo peut être (renommée puis archivée)
        def _nom_archive(photo):
            if self.log_handler.is_photo_renamed(photo):
                fn = self.log_handler.get_final_photo_name(photo)
                return fn if fn else photo
            return photo
        
        qfield_sync_dcim = os.path.join(os.path.dirname(dcim_path), '.qfieldsync', 'download', 'DCIM')
        if os.path.exists(qfield_sync_dcim):
            sync_photos = {f for f in os.listdir(qfield_sync_dcim) 
                          if f.lower().endswith(('.jpg', '.jpeg'))}
            for photo in photos_disparues:
                nom_a_chercher = _nom_archive(photo)
                if photo in sync_photos or nom_a_chercher in sync_photos:
                    photos_deplacees_qfield.add(photo)
                elif photo in archive_list or nom_a_chercher in archive_list:
                    photos_archivees.add(photo)
                else:
                    photos_reellement_disparues.add(photo)
        else:
            for photo in photos_disparues:
                nom_a_chercher = _nom_archive(photo)
                if photo in archive_list or nom_a_chercher in archive_list:
                    photos_archivees.add(photo)
                else:
                    photos_reellement_disparues.add(photo)
        
        # Afficher les résultats avec messages améliorés
        if photos_archivees:
            self.log_handler.info(f"📦 {len(photos_archivees)} photo(s) déplacée(s) vers {archive_dir} (mode sécurisé, pas de suppression):")
            for photo in sorted(photos_archivees)[:5]:
                self.log_handler.info(f"   • {photo}")
            if len(photos_archivees) > 5:
                self.log_handler.info(f"   • ... et {len(photos_archivees) - 5} autres")
        if photos_deplacees_qfield:
            self.log_handler.warning(f"⚠️  {len(photos_deplacees_qfield)} photos ont été déplacées dans le dossier de synchronisation QField:")
            self.log_handler.warning("   Cela peut être dû à la synchronisation avec QField Cloud.")
            for photo in sorted(photos_deplacees_qfield)[:5]:
                self.log_handler.warning(f"   • {photo}")
            if len(photos_deplacees_qfield) > 5:
                self.log_handler.warning(f"   • ... et {len(photos_deplacees_qfield) - 5} autres")
        
        if photos_reellement_disparues:
            self.log_handler.error(f"❌ ATTENTION: {len(photos_reellement_disparues)} photos n'ont pas été retrouvées (ni dans DCIM, ni dans {ARCHIVE_DOUBLONS_DIR_NAME}):")
            self.log_handler.error("Cela peut indiquer un problème lors du traitement. Vérifiez les logs détaillés.")
            for photo in sorted(photos_reellement_disparues):
                self.log_handler.error(f"  🚨 {photo}")
            self.log_handler.warning("💡 Actions recommandées:")
            self.log_handler.warning("  1. Vérifiez la sauvegarde créée au début du traitement")
            self.log_handler.warning("  2. Consultez le rapport détaillé des opérations")
            self.log_handler.warning("  3. Vérifiez que ces photos n'ont pas été renommées ou déplacées")
        elif photos_archivees or photos_deplacees_qfield:
            self.log_handler.success("✅ Toutes les photos initiales sont prises en compte (renommées, archivées ou déplacées QField)")
            if photos_archivees:
                self.log_handler.info(f"   📦 {len(photos_archivees)} dans {ARCHIVE_DOUBLONS_DIR_NAME} (mode sécurisé)")
            if photos_deplacees_qfield:
                self.log_handler.info(f"   📁 {len(photos_deplacees_qfield)} dans le dossier de sync QField")
        else:
            self.log_handler.success("✅ Toutes les photos initiales ont été correctement traitées")
            self.log_handler.success("   - Les photos renommées sont suivies et accessibles")
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
        
        if len(photos_reellement_disparues) > 0:
            self.log_handler.error(f"  ❌ Photos non retrouvées (à vérifier): {len(photos_reellement_disparues)}")
            if photos_archivees:
                self.log_handler.info(f"  📦 Photos archivées ({ARCHIVE_DOUBLONS_DIR_NAME}): {len(photos_archivees)}")
        elif len(photos_disparues) > 0:
            self.log_handler.info(f"  📦 Photos déplacées/archivées: {len(photos_disparues)} (voir détails ci-dessus)")
        else:
            self.log_handler.success(f"  ✅ Toutes les photos initiales sont traitées ou archivées")
        
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
        
        # Avertissement uniquement si des photos vraiment perdues (ni renommées, ni archivées)
        if photos_reellement_disparues:
            self.log_handler.error(f"❌ ATTENTION: Des photos n'ont pas été retrouvées (ni en DCIM ni dans {ARCHIVE_DOUBLONS_DIR_NAME}).")
            self.log_handler.error("Veuillez consulter le rapport détaillé pour plus d'informations.")
        elif photos_archivees and not photos_reellement_disparues:
            self.log_handler.success(f"✅ Aucune perte : les photos « manquantes » sont dans {archive_dir} (mode sécurisé).")
        else:
            self.log_handler.success("✅ Toutes les photos ont été correctement traitées sans perte")
    
    def run_renommage_mode(self):
        """Exécute le mode renommage isolé"""
        self.log_handler.info("📋 Mode Renommage en cours...")
        
        # Paramètres
        dcim_path = get_dcim_path()
        gpkg_file = get_gpkg_path()
        layer_name = get_layer_name()
        
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
        dcim_path = get_dcim_path()
        gpkg_file = get_gpkg_path()
        layer_name = get_layer_name()
        
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
        dcim_path = get_dcim_path()
        gpkg_file = get_gpkg_path()
        layer_name = get_layer_name()
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
        dcim_path = get_dcim_path()
        gpkg_file = get_gpkg_path()
        layer_name = get_layer_name()
        
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
            layer = self.get_layer(gpkg_file, layer_name)
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
        photo_field_idx = layer.fields().indexFromName(get_photo_field_name())
        if photo_field_idx < 0:
            self.log_handler.warning("⚠️  Champ 'photo' introuvable")
            layer.rollBack()
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
                        if abs(point.x() - float(x)) < get_coord_tolerance() and abs(point.y() - float(y)) < get_coord_tolerance():
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
                    
                    photo_existante = existing_feature[get_photo_field_name()] if existing_feature else None
                    old_path = os.path.join(dcim_path, photo_name)
                    
                    if photo_existante and isinstance(photo_existante, str) and photo_existante.strip():
                        # L'entité a déjà une photo valide → supprimer ou archiver le doublon
                        if self._supprimer_ou_archiver_doublon(
                            old_path, f"entité FID {existing_fid} a déjà une photo aux mêmes coordonnées", dcim_path
                        ):
                            photos_corrigees += 1
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
                        # Si le fichier avec le nouveau nom existe déjà, supprimer ou archiver l'ancien
                        self._supprimer_ou_archiver_doublon(
                            old_path, f"fichier {new_photo_name} existe déjà pour entité FID {existing_fid}", dcim_path
                        )
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
                    new_feature[get_photo_field_name()] = f'DCIM/{photo_name}'
                    
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
                            if abs(feat_point.x() - float(x)) < get_coord_tolerance() and abs(feat_point.y() - float(y)) < get_coord_tolerance():
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
        dcim_path = get_dcim_path()
        
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
        self.log_handler.info("📋 Optimisation des images (mode isolé)...")
        
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
        from .operations.backups import create_dcim_backup as _create_dcim_backup

        return _create_dcim_backup(
            dcim_path,
            self.log_handler,
            get_backup_dir(),
            lambda p: self.get_dcim_photos(p),
        )

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
                    photo_field = feature[get_photo_field_name()]
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
                                if abs(point.x() - x) < get_coord_tolerance() and abs(point.y() - y) < get_coord_tolerance():
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
                photo_field = feature[get_photo_field_name()]
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
        from .operations.backups import create_gpkg_backup as _create_gpkg_backup

        return _create_gpkg_backup(gpkg_path, self.log_handler, get_backup_dir())
    
    def get_dcim_photos(self, dcim_path):
        """Récupère les photos dans le dossier DCIM et le dossier de synchronisation QField"""
        from .dcim_utils import list_dcim_photo_basenames

        return list_dcim_photo_basenames(dcim_path)
        
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
        from .layer_utils import load_vector_layer_from_gpkg

        return load_vector_layer_from_gpkg(gpkg_path, layer_name)

    def _extraire_nom_fichier_photo(self, photo_val):
        """Extrait le nom de fichier depuis un champ photo (DCIM/xxx.jpg, file:///path/xxx.jpg, etc.)."""
        if not photo_val or not isinstance(photo_val, str):
            return None
        s = photo_val.strip()
        # Retirer préfixes courants (DCIM/, file://, content://, chemins absolus)
        for prefix in ('DCIM/', 'file://', 'content://'):
            if s.lower().startswith(prefix):
                s = s[len(prefix):].lstrip('/')
        # Prendre le dernier segment du chemin (nom de fichier)
        name = s.split('/')[-1].split('\\')[-1].strip()
        return name if name.lower().endswith(('.jpg', '.jpeg')) else None

    def _get_dcim_search_dirs(self, dcim_path):
        """Retourne les répertoires à fouiller (DCIM principal + .qfieldsync/download/DCIM)."""
        sync_dcim = os.path.join(os.path.dirname(dcim_path), '.qfieldsync', 'download', 'DCIM')
        return [d for d in (dcim_path, sync_dcim) if os.path.isdir(d)]

    def _trouver_photo_par_fid_dans_dcim(self, dcim_path, entity_fid, old_name=None, feature=None):
        """
        Cherche dans DCIM (et .qfieldsync/download/DCIM) un fichier dont le nom contient le FID de l'entité.
        Quand plusieurs photos ont le même FID (sessions différentes), préfère celle qui correspond
        à l'agent de old_name ou au nom_agent de l'entité (ex. maurin_aguirre vs cuenin_chris).
        """
        pattern = f"_{entity_fid}_"
        candidates = []
        seen = set()
        for search_dir in self._get_dcim_search_dirs(dcim_path):
            for f in os.listdir(search_dir):
                if f.lower().endswith(('.jpg', '.jpeg')) and pattern in f and f not in seen:
                    seen.add(f)
                    candidates.append(f)
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        # Plusieurs photos avec le même FID : préférer celle qui correspond à l'agent
        agent_hint = None
        if old_name:
            # Format: DT_YYYY-MM-DD_FID_agent_type_X_Y.jpg → capturer agent (ex. maurin_aguirre)
            match = re.match(r'DT_\d{4}-\d{2}-\d{2}_\d+_([^_]+(?:_[^_]+)?)_', old_name)
            if match:
                agent_hint = match.group(1).lower()
        if not agent_hint and feature is not None:
            nom = feature['nom_agent'] if 'nom_agent' in feature.fields().names() else None
            if nom and str(nom).strip().upper() != 'INCONNU':
                agent_hint = self._sanitize_for_filename(str(nom)).replace(' ', '_').lower()
        if agent_hint:
            parts = [p for p in agent_hint.replace('-', '_').split('_') if len(p) > 1]
            for c in candidates:
                c_lower = c.lower()
                if agent_hint in c_lower or (parts and all(p in c_lower for p in parts)):
                    return c
            self.log_handler.warning(
                f"⚠️ Plusieurs photos avec FID {entity_fid} (sessions différentes). "
                f"Aucune ne correspond à l'agent '{agent_hint}'. Utilisation de la première trouvée."
            )
        return candidates[0]

    def _trouver_photo_par_coord_dans_dcim(self, dcim_path, old_name, entity_fid):
        """
        Cherche dans DCIM un fichier par coordonnées.
        Cas 1: ancien format DT_YYYYMMDD_HHMMSS_X_Y.jpg → photos renommées par le plugin
        peuvent être en DT_YYYY-MM-DD_0_INCONNU_INCONNU_X_Y.jpg ou DT_YYYY-MM-DD_FID_...
        """
        from ..scripts.analyse_orphelines import extraire_coord_du_nom
        _, x_old, y_old = extraire_coord_du_nom(old_name)
        if x_old is None or y_old is None:
            return None
        tol = 0.02  # tolérance pour arrondis (ex. 5985522.246 vs 5985522.25)
        candidates_with_fid = []
        candidates_any = []
        for search_dir in self._get_dcim_search_dirs(dcim_path):
            for f in os.listdir(search_dir):
                if not f.lower().endswith(('.jpg', '.jpeg')):
                    continue
                fid_in_name, x, y = extraire_coord_du_nom(f)
                if x is None or y is None:
                    continue
                if abs(float(x) - float(x_old)) < tol and abs(float(y) - float(y_old)) < tol:
                    if fid_in_name == entity_fid:
                        candidates_with_fid.append(f)
                    else:
                        candidates_any.append(f)
        # Priorité : fichier avec le FID de l'entité, sinon fichier unique par coordonnées
        if candidates_with_fid:
            return candidates_with_fid[0]
        if len(candidates_any) == 1:
            return candidates_any[0]
        # Plusieurs candidats : préférer _0_INCONNU (format intermédiaire du plugin)
        for c in candidates_any:
            if "_0_INCONNU" in c:
                return c
        return candidates_any[0] if candidates_any else None

    def _trouver_photo_par_coord_dans_archive(self, archive_dir, old_name, entity_fid, feature=None):
        """
        Cherche dans l'archive un fichier par coordonnées (format ancien QField ou nouveau).
        Utilise old_name pour les coords, ou la géométrie de l'entité si disponible.
        """
        from ..scripts.analyse_orphelines import extraire_coord_du_nom
        x_ref, y_ref = None, None
        if feature and feature.geometry() and not feature.geometry().isEmpty():
            pt = feature.geometry().asPoint()
            x_ref, y_ref = pt.x(), pt.y()
        if x_ref is None or y_ref is None:
            _, x_ref, y_ref = extraire_coord_du_nom(old_name)
        if x_ref is None or y_ref is None:
            return None
        tol = 0.02
        candidates_with_fid = []
        candidates_any = []
        for f in os.listdir(archive_dir):
            if not f.lower().endswith(('.jpg', '.jpeg')):
                continue
            fid_in_name, x, y = extraire_coord_du_nom(f)
            if x is None or y is None:
                continue
            if abs(float(x) - float(x_ref)) < tol and abs(float(y) - float(y_ref)) < tol:
                if fid_in_name == entity_fid:
                    candidates_with_fid.append(f)
                else:
                    candidates_any.append(f)
        if candidates_with_fid:
            return candidates_with_fid[0]
        if len(candidates_any) == 1:
            return candidates_any[0]
        for c in candidates_any:
            if "_0_INCONNU" in c:
                return c
        return candidates_any[0] if candidates_any else None

    def _chemin_photo_existe(self, dcim_path, filename):
        """Vérifie si la photo existe dans DCIM ou .qfieldsync/download/DCIM. Retourne le chemin complet ou None."""
        for d in self._get_dcim_search_dirs(dcim_path):
            p = os.path.join(d, filename)
            if os.path.isfile(p):
                return p
        return None

    def synchroniser_champs_photo_entites(self, gpkg_file, layer_name, dcim_path=None):
        """
        Met à jour le champ 'photo' de chaque entité pour qu'il pointe vers le nom
        actuel du fichier (après renommage). Corrige les entités qui référencent
        encore un ancien nom de photo. Si le fichier est dans l'archive, le restaure
        dans DCIM avant de mettre à jour.
        Gère aussi les chemins au format QField (file://, etc.) et les cas où
        la photo a été renommée mais le champ n'a pas été mis à jour (recherche par FID).
        Retourne le nombre d'entités mises à jour.
        """
        self.log_handler.info("📋 Synchronisation des champs photo des entités...")
        dcim_path = dcim_path or get_dcim_path()
        try:
            layer = self.get_layer(gpkg_file, layer_name)
            photo_field_idx = layer.fields().indexFromName(get_photo_field_name())
            if photo_field_idx < 0:
                self.log_handler.warning("⚠️  Champ 'photo' introuvable dans la couche")
                return 0
            archive_dir = self._get_archive_doublons_dir(dcim_path)
            archive_list = {}
            if archive_dir and os.path.exists(archive_dir):
                archive_list = {f for f in os.listdir(archive_dir) if f.lower().endswith(('.jpg', '.jpeg'))}
            
            updated = 0
            layer.startEditing()
            for feature in layer.getFeatures():
                photo_val = feature[get_photo_field_name()]
                if not photo_val or not isinstance(photo_val, str):
                    continue
                old_name = self._extraire_nom_fichier_photo(photo_val)
                if not old_name:
                    continue
                new_name = self.log_handler.get_final_photo_name(old_name)
                if not new_name:
                    new_name = old_name
                # Si pas de renommage connu (mapping vide) et fichier absent : chercher par FID puis par coordonnées
                if new_name == old_name and not os.path.exists(os.path.join(dcim_path, old_name)):
                    candidate = self._trouver_photo_par_fid_dans_dcim(
                        dcim_path, feature.id(), old_name=old_name, feature=feature
                    )
                    if not candidate:
                        candidate = self._trouver_photo_par_coord_dans_dcim(dcim_path, old_name, feature.id())
                    if not candidate and archive_dir and os.path.exists(archive_dir) and archive_list:
                        candidate = self._trouver_photo_par_coord_dans_archive(
                            archive_dir, old_name, feature.id(), feature
                        )
                    if candidate:
                        # Vérifier que les coords du candidat correspondent à l'entité (éviter mauvaises associations)
                        from ..scripts.analyse_orphelines import extraire_coord_du_nom as _extraire
                        _, x_cand, y_cand = _extraire(candidate)
                        geom = feature.geometry()
                        if x_cand is not None and y_cand is not None and geom and not geom.isEmpty():
                            pt = geom.asPoint()
                            if abs(pt.x() - float(x_cand)) >= 0.02 or abs(pt.y() - float(y_cand)) >= 0.02:
                                self.log_handler.warning(
                                    f"⚠️  Entité FID {feature.id()}: candidat {candidate} ignoré "
                                    f"(coords {x_cand:.2f},{y_cand:.2f} ≠ entité {pt.x():.2f},{pt.y():.2f})"
                                )
                                candidate = None
                        if candidate:
                            new_name = candidate
                            self.log_handler.info(f"📋 Entité FID {feature.id()}: chemin obsolète ({old_name}) → {new_name}")
                if new_name == old_name:
                    # Fichier absent et aucune correspondance trouvée : avertir (photo peut-être non synchronisée depuis QField)
                    if not os.path.exists(os.path.join(dcim_path, old_name)):
                        self.log_handler.warning(
                            f"⚠️ Entité FID {feature.id()}: photo {old_name} introuvable "
                            "(DCIM, archive, .qfieldsync). Pensez à synchroniser le projet depuis QField."
                        )
                    continue
                # Si FID dans le nouveau nom est valide (!=0) et différent de l'entité, éviter les mauvaises associations
                fid_dans_nom = self._fid_depuis_nom_photo(new_name)
                if fid_dans_nom is not None and fid_dans_nom != 0 and feature.id() != fid_dans_nom:
                    continue
                # Vérifier si le fichier existe (DCIM, .qfieldsync, ou archive)
                new_path = os.path.join(dcim_path, new_name)
                src_path = self._chemin_photo_existe(dcim_path, new_name)
                if src_path and src_path != new_path:
                    # Fichier dans .qfieldsync/download/DCIM : copier vers DCIM
                    try:
                        import shutil
                        shutil.copy2(src_path, new_path)
                        self.log_handler.info(f"📦 Photo copiée depuis .qfieldsync: {new_name}")
                    except Exception as e:
                        self.log_handler.warning(f"⚠️ Impossible de copier {new_name}: {e}")
                        continue
                elif not os.path.exists(new_path) and archive_list:
                    # Fichier dans l'archive : restaurer vers DCIM
                    if new_name in archive_list:
                        src = os.path.join(archive_dir, new_name)
                        if os.path.isfile(src):
                            try:
                                import shutil
                                shutil.copy2(src, new_path)
                                self.log_handler.info(f"📦 Photo restaurée depuis l'archive: {new_name}")
                            except Exception as e:
                                self.log_handler.warning(f"⚠️  Impossible de restaurer {new_name} depuis l'archive: {e}")
                                continue
                    else:
                        self.log_handler.warning(f"⚠️  Fichier {new_name} introuvable (DCIM et archive), entité FID {feature.id()}")
                        continue
                elif not os.path.exists(new_path):
                    self.log_handler.warning(f"⚠️  Fichier {new_name} introuvable, entité FID {feature.id()}")
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
                if getattr(layer, 'isEditable', getattr(layer, 'isEditing', lambda: False))() and hasattr(layer, 'rollBack'):
                    layer.rollBack()
            except (NameError, AttributeError):
                pass
            return 0
    
    def reparer_photos_manquantes_depuis_archive(self, gpkg_file, layer_name, dcim_path=None):
        """
        Pour les entités dont le champ photo pointe vers un fichier absent du DCIM,
        cherche ce fichier dans l'archive (nom exact, chaîne de renommage, ou par coordonnées) et le restaure.
        Retourne le nombre de photos restaurées.
        """
        from ..scripts.analyse_orphelines import extraire_coord_du_nom
        dcim_path = dcim_path or get_dcim_path()
        archive_dir = self._get_archive_doublons_dir(dcim_path)
        if not os.path.isdir(archive_dir):
            return 0
        archive_files = sorted(f for f in os.listdir(archive_dir) if f.lower().endswith(('.jpg', '.jpeg')))
        if not archive_files:
            return 0
        import shutil
        restored = 0
        try:
            layer = self.get_layer(gpkg_file, layer_name)
            photo_idx = layer.fields().indexFromName(get_photo_field_name())
            if photo_idx < 0:
                return 0
            for feature in layer.getFeatures():
                photo_val = feature[get_photo_field_name()]
                if not photo_val or not isinstance(photo_val, str):
                    continue
                filename = photo_val.replace('DCIM/', '').strip()
                if not filename.lower().endswith(('.jpg', '.jpeg')):
                    continue
                dcim_path_file = os.path.join(dcim_path, filename)
                if os.path.isfile(dcim_path_file):
                    continue
                # Fichier absent du DCIM : chercher dans l'archive
                cand = filename
                if cand in archive_files:
                    src = os.path.join(archive_dir, cand)
                    try:
                        shutil.copy2(src, dcim_path_file)
                        restored += 1
                        self.log_handler.info(f"📦 Photo restaurée depuis l'archive: {filename} (entité FID {feature.id()})")
                    except Exception as e:
                        self.log_handler.warning(f"⚠️  Impossible de restaurer {filename}: {e}")
                    continue
                # Essayer le nom après renommage (chaîne enregistrée)
                final_name = self.log_handler.get_final_photo_name(filename)
                if final_name and final_name != filename and final_name in archive_files:
                    src = os.path.join(archive_dir, final_name)
                    dest = os.path.join(dcim_path, final_name)
                    try:
                        shutil.copy2(src, dest)
                        layer.startEditing()
                        layer.changeAttributeValue(feature.id(), photo_idx, f'DCIM/{final_name}')
                        layer.commitChanges()
                        restored += 1
                        self.log_handler.info(f"📦 Photo restaurée: {filename} → {final_name} (entité FID {feature.id()})")
                    except Exception as e:
                        self.log_handler.warning(f"⚠️  Impossible de restaurer {final_name}: {e}")
                    continue
                # Fallback : chercher par coordonnées (entité ou nom de fichier)
                x_ref, y_ref = None, None
                if feature.geometry() and not feature.geometry().isEmpty():
                    pt = feature.geometry().asPoint()
                    x_ref, y_ref = pt.x(), pt.y()
                else:
                    _, x_ref, y_ref = extraire_coord_du_nom(filename)
                if x_ref is not None and y_ref is not None:
                    for arch_name in archive_files:
                        _, x_a, y_a = extraire_coord_du_nom(arch_name)
                        if x_a is not None and y_a is not None:
                            if abs(float(x_a) - float(x_ref)) < get_coord_tolerance() and abs(float(y_a) - float(y_ref)) < get_coord_tolerance():
                                src = os.path.join(archive_dir, arch_name)
                                dest = os.path.join(dcim_path, arch_name)
                                try:
                                    shutil.copy2(src, dest)
                                    layer.startEditing()
                                    layer.changeAttributeValue(feature.id(), photo_idx, f'DCIM/{arch_name}')
                                    layer.commitChanges()
                                    restored += 1
                                    self.log_handler.info(f"📦 Photo restaurée par coords: {filename} → {arch_name} (entité FID {feature.id()})")
                                except Exception as e:
                                    self.log_handler.warning(f"⚠️  Impossible de restaurer {arch_name}: {e}")
                                break
        except Exception as e:
            self.log_handler.error(f"❌ Erreur réparation depuis archive: {e}")
        return restored
    
    def clean_inconsistent_photo_fields(self, gpkg_file, layer_name):
        """
        Vide le champ 'photo' des entités dans les cas suivants :
        1) FID dans le nom de fichier ≠ FID réel de l'entité
        2) FID correspond mais coordonnées différentes (collision FID, ex. 555 maurin vs 555 cuenin)
        Pour les fichiers orphelins ainsi créés :
        - Si une entité existe aux mêmes coordonnées → associer ou supprimer doublon
        - Sinon → crée une nouvelle entité pour la photo orpheline
        Retourne le nombre d'entités modifiées.
        """
        self.log_handler.info("🔍 Recherche des champs photo incohérents (FID nom ≠ FID entité)...")
        dcim_path = get_dcim_path()
        layer = self.get_layer(gpkg_file, layer_name)
        photo_idx = layer.fields().indexFromName(get_photo_field_name())
        if photo_idx < 0:
            self.log_handler.warning("⚠️  Champ 'photo' introuvable dans la couche")
            return 0
        
        from ..scripts.analyse_orphelines import extraire_coord_du_nom
        
        TOL = 0.02  # tolérance coordonnées (aligné avec reconcilier_photos)
        updated = 0
        fichiers_orphelins = []  # Liste des fichiers qui deviennent orphelins
        
        layer.startEditing()
        for feature in layer.getFeatures():
            photo_val = feature[get_photo_field_name()]
            if not photo_val or not isinstance(photo_val, str):
                continue
            filename = photo_val.replace('DCIM/', '').strip().split('/')[-1]
            fid_in_name = self._fid_depuis_nom_photo(filename)
            if fid_in_name is None:
                continue
            # Incohérence 1: FID dans le nom ≠ FID de l'entité
            if fid_in_name != feature.id():
                self.log_handler.warning(
                    f"⚠️  Incohérence FID pour entité {feature.id()}: "
                    f"champ photo → {filename} (FID {fid_in_name})"
                )
                _, x_orphan, y_orphan = extraire_coord_du_nom(filename)
                if x_orphan is not None and y_orphan is not None:
                    if not any(f[0] == filename for f in fichiers_orphelins):
                        fichiers_orphelins.append((filename, x_orphan, y_orphan, feature.id()))
                layer.changeAttributeValue(feature.id(), photo_idx, None)
                updated += 1
                continue
            # Incohérence 2: FID correspond mais coordonnées différentes (collision FID, ex. 555 maurin vs 555 cuenin)
            _, x_photo, y_photo = extraire_coord_du_nom(filename)
            if x_photo is not None and y_photo is not None:
                geom = feature.geometry()
                if geom and not geom.isEmpty():
                    pt = geom.asPoint()
                    if abs(pt.x() - float(x_photo)) >= TOL or abs(pt.y() - float(y_photo)) >= TOL:
                        self.log_handler.warning(
                            f"⚠️  Collision FID pour entité {feature.id()}: champ photo → {filename} "
                            f"(coords photo: {x_photo:.2f},{y_photo:.2f} ≠ entité: {pt.x():.2f},{pt.y():.2f})"
                        )
                        # Éviter doublon si le même fichier est référencé par plusieurs entités
                        if not any(f[0] == filename for f in fichiers_orphelins):
                            fichiers_orphelins.append((filename, float(x_photo), float(y_photo), feature.id()))
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
                        if abs(point.x() - float(x_orphan)) < get_coord_tolerance() and abs(point.y() - float(y_orphan)) < get_coord_tolerance():
                            entite_existante_meme_coord = feature
                            break
                
                if entite_existante_meme_coord:
                    # Une entité existe aux mêmes coordonnées
                    photo_existante = entite_existante_meme_coord[get_photo_field_name()]
                    if photo_existante and isinstance(photo_existante, str):
                        # L'entité a déjà une photo valide → supprimer ou archiver le doublon
                        if self._supprimer_ou_archiver_doublon(
                            file_path,
                            f"entité FID {entite_existante_meme_coord.id()} a déjà une photo aux mêmes coordonnées",
                        ):
                            fichiers_supprimes += 1
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
                        new_feature[get_photo_field_name()] = f'DCIM/{filename}'
                        
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

    def reconcilier_photos_avec_entites(self, gpkg_file, layer_name, dcim_path):
        """
        Pour chaque photo dans DCIM :
        - Si attachée à une entité : vérifie que les coordonnées correspondent (tolérance 0.02).
          Si non : vide le champ photo de l'entité (mauvaise association).
        - Si non attachée : cherche une entité par FID (si dans le nom) ou par coordonnées.
          Si trouvée : attache la photo. Sinon : crée une entité.
        Retourne (nb_verif, nb_attachees, nb_creees).
        """
        from ..scripts.analyse_orphelines import extraire_coord_du_nom
        
        layer = self.get_layer(gpkg_file, layer_name)
        photo_idx = layer.fields().indexFromName(get_photo_field_name())
        if photo_idx < 0:
            self.log_handler.warning("⚠️  Champ 'photo' introuvable dans la couche")
            return 0, 0, 0
        
        if not os.path.exists(dcim_path):
            self.log_handler.error(f"❌ Dossier DCIM introuvable: {dcim_path}")
            return 0, 0, 0
        
        photos = [f for f in os.listdir(dcim_path) if f.lower().endswith(('.jpg', '.jpeg'))]
        self.log_handler.info(f"📷 {len(photos)} photos à traiter dans DCIM")
        
        # Construire photo -> entités qui la référencent
        photo_to_entities = {}
        for feature in layer.getFeatures():
            photo_val = feature[get_photo_field_name()]
            if not photo_val or not isinstance(photo_val, str):
                continue
            filename = photo_val.replace('DCIM/', '').strip().split('/')[-1]
            if filename not in photo_to_entities:
                photo_to_entities[filename] = []
            photo_to_entities[filename].append(feature.id())
        
        TOL = 0.02
        nb_verif, nb_attachees, nb_creees = 0, 0, 0
        layer.startEditing()
        
        for photo_name in photos:
            fid, x, y = extraire_coord_du_nom(photo_name)
            if x is None or y is None:
                self.log_handler.debug(f"ℹ️  Format non reconnu, ignoré: {photo_name}")
                continue
            
            entity_ids = list(photo_to_entities.get(photo_name, []))
            still_correctly_attached = False
            
            # Phase 1 : si attachée, vérifier les coordonnées
            for eid in entity_ids:
                feat = next((f for f in layer.getFeatures() if f.id() == eid), None)
                if not feat or not feat.geometry() or feat.geometry().isEmpty():
                    continue
                pt = feat.geometry().asPoint()
                if abs(pt.x() - float(x)) < TOL and abs(pt.y() - float(y)) < TOL:
                    nb_verif += 1
                    still_correctly_attached = True
                else:
                    # Mauvaise association : coordonnées ne correspondent pas
                    self.log_handler.warning(
                        f"⚠️  Photo {photo_name} attachée à entité FID {eid} mais coordonnées différentes "
                        f"(photo: {x:.2f},{y:.2f} vs entité: {pt.x():.2f},{pt.y():.2f}). Champ photo vidé."
                    )
                    layer.changeAttributeValue(eid, photo_idx, None)
            
            if still_correctly_attached:
                continue  # Photo correctement attachée, passer à la suivante
            
            # Phase 2 : photo non attachée → trouver ou créer entité
            entite_trouvee = None
            
            # Chercher par FID si présent et != 0, MAIS vérifier que les coordonnées correspondent
            # (évite les collisions FID : deux photos avec même FID mais sessions différentes)
            if fid is not None and fid != 0:
                for feature in layer.getFeatures():
                    if feature.id() == fid and feature.geometry() and not feature.geometry().isEmpty():
                        pt = feature.geometry().asPoint()
                        if abs(pt.x() - float(x)) < TOL and abs(pt.y() - float(y)) < TOL:
                            entite_trouvee = feature
                            break
                        # FID trouvé mais coords différentes = collision (ex. 555 maurin vs 555 cuenin)
                        self.log_handler.debug(
                            f"ℹ️  FID {fid} trouvé mais coords différentes (photo: {x:.2f},{y:.2f}), "
                            f"recherche par coordonnées..."
                        )
                        break  # Ne pas attacher à cette entité
            
            # Sinon chercher par coordonnées
            if entite_trouvee is None:
                for feature in layer.getFeatures():
                    if feature.geometry() and not feature.geometry().isEmpty():
                        pt = feature.geometry().asPoint()
                        if abs(pt.x() - float(x)) < TOL and abs(pt.y() - float(y)) < TOL:
                            entite_trouvee = feature
                            break
            
            if entite_trouvee:
                photo_existante = entite_trouvee[get_photo_field_name()]
                existant = (photo_existante.split('/')[-1].strip() if photo_existante else None)
                if existant and existant.lower() == photo_name.lower():
                    continue  # Déjà la bonne photo
                # Ne pas écraser si l'entité a déjà une photo valide aux mêmes coordonnées
                if existant:
                    existant_path = os.path.join(dcim_path, existant)
                    if os.path.exists(existant_path):
                        _, x_ex, y_ex = extraire_coord_du_nom(existant)
                        if x_ex is not None and abs(float(x_ex) - float(x)) < TOL and abs(float(y_ex) - float(y)) < TOL:
                            self.log_handler.info(
                                f"ℹ️  Entité FID {entite_trouvee.id()} a déjà une photo valide aux mêmes coords, "
                                f"photo orpheline {photo_name} non attachée (possible doublon)"
                            )
                            continue
                # Attacher la photo
                layer.changeAttributeValue(entite_trouvee.id(), photo_idx, f'DCIM/{photo_name}')
                nb_attachees += 1
                self.log_handler.success(
                    f"✅ Photo {photo_name} attachée à entité FID {entite_trouvee.id()}"
                )
            else:
                # Créer une nouvelle entité
                try:
                    from qgis.core import QgsFeature, QgsGeometry, QgsPointXY
                    new_feature = QgsFeature(layer.fields())
                    
                    date_str = None
                    agent, type_saisie = 'INCONNU', 'INCONNU'
                    m_std = re.match(r'DT_(\d{4}-\d{2}-\d{2})_(\d+)_([^_]+)_([^_]+)_', photo_name)
                    m_ancien = re.match(r'DT_(\d{4})(\d{2})(\d{2})_', photo_name)
                    if m_std:
                        date_str = m_std.group(1)
                        agent = m_std.group(3).replace('_', ' ')
                        type_saisie = m_std.group(4).replace('_', ' ')
                    elif m_ancien:
                        date_str = f"{m_ancien.group(1)}-{m_ancien.group(2)}-{m_ancien.group(3)}"
                    
                    new_feature['date_saisie'] = f"{date_str}T00:00:00" if date_str else None
                    new_feature['x_saisie'] = float(x)
                    new_feature['y_saisie'] = float(y)
                    new_feature['nom_agent'] = agent
                    new_feature['type_saisie'] = type_saisie
                    new_feature[get_photo_field_name()] = f'DCIM/{photo_name}'
                    new_feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(float(x), float(y))))
                    
                    if layer.addFeature(new_feature):
                        nb_creees += 1
                        self.log_handler.success(
                            f"✅ Nouvelle entité créée pour photo orpheline: {photo_name}"
                        )
                except Exception as e:
                    self.log_handler.error(f"❌ Erreur création entité pour {photo_name}: {e}")
        
        try:
            layer.commitChanges()
        except Exception as e:
            self.log_handler.error(f"❌ Erreur commit: {e}")
            if hasattr(layer, 'rollBack'):
                layer.rollBack()
        
        return nb_verif, nb_attachees, nb_creees

    def renommer_photos(self, dcim_path, layer):
        """Renomme les photos selon le format standard"""
        self.log_handler.info("📋 Renommage des photos...")
        
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
        from .photo_patterns import fid_from_photo_filename

        return fid_from_photo_filename(photo_name)

    def _mettre_a_jour_couche_photos(self, layer, old_name, new_name):
        """Met à jour la référence photo pour toute entité qui référence old_name.
        Quand le nouveau nom a FID=0, les entités concernées peuvent avoir un FID différent (ex. 521, 522)
        car l'entité a été créée aux mêmes coordonnées avant que le FID soit assigné."""
        try:
            photo_idx = layer.fields().indexFromName(get_photo_field_name())
            if photo_idx < 0:
                return
            fid_dans_nom = self._fid_depuis_nom_photo(new_name)
            layer.startEditing()
            for feature in layer.getFeatures():
                photo_field = feature[get_photo_field_name()]
                if not photo_field or old_name not in photo_field:
                    continue
                # Si FID dans le nouveau nom est valide et différent de l'entité, éviter les mauvaises associations
                # (sauf quand FID=0 : la photo n'a pas encore de FID assigné, l'entité existe aux mêmes coords)
                if fid_dans_nom is not None and fid_dans_nom != 0 and feature.id() != fid_dans_nom:
                    continue
                new_photo_path = photo_field.replace(old_name, new_name)
                layer.changeAttributeValue(feature.id(), photo_idx, new_photo_path)
                self.log_handler.info(f"📋 Mise à jour de l'entité {feature.id()}: {old_name} → {new_name}")
            
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
        photo_idx = layer.fields().indexFromName(get_photo_field_name())
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
                photo_val = feature[get_photo_field_name()]
                if not photo_val or not isinstance(photo_val, str):
                    continue
                old_name = photo_val.replace('DCIM/', '').strip().split('/')[-1]
                if not old_name.lower().endswith(('.jpg', '.jpeg')):
                    continue
                old_path = os.path.join(dcim_path, old_name)
                if not os.path.exists(old_path):
                    continue
                # Vérifier que les coordonnées de la photo correspondent à l'entité (éviter mauvaises associations)
                _, x_photo, y_photo = extraire_coord_du_nom(old_name)
                if x_photo is not None and y_photo is not None:
                    geom_check = feature.geometry()
                    pt = geom_check.asPoint() if geom_check and not geom_check.isEmpty() else None
                    if pt and (abs(pt.x() - float(x_photo)) >= 0.02 or abs(pt.y() - float(y_photo)) >= 0.02):
                        self.log_handler.warning(
                            f"⚠️  Entité FID {feature.id()}: photo {old_name} ignorée (coords photo "
                            f"{x_photo:.2f},{y_photo:.2f} ≠ entité {pt.x():.2f},{pt.y():.2f})"
                        )
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
                        
                        # Si l'ancien fichier existe toujours et que c'est un doublon (mêmes coordonnées), le supprimer ou archiver
                        if os.path.exists(old_path):
                            _, x_old, y_old = extraire_coord_du_nom(old_name)
                            if x_old is not None and y_old is not None:
                                if abs(float(x_old) - float(x)) < get_coord_tolerance() and abs(float(y_old) - float(y)) < get_coord_tolerance():
                                    self._supprimer_ou_archiver_doublon(old_path, f"mêmes coordonnées que {new_name}", dcim_path)
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
            if getattr(layer, 'isEditable', getattr(layer, 'isEditing', lambda: False))() and hasattr(layer, 'rollBack'):
                layer.rollBack()
            return renamed_count
        return renamed_count

    def creer_entites_pour_photos_orphelines_avec_fid(self, dcim_path, layer):
        """Rattache les photos orphelines aux entités existantes (champ photo) ou crée des entités si le FID n'existe pas.
        Vérifie les coordonnées avant de rattacher par FID pour éviter les collisions (ex. 555 maurin vs 555 cuenin)."""
        from ..scripts.analyse_orphelines import extraire_coord_du_nom

        self.log_handler.info("📋 Détection et création d'entités pour photos orphelines avec FID...")
        
        # D'abord, obtenir la liste des FID existants et l'index du champ photo
        fid_existants = set()
        for feature in layer.getFeatures():
            fid_existants.add(feature.id())
        
        photo_field_idx = layer.fields().indexFromName(get_photo_field_name())
        if photo_field_idx < 0:
            self.log_handler.warning("⚠️  Champ 'photo' introuvable dans la couche")
            return 0
        
        TOL = 0.02  # tolérance pour coordonnées (aligné avec reconcilier_photos_avec_entites)
        
        # 1) Rattacher les photos dont le FID existe déjà : remplir le champ photo de l'entité (plus d'orphelines)
        # Vérification des coordonnées obligatoire pour éviter les collisions FID (sessions différentes)
        rattachees = 0
        layer.startEditing()
        for filename in os.listdir(dcim_path):
            if not filename.lower().endswith(('.jpg', '.jpeg')):
                continue
            fid = self._fid_depuis_nom_photo(filename)
            if fid is None or fid not in fid_existants:
                continue
            # Extraire les coordonnées de la photo pour vérification
            _, x_photo, y_photo = extraire_coord_du_nom(filename)
            if x_photo is None or y_photo is None:
                self.log_handler.debug(f"ℹ️  Photo {filename}: format sans coordonnées, ignorée pour rattachement par FID")
                continue
            # Entité existante pour ce FID : vérifier si la photo est déjà associée
            feature = None
            for f in layer.getFeatures():
                if f.id() == fid:
                    feature = f
                    break
            if not feature:
                continue
            # Vérifier que les coordonnées de l'entité correspondent à celles de la photo
            geom = feature.geometry()
            if not geom or geom.isEmpty():
                self.log_handler.debug(f"ℹ️  Entité FID {fid}: pas de géométrie, rattachement par FID ignoré (éviter collision)")
                continue
            pt = geom.asPoint()
            if abs(pt.x() - float(x_photo)) >= TOL or abs(pt.y() - float(y_photo)) >= TOL:
                self.log_handler.debug(
                    f"ℹ️  Photo {filename} (FID {fid}): coordonnées différentes "
                    f"(photo: {x_photo:.2f},{y_photo:.2f} vs entité: {pt.x():.2f},{pt.y():.2f}), "
                    f"rattachement ignoré (collision FID)"
                )
                continue
            photo_val = feature[get_photo_field_name()]
            current = (photo_val.split('/')[-1].strip() if photo_val and isinstance(photo_val, str) else None)
            if current and current.lower() == filename.lower():
                continue
            # Rattacher cette photo à l'entité (coordonnées vérifiées)
            layer.changeAttributeValue(fid, photo_field_idx, f'DCIM/{filename}')
            rattachees += 1
            self.log_handler.info(f"  Entité FID {fid}: champ photo rattaché → {filename}")
        if rattachees:
            try:
                layer.commitChanges()
                self.log_handler.info(f"✅ {rattachees} photo(s) orpheline(s) rattachée(s) à une entité existante (champ photo rempli)")
            except Exception as e:
                self.log_handler.error(f"❌ Erreur commit rattachement: {e}")
                if hasattr(layer, 'rollBack'):
                    layer.rollBack()
        else:
            if getattr(layer, 'isEditable', getattr(layer, 'isEditing', lambda: False))() and hasattr(layer, 'rollBack'):
                layer.rollBack()
        
        # 2) Lister les photos orphelines avec FID valide mais pas d'entité correspondante (création)
        photos_orphelines_avec_fid = []
        for filename in os.listdir(dcim_path):
            if filename.lower().endswith('.jpg'):
                match = re.match(r'DT_(\d{4}-\d{2}-\d{2})_(\d+)_([^_]+)_([^_]+)_([-+]?\d+\.?\d*)_([-+]?\d+\.?\d*)\.jpg', filename)
                if match:
                    fid = int(match.group(2))
                    if fid not in fid_existants:
                        date_str = match.group(1)
                        agent = match.group(3).replace('_', ' ')
                        type_saisie = match.group(4).replace('_', ' ')
                        x = float(match.group(5))
                        y = float(match.group(6))
                        photos_orphelines_avec_fid.append((filename, date_str, fid, agent, type_saisie, x, y))
        
        if not photos_orphelines_avec_fid:
            if rattachees == 0:
                self.log_handler.info("ℹ️  Aucune photo orpheline avec FID nécessitant traitement (toutes déjà rattachées ou sans FID valide)")
            # Retourner 0 pour ne pas afficher "X entités créées" (on a seulement rattaché des photos)
            return 0
        
        self.log_handler.warning(f"⚠️  {len(photos_orphelines_avec_fid)} photos orphelines avec FID à traiter")
        
        # Démarrer l'édition de la couche
        layer.startEditing()
        photo_field_idx = layer.fields().indexFromName(get_photo_field_name())
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
                        if abs(point.x() - float(x)) < get_coord_tolerance() and abs(point.y() - float(y)) < get_coord_tolerance():
                            entite_existante_meme_coord = feature
                            break
                
                if entite_existante_meme_coord:
                    # Une entité existe déjà aux mêmes coordonnées
                    photo_existante = entite_existante_meme_coord[get_photo_field_name()]
                    file_path = os.path.join(dcim_path, photo_name)
                    existant_filename = (photo_existante.split('/')[-1].strip() if photo_existante and isinstance(photo_existante, str) else None)
                    existant_path = os.path.join(dcim_path, existant_filename) if existant_filename else None
                    
                    if photo_existante and isinstance(photo_existante, str):
                        # Vérifier si la photo actuelle de l'entité existe réellement (DCIM ou archive)
                        archive_dir = self._get_archive_doublons_dir(dcim_path)
                        existant_dans_archive = (os.path.isfile(os.path.join(archive_dir, existant_filename)) if existant_filename and os.path.exists(archive_dir) else False)
                        if not existant_path or (not os.path.exists(existant_path) and not existant_dans_archive):
                            # La photo référencée n'existe pas : mettre à jour l'entité avec notre fichier au lieu d'archiver
                            if os.path.exists(file_path):
                                try:
                                    layer.startEditing()
                                    layer.changeAttributeValue(entite_existante_meme_coord.id(), photo_field_idx, f'DCIM/{photo_name}')
                                    layer.commitChanges()
                                    self.log_handler.success(
                                        f"✅ Entité FID {entite_existante_meme_coord.id()}: champ photo mis à jour "
                                        f"({existant_filename or 'vide'} → {photo_name})"
                                    )
                                except Exception as e:
                                    self.log_handler.error(f"❌ Erreur mise à jour entité {entite_existante_meme_coord.id()}: {e}")
                            continue
                        # L'entité a déjà une photo valide → supprimer ou archiver le doublon
                        self._supprimer_ou_archiver_doublon(
                            file_path,
                            f"entité FID {entite_existante_meme_coord.id()} existe déjà aux mêmes coordonnées",
                            dcim_path,
                        )
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
                new_feature[get_photo_field_name()] = f'DCIM/{photo_name}'
                
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
                        if (abs(feat_point.x() - float(x)) < get_coord_tolerance() and 
                            abs(feat_point.y() - float(y)) < get_coord_tolerance()):
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
                if getattr(layer, 'isEditable', getattr(layer, 'isEditing', lambda: False))():
                    if hasattr(layer, 'rollBack'):
                        layer.rollBack()
        
        # Sauvegarder les modifications finales si on est encore en édition
        if getattr(layer, 'isEditable', getattr(layer, 'isEditing', lambda: False))():
            layer.commitChanges()
        self.log_handler.success(f"✅ {entites_creees}/{len(photos_orphelines_avec_fid)} entités créées pour photos orphelines avec FID")
        return entites_creees

    def creer_entites_pour_orphelines(self, dcim_path, layer):
        """Crée des entités pour les photos orphelines (uniquement les fichiers présents dans dcim_path)."""
        self.log_handler.info("📋 Création d'entités pour les photos orphelines...")
        
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
                        photo_existante = existing_feature[get_photo_field_name()] if existing_feature else None
                        
                        if photo_existante and isinstance(photo_existante, str) and photo_existante.strip():
                            # L'entité a déjà une photo valide → supprimer ou archiver le doublon
                            self._supprimer_ou_archiver_doublon(
                                file_path,
                                f"entité FID {existing_fid} a déjà une photo aux mêmes coordonnées",
                                dcim_path,
                            )
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
                                        photo_field_idx = layer.fields().indexFromName(get_photo_field_name())
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
                                photo_field_idx = layer.fields().indexFromName(get_photo_field_name())
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
                    new_feature[get_photo_field_name()] = f'DCIM/{photo_name}'
                    
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
                            if (abs(feat_point.x() - float(x)) < get_coord_tolerance() and 
                                abs(feat_point.y() - float(y)) < get_coord_tolerance()):
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
                    photo_field_idx = layer.fields().indexFromName(get_photo_field_name())
                    
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
