#!/usr/bin/env python3
"""
Script d'analyse complète de la table attributaire
Analyse tous les champs, leurs valeurs, types, statistiques et cohérences
"""

import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from qgis.core import QgsVectorLayer, QgsField, QgsFieldConstraints
from qgis.PyQt.QtCore import QVariant

try:
    from ..core.project_config import (
        get_dcim_path,
        get_gpkg_path,
        get_layer_name,
        get_photo_field_name,
        get_coord_tolerance,
    )
except ImportError:
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from core.project_config import (
        get_dcim_path,
        get_gpkg_path,
        get_layer_name,
        get_photo_field_name,
        get_coord_tolerance,
    )


def analyser_table_attributaire(log_handler, export_dir=None):
    """
    Effectue une analyse complète de la table attributaire de la couche saisies_terrain
    
    Args:
        log_handler: Handler pour afficher les messages et logs
        export_dir: Dossier pour exporter les résultats (optionnel)
    """
    
    # Configuration (config centralisée Linux / Windows)
    gpkg_file = get_gpkg_path()
    layer_name = get_layer_name()
    dcim_path = get_dcim_path()
    
    log_handler.info("=" * 80)
    log_handler.info("📊 ANALYSE COMPLÈTE DE LA TABLE ATTRIBUTAIRE")
    log_handler.info("=" * 80)
    
    # Charger la couche
    try:
        layer_path = f"{gpkg_file}|layername={layer_name}"
        layer = QgsVectorLayer(layer_path, layer_name, "ogr")
        
        if not layer.isValid():
            log_handler.error(f"❌ Impossible de charger la couche '{layer_name}' depuis {gpkg_file}")
            return False
        
        log_handler.info(f"✅ Couche '{layer_name}' chargée avec succès")
        log_handler.info(f"📈 Nombre total d'entités: {layer.featureCount()}")
        log_handler.info("")
        
    except Exception as e:
        log_handler.error(f"❌ Erreur lors du chargement de la couche: {e}")
        return False
    
    # 1. ANALYSE DES CHAMPS
    log_handler.info("=" * 80)
    log_handler.info("1. STRUCTURE DES CHAMPS")
    log_handler.info("=" * 80)
    
    fields = layer.fields()
    field_info = {}
    
    for field in fields:
        field_name = field.name()
        field_type = field.typeName()
        field_type_id = field.type()
        length = field.length()
        precision = field.precision()
        
        # Vérifier si le champ est nullable (simplifié pour éviter les erreurs d'API)
        is_nullable = True  # Par défaut, considérer comme nullable
        try:
            constraints = field.constraints()
            # Vérifier si la contrainte NOT NULL existe avec la bonne API
            not_null_strength = constraints.constraintStrength(QgsFieldConstraints.ConstraintNotNull)
            # Si la contrainte est forte (Required), le champ n'est pas nullable
            if not_null_strength == QgsFieldConstraints.ConstraintStrengthHard:
                is_nullable = False
        except (AttributeError, TypeError, Exception):
            # Si l'API n'est pas disponible ou erreur, considérer comme nullable par défaut
            is_nullable = True
        
        field_info[field_name] = {
            'type': field_type,
            'type_id': field_type_id,
            'length': length,
            'precision': precision,
            'is_nullable': is_nullable
        }
        
        log_handler.info(f"  • {field_name}")
        log_handler.info(f"    Type: {field_type} (ID: {field_type_id})")
        if length > 0:
            log_handler.info(f"    Longueur: {length}")
        if precision > 0:
            log_handler.info(f"    Précision: {precision}")
        log_handler.info("")
    
    # 2. STATISTIQUES PAR CHAMP
    log_handler.info("=" * 80)
    log_handler.info("2. STATISTIQUES PAR CHAMP")
    log_handler.info("=" * 80)
    
    stats = {}
    total_features = layer.featureCount()
    
    for field_name in field_info.keys():
        stats[field_name] = {
            'total': total_features,
            'non_null': 0,
            'null': 0,
            'empty_string': 0,
            'unique_values': set(),
            'value_counts': Counter(),
            'examples': []
        }
    
    # Parcourir toutes les entités
    for feature in layer.getFeatures():
        for field_name in field_info.keys():
            value = feature[field_name]
            stat = stats[field_name]
            
            if value is None or value == QVariant():
                stat['null'] += 1
            elif isinstance(value, str) and value.strip() == '':
                stat['empty_string'] += 1
            else:
                stat['non_null'] += 1
                stat['unique_values'].add(str(value))
                stat['value_counts'][str(value)] += 1
                
                # Garder quelques exemples
                if len(stat['examples']) < 5:
                    stat['examples'].append(str(value))
    
    # Afficher les statistiques
    for field_name, stat in stats.items():
        log_handler.info(f"📋 Champ: {field_name}")
        log_handler.info(f"   Total d'entités: {stat['total']}")
        log_handler.info(f"   Valeurs non nulles: {stat['non_null']} ({stat['non_null']*100/stat['total']:.1f}%)")
        log_handler.info(f"   Valeurs nulles: {stat['null']} ({stat['null']*100/stat['total']:.1f}%)")
        log_handler.info(f"   Chaînes vides: {stat['empty_string']} ({stat['empty_string']*100/stat['total']:.1f}%)")
        log_handler.info(f"   Valeurs uniques: {len(stat['unique_values'])}")
        
        # Afficher les valeurs les plus fréquentes
        if stat['value_counts']:
            log_handler.info(f"   Top 5 valeurs les plus fréquentes:")
            for val, count in stat['value_counts'].most_common(5):
                log_handler.info(f"     • '{val}': {count} fois ({count*100/stat['total']:.1f}%)")
        
        # Afficher quelques exemples
        if stat['examples']:
            log_handler.info(f"   Exemples: {', '.join(stat['examples'][:3])}")
        
        log_handler.info("")
    
    # 3. ANALYSE SPÉCIFIQUE DES CHAMPS IMPORTANTS
    log_handler.info("=" * 80)
    log_handler.info("3. ANALYSE DÉTAILLÉE DES CHAMPS MÉTIER")
    log_handler.info("=" * 80)
    
    # 3.1 Champ PHOTO
    if get_photo_field_name() in field_info:
        analyser_champ_photo(layer, log_handler, dcim_path)
    
    # 3.2 Champ DATE_SAISIE
    if 'date_saisie' in field_info:
        analyser_champ_date_saisie(layer, log_handler)
    
    # 3.3 Champ NOM_AGENT
    if 'nom_agent' in field_info:
        analyser_champ_nom_agent(layer, log_handler)
    
    # 3.4 Champ TYPE_SAISIE
    if 'type_saisie' in field_info:
        analyser_champ_type_saisie(layer, log_handler)
    
    # 3.5 Champs COORDONNÉES
    if 'x_saisie' in field_info and 'y_saisie' in field_info:
        analyser_champs_coordonnees(layer, log_handler)
    
    # 4. ANALYSE DE COHÉRENCE
    log_handler.info("=" * 80)
    log_handler.info("4. ANALYSE DE COHÉRENCE")
    log_handler.info("=" * 80)
    
    analyser_coherence(layer, log_handler, dcim_path)
    
    # 5. EXPORT DES RÉSULTATS
    if export_dir:
        exporter_resultats(layer, field_info, stats, log_handler, export_dir)
    
    log_handler.info("=" * 80)
    log_handler.info("✅ Analyse complète terminée")
    log_handler.info("=" * 80)
    
    return True


def analyser_champ_photo(layer, log_handler, dcim_path):
    """Analyse détaillée du champ photo"""
    pfn = get_photo_field_name()
    log_handler.info(f"📷 CHAMP: {pfn}")

    photo_field_idx = layer.fields().indexFromName(pfn)
    if photo_field_idx < 0:
        log_handler.warning(f"   ⚠️  Champ '{pfn}' introuvable")
        return
    
    total = 0
    avec_photo = 0
    sans_photo = 0
    photos_valides = 0
    photos_invalides = 0
    photos_manquantes = 0
    formats_photo = Counter()
    prefixes_photo = Counter()
    
    # Lister les photos dans DCIM
    photos_dcim = set()
    if os.path.exists(dcim_path):
        for f in os.listdir(dcim_path):
            if f.lower().endswith(('.jpg', '.jpeg')):
                photos_dcim.add(f)
    
    for feature in layer.getFeatures():
        total += 1
        photo_val = feature[pfn]
        
        if not photo_val or (isinstance(photo_val, str) and photo_val.strip() == ''):
            sans_photo += 1
            continue
        
        avec_photo += 1
        photo_str = str(photo_val)
        
        # Analyser le format du chemin
        if photo_str.startswith('DCIM/'):
            prefixes_photo['DCIM/'] += 1
        elif photo_str.startswith('file://'):
            prefixes_photo['file://'] += 1
        elif photo_str.startswith('content://'):
            prefixes_photo['content://'] += 1
        else:
            prefixes_photo['autre'] += 1
        
        # Extraire le nom de fichier
        filename = photo_str.split('/')[-1].split('\\')[-1]
        
        if filename.lower().endswith('.jpg'):
            formats_photo['.jpg'] += 1
        elif filename.lower().endswith('.jpeg'):
            formats_photo['.jpeg'] += 1
        else:
            formats_photo['autre'] += 1
        
        # Vérifier si le fichier existe
        if filename in photos_dcim:
            photos_valides += 1
        else:
            photos_invalides += 1
            if filename and filename.lower().endswith(('.jpg', '.jpeg')):
                photos_manquantes += 1
    
    log_handler.info(f"   Total d'entités: {total}")
    log_handler.info(f"   Entités avec photo: {avec_photo} ({avec_photo*100/total:.1f}%)")
    log_handler.info(f"   Entités sans photo: {sans_photo} ({sans_photo*100/total:.1f}%)")
    log_handler.info(f"   Photos valides (fichier présent): {photos_valides}")
    log_handler.info(f"   Photos invalides (fichier absent): {photos_invalides}")
    log_handler.info(f"   Photos manquantes: {photos_manquantes}")
    log_handler.info(f"   Formats: {dict(formats_photo)}")
    log_handler.info(f"   Préfixes: {dict(prefixes_photo)}")
    log_handler.info("")


def analyser_champ_date_saisie(layer, log_handler):
    """Analyse détaillée du champ date_saisie"""
    log_handler.info("📅 CHAMP: date_saisie")
    
    total = 0
    dates_valides = 0
    dates_invalides = 0
    formats_dates = Counter()
    annees = Counter()
    mois = Counter()
    
    for feature in layer.getFeatures():
        total += 1
        date_val = feature['date_saisie']
        
        if not date_val:
            dates_invalides += 1
            continue
        
        date_str = str(date_val)
        
        # Détecter le format
        if re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', date_str):
            formats_dates['ISO avec heure'] += 1
        elif re.match(r'\d{4}-\d{2}-\d{2}', date_str):
            formats_dates['ISO date seule'] += 1
        elif re.match(r'\d{8}', date_str):
            formats_dates['YYYYMMDD'] += 1
        else:
            formats_dates['autre'] += 1
        
        # Extraire année et mois
        match = re.search(r'(\d{4})', date_str)
        if match:
            annee = match.group(1)
            annees[annee] += 1
            
            match_mois = re.search(r'(\d{4})-(\d{2})', date_str)
            if match_mois:
                mois[match_mois.group(2)] += 1
        
        dates_valides += 1
    
    log_handler.info(f"   Total d'entités: {total}")
    log_handler.info(f"   Dates valides: {dates_valides} ({dates_valides*100/total:.1f}%)")
    log_handler.info(f"   Dates invalides/vides: {dates_invalides} ({dates_invalides*100/total:.1f}%)")
    log_handler.info(f"   Formats détectés: {dict(formats_dates)}")
    log_handler.info(f"   Répartition par année: {dict(annees.most_common(10))}")
    log_handler.info(f"   Répartition par mois: {dict(mois.most_common(12))}")
    log_handler.info("")


def analyser_champ_nom_agent(layer, log_handler):
    """Analyse détaillée du champ nom_agent"""
    log_handler.info("👤 CHAMP: nom_agent")
    
    total = 0
    agents = Counter()
    valeurs_speciales = Counter()
    
    for feature in layer.getFeatures():
        total += 1
        agent_val = feature['nom_agent']
        
        if not agent_val:
            valeurs_speciales['NULL'] += 1
            continue
        
        agent_str = str(agent_val).strip()
        
        if agent_str.upper() == 'INCONNU':
            valeurs_speciales['INCONNU'] += 1
        elif agent_str == '':
            valeurs_speciales['vide'] += 1
        else:
            agents[agent_str] += 1
    
    log_handler.info(f"   Total d'entités: {total}")
    log_handler.info(f"   Agents uniques: {len(agents)}")
    log_handler.info(f"   Top 10 agents: {dict(agents.most_common(10))}")
    log_handler.info(f"   Valeurs spéciales: {dict(valeurs_speciales)}")
    log_handler.info("")


def analyser_champ_type_saisie(layer, log_handler):
    """Analyse détaillée du champ type_saisie"""
    log_handler.info("🏷️  CHAMP: type_saisie")
    
    total = 0
    types = Counter()
    valeurs_speciales = Counter()
    
    for feature in layer.getFeatures():
        total += 1
        type_val = feature['type_saisie']
        
        if not type_val:
            valeurs_speciales['NULL'] += 1
            continue
        
        type_str = str(type_val).strip()
        
        if type_str.upper() == 'INCONNU':
            valeurs_speciales['INCONNU'] += 1
        elif type_str == '':
            valeurs_speciales['vide'] += 1
        else:
            types[type_str] += 1
    
    log_handler.info(f"   Total d'entités: {total}")
    log_handler.info(f"   Types uniques: {len(types)}")
    log_handler.info(f"   Répartition des types: {dict(types.most_common(20))}")
    log_handler.info(f"   Valeurs spéciales: {dict(valeurs_speciales)}")
    log_handler.info("")


def analyser_champs_coordonnees(layer, log_handler):
    """Analyse détaillée des champs x_saisie et y_saisie"""
    log_handler.info("📍 CHAMPS: x_saisie, y_saisie")
    
    total = 0
    avec_coord = 0
    sans_coord = 0
    coord_invalides = 0
    x_values = []
    y_values = []
    
    for feature in layer.getFeatures():
        total += 1
        x_val = feature['x_saisie']
        y_val = feature['y_saisie']
        
        try:
            x = float(x_val) if x_val else None
            y = float(y_val) if y_val else None
            
            if x is not None and y is not None:
                avec_coord += 1
                x_values.append(x)
                y_values.append(y)
            else:
                sans_coord += 1
        except (ValueError, TypeError):
            coord_invalides += 1
    
    if x_values and y_values:
        log_handler.info(f"   Total d'entités: {total}")
        log_handler.info(f"   Entités avec coordonnées: {avec_coord} ({avec_coord*100/total:.1f}%)")
        log_handler.info(f"   Entités sans coordonnées: {sans_coord} ({sans_coord*100/total:.1f}%)")
        log_handler.info(f"   Coordonnées invalides: {coord_invalides}")
        log_handler.info(f"   X min: {min(x_values):.2f}, max: {max(x_values):.2f}, moyenne: {sum(x_values)/len(x_values):.2f}")
        log_handler.info(f"   Y min: {min(y_values):.2f}, max: {max(y_values):.2f}, moyenne: {sum(y_values)/len(y_values):.2f}")
    else:
        log_handler.info(f"   Aucune coordonnée valide trouvée")
    
    log_handler.info("")


def analyser_coherence(layer, log_handler, dcim_path):
    """Analyse de cohérence entre les différents champs"""
    pfn = get_photo_field_name()
    tol = get_coord_tolerance()
    log_handler.info("🔍 ANALYSE DE COHÉRENCE")
    
    # Cohérence photo / FID dans le nom
    log_handler.info("   📋 Cohérence photo / FID dans le nom de fichier")
    
    incoherences_fid = 0
    photos_avec_fid = 0
    photos_sans_fid = 0
    
    for feature in layer.getFeatures():
        fid = feature.id()
        photo_val = feature[pfn]
        
        if not photo_val:
            continue
        
        photo_str = str(photo_val)
        filename = photo_str.split('/')[-1].split('\\')[-1]
        
        # Chercher le FID dans le nom de fichier
        match = re.search(r'_(\d+)_', filename)
        if match:
            photos_avec_fid += 1
            fid_in_name = int(match.group(1))
            if fid_in_name != fid:
                incoherences_fid += 1
                if incoherences_fid <= 5:  # Afficher les 5 premières
                    log_handler.info(f"     ⚠️  FID {fid}: photo '{filename}' contient FID {fid_in_name}")
        else:
            photos_sans_fid += 1
    
    log_handler.info(f"     Photos avec FID dans le nom: {photos_avec_fid}")
    log_handler.info(f"     Photos sans FID dans le nom: {photos_sans_fid}")
    log_handler.info(f"     Incohérences FID: {incoherences_fid}")
    
    # Cohérence coordonnées / géométrie
    log_handler.info("   📋 Cohérence coordonnées / géométrie")
    
    incoherences_coord = 0
    avec_geom = 0
    
    for feature in layer.getFeatures():
        if not feature.geometry() or feature.geometry().isEmpty():
            continue
        
        avec_geom += 1
        geom_point = feature.geometry().asPoint()
        
        try:
            x_saisie = float(feature['x_saisie']) if feature['x_saisie'] else None
            y_saisie = float(feature['y_saisie']) if feature['y_saisie'] else None
            
            if x_saisie is not None and y_saisie is not None:
                if abs(geom_point.x() - x_saisie) > tol or abs(geom_point.y() - y_saisie) > tol:
                    incoherences_coord += 1
                    if incoherences_coord <= 5:
                        log_handler.info(f"     ⚠️  FID {feature.id()}: géométrie ({geom_point.x():.2f}, {geom_point.y():.2f}) != coord ({x_saisie:.2f}, {y_saisie:.2f})")
        except (ValueError, TypeError):
            pass
    
    log_handler.info(f"     Entités avec géométrie: {avec_geom}")
    log_handler.info(f"     Incohérences coordonnées: {incoherences_coord}")
    
    log_handler.info("")


def exporter_resultats(layer, field_info, stats, log_handler, export_dir):
    """Exporte les résultats de l'analyse dans un fichier"""
    try:
        os.makedirs(export_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = os.path.join(export_dir, f"analyse_table_attributaire_{timestamp}.txt")
        
        with open(export_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("ANALYSE COMPLÈTE DE LA TABLE ATTRIBUTAIRE\n")
            f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Nombre total d'entités: {layer.featureCount()}\n\n")
            
            f.write("STRUCTURE DES CHAMPS\n")
            f.write("-" * 80 + "\n")
            for field_name, info in field_info.items():
                f.write(f"{field_name}: {info['type']}\n")
            
            f.write("\nSTATISTIQUES PAR CHAMP\n")
            f.write("-" * 80 + "\n")
            for field_name, stat in stats.items():
                f.write(f"\n{field_name}:\n")
                f.write(f"  Non nulles: {stat['non_null']} ({stat['non_null']*100/stat['total']:.1f}%)\n")
                f.write(f"  Nulles: {stat['null']} ({stat['null']*100/stat['total']:.1f}%)\n")
                f.write(f"  Valeurs uniques: {len(stat['unique_values'])}\n")
        
        log_handler.info(f"💾 Résultats exportés: {export_file}")
        
    except Exception as e:
        log_handler.error(f"❌ Erreur lors de l'export: {e}")
