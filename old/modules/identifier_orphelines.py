#!/usr/bin/env python3

import logging
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/' + os.path.basename(__file__).replace('.py', '.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

"""Script pour identifier précisément les photos orphelines et leur correspondance"""

import re
from qgis.core import QgsProject

def extraire_fid_du_nom(nom_fichier):
    """Extraire le FID d'un nom de photo"""
    pattern = r'DT_\d{4}-\d{2}-\d{2}_(\d+)_'
    match = re.search(pattern, nom_fichier)
    return int(match.group(1)) if match else None

def identifier_orphelines():
    """Fonction principale pour identifier les photos orphelines"""
    logger.info("=== ANALYSE DES PHOTOS ORPHELINES ===")
    layer_name = "donnees_terrain"
    base_path = "/home/e357/Qfield/cloud/DataTerrain"
    dcim = os.path.join(base_path, "DCIM")

    try:
        layers = QgsProject.instance().mapLayersByName(layer_name)
        if not layers:
            logger.info(f"⚠️  La couche '{layer_name}' est introuvable.")
            return
        layer = layers[0]
    except Exception as e:
        logger.info(f"⚠️  Erreur lors de la récupération de la couche : {e}")
        return

    all_photos = [f for f in os.listdir(dcim) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    logger.info(f"Photos dans DCIM : {len(all_photos)}")
    used_photos = {}
    for f in layer.getFeatures():
        photo = f['photo']
        if photo:
            photo_name = os.path.basename(photo)
            used_photos[photo_name] = f
    logger.info(f"Photos référencées dans la couche : {len(used_photos)}")
    orphelines = [p for p in all_photos if p not in used_photos]
    logger.info(f"Photos orphelines : {len(orphelines)}")

    logger.info("\n=== DÉTAIL DES PHOTOS ORPHELINES ===")
    for photo_name in orphelines:
        fid = extraire_fid_du_nom(photo_name)
        logger.info(f"\nPhoto : {photo_name}")
        if fid is not None:
            logger.info(f"FID extrait : {fid}")
            entite_trouvee = None
            for f in layer.getFeatures():
                if f.id() == fid:
                    entite_trouvee = f
                    break
            if entite_trouvee:
                photo_attribut = entite_trouvee['photo']
                logger.info(f"Entité FID {fid} trouvée")
                logger.info(f"Valeur du champ photo : {photo_attribut}")
                if not photo_attribut:
                    logger.info("⚠️  PROBLÈME : Champ photo est NULL")
                elif photo_attribut != f"DCIM/{photo_name}":
                    logger.info(f"⚠️  PROBLÈME : Nom de photo différent")
                    logger.info(f"   Attendu : DCIM/{photo_name}")
                    logger.info(f"   Actuel : {photo_attribut}")
            else:
                logger.info(f"⚠️  PROBLÈME : Aucune entité avec FID {fid}")
        else:
            logger.info("⚠️  PROBLÈME : Impossible d'extraire le FID du nom")

    logger.info("\n=== ANALYSE DES ENTITÉS SANS PHOTO ===")
    entites_sans_photo = [f for f in layer.getFeatures() if not f['photo']]
    logger.info(f"Entités sans photo : {len(entites_sans_photo)}")
    logger.info("\nEntités sans photo qui pourraient avoir des photos correspondantes :")
    for entite in entites_sans_photo[:10]:
        fid = entite.id()
        photos_correspondantes = [p for p in all_photos if f"_{fid}_" in p]
        if photos_correspondantes:
            logger.info(f"FID {fid} : {photos_correspondantes}")
    logger.info("\n=== FIN DE L'ANALYSE ===")

    try:
        # Fichier dans old/modules/ : 3 niveaux pour atteindre la racine du plugin
        plugin_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        export_dir = os.path.join(plugin_dir, 'exports')
        os.makedirs(export_dir, exist_ok=True)
        report_path = os.path.join(export_dir, 'photos_non_referencées.txt')
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("Analyse des photos orphelines\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Photos dans DCIM : {len(all_photos)}\n")
            f.write(f"Photos référencées dans la couche : {len(used_photos)}\n")
            f.write(f"Photos orphelines : {len(orphelines)}\n\n")
            f.write("=== DÉTAIL DES PHOTOS ORPHELINES ===\n")
            for photo_name in orphelines:
                fid = extraire_fid_du_nom(photo_name)
                f.write(f"\nPhoto : {photo_name}\n")
                if fid is not None:
                    f.write(f"FID extrait : {fid}\n")
                    entite_trouvee = None
                    for f_entite in layer.getFeatures():
                        if f_entite.id() == fid:
                            entite_trouvee = f_entite
                            break
                    if entite_trouvee:
                        photo_attribut = entite_trouvee['photo']
                        f.write(f"Entité FID {fid} trouvée\n")
                        f.write(f"Valeur du champ photo : {photo_attribut}\n")
                        if not photo_attribut:
                            f.write("⚠️  PROBLÈME : Champ photo est NULL\n")
                        elif photo_attribut != f"DCIM/{photo_name}":
                            f.write(f"⚠️  PROBLÈME : Nom de photo différent\n")
                            f.write(f"   Attendu : DCIM/{photo_name}\n")
                            f.write(f"   Actuel : {photo_attribut}\n")
                    else:
                        f.write(f"⚠️  PROBLÈME : Aucune entité avec FID {fid}\n")
                else:
                    f.write("⚠️  PROBLÈME : Impossible d'extraire le FID du nom\n")
            f.write("\n\n=== ANALYSE DES ENTITÉS SANS PHOTO ===\n")
            f.write(f"Entités sans photo : {len(entites_sans_photo)}\n\n")
            f.write("Entités sans photo qui pourraient avoir des photos correspondantes :\n")
            for entite in entites_sans_photo[:10]:
                fid = entite.id()
                photos_correspondantes = [p for p in all_photos if f"_{fid}_" in p]
                if photos_correspondantes:
                    f.write(f"FID {fid} : {photos_correspondantes}\n")
        logger.info(f"\n📄 Rapport sauvegardé : {report_path}")
    except Exception as e:
        logger.info(f"⚠️  Erreur lors de la sauvegarde du rapport : {e}")
