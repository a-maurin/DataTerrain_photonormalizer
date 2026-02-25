# DataTerrain PhotoNormalizer

Plugin QGIS pour la normalisation et la gestion des photos de terrain dans le cadre de projets de collecte de données avec QField Cloud.

## Description

DataTerrain PhotoNormalizer est un plugin QGIS conçu pour normaliser, organiser et gérer les photos de terrain collectées via QField. Il permet de :

- **Détecter les photos non référencées** : Identifie les photos dans le dossier DCIM qui ne sont rattachées à aucune entité
- **Détecter les doublons** : Trouve les photos en double par comparaison de contenu (hash MD5) et par métadonnées (FID + coordonnées)
- **Analyser les photos orphelines** : Identifie les photos sans entité correspondante dans le GeoPackage
- **Renommer les photos** : Standardise les noms de fichiers selon le format `DT_YYYY-MM-DD_FID_agent_type_X_Y.jpg`
- **Créer des entités manquantes** : Génère automatiquement des entités pour les photos orphelines avec FID valide
- **Corriger les incohérences** : Nettoie les champs photo incohérents et synchronise les références
- **Optimiser les images** : Réduit la taille des photos tout en conservant la qualité

**Règle métier** : Toutes les photos (fichiers dans DCIM) doivent être rattachées à une entité dans la couche ; en revanche, une entité peut ne pas avoir de photo associée (la saisie terrain n'inclut pas toujours une photo).

## Auteur

**Aguirre MAURIN**  
Office français de la biodiversité (OFB) - Service départemental de la Côte d'Or  
Contact : aguirre.maurin@ofb.gouv.fr

## Prérequis

- QGIS 3.16 ou supérieur
- Python 3.x
- Modules Python optionnels (recommandés) :
  - `imagehash` : Pour une détection de doublons plus précise
  - `Pillow` : Pour l'optimisation des images

## Installation

### Installation du plugin

1. Téléchargez le plugin depuis le dépôt ou le fichier ZIP
2. Dans QGIS, allez dans `Extensions` → `Installer/Gérer les extensions`
3. Cliquez sur `Installer à partir d'un fichier ZIP` et sélectionnez le fichier ZIP du plugin
4. Redémarrez QGIS

### Installation des dépendances Python

#### Méthode 1 : Via la console Python de QGIS (recommandé)

1. Ouvrez QGIS
2. Menu `Extensions` → `Console Python` (ou `Ctrl+Alt+P`)
3. Exécutez les commandes suivantes ligne par ligne :

```python
import subprocess
import sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "imagehash"])
subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "Pillow"])
```

#### Méthode 2 : Via PowerShell/CMD

```powershell
& "CHEMIN_VERS_PYTHON_QGIS\python.exe" -m pip install --user imagehash Pillow
```

> **Note** : Le plugin fonctionne sans ces modules, mais avec des fonctionnalités réduites (détection de doublons moins précise, pas d'optimisation d'images).

## Configuration

### Chemins du projet

Le plugin utilise une configuration centralisée des chemins dans `core/project_config.py`. Par défaut :

- **Windows** : `C:\Users\VOTRE_UTILISATEUR\QField\cloud\DataTerrain`
- **Linux** : `/home/VOTRE_UTILISATEUR/Qfield/cloud/DataTerrain`

Pour modifier ces chemins, éditez le fichier `core/project_config.py` et ajustez les constantes `PROJECT_BASE_PATH` et `CLOUD_BASE_PATH` selon votre environnement.

### Structure attendue

```
DataTerrain/
├── DCIM/                      # Dossier contenant les photos
│   └── DT_*.jpg
└── donnees_terrain.gpkg       # GeoPackage avec la couche "saisies_terrain"
```

## Utilisation

### Interface principale

Le plugin propose deux modes d'utilisation :

#### Mode global (Mode complet)

Un seul bouton qui enchaîne toutes les étapes :
1. Sauvegarde automatique du GeoPackage et du dossier DCIM
2. Analyse des photos
3. Détection des doublons
4. Analyse des orphelines
5. Renommage des photos
6. Création d'entités pour photos orphelines
7. Correction des FID=0
8. Synchronisation des champs photo
9. Nettoyage des incohérences
10. Optimisation des images
11. Renommage d'après les formulaires

#### Modes avancés

Modes regroupés par catégories :

**Analyse et détection**
- **Détection photos non référencées** : Liste les photos DCIM non rattachées à une entité
- **Détection des doublons** : Détecte les photos en double et permet leur suppression via une interface interactive

**Orphelines**
- **Analyse des orphelines** : Analyse les photos sans entité correspondante
- **Créer entités pour photos avec FID** : Crée des entités pour les photos orphelines ayant un FID valide

**Cohérence et correction**
- **Correction des FID=0** : Corrige les photos avec FID=0 en les associant à des entités existantes
- **Nettoyer champs photo incohérents** : Vide les champs photo incohérents et restaure depuis l'archive si nécessaire

**Renommage**
- **Renommage au format standard** : Renomme les photos selon le format standard
- **Renommer d'après les formulaires** : Met à jour les noms des photos d'après les champs `nom_agent` et `type_saisie`

**Optimisation**
- **Optimisation des images** : Réduit la taille des photos (nécessite Pillow)

### Rapports et logs

Tous les rapports sont sauvegardés dans le dossier `exports/` :
- `photos_non_referencées.txt` : Liste des photos non référencées
- `doublons_detection.txt` : Détails des doublons détectés
- `analyse_orphelines.txt` : Analyse des photos orphelines
- `photo_operations_*.log` : Journal détaillé des opérations
- `renaming_summary_*.log` : Résumé des renommages effectués

Les logs sont sauvegardés dans le dossier `logs/` :
- `photonormalizer_YYYYMMDD_HHMMSS.log` : Logs détaillés de chaque exécution

## Format des noms de photos

Le plugin utilise le format standard suivant :

```
DT_YYYY-MM-DD_FID_agent_type_X_Y.jpg
```

Exemple : `DT_2025-09-24_67_maurin_aguirre_eau_tas_fumier_544424.297_6005030.410.jpg`

- `DT` : Préfixe fixe
- `YYYY-MM-DD` : Date de la prise de vue
- `FID` : Identifiant de l'entité dans le GeoPackage
- `agent` : Nom de l'agent de terrain
- `type` : Type de saisie (eau_tas_fumier, especes_eee, etc.)
- `X_Y` : Coordonnées géographiques

## Gestion des doublons

Par défaut, le plugin **ne supprime jamais automatiquement** les fichiers considérés comme doublons. Ces fichiers sont **déplacés** dans le dossier d'archive `DataTerrain_DCIM_archive_doublons/` pour éviter toute perte de photo.

Pour supprimer des doublons, utilisez l'interface de gestion des doublons qui s'affiche après la détection. Vous pouvez sélectionner manuellement les photos à supprimer.

## Compatibilité

- **Systèmes d'exploitation** : Windows, Linux
- **QGIS** : 3.16 et supérieur
- **Python** : 3.x

## Dépannage

### Le plugin ne détecte pas les doublons

Si vous voyez le message "Module 'imagehash' non installé", installez-le via la console Python de QGIS (voir section Installation). Le plugin fonctionne sans `imagehash` mais utilise une méthode de détection moins précise (hash MD5).

### Erreurs de chemins

Vérifiez que les chemins dans `core/project_config.py` correspondent à votre environnement. Le plugin doit pouvoir accéder au dossier DCIM et au fichier GeoPackage.

### Photos non détectées

Assurez-vous que :
- Les photos sont dans le dossier `DCIM/` du projet
- Les noms de fichiers respectent le format standard
- Le GeoPackage contient la couche `saisies_terrain` avec un champ `photo`

## Licence

Ce plugin est distribué sous la **licence Apache 2.0**. Voir le fichier `LICENSE` pour plus de détails.

## Support

Pour toute question ou problème, contactez : aguirre.maurin@ofb.gouv.fr

## Contribution

Les contributions sont les bienvenues. Veuillez respecter la licence Apache 2.0 et conserver les mentions de copyright lors de toute modification.
