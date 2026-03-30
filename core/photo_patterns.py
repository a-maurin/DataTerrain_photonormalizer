#!/usr/bin/env python3
"""
Extraction FID / coordonnées depuis les noms de fichiers standard DT_...
Logique partagée entre scripts et tests (sans dépendance QGIS).
"""

import re


def fid_from_photo_filename(photo_name):
    """Extrait le FID du nom (format DT_YYYY-MM-DD_FID_...). Retourne None si absent."""
    if not photo_name or not isinstance(photo_name, str):
        return None
    match = re.match(r"DT_\d{4}-\d{2}-\d{2}_(\d+)_", photo_name)
    return int(match.group(1)) if match else None


def group_contains_duplicate_same_fid(photo_list):
    """
    True si le groupe contient au moins deux FID identiques dans le nom (sessions différentes).
    """
    fids = [f for f in (fid_from_photo_filename(p) for p in photo_list) if f is not None]
    return len(fids) != len(set(fids))


def extract_coords_from_standard_filename(nom_fichier):
    """Extrait (x, y) depuis DT_..._X_Y.jpg ; (None, None) si échec."""
    pattern = r"DT_\d{4}-\d{2}-\d{2}_\d+_.+_([-+]?\d+\.?\d*)_([-+]?\d+\.?\d*)\.jpg$"
    match = re.match(pattern, nom_fichier)
    if match:
        try:
            return float(match.group(1)), float(match.group(2))
        except (ValueError, IndexError):
            return None, None
    return None, None
