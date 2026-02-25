#!/usr/bin/env python3
"""
Configuration centralisée des chemins du projet DataTerrain.
Permet le fonctionnement du plugin sous Linux et Windows sans altérer la logique métier.
"""

import os
import sys

# Répertoire de base du projet et du cloud selon l'OS
if sys.platform == "win32":
    PROJECT_BASE_PATH = r"C:\Users\aguirre.maurin\QField\cloud\DataTerrain"
    CLOUD_BASE_PATH = r"C:\Users\aguirre.maurin\QField\cloud"
else:
    PROJECT_BASE_PATH = "/home/e357/Qfield/cloud/DataTerrain"
    CLOUD_BASE_PATH = "/home/e357/Qfield/cloud"


def get_project_base():
    """Chemin du répertoire du projet DataTerrain."""
    return PROJECT_BASE_PATH


def get_cloud_base():
    """Chemin du répertoire cloud (parent du projet)."""
    return CLOUD_BASE_PATH


def get_dcim_path():
    """Chemin du dossier DCIM des photos."""
    return os.path.join(PROJECT_BASE_PATH, "DCIM")


def get_gpkg_path():
    """Chemin du fichier GeoPackage donnees_terrain.gpkg."""
    return os.path.join(PROJECT_BASE_PATH, "donnees_terrain.gpkg")


def get_backup_dir():
    """Chemin du dossier des sauvegardes GeoPackage."""
    return os.path.join(CLOUD_BASE_PATH, "donnee_terrain_backups")
