# DataTerrain PhotoNormalizer

**Concepteur** : Aguirre MAURIN
**Contact** : aguirre.maurin@ofb.gouv.fr

## Description

DataTerrain PhotoNormalizer est un plugin QGIS conçu pour normaliser et gérer les photos de terrain dans le cadre de projets de collecte de données. Il permet de détecter les photos non référencées, les doublons, et de recréer des entités pour les photos orphelines.

## Structure du plugin

- **Racine** : `__init__.py` (entrée QGIS), `main.py` (plugin, menu), `metadata.txt`, `README.md`, `STRUCTURE.md`.
- **core/** : logique principale et UI (`normalizer.py`, `log_handler.py`, `doublons_dialog.py`).
- **scripts/** : logique métier (détection, orphelines, doublons). Voir `STRUCTURE.md` pour l’arborescence détaillée et les règles d’import.

## Interface : Mode global et Modes avancés

- **Mode global** : un seul bouton « Mode complet » qui enchaîne toutes les étapes (sauvegardes, détection, renommage, entités, correction FID, synchro champs photo, nettoyage, vérification, optimisation, renommage formulaires).
- **Modes avancés** (onglet) : modes regroupés en sections :
  - **Analyse et détection** : Détection photos non référencées, Détection des doublons.
  - **Orphelines** : Analyse des orphelines, Créer entités pour photos avec FID.
  - **Cohérence et correction** : Correction des FID=0, Nettoyer champs photo incohérents.
  - **Renommage** : Renommage au format standard, Renommer d’après les formulaires.
  - **Optimisation** : Optimisation des images.

## Fonctionnalités

- **Détection des photos non référencées** : Identifie les photos dans le dossier DCIM qui ne sont pas associées à des entités dans la couche de données.
- **Détection des doublons** : Détecte les photos en double dans le dossier DCIM.
- **Analyse des photos orphelines** : Analyse les photos orphelines et compare avec les entités.
- **Recréation des entités** : Recrée les entités manquantes à partir des photos au format ancien.

## Installation

### Prérequis

- QGIS 3.x
- Python 3.x
- Modules Python requis : `imagehash`, `Pillow`

### Étapes d'installation

1. **Télécharger le plugin** : Téléchargez le dossier du plugin depuis le dépôt ou le fichier zip.

2. **Installer le plugin dans QGIS** :
   - Ouvrez QGIS.
   - Allez dans `Extensions` > `Installer/Gérer les extensions`.
   - Cliquez sur `Installer à partir d'un fichier ZIP` et sélectionnez le fichier zip du plugin.
   - Redémarrez QGIS.

3. **Installer les dépendances Python** :
   - Ouvrez une invite de commande ou un terminal.
   - Exécutez les commandes suivantes pour installer les dépendances :
     ```bash
     pip install imagehash
     pip install Pillow
     ```

## Utilisation

### Configuration

1. **Ouvrir le projet QGIS** : Ouvrez le projet QGIS contenant la couche `donnees_terrain`.

2. **Configurer les chemins** : Assurez-vous que le chemin vers le dossier DCIM est correctement configuré dans les scripts. Par défaut, le chemin est `/home/e357/Qfield/cloud/DataTerrain/DCIM`.

### Détection des photos non référencées

1. **Ouvrir le plugin** : Dans QGIS, allez dans `Extensions` > `DataTerrain PhotoNormalizer` > `Détection des photos non référencées`.

2. **Exécuter la détection** : Cliquez sur le bouton `Exécuter` pour lancer la détection des photos non référencées.

3. **Consulter les résultats** : Les résultats seront affichés dans la console et un rapport sera généré dans le dossier `exports` sous le nom `photos_non_referencées.txt`.

### Détection des doublons

1. **Ouvrir le plugin** : Dans QGIS, allez dans `Extensions` > `DataTerrain PhotoNormalizer` > `Détection des doublons`.

2. **Exécuter la détection** : Cliquez sur le bouton `Exécuter` pour lancer la détection des doublons.

3. **Consulter les résultats** : Les résultats seront affichés dans la console et un rapport sera généré dans le dossier `exports` sous le nom `doublons_detection.txt`.

### Analyse des photos orphelines

1. **Ouvrir le plugin** : Dans QGIS, allez dans `Extensions` > `DataTerrain PhotoNormalizer` > `Analyse des photos orphelines`.

2. **Exécuter l'analyse** : Cliquez sur le bouton `Exécuter` pour lancer l'analyse des photos orphelines.

3. **Consulter les résultats** : Les résultats seront affichés dans la console et un rapport sera généré dans le dossier `exports` sous le nom `analyse_orphelines.txt`.

### Recréation des entités

1. **Ouvrir le plugin** : Dans QGIS, allez dans `Extensions` > `DataTerrain PhotoNormalizer` > `Recréation des entités`.

2. **Exécuter la recréation** : Cliquez sur le bouton `Exécuter` pour lancer la recréation des entités.

3. **Consulter les résultats** : Les résultats seront affichés dans la console et les entités seront ajoutées à la couche `donnees_terrain`.

## Dossiers et fichiers

- **exports** : Contient les rapports générés par les différents modules.
- **logs** : Contient les logs de debug.
- **core** : Logique principale et interface du plugin.
- **scripts** : Logique métier (détection, orphelines, doublons). Voir `STRUCTURE.md`.
- **old** : Ancien code (référence), non utilisé par le plugin actuel.
- **resources** : Ressources du plugin (icônes, etc.).

---

## GitHub

### 1. Installation par d’autres utilisateurs depuis GitHub

**Option A – Fichier ZIP (recommandé pour un plugin QGIS)**  
- Sur la page du dépôt GitHub : **Code** → **Download ZIP**.  
- Dans QGIS : **Extensions** → **Installer/Gérer les extensions** → **Installer à partir d’un fichier ZIP** → sélectionner le ZIP.  
- Important : le ZIP doit contenir à la racine un dossier dont le nom est celui du plugin (ex. `DataTerrain_photonormalizer`) avec `metadata.txt` et `__init__.py` à l’intérieur. En téléchargeant « Code → Download ZIP » depuis la racine du dépôt, c’est le cas.

**Option B – Clone manuel**  
- Cloner le dépôt dans le dossier des plugins QGIS (ex. sous Linux : `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`), puis redémarrer QGIS.

### 2. Versions et releases (optionnel)

Pour proposer des versions stables (ex. 1.0, 1.1) :  
- **Releases** → **Create a new release** → choisir un tag (ex. `v1.0`) → attacher un fichier ZIP du plugin si vous voulez que les utilisateurs téléchargent une archive prête à installer.

## Support

Pour toute question ou problème, veuillez contacter Aguirre MAURIN à l'adresse suivante : aguirre.maurin@ofb.gouv.fr.

## Licence

Ce plugin est distribué sous **licence Apache 2.0** (licence standard proposée par GitHub). Cette licence impose de **citer l'auteur original** et de conserver les mentions de copyright et d'attribution (voir fichier [NOTICE](NOTICE)) lors de toute redistribution ou œuvre dérivée. Détails complets dans [LICENSE](LICENSE).
