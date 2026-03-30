#!/usr/bin/env python3
"""Chargement de couches vecteur OGR (GeoPackage)."""

from qgis.core import QgsVectorLayer


def load_vector_layer_from_gpkg(gpkg_path, layer_name):
    """
    Charge une couche depuis un GPKG. Lève ValueError si invalide.
    """
    layer_path = f"{gpkg_path}|layername={layer_name}"
    layer = QgsVectorLayer(layer_path, layer_name, "ogr")
    if not layer.isValid():
        raise ValueError(f"Impossible de charger la couche {layer_name}")
    return layer
