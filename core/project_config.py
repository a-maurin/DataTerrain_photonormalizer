#!/usr/bin/env python3
"""
Configuration centralisée : chemins DataTerrain, nom de couche, champs, tolérances.
Sous QGIS : résolution via dossier du projet, paramètres persistés ou dossier choisi par l'utilisateur.
"""

import os
import sys

# ——— Données métier (couche GPKG) ———
GPKG_FILENAME = "donnees_terrain.gpkg"
LAYER_NAME = "saisies_terrain"
PHOTO_FIELD_NAME = "photo"
COORD_TOLERANCE = 0.01
COORD_KEY_DECIMALS = 2

SETTINGS_NAMESPACE = "DataTerrainPhotoNormalizer"
SETTINGS_KEY_PROJECT_BASE = f"{SETTINGS_NAMESPACE}/project_base"

# Répertoire par défaut si aucune résolution dynamique
if sys.platform == "win32":
    PROJECT_BASE_PATH = r"C:\Users\aguirre.maurin\QField\cloud\DataTerrain"
else:
    PROJECT_BASE_PATH = "/home/e357/Qfield/cloud/DataTerrain"

CLOUD_BASE_PATH = os.path.dirname(PROJECT_BASE_PATH)

_runtime_project_base = None


def is_valid_dataterrain_root(path):
    """True si le dossier contient DCIM/ et le fichier GeoPackage attendu."""
    if not path or not os.path.isdir(path):
        return False
    dcim = os.path.join(path, "DCIM")
    gpkg = os.path.join(path, GPKG_FILENAME)
    return os.path.isdir(dcim) and os.path.isfile(gpkg)


def resolve_dataterrain_from_home(home_path):
    """Si le .qgz/.qgs est dans DataTerrain ou dans un parent, retourne le chemin DataTerrain."""
    if not home_path or not os.path.isdir(home_path):
        return None
    home_path = os.path.abspath(home_path)
    if is_valid_dataterrain_root(home_path):
        return home_path
    sub = os.path.join(home_path, "DataTerrain")
    if is_valid_dataterrain_root(sub):
        return os.path.abspath(sub)
    return None


def set_runtime_project_base(path):
    global _runtime_project_base
    if path:
        _runtime_project_base = os.path.abspath(path)
    else:
        _runtime_project_base = None


def clear_runtime_project_base():
    global _runtime_project_base
    _runtime_project_base = None


def persist_project_base(path):
    try:
        from qgis.PyQt.QtCore import QSettings

        QSettings().setValue(SETTINGS_KEY_PROJECT_BASE, path or "")
    except ImportError:
        pass


def load_persisted_project_base():
    try:
        from qgis.PyQt.QtCore import QSettings

        v = QSettings().value(SETTINGS_KEY_PROJECT_BASE, "", type=str)
        if v and is_valid_dataterrain_root(v):
            return os.path.abspath(v)
    except ImportError:
        pass
    return None


def refresh_paths_from_qgis():
    """
    À appeler au lancement du plugin (ou avant les modes).
    Ordre : base runtime déjà valide → QSettings → dossier du projet QGIS → défaut.
    """
    global _runtime_project_base
    if _runtime_project_base and is_valid_dataterrain_root(_runtime_project_base):
        return _runtime_project_base
    persisted = load_persisted_project_base()
    if persisted:
        _runtime_project_base = persisted
        return _runtime_project_base
    try:
        from qgis.core import QgsProject

        resolved = resolve_dataterrain_from_home(QgsProject.instance().homePath())
        if resolved:
            _runtime_project_base = resolved
            return _runtime_project_base
    except ImportError:
        pass
    return None


def get_project_base():
    if _runtime_project_base and is_valid_dataterrain_root(_runtime_project_base):
        return os.path.abspath(_runtime_project_base)
    if is_valid_dataterrain_root(PROJECT_BASE_PATH):
        return os.path.abspath(PROJECT_BASE_PATH)
    return os.path.abspath(PROJECT_BASE_PATH)


def get_cloud_base():
    return os.path.dirname(get_project_base())


def get_dcim_path():
    return os.path.join(get_project_base(), "DCIM")


def get_gpkg_path():
    return os.path.join(get_project_base(), GPKG_FILENAME)


def get_backup_dir():
    return os.path.join(get_cloud_base(), "donnee_terrain_backups")


def get_layer_name():
    return LAYER_NAME


def get_photo_field_name():
    return PHOTO_FIELD_NAME


def get_coord_tolerance():
    return COORD_TOLERANCE


def get_coord_key_decimals():
    return COORD_KEY_DECIMALS
