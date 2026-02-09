#!/usr/bin/env python3
"""
Fenêtre de log unifiée pour le plugin PhotoNormalizer
"""

from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout,
                                QLabel, QComboBox, QFrame, QSizePolicy)
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QTextOption
import os

class LogWindow(QDialog):
    """
    Fenêtre unifiée pour afficher les logs et gérer l'exécution du plugin
    """
    
    # Signal émis lorsque l'utilisateur sélectionne un mode et clique sur Exécuter
    run_mode_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Photo Normalizer - Interface Unifiée")
        self.setMinimumSize(800, 600)
        
        # Layout principal
        main_layout = QVBoxLayout()
        
        # ===== Section Menu =====
        # Titre
        title_label = QLabel("Photo Normalizer - Interface Unifiée")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Séparateur
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(separator)
        
        # Menu principal
        menu_label = QLabel("Mode de fonctionnement:")
        menu_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        main_layout.addWidget(menu_label)
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("🔍 Détection des photos non référencées", "detection")
        self.mode_combo.addItem("⚙️ Mode Normal (toutes fonctionnalités)", "normal")
        self.mode_combo.setStyleSheet("padding: 5px;")
        main_layout.addWidget(self.mode_combo)
        
        # Bouton d'exécution
        self.run_button = QPushButton("🚀 Lancer le traitement")
        self.run_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                font-size: 14px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.run_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        main_layout.addWidget(self.run_button, alignment=Qt.AlignCenter)
        
        # Espaceur
        main_layout.addSpacing(15)
        
        # ===== Section Console =====
        # Titre de la console
        console_title = QLabel("Console d'exécution")
        console_title.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 5px;")
        main_layout.addWidget(console_title)
        
        # Zone de texte pour les logs
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFontFamily("Monospace")
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        self.log_text.setStyleSheet("background-color: #f5f5f5; padding: 8px;")
        self.log_text.setAcceptRichText(True)
        main_layout.addWidget(self.log_text, stretch=1)
        
        # Boutons de la console
        button_layout = QHBoxLayout()
        
        self.clear_button = QPushButton("🗑️ Effacer")
        self.clear_button.clicked.connect(self.clear_logs)
        self.clear_button.setStyleSheet("padding: 5px 10px;")
        
        self.save_button = QPushButton("💾 Sauvegarder")
        self.save_button.clicked.connect(self.save_logs)
        self.save_button.setStyleSheet("padding: 5px 10px;")
        
        self.close_button = QPushButton("❌ Fermer")
        self.close_button.clicked.connect(self.accept)
        self.close_button.setStyleSheet("padding: 5px 10px;")
        
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.save_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        main_layout.addLayout(button_layout)
        
        self.setLayout(main_layout)
        
        # Connexions des signaux
        self.run_button.clicked.connect(self.on_run_clicked)

    def log_message(self, message, level="INFO"):
        """
        Ajoute un message au log
        
        Args:
            message (str): Le message à ajouter
            level (str): Niveau du message (INFO, WARNING, ERROR, SUCCESS)
        """
        # Déterminer la couleur et le préfixe
        colors = {
            "INFO": "#000000",
            "WARNING": "#FF8C00",
            "ERROR": "#FF0000",
            "SUCCESS": "#008000",
            "DEBUG": "#808080"
        }
        
        prefixes = {
            "INFO": "ℹ️ ",
            "WARNING": "⚠️ ",
            "ERROR": "❌ ",
            "SUCCESS": "✅ ",
            "DEBUG": "🐞 "
        }
        
        color = colors.get(level, "#000000")
        prefix = prefixes.get(level, "ℹ️ ")
        
        # Remplacer les retours à la ligne par des balises HTML
        message_with_breaks = message.replace('\n', '<br>')
        
        # Formater le message (sans timestamp)
        formatted_message = f"<span style='color:{color};'>{prefix}{message_with_breaks}</span>"
        
        # Ajouter au texte existant
        self.log_text.append(formatted_message)
        
        # Faire défiler vers le bas
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def clear_logs(self):
        """Efface tous les logs"""
        self.log_text.clear()

    def save_logs(self):
        """Sauvegarde les logs dans un fichier"""
        # Utiliser le dossier d'exportation par défaut
        export_dir = os.path.dirname(os.path.abspath(__file__))
        log_filename = "photo_normalizer_logs.log"
        file_path = os.path.join(export_dir, log_filename)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.log_text.toPlainText())
            self.log_message(f"💾 Logs sauvegardés avec succès : {file_path}", level="SUCCESS")
        except Exception as e:
            self.log_message(f"❌ Erreur lors de la sauvegarde : {e}", level="ERROR")

    def on_run_clicked(self):
        """Gère le clic sur le bouton d'exécution"""
        selected_mode = self.mode_combo.currentData()
        self.run_mode_selected.emit(selected_mode)

    def show(self):
        """Affiche la fenêtre"""
        super().show()
        self.raise_()
        self.activateWindow()

class LogHandler:
    """
    Handler pour gérer les logs et les afficher dans la fenêtre
    """
    
    def __init__(self, log_window):
        self.log_window = log_window
    
    def debug(self, msg):
        self.log_window.log_message(msg, level="DEBUG")
    
    def info(self, msg):
        self.log_window.log_message(msg, level="INFO")
    
    def warning(self, msg):
        self.log_window.log_message(msg, level="WARNING")
    
    def error(self, msg):
        self.log_window.log_message(msg, level="ERROR")
    
    def success(self, msg):
        self.log_window.log_message(msg, level="SUCCESS")
    
    def log_message(self, msg, level="INFO"):
        self.log_window.log_message(msg, level)