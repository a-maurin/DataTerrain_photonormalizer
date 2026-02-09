# Structure du plugin DataTerrain PhotoNormalizer

## Arborescence

```
DataTerrain_photonormalizer/
├── __init__.py              # Point d'entrée QGIS (classFactory)
├── main.py                  # Plugin principal (PhotoNormalizerPlugin), menu et toolbar
├── metadata.txt             # Métadonnées du plugin QGIS
├── README.md
├── STRUCTURE.md             # Ce fichier
├── LICENSE
│
├── core/                    # Cœur du plugin : orchestration et UI
│   ├── __init__.py
│   ├── normalizer.py        # Logique principale (PhotoNormalizer), tous les modes
│   ├── log_handler.py       # Fenêtre de log, onglets Mode global / Modes avancés
│   └── doublons_dialog.py   # Dialogue de gestion des doublons
│
├── scripts/                 # Logique métier du plugin (un seul dossier pour les scripts)
│   ├── __init__.py
│   ├── photo_detection.py           # Détection des photos non référencées
│   ├── detect_doublons.py           # Détection des doublons (contenu)
│   ├── analyse_orphelines.py       # Analyse orphelines + extraire_coord_du_nom
│   ├── correct_fid_zero_photos.py  # Script standalone correction FID=0 (optionnel)
│   └── corriger_references_photos.py
│
├── resources/               # Ressources (icônes, etc.)
│   ├── __init__.py
│   ├── icon.png             # Icône principale du plugin
│   ├── resources.qrc
│   └── icons/               # Icônes SVG/PNG des modes
│
├── utils/                   # Utilitaires partagés (si besoin)
│   └── __init__.py
│
├── exports/                 # Rapports générés (créé à l'exécution)
├── logs/                    # Fichiers de log (créés à l'exécution)
│
└── old/                     # Ancien code (référence, non utilisé par le plugin actuel)
    ├── __init__.py
    ├── main_plugin.py       # Ancienne interface
    ├── modules/             # Anciens modules (importés par old/main_plugin.py)
    │   ├── __init__.py
    │   ├── analyse_photos_orphelines.py
    │   ├── identifier_orphelines.py
    │   └── recreer_entites_orphelines_v3.py
    └── ...                  # autres scripts legacy
```

## Scripts (logique métier)

- **scripts/** : seul dossier de logique métier utilisé par le plugin actuel (`core/normalizer.py`). Toute la logique (détection, orphelines, doublons) doit rester ou être ajoutée ici.
- L’ancien dossier **modules/** à la racine a été supprimé ; son contenu a été déplacé dans **old/modules/** pour que tout le code legacy soit sous **old/**.

## Règles d'import

- **Racine du plugin** : `os.path.dirname(__file__)` dans `main.py` ou `__init__.py` ; depuis `core/`, `os.path.dirname(os.path.dirname(__file__))`.
- **Depuis `core/normalizer.py`** : `from .log_handler import ...` ; `from ..scripts.photo_detection import ...` ; `from ..scripts.analyse_orphelines import extraire_coord_du_nom`. N'utiliser que le package **scripts**, pas modules.
- **Ressources** : chemins construits via `get_plugin_dir()` dans `log_handler.py`, puis `resources/` ou `resources/icons/`.

## Flux d'exécution

1. QGIS charge `__init__.py` → `classFactory(iface)` → `PhotoNormalizerPlugin(iface)`.
2. L’utilisateur clique sur l’action → `PhotoNormalizerPlugin.run()` → `PhotoNormalizer.run()`.
3. `PhotoNormalizer.run()` crée `LogWindow` et `LogHandler`, affiche la fenêtre.
4. Sélection d’un mode (global ou avancé) puis « Lancer » → `on_mode_selected(mode)` dans `normalizer.py` exécute le mode correspondant (scripts appelés depuis `core/normalizer.py`).
