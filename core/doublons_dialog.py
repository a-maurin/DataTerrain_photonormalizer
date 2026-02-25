#!/usr/bin/env python3
"""
Interface pour la gestion des doublons
Permet à l'utilisateur de sélectionner quels doublons supprimer
"""

import os
from functools import partial
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QListWidget, QGroupBox, QCheckBox, QMessageBox, QScrollArea, QWidget, QFrame
)
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import QPixmap

class DoublonsDialog(QDialog):
    """Dialogue pour gérer les doublons"""
    
    doublons_supprimes = pyqtSignal(list)  # Signal émis avec la liste des fichiers supprimés
    
    def __init__(self, doublons_groups, dcim_path, parent=None, log_handler=None):
        super().__init__(parent)
        self.setWindowTitle("Gestion des doublons")
        self.setMinimumSize(1000, 600)
        
        self.doublons_groups = doublons_groups
        self.dcim_path = dcim_path
        self.log_handler = log_handler or DummyLogHandler()  # Utiliser un log_handler par défaut si non fourni
        self.selection = {}  # Dictionnaire pour stocker la sélection
        
        # Debug: afficher les données reçues
        self.log_handler.debug(f"📋 Données reçues - Type: {type(doublons_groups)}")
        if isinstance(doublons_groups, list):
            self.log_handler.debug(f"📋 Nombre de groupes: {len(doublons_groups)}")
            for i, group in enumerate(doublons_groups):
                self.log_handler.debug(f"📋 Groupe {i}: {len(group)} photos - Type: {type(group)}")
                if i < 3:  # Afficher les 3 premiers groupes pour le debug
                    self.log_handler.debug(f"   Photos: {group}")
        
        # Initialiser la sélection (par défaut, ne rien sélectionner)
        # Vérifier que doublons_groups est une liste de listes
        if isinstance(doublons_groups, list):
            for group_id, photos in enumerate(doublons_groups):
                if isinstance(photos, list):
                    self.selection[group_id] = {photo: False for photo in photos}
                    self.log_handler.debug(f"📋 Groupe {group_id} initialisé avec {len(photos)} photos")
                    self.log_handler.debug(f"   Photos: {photos[:3]}...")  # Afficher les 3 premières photos
                else:
                    self.log_handler.error(f"❌ Groupe {group_id} n'est pas une liste: {type(photos)}")
        else:
            self.log_handler.error(f"❌ doublons_groups n'est pas une liste: {type(doublons_groups)}")
        
        self.init_ui()
    
    def init_ui(self):
        """Initialise l'interface utilisateur"""
        # Vérifier que la dialogue n'a pas déjà un layout
        if self.layout() is not None:
            self.log_handler.warning("⚠️  Dialogue a déjà un layout, suppression...")
            old_layout = self.layout()
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            old_layout.deleteLater()
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # En-tête avec style cohérent avec la fenêtre principale
        header_layout = QHBoxLayout()
        
        title_label = QLabel("Gestion des doublons")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        
        subtitle_label = QLabel("Sélectionnez les photos à supprimer")
        subtitle_label.setStyleSheet("font-size: 12px; color: #7f8c8d;")
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(subtitle_label)
        main_layout.addLayout(header_layout)
        
        # Séparateur
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("background-color: #3498db; height: 2px; margin: 10px 0;")
        main_layout.addWidget(separator)
        
        # Description
        description = QLabel(
            "Les photos sont regroupées par similarité. Pour chaque groupe, "
            "vous pouvez sélectionner les photos à supprimer. "
            "Toutes les photos peuvent être sélectionnées pour suppression."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #666; margin-bottom: 20px; font-size: 13px;")
        main_layout.addWidget(description)
        
        # Zone de défilement pour les groupes
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        scroll_content = QWidget()
        # Vérifier que le scroll_content n'a pas déjà un layout
        if scroll_content.layout() is not None:
            self.log_handler.warning("⚠️  Scroll content a déjà un layout, suppression...")
            old_layout = scroll_content.layout()
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            old_layout.deleteLater()
        
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setAlignment(Qt.AlignTop)
        scroll_layout.setSpacing(15)
        
        # Créer un groupe pour chaque ensemble de doublons
        for group_id, photos in enumerate(self.doublons_groups):
            group_box = self.create_doublon_group(group_id, photos)
            scroll_layout.addWidget(group_box)
            scroll_layout.addSpacing(15)
        
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        
        # Boutons d'action - style cohérent avec la fenêtre principale
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 15, 0, 15)
        button_layout.setSpacing(12)
        
        # Bouton Sélectionner tout
        select_all_btn = QPushButton("  Sélectionner tout  ")
        select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db; 
                color: white;
                padding: 10px 20px;
                border: none; 
                border-radius: 8px;
                font-weight: bold; 
                font-size: 13px;
                min-width: 120px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        select_all_btn.clicked.connect(self.select_all_doublons)
        button_layout.addWidget(select_all_btn)
        
        # Bouton Désélectionner tout
        deselect_all_btn = QPushButton("  Désélectionner tout  ")
        deselect_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6; 
                color: white;
                padding: 10px 20px;
                border: none; 
                border-radius: 8px;
                font-weight: bold; 
                font-size: 13px;
                min-width: 120px;
            }
            QPushButton:hover { background-color: #7f8c8d; }
        """)
        deselect_all_btn.clicked.connect(self.deselect_all_doublons)
        button_layout.addWidget(deselect_all_btn)
        
        # Bouton Supprimer sélection
        delete_btn = QPushButton("  Supprimer la sélection  ")
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; 
                color: white;
                padding: 10px 20px;
                border: none; 
                border-radius: 8px;
                font-weight: bold; 
                font-size: 13px;
                min-width: 120px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        delete_btn.clicked.connect(self.delete_selected_doublons)
        button_layout.addWidget(delete_btn)
        
        # Bouton Passer à l'étape suivante (ferme la fenêtre et continue le traitement)
        continue_btn = QPushButton("  Passer à l'étape suivante  ")
        continue_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 13px;
                min-width: 180px;
            }
            QPushButton:hover { background-color: #219a52; }
        """)
        continue_btn.setToolTip("Fermer cette fenêtre et continuer le traitement sans supprimer de photos")
        continue_btn.clicked.connect(self.accept)
        button_layout.addWidget(continue_btn)
        
        # Bouton Annuler (ferme sans supprimer)
        cancel_btn = QPushButton("  Annuler  ")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #7f8c8d; 
                color: white;
                padding: 10px 20px;
                border: none; 
                border-radius: 8px;
                font-weight: bold; 
                font-size: 13px;
                min-width: 120px;
            }
            QPushButton:hover { background-color: #6c7a7d; }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        main_layout.addLayout(button_layout)
        
        # Statistiques
        stats_label = QLabel(f"{len(self.doublons_groups)} groupes de doublons - {sum(len(photos) for photos in self.doublons_groups)} photos")
        stats_label.setStyleSheet("color: #7f8c8d; margin-top: 15px; font-size: 12px; font-style: italic;")
        main_layout.addWidget(stats_label)
        
        # Vérifier que les checkboxes sont bien créées
        self.verify_checkboxes()
    
    def set_as_reference(self, group_id, photo_name):
        """Définir une photo comme référence du groupe"""
        try:
            # Trouver l'index de la photo dans le groupe
            if group_id in self.doublons_groups:
                photos = self.doublons_groups[group_id]
                if photo_name in photos:
                    # Trouver l'index
                    current_index = photos.index(photo_name)
                    
                    # Échanger avec la première photo
                    if current_index > 0:
                        # Échanger les positions
                        photos[0], photos[current_index] = photos[current_index], photos[0]
                        
                        # Mettre à jour la sélection
                        self.selection[group_id] = {photo: False for photo in photos}
                        
                        # Reconstruire l'interface pour ce groupe
                        self.rebuild_group(group_id)
                        
                        self.log_handler.info(f"✅ Nouvelle référence: {photo_name}")
                        return True
            
            self.log_handler.error(f"❌ Photo non trouvée dans le groupe {group_id}")
            return False
            
        except Exception as e:
            self.log_handler.error(f"❌ Erreur définition référence: {e}")
            return False
    
    def rebuild_group(self, group_id):
        """Reconstruit un groupe après changement de référence"""
        try:
            if group_id in self.doublons_groups:
                photos = self.doublons_groups[group_id]
                
                # Trouver le group_box existant et le remplacer
                for i in reversed(range(self.scroll_area.widget().layout().count())):
                    widget = self.scroll_area.widget().layout().itemAt(i).widget()
                    if widget and widget.objectName() == f"group_{group_id}":
                        # Supprimer l'ancien groupe
                        self.scroll_area.widget().layout().takeAt(i).widget().deleteLater()
                        
                        # Créer un nouveau groupe
                        new_group_box = self.create_doublon_group(group_id, photos)
                        new_group_box.setObjectName(f"group_{group_id}")
                        self.scroll_area.widget().layout().insertWidget(i, new_group_box)
                        
                        self.log_handler.info(f"✅ Groupe {group_id} reconstruit")
                        return True
            
            return False
            
        except Exception as e:
            self.log_handler.error(f"❌ Erreur reconstruction groupe {group_id}: {e}")
            return False
    
    def verify_checkboxes(self):
        """Vérifie que les checkboxes sont bien créées et connectées"""
        checkbox_count = 0
        connected_count = 0
        
        for child in self.findChildren(QCheckBox):
            checkbox_count += 1
            
            # Vérifier si le signal est connecté
            if child.receivers(child.stateChanged) > 0:
                connected_count += 1
            else:
                self.log_handler.warning(f"⚠️  Checkbox non connectée: {child.objectName()}")
        
        expected_count = sum(len(photos) for photos in self.doublons_groups)
        
        if checkbox_count == expected_count:
            self.log_handler.info(f"✅ {checkbox_count} checkboxes créées avec succès")
        else:
            self.log_handler.warning(f"⚠️  Nombre de checkboxes inattendu: {checkbox_count} (attendu: {expected_count})")
            
        if connected_count == checkbox_count:
            self.log_handler.info(f"✅ Toutes les checkboxes sont connectées ({connected_count}/{checkbox_count})")
        else:
            self.log_handler.warning(f"⚠️  Certaines checkboxes ne sont pas connectées ({connected_count}/{checkbox_count})")
    
    def create_doublon_group(self, group_id, photos):
        """Crée un groupe pour un ensemble de doublons"""
        group_box = QGroupBox(f"Groupe {group_id + 1} ({len(photos)} photos)")
        # Vérifier que le group_box n'a pas déjà un layout
        if group_box.layout() is not None:
            self.log_handler.warning(f"⚠️  GroupBox {group_id} a déjà un layout, suppression...")
            old_layout = group_box.layout()
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            old_layout.deleteLater()
        
        group_layout = QVBoxLayout()
        group_layout.setContentsMargins(10, 10, 10, 10)
        group_layout.setSpacing(8)
        
        # Ajouter chaque photo au groupe
        for i, photo in enumerate(photos):
            photo_widget = self.create_photo_widget(group_id, photo, i == 0)  # Le premier est conservé par défaut
            group_layout.addWidget(photo_widget)
        
        group_box.setLayout(group_layout)
        group_box.setObjectName(f"group_{group_id}")  # Pour pouvoir identifier le groupe plus tard
        
        # Style cohérent avec la fenêtre principale
        group_box.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3498db;
                border-radius: 8px;
                margin-top: 15px;
                padding-top: 18px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                subcontrol-position: top left;
            }
        """)
        
        return group_box
    
    def create_photo_widget(self, group_id, photo_name, is_first):
        """Crée un widget pour une photo individuelle"""
        photo_widget = QWidget()
        # Vérifier que le widget n'a pas déjà un layout
        if photo_widget.layout() is not None:
            self.log_handler.warning(f"⚠️  Widget {photo_name} a déjà un layout, suppression...")
            # Supprimer l'ancien layout
            old_layout = photo_widget.layout()
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            old_layout.deleteLater()
        
        photo_layout = QHBoxLayout()
        photo_layout.setContentsMargins(8, 8, 8, 8)
        photo_layout.setAlignment(Qt.AlignLeft)  # Aligner tout à gauche
        photo_layout.setSpacing(12)
        
        # Case à cocher - maintenant activée pour toutes les photos
        checkbox = QCheckBox()
        # Utiliser un séparateur unique pour éviter les conflits avec les underscores dans les noms de fichiers
        checkbox.setObjectName(f"checkbox_{group_id}|{photo_name}")  # Nom unique pour chaque checkbox
        checkbox.setChecked(False)
        
        # Utiliser une fonction partielle pour éviter les problèmes de capture de variables
        from functools import partial
        # Note: L'ordre des paramètres est important - state est le premier paramètre de on_checkbox_state_changed
        checkbox.stateChanged.connect(lambda state, g=group_id, p=photo_name: self.on_checkbox_state_changed(state, g, p))
        
        self.log_handler.debug(f"📋 Checkbox créée: {photo_name} (objectName: {checkbox.objectName()})")
        
        # Toutes les photos peuvent maintenant être sélectionnées pour suppression
        # Suppression du marquage spécial pour la première photo
        checkbox.setEnabled(True)
        checkbox.setToolTip("Cocher pour sélectionner cette photo à supprimer")
        
        photo_layout.addWidget(checkbox)
        
        # Aperçu de la photo (si possible) - aligné à gauche
        preview_label = QLabel()
        preview_label.setFixedSize(100, 100)
        preview_label.setStyleSheet("border: 1px solid #ddd; background-color: #f5f5f5;")
        
        # Charger l'aperçu
        photo_path = os.path.join(self.dcim_path, photo_name)
        if os.path.exists(photo_path):
            try:
                from PIL import Image
                import io
                
                # Charger et redimensionner l'image
                with Image.open(photo_path) as img:
                    img.thumbnail((100, 100), Image.Resampling.LANCZOS)
                    
                    # Convertir en QPixmap
                    img_byte_arr = io.BytesIO()
                    img.save(img_byte_arr, format='PNG')
                    pixmap = QPixmap()
                    pixmap.loadFromData(img_byte_arr.getvalue())
                    preview_label.setPixmap(pixmap)
            except Exception:
                preview_label.setText("Aperçu")
                preview_label.setAlignment(Qt.AlignCenter)
        else:
            preview_label.setText("Fichier")
            preview_label.setStyleSheet("border: 1px solid #e74c3c; background-color: #fadbd8;")
            preview_label.setAlignment(Qt.AlignCenter)
            preview_label.setToolTip("Fichier introuvable")
        
        photo_layout.addWidget(preview_label)
        
        # Informations sur la photo
        info_layout = QVBoxLayout()
        info_layout.setAlignment(Qt.AlignLeft)  # Aligner à gauche
        info_layout.setSpacing(6)
        
        # Nom du fichier
        name_label = QLabel(photo_name)
        name_label.setStyleSheet("font-weight: bold;")
        name_label.setWordWrap(True)
        info_layout.addWidget(name_label)
        
        # Taille du fichier
        file_size = "N/A"
        try:
            if os.path.exists(photo_path):
                size_bytes = os.path.getsize(photo_path)
                file_size = f"{size_bytes / 1024:.1f} Ko"
        except Exception as e:
            self.log_handler.warning(f"⚠️  Erreur lors de la récupération de la taille du fichier: {e}")
        
        size_label = QLabel(f"Taille: {file_size}")
        size_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        info_layout.addWidget(size_label)
        
        photo_layout.addLayout(info_layout)
        
        # Bouton pour ouvrir le fichier
        open_btn = QPushButton("📁 Ouvrir")
        open_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db; 
                color: white;
                padding: 6px 12px;
                border: none; 
                border-radius: 6px;
                font-weight: bold; 
                font-size: 12px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        open_btn.setFixedWidth(80)
        open_btn.clicked.connect(lambda: self.open_file_location(photo_path))
        photo_layout.addWidget(open_btn)
        
        # Bouton pour définir comme photo de référence (uniquement pour les photos non premières)
        # Suppression du bouton référence pour simplifier l'interface
        # if not is_first:
        #     set_ref_btn = QPushButton("⭐ Réf")
        #     set_ref_btn.setFixedWidth(60)
        #     set_ref_btn.setToolTip("Définir cette photo comme référence du groupe")
        #     set_ref_btn.clicked.connect(lambda: self.set_as_reference(group_id, photo_name))
        #     photo_layout.addWidget(set_ref_btn)
        
        photo_widget.setLayout(photo_layout)
        photo_widget.setStyleSheet("""
            background-color: white; 
            border-radius: 8px; 
            padding: 10px; 
            border: 1px solid #e0e0e0;
            margin-bottom: 10px;
        """)
        photo_widget.setMinimumWidth(850)  # Largeur minimale pour éviter le défilement horizontal
        
        return photo_widget
    
    def on_checkbox_state_changed(self, state, group_id, photo_name):
        """Gère le changement d'état d'une checkbox"""
        self.log_handler.debug(f"📋 Clic sur checkbox - group_id: {group_id}, photo: {photo_name}, state: {state}")
        
        # Mettre à jour la sélection
        self.update_selection(group_id, photo_name, state)
        
        self.log_handler.info(f"📋 Sélection mise à jour: {photo_name} ({'coché' if state == Qt.Checked else 'décoché'})")
    
    def update_selection(self, group_id, photo_name, state):
        """Met à jour la sélection des doublons"""
        try:
            # Vérifier que le groupe existe
            if group_id not in self.selection:
                self.log_handler.error(f"❌ Groupe {group_id} non trouvé dans la sélection")
                return
            
            # Vérifier que la photo existe dans le groupe
            if photo_name not in self.selection[group_id]:
                self.log_handler.error(f"❌ Photo '{photo_name}' non trouvée dans le groupe {group_id}")
                return
            
            # Mettre à jour la sélection
            self.selection[group_id][photo_name] = state == Qt.Checked
            self.log_handler.debug(f"📋 Sélection mise à jour: {photo_name} ({'coché' if state == Qt.Checked else 'décoché'})")
            
        except Exception as e:
            self.log_handler.error(f"❌ Erreur mise à jour sélection pour {photo_name}: {e}")
    
    def select_all_doublons(self):
        """Sélectionne tous les doublons (y compris les premiers de chaque groupe)"""
        selected_count = 0
        
        for group_id, photos in enumerate(self.doublons_groups):
            for i, photo in enumerate(photos):
                # Sélectionner toutes les photos
                self.selection[group_id][photo] = True
                selected_count += 1
        
        # Mettre à jour l'interface
        self.update_checkboxes()
        self.log_handler.info(f"✅ Tous les doublons sélectionnés ({selected_count} photos)")
    
    def deselect_all_doublons(self):
        """Désélectionne tous les doublons"""
        for group_id in self.selection:
            for photo in self.selection[group_id]:
                self.selection[group_id][photo] = False
        
        # Mettre à jour l'interface
        self.update_checkboxes()
        self.log_handler.info("✅ Tous les doublons désélectionnés")
    
    def update_checkboxes(self):
        """Met à jour l'état des cases à cocher"""
        # Parcourir tous les widgets pour mettre à jour les checkboxes
        for child in self.findChildren(QCheckBox):
            obj_name = child.objectName()
            if obj_name and obj_name.startswith("checkbox_"):
                try:
                    # Extraire group_id et photo_name du nom
                    # Format: "checkbox_groupID|photoName"
                    if "|" in obj_name:
                        parts = obj_name.split("|", 1)
                        if len(parts) == 2:
                            group_id = int(parts[0].replace("checkbox_", ""))
                            photo_name = parts[1]  # Le nom complet du fichier
                        
                        # Mettre à jour l'état de la checkbox
                        if group_id in self.selection and photo_name in self.selection[group_id]:
                            # Bloquer temporairement le signal pour éviter les boucles
                            child.blockSignals(True)
                            child.setChecked(self.selection[group_id][photo_name])
                            child.blockSignals(False)
                except Exception as e:
                    self.log_handler.error(f"Erreur mise à jour checkbox {obj_name}: {e}")
    
    def delete_selected_doublons(self):
        """Supprime les doublons sélectionnés"""
        # Demander confirmation
        reply = QMessageBox.question(
            self, "Confirmation",
            "Êtes-vous sûr de vouloir supprimer les photos sélectionnées ? "
            "Cette opération est irréversible.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
        
        # Lister les fichiers à supprimer (sauf les premières photos de chaque groupe)
        files_to_delete = []
        self.log_handler.debug(f"📋 Recherche des photos sélectionnées...")
        self.log_handler.debug(f"📋 Groupes dans self.selection: {list(self.selection.keys())}")
        
        for group_id, photos in self.selection.items():
            self.log_handler.debug(f"📋 Groupe {group_id}: {len(photos)} photos")
            for i, (photo, selected) in enumerate(photos.items()):
                self.log_handler.debug(f"  - Photo {i}: {photo} - Sélectionnée: {selected}")
                if selected:  # Supprimer toutes les photos sélectionnées
                    files_to_delete.append(photo)
                    self.log_handler.debug(f"    → Ajoutée à la suppression: {photo}")
        
        self.log_handler.debug(f"📋 Total photos à supprimer: {len(files_to_delete)}")
        if len(files_to_delete) == 0:
            self.log_handler.debug("📋 Aucune photo sélectionnée pour suppression")
        
        if not files_to_delete:
            QMessageBox.information(self, "Information", "Aucune photo sélectionnée pour suppression.")
            return
        
        deleted_files = []
        errors = []
        
        # Vérification avant suppression
        photos_before = set(os.listdir(self.dcim_path))
        self.log_handler.debug(f"Photos avant suppression: {len(photos_before)} fichiers")
        
        for photo_name in files_to_delete:
            photo_path = os.path.join(self.dcim_path, photo_name)
            
            # AVANT suppression : vérifier si une entité référence cette photo
            # Si oui, mettre à jour l'entité vers une photo conservée du même groupe (ne jamais supprimer d'entité)
            redirect_ok = self._rediriger_entites_vers_photo_conservee(photo_name, files_to_delete)
            if not redirect_ok:
                self.log_handler.warning(
                    f"⚠️ Photo {photo_name} référencée par une entité : suppression annulée pour éviter la perte de données."
                )
                errors.append(f"Référencée par une entité (conservée): {photo_name}")
                continue
            
            # Log l'opération de suppression
            op_id = self.log_handler.log_photo_operation(
                "DELETE", photo_name, photo_path, None,
                f"Suppression de doublon: {photo_name}"
            )
            
            try:
                if os.path.exists(photo_path):
                    # Vérification avant suppression
                    if photo_name not in photos_before:
                        self.log_handler.error(f"❌ Incohérence: {photo_name} non trouvé dans la liste initiale")
                        errors.append(f"Incohérence: {photo_name}")
                        continue
                    
                    # Supprimer le fichier
                    self.log_handler.debug(f"🗑️  Tentative de suppression: {photo_path}")
                    os.remove(photo_path)
                    
                    # Vérification après suppression
                    if os.path.exists(photo_path):
                        self.log_handler.error(f"❌ ERREUR CRITIQUE: {photo_name} existe toujours après suppression!")
                        errors.append(f"Suppression échouée: {photo_name}")
                        self.log_handler.log_operation_end(
                            f"DELETE_{op_id}", 
                            self.log_handler.log_operation_start(f"DELETE_{op_id}"),
                            success=False,
                            context="Fichier toujours présent après suppression"
                        )
                        continue
                    
                    deleted_files.append(photo_name)
                    self.log_handler.success(f"✅ Doublon supprimé: {photo_name} (conservation de la version la plus récente)")
                    self.log_handler.log_operation_end(
                        f"DELETE_{op_id}", 
                        self.log_handler.log_operation_start(f"DELETE_{op_id}"),
                        success=True,
                        context=f"Suppression doublon réussie: {photo_name}"
                    )
                else:
                    error_msg = f"Fichier introuvable: {photo_name}"
                    errors.append(error_msg)
                    self.log_handler.error(error_msg)
                    self.log_handler.log_operation_end(
                        f"DELETE_{op_id}", 
                        self.log_handler.log_operation_start(f"DELETE_{op_id}"),
                        success=False,
                        context="Fichier introuvable"
                    )
            except Exception as e:
                error_msg = f"Erreur suppression {photo_name}: {str(e)}"
                errors.append(error_msg)
                self.log_handler.error(error_msg)
                self.log_handler.log_operation_end(
                    f"DELETE_{op_id}", 
                    self.log_handler.log_operation_start(f"DELETE_{op_id}"),
                    success=False,
                    context=f"Exception: {str(e)}"
                )
        
        # Vérification finale après toutes les suppressions
        photos_after = set(os.listdir(self.dcim_path))
        self.log_handler.debug(f"Photos après suppression: {len(photos_after)} fichiers")
        
        # Vérifier que le nombre de photos a bien diminué
        expected_count = len(photos_before) - len(deleted_files)
        if len(photos_after) != expected_count:
            self.log_handler.error(
                f"❌ INCOHERENCE: {len(photos_before)} → {len(photos_after)} photos "
                f"(attendu: {expected_count}, supprimé: {len(deleted_files)})"
            )
        
        # Afficher le résultat
        result_msg = f"{len(deleted_files)} fichier(s) supprimé(s) avec succès."
        blocked = [e for e in errors if "Référencée par une entité" in e]
        if blocked:
            result_msg += f"\n\n⚠️ {len(blocked)} photo(s) non supprimée(s) : référencée(s) par une entité (données protégées)."
        other_errors = [e for e in errors if e not in blocked]
        if other_errors:
            result_msg += f"\n{len(other_errors)} autre(s) erreur(s) rencontrée(s)."
        
        QMessageBox.information(self, "Résultat", result_msg)
        
        # Émettre le signal avec les fichiers supprimés
        self.doublons_supprimes.emit(deleted_files)
        
        # Fermer la dialogue
        self.accept()
    
    def _entites_referencant_photo(self, photo_name):
        """Retourne la liste des FID des entités dont le champ photo référence photo_name."""
        try:
            from qgis.core import QgsVectorLayer
            gpkg_file = os.path.join(os.path.dirname(self.dcim_path), "donnees_terrain.gpkg")
            layer_name = "saisies_terrain"
            layer = QgsVectorLayer(f"{gpkg_file}|layername={layer_name}", layer_name, "ogr")
            if not layer.isValid():
                return []
            fids = []
            for feature in layer.getFeatures():
                photo_field = feature['photo']
                if photo_field and photo_name in photo_field:
                    fids.append(feature.id())
            return fids
        except Exception:
            return []

    def _rediriger_entites_vers_photo_conservee(self, photo_name, files_to_delete):
        """
        Si des entités référencent photo_name, les rediriger vers une photo conservée du même groupe.
        Retourne True si la suppression peut avoir lieu (aucune entité ou redirection réussie).
        Retourne False si une entité référence cette photo et qu'on ne peut pas la rediriger.
        """
        fids = self._entites_referencant_photo(photo_name)
        if not fids:
            return True
        
        # Trouver une photo conservée du même groupe (une photo du groupe qu'on ne supprime pas)
        photo_conservee = None
        for group_id, photos in self.selection.items():
            if photo_name in photos:
                for p in photos.keys():
                    if p != photo_name and p not in files_to_delete and os.path.exists(os.path.join(self.dcim_path, p)):
                        photo_conservee = p
                        break
                break
        
        if not photo_conservee:
            self.log_handler.warning(
                f"⚠️ Entité(s) {fids} référencent {photo_name} mais aucune photo conservée dans le groupe. "
                "Suppression annulée."
            )
            return False
        
        try:
            from qgis.core import QgsVectorLayer
            gpkg_file = os.path.join(os.path.dirname(self.dcim_path), "donnees_terrain.gpkg")
            layer_name = "saisies_terrain"
            layer = QgsVectorLayer(f"{gpkg_file}|layername={layer_name}", layer_name, "ogr")
            if not layer.isValid():
                return False
            photo_idx = layer.fields().indexFromName('photo')
            if photo_idx < 0:
                return False
            new_val = f"DCIM/{photo_conservee}" if "DCIM/" not in photo_conservee else photo_conservee
            if "DCIM/" not in new_val:
                new_val = f"DCIM/{photo_conservee}"
            layer.startEditing()
            for fid in fids:
                layer.changeAttributeValue(fid, photo_idx, new_val)
                self.log_handler.info(
                    f"📋 Entité FID {fid}: champ photo redirigé vers {photo_conservee} (avant suppression du doublon)"
                )
            layer.commitChanges()
            return True
        except Exception as e:
            self.log_handler.error(f"❌ Erreur redirection entités: {e}")
            return False
    
    def open_file_location(self, file_path):
        """Ouvre l'emplacement du fichier dans le gestionnaire de fichiers"""
        import subprocess
        import sys
        
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Erreur", "Le fichier n'existe pas.")
            return
        
        # Ouvrir le dossier contenant le fichier
        folder_path = os.path.dirname(file_path)
        
        try:
            if sys.platform == 'win32':
                subprocess.Popen(['explorer', folder_path])
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', folder_path])
            else:  # Linux
                subprocess.Popen(['xdg-open', folder_path])
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Impossible d'ouvrir le dossier: {str(e)}")


# Classe factice pour le log_handler (à remplacer par le vrai)
class DummyLogHandler:
    def info(self, msg):
        print(f"INFO: {msg}")
    
    def error(self, msg):
        print(f"ERROR: {msg}")


if __name__ == "__main__":
    # Test de l'interface
    import sys
    from qgis.PyQt.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Exemple de données
    test_doublons = [
        ["photo1.jpg", "photo1_dup1.jpg", "photo1_dup2.jpg"],
        ["photo2.jpg", "photo2_dup1.jpg"],
        ["photo3.jpg", "photo3_dup1.jpg", "photo3_dup2.jpg", "photo3_dup3.jpg"]
    ]
    
    log_handler = DummyLogHandler()
    dialog = DoublonsDialog(test_doublons, "/chemin/vers/dcim", log_handler=log_handler)
    dialog.show()
    
    sys.exit(app.exec_())