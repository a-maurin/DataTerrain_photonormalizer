#!/usr/bin/env python3

import logging
import os
import sys
import hashlib

try:
    from ..core.project_config import (
        get_dcim_path,
        get_gpkg_path,
        get_layer_name,
        get_photo_field_name,
        get_coord_key_decimals,
    )
    from ..core.photo_patterns import (
        fid_from_photo_filename,
        group_contains_duplicate_same_fid,
        extract_coords_from_standard_filename,
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
        get_coord_key_decimals,
    )
    from core.photo_patterns import (
        fid_from_photo_filename,
        group_contains_duplicate_same_fid,
        extract_coords_from_standard_filename,
    )

# Configuration du logging (sans FileHandler pour éviter ResourceWarning de fichier non fermé)
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

"""
Script de détection des doublons dans les photos
"""

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.info("⚠️  Module PIL/Pillow non disponible. Détection par imagehash désactivée ; MD5 utilisé si besoin.")

try:
    import imagehash

    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False
    logger.info(
        "⚠️  Module 'imagehash' non disponible. Installation recommandée: pip install imagehash"
    )


def _calculer_hash_fichier(file_path):
    """Calcule le hash MD5 d'un fichier pour comparaison."""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return None


def _collect_file_duplicate_phase(dcim_path, potential_doubles, use_imagehash_branch):
    """
    Phase fichier uniquement (thread-safe : pas de QGIS, pas de log UI).
    use_imagehash_branch : True si imagehash ET Pillow disponibles.
    Retourne (true_doubles dict, messages_log).
    """
    true_doubles = {}
    messages = []

    for _size_key, photo_list in potential_doubles.items():
        if use_imagehash_branch:
            hash_groups = {}
            for photo in photo_list:
                file_path = os.path.join(dcim_path, photo)
                try:
                    with Image.open(file_path) as img:
                        img_hash = str(imagehash.average_hash(img))
                        hash_groups.setdefault(img_hash, []).append(photo)
                except Exception as e:
                    messages.append(("warning", f"⚠️ Erreur traitement {photo}: {e}"))

            for hash_val, photos in list(hash_groups.items()):
                if len(photos) > 1:
                    base_photo = photos[0]
                    base_path = os.path.join(dcim_path, base_photo)
                    for photo in photos[1:]:
                        photo_path = os.path.join(dcim_path, photo)
                        try:
                            with Image.open(base_path) as base_img, Image.open(
                                photo_path
                            ) as compare_img:
                                if (
                                    base_img.size != compare_img.size
                                    or base_img.mode != compare_img.mode
                                ):
                                    messages.append(
                                        (
                                            "info",
                                            f"ℹ️  {photo} n'est pas un doublon de {base_photo} (taille ou mode différent)",
                                        )
                                    )
                                    hash_groups[hash_val].remove(photo)
                                    continue
                                if list(base_img.getdata()) != list(compare_img.getdata()):
                                    messages.append(
                                        (
                                            "info",
                                            f"ℹ️  {photo} n'est pas un doublon de {base_photo} (contenu différent)",
                                        )
                                    )
                                    hash_groups[hash_val].remove(photo)
                        except Exception as e:
                            messages.append(
                                ("warning", f"⚠️ Erreur comparaison {photo}: {e}")
                            )

            for hash_val, photos in hash_groups.items():
                if len(photos) > 1:
                    filtered_photos = [p for p in photos if "_INCONNU_INCONNU_" not in p]
                    if len(filtered_photos) > 1:
                        if group_contains_duplicate_same_fid(filtered_photos):
                            messages.append(
                                (
                                    "info",
                                    f"ℹ️  Groupe exclu (même FID, sessions différentes): "
                                    f"{[p for p in filtered_photos[:3]]}{'...' if len(filtered_photos) > 3 else ''}",
                                )
                            )
                        else:
                            true_doubles.setdefault(hash_val, []).extend(filtered_photos)
                            messages.append(
                                (
                                    "warning",
                                    "⚠️  DOUBLONS DÉTECTÉS (non supprimés automatiquement):",
                                )
                            )
                            for p in filtered_photos:
                                messages.append(("warning", f"   • {p}"))
                            messages.append(
                                (
                                    "warning",
                                    "📋 Ces photos ont le même contenu visuel mais NE SERONT PAS supprimées automatiquement.",
                                )
                            )
                            messages.append(
                                (
                                    "warning",
                                    "💡 Pour supprimer des doublons, utilisez l'interface de gestion des doublons avec prudence.",
                                )
                            )
        else:
            messages.append(
                (
                    "warning",
                    "⚠️  Module imagehash non disponible ou Pillow absent, utilisation de la comparaison par hash MD5",
                )
            )
            hash_groups = {}
            for photo in photo_list:
                file_path = os.path.join(dcim_path, photo)
                try:
                    file_hash = _calculer_hash_fichier(file_path)
                    if file_hash:
                        hash_groups.setdefault(file_hash, []).append(photo)
                    else:
                        messages.append(
                            ("warning", f"⚠️ Impossible de calculer le hash pour {photo}")
                        )
                except Exception as e:
                    messages.append(("warning", f"⚠️ Erreur traitement {photo}: {e}"))

            for file_hash, photos in hash_groups.items():
                if len(photos) > 1 and not group_contains_duplicate_same_fid(photos):
                    true_doubles.setdefault(file_hash, []).extend(photos)

    return true_doubles, messages


def _detecter_doublons_par_metadonnees(dcim_path, log_handler):
    """
    Détecte les doublons basés sur les métadonnées : photos orphelines avec même FID et coordonnées
    qu'une photo déjà attachée à une entité.
    """
    try:
        from qgis.core import QgsVectorLayer

        gpkg_file = get_gpkg_path()
        layer_name = get_layer_name()
        pfn = get_photo_field_name()
        layer = QgsVectorLayer(f"{gpkg_file}|layername={layer_name}", layer_name, "ogr")

        if not layer.isValid():
            return []

        nd = get_coord_key_decimals()
        photos_attachees = {}
        for feature in layer.getFeatures():
            photo_field = feature[pfn]
            if photo_field and isinstance(photo_field, str):
                photo_name = photo_field.split("/")[-1]
                if photo_name.lower().endswith((".jpg", ".jpeg")):
                    fid = feature.id()
                    if feature.geometry() and not feature.geometry().isEmpty():
                        pt = feature.geometry().asPoint()
                        key = (fid, round(pt.x(), nd), round(pt.y(), nd))
                        photos_attachees.setdefault(key, []).append(photo_name)

        doublons_metadonnees = []
        for file in os.listdir(dcim_path):
            if not file.lower().endswith((".jpg", ".jpeg")):
                continue

            fid = fid_from_photo_filename(file)
            if fid is None or fid == 0:
                continue

            x, y = extract_coords_from_standard_filename(file)
            if x is None or y is None:
                continue

            photo_field = None
            for feature in layer.getFeatures():
                pf = feature[pfn]
                if pf and file in pf:
                    photo_field = pf
                    break

            if photo_field:
                continue

            key = (fid, round(x, nd), round(y, nd))
            if key in photos_attachees:
                groupe = [file] + photos_attachees[key]
                doublons_metadonnees.append(groupe)

        return doublons_metadonnees
    except Exception as e:
        log_handler.warning(f"⚠️ Erreur détection doublons par métadonnées: {e}")
        return []


def detect_doublons(log_handler, export_dir=None):
    """
    Détecte les photos en double dans le dossier DCIM.

    Returns:
        list: liste des groupes de doublons (chaque groupe est une liste de noms de fichiers).
    """
    dcim_path = get_dcim_path()

    log_handler.info("🔍 Détection des doublons en cours...")

    if not HAS_IMAGEHASH:
        log_handler.warning(
            "⚠️  Module 'imagehash' non installé. Pour une meilleure détection, installez-le avec: pip install imagehash"
        )
        log_handler.warning("📋 Utilisation du mode fallback (comparaison par contenu)")

    if not os.path.exists(dcim_path):
        log_handler.error(f"❌ Dossier DCIM introuvable: {dcim_path}")
        return []

    photos = []
    for file in os.listdir(dcim_path):
        if file.lower().endswith((".jpg", ".jpeg", ".png")):
            photos.append(file)

    total_photos = len(photos)
    log_handler.info(f"📷 Trouvé {total_photos} photos dans DCIM")

    if total_photos == 0:
        log_handler.info("ℹ️ Aucune photo trouvée")
        return []

    log_handler.info("📊 Analyse par taille de fichier...")
    size_groups = {}
    for photo in photos:
        file_path = os.path.join(dcim_path, photo)
        try:
            file_size = os.path.getsize(file_path)
            size_groups.setdefault(file_size, []).append(photo)
        except Exception as e:
            log_handler.warning(f"⚠️ Erreur lecture {photo}: {e}")

    potential_doubles = {k: v for k, v in size_groups.items() if len(v) > 1}

    log_handler.info(f"📊 Trouvé {len(potential_doubles)} groupes de photos avec même taille")

    true_doubles = {}

    if potential_doubles:
        log_handler.info("🔍 Analyse par hash visuel ou MD5 (phase fichiers)...")
        use_ih = HAS_IMAGEHASH and HAS_PIL
        try:
            from ..core.tasks import run_in_worker_thread
        except ImportError:
            try:
                from core.tasks import run_in_worker_thread
            except ImportError:
                run_in_worker_thread = None

        try:
            if run_in_worker_thread is not None:
                true_doubles, phase_messages = run_in_worker_thread(
                    "PhotoNormalizer: analyse doublons (fichiers)",
                    lambda: _collect_file_duplicate_phase(
                        dcim_path, potential_doubles, use_ih
                    ),
                )
            else:
                true_doubles, phase_messages = _collect_file_duplicate_phase(
                    dcim_path, potential_doubles, use_ih
                )
        except Exception as e:
            log_handler.warning(
                f"⚠️ Analyse en arrière-plan échouée ({e}), nouvelle tentative sur le thread principal."
            )
            true_doubles, phase_messages = _collect_file_duplicate_phase(
                dcim_path, potential_doubles, use_ih
            )

        for level, msg in phase_messages:
            if level == "warning":
                log_handler.warning(msg)
            else:
                log_handler.info(msg)

        log_handler.info("🔍 Détection des doublons par métadonnées (FID + coordonnées)...")
        doublons_metadonnees = _detecter_doublons_par_metadonnees(dcim_path, log_handler)
        if doublons_metadonnees:
            log_handler.info(
                f"📊 Trouvé {len(doublons_metadonnees)} groupes de doublons par métadonnées"
            )
            for i, groupe in enumerate(doublons_metadonnees, 1):
                meta_key = f"meta_{i}"
                true_doubles[meta_key] = groupe
                log_handler.info(
                    f"  📋 Groupe métadonnées {i}: {len(groupe)} photos (même FID + coordonnées)"
                )

        log_handler.info(f"📊 Trouvé {len(true_doubles)} groupes de vrais doublons au total")

        try:
            if export_dir:
                os.makedirs(export_dir, exist_ok=True)
            else:
                plugin_dir = os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
                export_dir = os.path.join(plugin_dir, "exports")
                os.makedirs(export_dir, exist_ok=True)

            report_path = os.path.join(export_dir, "doublons_detection.txt")
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("Détection de doublons\n")
                f.write("=" * 50 + "\n\n")
                f.write(f"Photos analysées: {total_photos}\n")
                f.write(f"Groupes de doublons: {len(true_doubles)}\n\n")

                for i, (hash_val, photo_list) in enumerate(true_doubles.items(), 1):
                    f.write(f"Groupe {i} (hash: {hash_val}):\n")
                    for photo in photo_list:
                        f.write(f"  • {photo}\n")
                    f.write("\n")

            log_handler.info(f"📄 Rapport sauvegardé: {report_path}")

            if len(true_doubles) > 0:
                log_handler.info("📋 Résumé des doublons:")
                for i, (hash_val, photo_list) in enumerate(true_doubles.items(), 1):
                    if i <= 5:
                        log_handler.info(f"  Groupe {i}: {len(photo_list)} photos")

        except Exception as e:
            log_handler.error(f"❌ Erreur sauvegarde rapport: {e}")
            return []

        log_handler.info("✅ Détection des doublons terminée")

        if true_doubles:
            log_handler.debug(f"📋 Format des données: {type(true_doubles)}")
            log_handler.debug(f"📋 Nombre de groupes: {len(true_doubles)}")
            for i, (key, plist) in enumerate(list(true_doubles.items())[:3]):
                log_handler.debug(f"📋 Groupe {i}: clé='{key}', {len(plist)} photos")

        return list(true_doubles.values()) if true_doubles else []

    log_handler.info("✅ Aucune photo en double détectée")
    return []
