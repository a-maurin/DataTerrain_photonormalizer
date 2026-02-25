# Structure du plugin DataTerrain PhotoNormalizer

## Arborescence

```
DataTerrain_photonormalizer/
├── __init__.py              # Point d'entrée QGIS (classFactory)
├── main.py                  # Plugin principal (PhotoNormalizerPlugin), menu et toolbar
├── metadata.txt             # Métadonnées du plugin QGIS
├── README.md                # Documentation principale
├── STRUCTURE.md             # Ce fichier
├── LICENSE                  # Licence Apache 2.0
├── NOTICE                   # Notice d'attribution
├── .gitignore              # Fichiers ignorés par Git
│
├── core/                    # Cœur du plugin : orchestration et UI
│   ├── __init__.py
│   ├── project_config.py   # Configuration centralisée des chemins (Linux/Windows)
│   ├── normalizer.py       # Logique principale (PhotoNormalizer), tous les modes
│   ├── log_handler.py      # Fenêtre de log, onglets Mode global / Modes avancés
│   └── doublons_dialog.py  # Dialogue de gestion des doublons
│
├── scripts/                 # Logique métier du plugin
│   ├── __init__.py
│   ├── photo_detection.py          # Détection des photos non référencées
│   ├── detect_doublons.py          # Détection des doublons (contenu + métadonnées)
│   ├── analyse_orphelines.py      # Analyse orphelines + extraction coordonnées
│   ├── analyse_table_attributaire.py  # Analyse complète de la table attributaire
│   └── correct_fid_zero_photos.py  # Script standalone correction FID=0 (optionnel)
│
├── resources/               # Ressources (icônes, etc.)
│   ├── icon.png             # Icône principale du plugin
│   ├── resources.qrc        # Fichier de ressources Qt
│   └── icons/               # Icônes SVG/PNG des modes
│
├── exports/                 # Rapports générés (créé à l'exécution)
│   └── .gitkeep
│
├── logs/                    # Fichiers de log (créés à l'exécution)
│   └── .gitkeep
│
└── old/                     # Ancien code (référence, non utilisé par le plugin actuel)
    ├── __init__.py
    ├── main_plugin.py       # Ancienne interface
    ├── modules/             # Anciens modules
    └── ...                  # autres scripts legacy
```

## Architecture

### Point d'entrée

- **`__init__.py`** : Fonction `classFactory(iface)` requise par QGIS, retourne une instance de `PhotoNormalizerPlugin`
- **`main.py`** : Classe `PhotoNormalizerPlugin` qui gère l'intégration dans QGIS (menu, toolbar, actions)

### Cœur du plugin (`core/`)

- **`project_config.py`** : Configuration centralisée des chemins du projet selon l'OS (Windows/Linux)
  - `get_dcim_path()` : Chemin du dossier DCIM
  - `get_gpkg_path()` : Chemin du GeoPackage
  - `get_cloud_base()` : Chemin du répertoire cloud
  - `get_backup_dir()` : Chemin du dossier de sauvegarde

- **`normalizer.py`** : Classe principale `PhotoNormalizer` qui orchestre tous les modes
  - `run()` : Point d'entrée principal
  - `on_mode_selected()` : Gère la sélection du mode et exécute le traitement correspondant
  - Méthodes pour chaque mode (détection, doublons, orphelines, renommage, etc.)

- **`log_handler.py`** : Gestion de l'interface utilisateur
  - `LogWindow` : Fenêtre principale avec onglets (Mode global / Modes avancés)
  - `LogHandler` : Gestion des messages de log avec couleurs et formatage

- **`doublons_dialog.py`** : Interface interactive pour la gestion des doublons
  - Affichage des groupes de doublons
  - Sélection manuelle des photos à supprimer
  - Redirection des entités vers les photos conservées

### Scripts métier (`scripts/`)

- **`photo_detection.py`** : Détecte les photos non référencées dans DCIM
- **`detect_doublons.py`** : Détection des doublons par :
  - Comparaison de contenu (hash MD5 ou imagehash si disponible)
  - Métadonnées (FID + coordonnées identiques)
- **`analyse_orphelines.py`** : Analyse les photos orphelines et extraction des coordonnées depuis les noms de fichiers
- **`analyse_table_attributaire.py`** : Analyse complète de la structure et du contenu de la table attributaire
- **`correct_fid_zero_photos.py`** : Script standalone pour corriger les photos avec FID=0

## Règles d'import

### Depuis `core/normalizer.py`

```python
from .log_handler import LogHandler, LogWindow
from .project_config import get_dcim_path, get_gpkg_path, get_cloud_base, get_backup_dir
from .doublons_dialog import DoublonsDialog
from ..scripts.photo_detection import detect_unreferenced_photos
from ..scripts.detect_doublons import detect_doublons
from ..scripts.analyse_orphelines import analyser_photos_orphelines
```

### Depuis les scripts (`scripts/`)

```python
try:
    from ..core.project_config import get_dcim_path, get_gpkg_path
except ImportError:
    # Fallback pour exécution standalone
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from core.project_config import get_dcim_path, get_gpkg_path
```

### Chemins de ressources

Les ressources sont accessibles via `log_handler.py` :
- `get_plugin_dir()` : Retourne le répertoire racine du plugin
- `get_icon_path(filename)` : Retourne le chemin vers une icône dans `resources/icons/`

## Flux d'exécution

1. **Chargement** : QGIS charge `__init__.py` → `classFactory(iface)` → `PhotoNormalizerPlugin(iface)`
2. **Initialisation** : `PhotoNormalizerPlugin.initGui()` ajoute l'action au menu et à la toolbar
3. **Démarrage** : L'utilisateur clique sur l'action → `PhotoNormalizerPlugin.run()` → `PhotoNormalizer.run()`
4. **Interface** : `PhotoNormalizer.run()` crée `LogWindow` et `LogHandler`, affiche la fenêtre
5. **Sélection du mode** : L'utilisateur sélectionne un mode et clique sur "Lancer"
6. **Exécution** : `on_mode_selected(mode)` dans `normalizer.py` exécute le mode correspondant
7. **Scripts** : Les scripts métier sont appelés depuis `core/normalizer.py` avec les paramètres appropriés
8. **Rapports** : Les résultats sont sauvegardés dans `exports/` et les logs dans `logs/`

## Format des noms de photos

Le plugin utilise le format standard suivant :

```
DT_YYYY-MM-DD_FID_agent_type_X_Y.jpg
```

- `DT` : Préfixe fixe
- `YYYY-MM-DD` : Date de la prise de vue
- `FID` : Identifiant de l'entité dans le GeoPackage
- `agent` : Nom de l'agent de terrain
- `type` : Type de saisie (peut contenir des underscores)
- `X_Y` : Coordonnées géographiques (format décimal)

## Gestion des chemins

Le plugin utilise `core/project_config.py` pour centraliser la gestion des chemins et assurer la compatibilité Windows/Linux. Tous les chemins hardcodés ont été remplacés par des appels aux fonctions de configuration.

## Dossiers générés

- **`exports/`** : Contient tous les rapports générés par les différents modes
- **`logs/`** : Contient les fichiers de log détaillés de chaque exécution
- **Archive doublons** : `CLOUD_BASE_PATH/DataTerrain_DCIM_archive_doublons/` (défini dans `project_config.py`)
- **Sauvegardes** : `CLOUD_BASE_PATH/donnee_terrain_backups/` (défini dans `project_config.py`)
