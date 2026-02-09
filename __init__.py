#!/usr/bin/env python3
"""
Package principal du plugin PhotoNormalizer
"""

# Import des modules principaux
from .main import PhotoNormalizerPlugin

# Définition des métadonnées du plugin
def classFactory(iface):
    """Retourne l'instance du plugin"""
    return PhotoNormalizerPlugin(iface)