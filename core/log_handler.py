#!/usr/bin/env python3
"""
Gestion des logs pour le plugin PhotoNormalizer
"""

from qgis.PyQt.QtWidgets import (QDialog, QVBoxLayout, QTextEdit, QPushButton,
                                QHBoxLayout, QLabel, QComboBox, QFrame, QSizePolicy, QGridLayout,
                                QScrollBar, QCheckBox, QGroupBox, QScrollArea, QWidget, QSpacerItem, QApplication)
from qgis.PyQt.QtCore import Qt, pyqtSignal, QSize, QDateTime
from qgis.PyQt.QtGui import QTextOption, QIcon, QTextCursor, QFont, QPalette, QPixmap
import os

class LogWindow(QDialog):
    """Fenêtre unifiée pour afficher les logs"""
    run_mode_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Photo Normalizer - Gestion Avancée")
        self.setMinimumSize(900, 700)
        self.setup_styles()  # Configurer les styles en premier
        self.setup_ui()
        self.selected_mode = None
        self._configure_paths_callback = None

    def set_configure_paths_callback(self, callback):
        """Callback sans argument : ouvre la configuration du dossier DataTerrain (plugin)."""
        self._configure_paths_callback = callback

    def smooth_scroll_to_bottom(self):
        """Fait défiler la console vers le bas de manière fluide"""
        scrollbar = self.log_text.verticalScrollBar()
        max_value = scrollbar.maximum()
        if max_value <= 0:
            scrollbar.setValue(0)
            return
        step = max(1, max_value // 10)
        for i in range(0, max_value + 1, step):
            scrollbar.setValue(i)
            QApplication.processEvents()
        scrollbar.setValue(max_value)
    

    
    def log_message(self, message, level="INFO"):
        """Ajoute un message au log avec couleur et défilement intelligent"""
        colors = {
            "INFO": "#00d2ff",
            "WARNING": "#f39c12", 
            "ERROR": "#e74c3c",
            "SUCCESS": "#2ecc71",
            "DEBUG": "#95a5a6"
        }
        
        color = colors.get(level, "#ffffff")
        
        # Ajouter un timestamp
        timestamp = QDateTime.currentDateTime().toString("[HH:mm:ss]")
        html_message = f'<span style="color:{color}; font-family: Courier New;">{timestamp} {message}</span>'
        
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertHtml(html_message + '<br>')
        
        # Défilement automatique
        self.smooth_scroll_to_bottom()
        
        # Limiter le nombre de lignes pour éviter la surcharge mémoire
        self.limit_log_lines()
    
    def limit_log_lines(self):
        """Limite le nombre de lignes dans la console pour éviter la surcharge"""
        max_lines = 1000
        lines = self.log_text.toPlainText().split("\n")
        if len(lines) > max_lines:
            # Garder les dernières max_lines lignes
            self.log_text.setPlainText("\n".join(lines[-max_lines:]))
    
    def setup_styles(self):
        """Configure les styles globaux"""
        # Palette de couleurs professionnelles
        self.colors = {
            'primary': '#3498db',
            'success': '#2ecc71',
            'warning': '#f39c12',
            'danger': '#e74c3c',
            'info': '#1abc9c',
            'dark': '#2c3e50',
            'light': '#ecf0f1',
            'background': '#f8f9fa',
            'text': '#2c3e50',
            'secondary': '#95a5a6',
            'accent': '#9b59b6'
        }
        
        # Style global
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {self.colors['background']};
                font-family: 'Segoe UI', Arial, sans-serif;
            }}
            
            QLabel {{
                color: {self.colors['text']};
            }}
            
            QPushButton {{
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 12px;
            }}
            
            QGroupBox {{
                border: 1px solid {self.colors['light']};
                border-radius: 8px;
                margin-top: 10px;
                padding: 10px;
                background-color: white;
            }}
            
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: {self.colors['dark']};
                font-weight: bold;
                font-size: 14px;
            }}
        """)
    
    def create_mode_card(self, title, description, icon_path, color, mode_name, compact=False):
        """Crée une carte de mode avec description. Bouton sous la description."""
        card = QGroupBox()
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(8)
        
        size = 28 if compact else 32
        icon_label = QLabel()
        icon_label.setPixmap(self.load_icon_pixmap(icon_path, size))
        icon_label.setFixedSize(size, size)
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: {13 if compact else 14}px;
            font-weight: bold;
            color: {color};
        """)
        title_label.setWordWrap(True)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label, 1)
        card_layout.addLayout(header_layout)
        
        desc_label = QLabel(description)
        desc_label.setStyleSheet("""
            font-size: 11px;
            color: #555;
            line-height: 1.35;
        """)
        desc_label.setWordWrap(True)
        desc_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        desc_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        card_layout.addWidget(desc_label, 1)
        
        action_btn = QPushButton("Lancer ce mode" if not compact else "Lancer")
        action_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                padding: {6 if compact else 8}px {12 if compact else 16}px;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: {11 if compact else 12}px;
            }}
            QPushButton:hover {{
                background-color: {self.darken_color(color, 10)};
            }}
        """)
        action_btn.clicked.connect(lambda: self.run_mode(mode_name))
        action_btn.setCursor(Qt.PointingHandCursor)
        card_layout.addWidget(action_btn)
        
        card.setLayout(card_layout)
        card.setStyleSheet(f"""
            QGroupBox {{
                border: 1px solid {self.colors['light']};
                border-radius: 8px;
                margin: 4px 0;
                padding: 4px;
                background-color: #fafbfc;
            }}
            QGroupBox:hover {{
                border: 1px solid {color};
                background-color: rgba({self.hex_to_rgb(color)}, 0.06);
            }}
        """)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        card.setMinimumHeight(100 if compact else 120)
        
        return card
    
    def _create_section_group(self, title, color=None):
        """Crée un QGroupBox de section avec un style uniforme."""
        section = QGroupBox(title)
        section.setStyleSheet(f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 12px;
                color: {color or self.colors['dark']};
                border: 1px solid {self.colors['light']};
                border-radius: 8px;
                margin-top: 12px;
                padding: 10px 10px 6px 10px;
                background-color: white;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 6px;
            }}
        """)
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 18, 8, 8)
        layout.setSpacing(6)
        section.setLayout(layout)
        return section
    
    def create_orphans_section(self):
        """Crée la section regroupée Orphelines (analyse + photos avec FID)."""
        section = self._create_section_group("Orphelines", self.colors['accent'])
        layout = section.layout()
        
        card_analyse = self.create_mode_card(
            "Analyse des orphelines",
            "Liste les photos sans entité correspondante dans le GeoPackage. Rapport dans exports/.",
            self.get_icon_path('iconOrphelines_colored.svg'),
            self.colors['accent'],
            "orphan_analysis",
            compact=True
        )
        card_fid = self.create_mode_card(
            "Créer entités pour photos avec FID",
            "Photos au format standard avec FID valide mais sans entité : crée les entités manquantes.",
            self.get_icon_path('iconOrphelines_colored.svg'),
            self.colors['warning'],
            "photos_orphelines_fid",
            compact=True
        )
        layout.addWidget(card_analyse)
        layout.addWidget(card_fid)
        return section
    
    def darken_color(self, color, percent):
        """Assombrit une couleur hexadécimale"""
        if color.startswith('#'):
            color = color[1:]
        
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
        
        r = max(0, r - (r * percent // 100))
        g = max(0, g - (g * percent // 100))
        b = max(0, b - (b * percent // 100))
        
        return f"#{r:02x}{g:02x}{b:02x}"
    
    def hex_to_rgb(self, color):
        """Convertit une couleur hex en RGB"""
        if color.startswith('#'):
            color = color[1:]
        return f"{int(color[0:2], 16)}, {int(color[2:4], 16)}, {int(color[4:6], 16)}"
    
    def setup_ui(self):
        """Configure l'interface utilisateur"""
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # En-tête moderne
        header_layout = QHBoxLayout()
        
        logo_label = QLabel()
        logo_label.setPixmap(self.load_icon_pixmap(self.get_icon_path('iconNormal_colored.svg'), 48))
        logo_label.setFixedSize(48, 48)
        
        # Titre et sous-titre
        title_layout = QVBoxLayout()
        title_label = QLabel("Photo Normalizer")
        title_label.setStyleSheet("""
            font-size: 20px;
            font-weight: bold;
            color: #2c3e50;
        """)
        
        subtitle_label = QLabel("Normalisation des photos QField / DataTerrain")
        subtitle_label.setStyleSheet("""
            font-size: 13px;
            color: #7f8c8d;
        """)
        
        title_layout.addWidget(title_label)
        title_layout.addWidget(subtitle_label)
        
        header_layout.addWidget(logo_label)
        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        folder_btn = QPushButton("📁")
        folder_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                padding: 0 8px;
                background-color: #16a085;
                color: white;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #138d75;
            }
        """)
        folder_btn.setToolTip(
            "Choisir le dossier DataTerrain (contient DCIM/ et donnees_terrain.gpkg)"
        )
        folder_btn.clicked.connect(self._on_configure_folder_clicked)
        header_layout.addWidget(folder_btn)

        # Bouton d'aide
        help_btn = QPushButton("❓")
        help_btn.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                padding: 0 8px;
                background-color: #3498db;
                color: white;
                border-radius: 12px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        help_btn.setToolTip("Afficher l'aide")
        header_layout.addWidget(help_btn)
        
        main_layout.addLayout(header_layout)
        
        # Séparateur élégant
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet(f"""
            background-color: {self.colors['primary']};
            height: 2px;
            margin: 10px 0;
        """)
        main_layout.addWidget(separator)
        
        # Layout principal en deux colonnes
        main_content_layout = QHBoxLayout()
        main_content_layout.setSpacing(15)
        
        # Colonne de gauche - Menu des modes
        left_column = QVBoxLayout()
        left_column.setSpacing(15)
        left_column.setContentsMargins(0, 10, 0, 15)
        
        # Conteneur pour les onglets
        tabs_container = QWidget()
        tab_layout = QHBoxLayout(tabs_container)
        tab_layout.setSpacing(10)
        tab_layout.setContentsMargins(0, 0, 0, 10)
        tabs_container.setStyleSheet("""
            background-color: #f8f9fa;
            border-radius: 10px 10px 0 0;
            border: 1px solid #e0e0e0;
            border-bottom: none;
        """)
        
        # Boutons d'onglets : Mode global (solitaire) | Modes avancés (toutes les actions)
        self.basic_tab_btn = QPushButton(" Mode global")
        self.advanced_tab_btn = QPushButton(" Modes avancés")
        
        # Style des onglets
        tab_style = f"""
            QPushButton {{
                background-color: {self.colors['light']};
                color: {self.colors['text']};
                padding: 10px 18px;
                border: none;
                border-radius: 8px 8px 0 0;
                font-size: 13px;
                font-weight: bold;
                min-width: 130px;
            }}
            QPushButton:hover {{
                background-color: {self.colors['primary']};
                color: white;
            }}
            QPushButton:checked {{
                background-color: {self.colors['primary']};
                color: white;
            }}
        """
        
        self.basic_tab_btn.setStyleSheet(tab_style)
        self.advanced_tab_btn.setStyleSheet(tab_style)
        
        self.basic_tab_btn.setIcon(self.load_icon_qicon('iconNormal_colored.svg'))
        self.advanced_tab_btn.setIcon(self.load_icon_qicon('iconDetection_colored.svg'))
        
        self.basic_tab_btn.setCheckable(True)
        self.advanced_tab_btn.setCheckable(True)
        
        self.basic_tab_btn.setChecked(True)
        self.advanced_tab_btn.setChecked(False)
        
        tab_layout.addWidget(self.basic_tab_btn)
        tab_layout.addWidget(self.advanced_tab_btn)
        tab_layout.addStretch()
        
        self.run_button = QPushButton("Lancer")
        self.run_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['success']};
                color: white;
                padding: 12px 24px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: {self.darken_color(self.colors['success'], 10)};
            }}
            QPushButton:disabled {{
                background-color: {self.colors['secondary']};
                color: white;
            }}
        """)
        self.run_button.setIcon(QIcon())
        self.run_button.setCursor(Qt.PointingHandCursor)
        self.run_button.clicked.connect(self.on_run_clicked)
        self.run_button.setEnabled(False)
        
        self.modes_container = QWidget()
        self.modes_container_layout = QVBoxLayout()
        self.modes_container_layout.setContentsMargins(10, 6, 10, 6)
        self.modes_container_layout.setSpacing(6)
        self.modes_container.setLayout(self.modes_container_layout)
        self.modes_container.setStyleSheet("""
            background-color: #f8f9fa;
            border-radius: 0 0 10px 10px;
            border: 1px solid #e0e0e0;
            border-top: none;
        """)
        self.modes_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.modes_container.setMaximumWidth(340)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.modes_container)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """)
        scroll_area.setMaximumWidth(360)
        scroll_area.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        
        left_column_widget = QWidget()
        left_column_widget.setMaximumWidth(360)
        left_column_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        left_layout = QVBoxLayout(left_column_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(tabs_container)
        left_layout.addWidget(scroll_area, 1)  # même stretch que log_text → même hauteur que la console
        left_layout.addWidget(self.run_button)
        
        left_column.addWidget(left_column_widget)
        
        # Colonne de droite - Console
        right_column = QVBoxLayout()
        right_column.setContentsMargins(0, 0, 0, 0)
        
        # Console - Design amélioré
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: #2b2b2b;
                color: #ecf0f1;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                padding: 12px;
                border: 1px solid {self.colors['dark']};
                border-radius: 8px;
            }}
        """)
        self.log_text.setLineWrapMode(QTextEdit.NoWrap)
        
        # Configurer la police monospace
        font = QFont("Courier New", 12)
        self.log_text.setFont(font)
        
        right_column.addWidget(self.log_text, stretch=1)
        
        # Boutons de contrôle sous la console
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.setSpacing(10)
        
        self.clear_button = QPushButton("Effacer la console")
        self.clear_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['danger']};
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {self.darken_color(self.colors['danger'], 10)};
            }}
        """)
        self.clear_button.clicked.connect(self.clear_logs)
        
        self.save_button = QPushButton("Sauvegarder la console")
        self.save_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['info']};
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {self.darken_color(self.colors['info'], 10)};
            }}
        """)
        self.save_button.clicked.connect(self.save_logs)
        
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.save_button)
        button_layout.addStretch()
        
        right_column.addLayout(button_layout)
        
        # Ajouter les colonnes au layout principal
        main_content_layout.addLayout(left_column, stretch=1)
        main_content_layout.addLayout(right_column, stretch=2)
        
        main_layout.addLayout(main_content_layout)
        
        self.close_button = QPushButton("Fermer")
        self.close_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.colors['secondary']};
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 8px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {self.darken_color(self.colors['secondary'], 10)};
            }}
        """)
        self.close_button.clicked.connect(self.accept)
        
        # Layout pour le bouton Fermer
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_layout.addWidget(self.close_button)
        main_layout.addLayout(close_layout)
        
        self.setLayout(main_layout)
        
        # Configurer les onglets
        self.setup_tabs()
        

    
    def setup_tabs(self):
        """Configure les onglets : Mode global (un seul mode) et Modes avancés (toutes les actions)."""
        self.basic_tab_btn.clicked.connect(lambda: self.on_tab_clicked("basic"))
        self.advanced_tab_btn.clicked.connect(lambda: self.on_tab_clicked("advanced"))
        
        self.basic_modes = []
        self.advanced_modes = []
        
        # ——— Mode global : une seule carte (recommandé) ———
        normal_card = self.create_mode_card(
            "Mode complet",
            "Enchaîne toutes les étapes : sauvegardes, détection des photos et des doublons, "
            "analyse des orphelines, renommage au format standard, création d'entités manquantes, "
            "correction des FID=0, synchronisation des champs photo, vérification d'intégrité, "
            "optimisation des images et renommage d'après les formulaires.",
            self.get_icon_path('iconNormal_colored.svg'),
            self.colors['success'],
            "normal"
        )
        normal_card.setMinimumHeight(140)
        self.basic_modes.append(normal_card)
        
        # ——— Modes avancés : organisés en sections logiques ———
        
        # 1. Section Analyse et détection
        section_analyse = self._create_section_group("Analyse et détection", self.colors['primary'])
        section_analyse.layout().addWidget(self.create_mode_card(
            "Détection des photos non référencées",
            "Identifie les photos du DCIM qui ne sont rattachées à aucune entité (toutes les photos doivent l'être ; les entités peuvent ne pas avoir de photo). Génère un rapport dans exports/.",
            self.get_icon_path('iconDetection_colored.svg'),
            self.colors['primary'],
            "detection",
            compact=True
        ))
        section_analyse.layout().addWidget(self.create_mode_card(
            "Détection des doublons",
            "Repère les photos en double (même contenu) et ouvre une fenêtre pour choisir lesquelles supprimer.",
            self.get_icon_path('iconDoublons_new.svg'),
            self.colors['danger'],
            "duplicate_detection",
            compact=True
        ))
        section_analyse.layout().addWidget(self.create_mode_card(
            "Analyse complète de la table attributaire",
            "Analyse tous les champs de la table attributaire : structure, statistiques, valeurs, cohérences et exporte un rapport détaillé.",
            self.get_icon_path('iconDetection_colored.svg'),
            self.colors['info'],
            "analyse_table",
            compact=True
        ))
        self.advanced_modes.append(section_analyse)
        
        # 2. Section Orphelines
        self.advanced_modes.append(self.create_orphans_section())
        
        # 3. Section Cohérence et correction
        section_coherence = self._create_section_group("Cohérence et correction", self.colors['accent'])
        section_coherence.layout().addWidget(self.create_mode_card(
            "Correction des FID=0",
            "Photos avec FID=0 : associe à une entité existante (mêmes coordonnées) ou crée une entité, puis renomme le fichier.",
            self.get_icon_path('iconCorrectionFID.svg'),
            self.colors['accent'],
            "correction_fid",
            compact=True
        ))
        section_coherence.layout().addWidget(self.create_mode_card(
            "Nettoyer champs photo incohérents",
            "Vide le champ photo des entités dont le FID dans le nom du fichier ne correspond pas au FID de l'entité. Gère les orphelins (suppression doublons ou création d'entité).",
            self.get_icon_path('iconCorrectionFID.svg'),
            self.colors['secondary'],
            "clean_photos",
            compact=True
        ))
        section_coherence.layout().addWidget(self.create_mode_card(
            "Réconcilier photos et entités",
            "Pour chaque photo : vérifie les coordonnées si attachée ; sinon attache à l'entité correspondante (FID ou coords) ou crée une entité.",
            self.get_icon_path('iconOrphelines_colored.svg'),
            self.colors['info'],
            "reconcilier_photos",
            compact=True
        ))
        self.advanced_modes.append(section_coherence)
        
        # 4. Section Renommage
        section_renommage = self._create_section_group("Renommage", self.colors['info'])
        section_renommage.layout().addWidget(self.create_mode_card(
            "Renommage au format standard",
            "Renomme les photos en DT_YYYY-MM-DD_FID_AGENT_TYPE_X_Y.jpg d'après les entités du GeoPackage.",
            self.get_icon_path('iconRenommage.svg'),
            self.colors['info'],
            "renommage",
            compact=True
        ))
        section_renommage.layout().addWidget(self.create_mode_card(
            "Renommer d'après les formulaires",
            "Met à jour les noms des photos à partir des champs nom_agent et type_saisie des entités.",
            self.get_icon_path('iconRenommage.svg'),
            self.colors['info'],
            "renommage_formulaires",
            compact=True
        ))
        self.advanced_modes.append(section_renommage)
        
        # 5. Section Optimisation
        section_optimisation = self._create_section_group("Optimisation", self.colors['warning'])
        section_optimisation.layout().addWidget(self.create_mode_card(
            "Optimisation des images",
            "Redimensionne les photos (max 800×600) et compresse en JPEG. Modifie les fichiers de façon irréversible.",
            self.get_icon_path('iconOptimisation.svg'),
            self.colors['warning'],
            "optimisation",
            compact=True
        ))
        self.advanced_modes.append(section_optimisation)
        
        self.show_tab("basic")
    
    def on_tab_clicked(self, tab_name):
        """Gère le clic sur un onglet"""
        # Désélectionner tous les boutons d'onglets
        self.basic_tab_btn.setChecked(False)
        self.advanced_tab_btn.setChecked(False)
        
        # Sélectionner le bouton cliqué
        if tab_name == "basic":
            self.basic_tab_btn.setChecked(True)
        elif tab_name == "advanced":
            self.advanced_tab_btn.setChecked(True)
        
        # Afficher le contenu de l'onglet
        self.show_tab(tab_name)
    
    def show_tab(self, tab_name):
        """Affiche le contenu d'un onglet"""
        # Effacer le contenu actuel
        for i in reversed(range(self.modes_container_layout.count())):
            widget = self.modes_container_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
        
        # Afficher les cartes appropriées
        if tab_name == "basic":
            modes = self.basic_modes
        elif tab_name == "advanced":
            modes = self.advanced_modes
        else:
            return
        
        for card in modes:
            self.modes_container_layout.addWidget(card)
        self.modes_container_layout.addStretch()
        
    def run_mode(self, mode):
        """Sélectionne le mode à exécuter"""
        self.selected_mode = mode
        
        # Mettre à jour l'interface
        self.run_button.setEnabled(True)
        self.run_button.setText("🚀 Lancer")
        
        # Log avec une couleur spécifique
        mode_colors = {
            "normal": self.colors['success'],
            "detection": self.colors['primary'],
            "duplicate_detection": self.colors['danger'],
            "renommage": self.colors['info'],
            "optimisation": self.colors['warning'],
            "orphan_analysis": self.colors['accent'],
            "correction_fid": self.colors['accent'],
            "photos_orphelines_fid": self.colors['warning'],
            "renommage_formulaires": self.colors['info'],
            "clean_photos": self.colors['secondary'],
            "reconcilier_photos": self.colors['info'],
            "analyse_table": self.colors['info'],
        }
        
        color = mode_colors.get(mode, self.colors['primary'])
        
        # Message de confirmation avec le nom complet du mode
        mode_display_name = self.get_mode_display_name(mode)
        self.log_message(f"✅ Mode sélectionné: <b><span style='color:{color};'>{mode_display_name}</span></b>", "SUCCESS")
        
        # Ajouter une description du mode sélectionné
        description = self.get_mode_description(mode)
        if description:
            self.log_message(f"ℹ️  {description}", "INFO")
    
    def get_mode_display_name(self, mode):
        """Retourne le nom complet d'un mode"""
        mode_names = {
            "normal": "Mode complet",
            "detection": "Détection des photos non référencées",
            "duplicate_detection": "Détection des doublons",
            "renommage": "Renommage au format standard",
            "optimisation": "Optimisation des images",
            "orphan_analysis": "Analyse des orphelines",
            "correction_fid": "Correction des FID=0",
            "photos_orphelines_fid": "Créer entités pour photos avec FID",
            "renommage_formulaires": "Renommer d'après les formulaires",
            "clean_photos": "Nettoyer champs photo incohérents",
            "reconcilier_photos": "Réconcilier photos et entités",
            "analyse_table": "Analyse complète de la table attributaire",
        }
        return mode_names.get(mode, mode)
    
    def get_mode_description(self, mode):
        """Retourne une description courte du mode"""
        descriptions = {
            "normal": "Enchaîne toutes les étapes avec sauvegardes automatiques.",
            "detection": "Identifie les photos DCIM non rattachées à une entité (toutes les photos doivent l'être).",
            "duplicate_detection": "Détecte les doublons et permet de les supprimer.",
            "renommage": "Renomme les photos au format DT_YYYY-MM-DD_FID_AGENT_TYPE_X_Y.jpg.",
            "optimisation": "Redimensionne et compresse les images (irréversible).",
            "orphan_analysis": "Liste les photos sans entité correspondante.",
            "correction_fid": "Associe ou crée des entités pour les photos avec FID=0.",
            "photos_orphelines_fid": "Crée les entités manquantes pour les photos avec FID valide.",
            "renommage_formulaires": "Met à jour les noms des photos d'après nom_agent et type_saisie.",
            "clean_photos": "Vide les champs photo incohérents ; gère les orphelins (doublons ou nouvelle entité).",
            "reconcilier_photos": "Pour chaque photo : vérifie les coordonnées si attachée ; sinon attache ou crée une entité.",
            "analyse_table": "Analyse tous les champs de la table attributaire : structure, statistiques, valeurs, cohérences et exporte un rapport détaillé.",
        }
        return descriptions.get(mode, "")
    
    def on_run_clicked(self):
        """Gère le clic sur le bouton Lancer"""
        if hasattr(self, 'selected_mode') and self.selected_mode:
            mode_display_name = self.get_mode_display_name(self.selected_mode)
            self.log_message(f"🚀 Lancement du traitement: {mode_display_name}", "SUCCESS")
            self.log_message("⏳ Veuillez patienter pendant l'exécution...", "INFO")
            self.run_button.setEnabled(False)
            self.run_button.setText("⏳ En cours...")
            self.run_mode_selected.emit(self.selected_mode)
        else:
            self.log_message("⚠️  Veuillez sélectionner un mode d'abord", "WARNING")
    
    def get_plugin_dir(self):
        """Répertoire racine du plugin (absolu)."""
        return os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

    def get_icon_path(self, filename):
        """Chemin absolu vers une icône dans resources/icons/."""
        return os.path.join(self.get_plugin_dir(), 'resources', 'icons', filename)

    def get_default_icon_path(self):
        """Chemin absolu vers l'icône par défaut (PNG, compatible QGIS 3.40)."""
        return os.path.join(self.get_plugin_dir(), 'resources', 'icon.png')

    def load_icon_pixmap(self, icon_path, size):
        """Charge un QPixmap pour affichage (SVG ou PNG). Fallback sur icon.png si échec."""
        path = icon_path if os.path.isabs(icon_path) else self.get_icon_path(icon_path)
        if not os.path.isfile(path):
            path = self.get_default_icon_path()
        icon = QIcon(path)
        pix = icon.pixmap(size, size) if not icon.isNull() else QPixmap()
        if pix.isNull() or pix.size().width() < 1:
            icon = QIcon(self.get_default_icon_path())
            pix = icon.pixmap(size, size)
        if pix.isNull():
            pix = QPixmap(size, size)
            pix.fill(Qt.transparent)
        return pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def load_icon_qicon(self, icon_path):
        """Retourne un QIcon (pour boutons, onglets). Fallback sur icon.png si échec."""
        path = icon_path if os.path.isabs(icon_path) else self.get_icon_path(icon_path)
        if not os.path.isfile(path):
            path = self.get_default_icon_path()
        icon = QIcon(path)
        if icon.isNull():
            icon = QIcon(self.get_default_icon_path())
        return icon

    def _on_configure_folder_clicked(self):
        if self._configure_paths_callback:
            self._configure_paths_callback()

    def clear_logs(self):
        """Efface les logs"""
        self.log_text.clear()
        self.log_message("📋 Console effacée", "INFO")
    
    def save_logs(self):
        """Sauvegarde les logs dans un fichier"""
        try:
            logs_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                'logs'
            )
            os.makedirs(logs_dir, exist_ok=True)
            
            timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
            log_file = os.path.join(logs_dir, f"photonormalizer_{timestamp}.log")
            
            with open(log_file, 'w') as f:
                f.write(self.log_text.toPlainText())
            
            self.log_message(f"✅ Logs sauvegardés: {log_file}", "SUCCESS")
        except Exception as e:
            self.log_message(f"❌ Erreur sauvegarde: {e}", "ERROR")


class LogHandler:
    """Handler pour gérer les logs"""
    
    def __init__(self, log_window):
        self.log_window = log_window
        self.operation_count = 0
        self.photo_operations = []
        self.photo_name_mapping = {}  # Mapping des anciens vers nouveaux noms
        self.current_photo_names = set()  # Ensemble des noms de photos actuels
        
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
    
    def enable_run_button(self):
        """Réactive le bouton Lancer après un traitement"""
        if hasattr(self.log_window, 'run_button'):
            self.log_window.run_button.setEnabled(True)
            self.log_window.run_button.setText("🚀 Lancer")
    
    def log_photo_operation(self, operation_type, photo_name, old_path=None, new_path=None, additional_info=""):
        """Log une opération critique sur une photo avec suivi détaillé"""
        self.operation_count += 1
        op_id = f"OP{self.operation_count:04d}"
        
        # Enregistrer l'opération pour suivi
        operation_record = {
            'id': op_id,
            'type': operation_type,
            'photo': photo_name,
            'old_path': old_path,
            'new_path': new_path,
            'timestamp': QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss"),
            'info': additional_info
        }
        self.photo_operations.append(operation_record)
        
        # Mettre à jour le mapping des noms pour les renommages
        if operation_type == "RENAME" and old_path and new_path:
            old_name = os.path.basename(old_path)
            new_name = os.path.basename(new_path)
            
            # Mettre à jour le mapping
            self.photo_name_mapping[old_name] = new_name
            
            # Mettre à jour l'ensemble des noms actuels
            if old_name in self.current_photo_names:
                self.current_photo_names.remove(old_name)
            self.current_photo_names.add(new_name)
            
            # Log le mapping
            self.debug(f"🔄 Mapping ajouté: {old_name} → {new_name}")
        
        # Mettre à jour pour les suppressions
        elif operation_type == "DELETE" and old_path:
            deleted_name = os.path.basename(old_path)
            if deleted_name in self.current_photo_names:
                self.current_photo_names.remove(deleted_name)
                self.debug(f"🗑️  Supprimé du suivi: {deleted_name}")
        
        # Log détaillé avec messages plus clairs
        if operation_type == "RENAME":
            self.log_window.log_message(
                f"📋 {op_id} [RENOMMAGE] {photo_name} → {os.path.basename(new_path) if new_path else 'UNKNOWN'}",
                level="INFO"
            )
        elif operation_type == "DELETE":
            self.log_window.log_message(
                f"🗑️  {op_id} [SUPPRESSION] {photo_name} (doublon détecté)",
                level="WARNING"
            )
        elif operation_type == "CREATE":
            self.log_window.log_message(
                f"📋 {op_id} [CRÉATION] {photo_name} at {new_path}",
                level="INFO"
            )
        elif operation_type == "CHECK":
            self.log_window.log_message(
                f"🔍 {op_id} [VÉRIFICATION] {photo_name} - {additional_info}",
                level="DEBUG"
            )
        
        # Log supplémentaire avec tous les détails
        self.debug(f"   Details: {additional_info}")
        
        return op_id
    
    def log_operation_start(self, operation_name, context=""):
        """Log le début d'une opération critique"""
        self.log_window.log_message(
            f"🔧 DEBUT {operation_name} - {context}",
            level="INFO"
        )
        return QDateTime.currentDateTime()
    
    def log_operation_end(self, operation_name, start_time, success=True, context=""):
        """Log la fin d'une opération critique avec durée"""
        end_time = QDateTime.currentDateTime()
        duration_ms = start_time.msecsTo(end_time)
        
        status = "✅ SUCCESS" if success else "❌ FAILED"
        self.log_window.log_message(
            f"{status} FIN {operation_name} - {context} ({duration_ms}ms)",
            level="SUCCESS" if success else "ERROR"
        )
    
    def initialize_photo_tracking(self, initial_photos):
        """Initialise le suivi des photos avec la liste initiale"""
        self.current_photo_names = set(initial_photos)
        self.debug(f"📊 Suivi initialisé avec {len(initial_photos)} photos")
        
    def get_final_photo_name(self, original_name):
        """Retourne le nom final d'une photo après tous les renommages"""
        current_name = original_name
        max_iterations = len(self.photo_name_mapping) + 1
        iterations = 0
        
        while current_name in self.photo_name_mapping and iterations < max_iterations:
            current_name = self.photo_name_mapping[current_name]
            iterations += 1
            
        if iterations >= max_iterations:
            self.warning(f"⚠️  Boucle de renommage détectée pour {original_name}")
            return None
            
        return current_name
    
    def is_photo_renamed(self, original_name):
        """Vérifie si une photo a été renommée"""
        final_name = self.get_final_photo_name(original_name)
        return final_name != original_name
    
    def generate_operation_report(self):
        """Génère un rapport complet des opérations sur les photos"""
        report_lines = [
            "="*80,
            "RAPPORT DES OPERATIONS SUR LES PHOTOS",
            "="*80,
            f"Nombre total d'opérations: {len(self.photo_operations)}",
            f"Nombre de renommages: {len(self.photo_name_mapping)}",
            "="*80,
            ""
        ]
        
        # Section mapping des renommages
        if self.photo_name_mapping:
            report_lines.append("MAPPING DES RENOMMAGES:")
            report_lines.append("-" * 80)
            for old_name, new_name in sorted(self.photo_name_mapping.items()):
                report_lines.append(f"  {old_name} → {new_name}")
            report_lines.append("")
        
        # Section opérations détaillées
        report_lines.append("OPERATIONS DETAILLEES:")
        report_lines.append("-" * 80)
        
        for op in self.photo_operations:
            report_lines.append(f"[{op['timestamp']}] {op['id']} {op['type']}: {op['photo']}")
            if op['old_path']:
                report_lines.append(f"  From: {op['old_path']}")
            if op['new_path']:
                report_lines.append(f"  To:   {op['new_path']}")
            if op['info']:
                report_lines.append(f"  Info: {op['info']}")
            report_lines.append("")
        
        return "\n".join(report_lines)
    
    def generate_renaming_summary(self):
        """Génère un résumé des renommages de photos"""
        if not self.photo_name_mapping:
            return "Aucun renommage effectué."
        
        summary_lines = [
            "="*80,
            "RESUME DES RENOMMAGES DE PHOTOS",
            "="*80,
            f"Nombre total de renommages: {len(self.photo_name_mapping)}",
            ""
        ]
        
        # Grouper les renommages par photo originale
        renaming_chains = {}
        
        for old_name in self.photo_name_mapping:
            if old_name not in renaming_chains:
                # Trouver la chaîne complète de renommages
                chain = []
                current_name = old_name
                
                while current_name in self.photo_name_mapping:
                    chain.append(current_name)
                    current_name = self.photo_name_mapping[current_name]
                
                chain.append(current_name)  # Ajouter le nom final
                
                if len(chain) > 1:
                    renaming_chains[old_name] = chain
        
        # Afficher les chaînes de renommages
        for original_name, chain in sorted(renaming_chains.items()):
            if len(chain) == 2:
                summary_lines.append(f"📋 {chain[0]} → {chain[1]}")
            else:
                summary_lines.append(f"🔄 {chain[0]} → {' → '.join(chain[1:-1])} → {chain[-1]}")
        
        return "\n".join(summary_lines)
    
    def register_renamed_photo(self, old_name, new_name):
        """Enregistre une photo renommée pour le suivi"""
        # Mettre à jour le mapping des noms
        self.photo_name_mapping[old_name] = new_name
        
        # Mettre à jour l'ensemble des noms actuels
        if old_name in self.current_photo_names:
            self.current_photo_names.remove(old_name)
        self.current_photo_names.add(new_name)
        
        self.debug(f"📋 Photo renommée enregistrée: {old_name} → {new_name}")

    def save_operation_report(self, report_dir):
        """Sauvegarde le rapport des opérations dans un fichier"""
        try:
            os.makedirs(report_dir, exist_ok=True)
            timestamp = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
            report_file = os.path.join(report_dir, f"photo_operations_{timestamp}.log")
            
            report_content = self.generate_operation_report()
            
            with open(report_file, 'w') as f:
                f.write(report_content)
            
            self.success(f"✅ Rapport des opérations sauvegardé: {report_file}")
            return report_file
            
        except Exception as e:
            self.error(f"❌ Erreur sauvegarde rapport opérations: {e}")
            return None


if __name__ == "__main__":
    import sys
    from qgis.PyQt.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    window = LogWindow()
    window.show()
    sys.exit(app.exec_())
