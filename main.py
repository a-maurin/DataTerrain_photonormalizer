#!/usr/bin/env python3
"""
Point d'entrée principal du plugin PhotoNormalizer
"""
# pyright: reportMissingImports=false
# Les modules qgis.* sont fournis par QGIS à l'exécution ; l'éditeur ne les résout pas.

from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QSettings
from .core.normalizer import PhotoNormalizer

class PhotoNormalizerPlugin:
    """
    Plugin principal pour QGIS
    """
    
    def __init__(self, iface):
        self.iface = iface
        self.normalizer = None
        
    def initGui(self):
        """Initialise l'interface graphique"""
        # Créer l'action principale
        self.action = QAction(
            QIcon(self.get_resource_path('icon.png')),
            "Normaliser les photos QField",
            self.iface.mainWindow()
        )
        self.action.triggered.connect(self.run)
        
        # Ajouter au menu
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&QField Tools", self.action)
        
    def unload(self):
        """Nettoie l'interface"""
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu("&QField Tools", self.action)
        
    def run(self):
        """Exécute le plugin"""
        if self.normalizer is None:
            self.normalizer = PhotoNormalizer(self.iface)
        self.normalizer.run()
        
    def get_resource_path(self, filename):
        """Retourne le chemin vers une ressource"""
        import os
        return os.path.join(
            os.path.dirname(__file__),
            'resources',
            filename
        )