#!/usr/bin/env python3
"""Sauvegardes DCIM et GeoPackage."""

import os
import shutil
from datetime import datetime


def create_dcim_backup(dcim_path, log_handler, backup_dir, list_dcim_photo_basenames_fn):
    """Copie le dossier DCIM vers backup_dir. list_dcim_photo_basenames_fn(dcim_path) -> liste de noms."""
    try:
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"DCIM_backup_{timestamp}"
        backup_path = os.path.join(backup_dir, backup_name)

        log_handler.info(f"💾 Création de la sauvegarde: {backup_path}")
        shutil.copytree(dcim_path, backup_path)

        if os.path.exists(backup_path):
            photos_in_backup = len(
                [
                    f
                    for f in os.listdir(backup_path)
                    if f.lower().endswith((".jpg", ".jpeg"))
                ]
            )
            photos_in_original = len(list_dcim_photo_basenames_fn(dcim_path))

            if photos_in_backup == photos_in_original:
                log_handler.success(
                    f"✅ Sauvegarde de sécurité créée: {photos_in_backup} photos sauvegardées"
                )
                log_handler.info(f"   Emplacement: {backup_path}")
                log_handler.info(
                    "   💡 Cette sauvegarde permet de restaurer les photos en cas de problème"
                )
                return True
            log_handler.error(
                f"❌ Échec de la sauvegarde: {photos_in_backup}/{photos_in_original} photos seulement"
            )
            log_handler.warning(
                "   Le traitement continuera mais sans filet de sécurité"
            )
            return False
        log_handler.error("❌ Échec de la création de la sauvegarde")
        return False
    except Exception as e:
        log_handler.error(f"❌ Erreur lors de la sauvegarde: {e}")
        return False


def create_gpkg_backup(gpkg_path, log_handler, backup_dir):
    """Copie le fichier .gpkg vers backup_dir."""
    try:
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"donnees_terrain_backup_{timestamp}.gpkg"
        backup_path = os.path.join(backup_dir, backup_name)

        log_handler.info(f"💾 Création de la sauvegarde GeoPackage: {backup_path}")
        shutil.copy2(gpkg_path, backup_path)

        if os.path.exists(backup_path):
            log_handler.success(f"✅ Sauvegarde GeoPackage créée: {backup_path}")
            log_handler.info(
                "   💡 Cette sauvegarde permet de restaurer les données en cas de problème"
            )
            return True
        log_handler.error("❌ Échec de la création de la sauvegarde GeoPackage")
        return False
    except Exception as e:
        log_handler.error(f"❌ Erreur lors de la sauvegarde GeoPackage: {e}")
        return False
