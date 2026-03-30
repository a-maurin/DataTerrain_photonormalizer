#!/usr/bin/env python3
"""Listage des photos DCIM (+ dossier de sync QField si présent)."""

import os


def list_dcim_photo_basenames(dcim_path):
    """
    Retourne les noms de fichiers .jpg/.jpeg du DCIM principal et,
    si présent, de .qfieldsync/download/DCIM au même niveau que le dossier parent de DCIM.
    """
    if not dcim_path or not os.path.exists(dcim_path):
        return []

    main_dcim_photos = [
        f
        for f in os.listdir(dcim_path)
        if f.lower().endswith((".jpg", ".jpeg"))
    ]

    qfield_sync_dcim = os.path.join(
        os.path.dirname(dcim_path), ".qfieldsync", "download", "DCIM"
    )
    sync_photos = []
    if os.path.exists(qfield_sync_dcim):
        sync_photos = [
            f
            for f in os.listdir(qfield_sync_dcim)
            if f.lower().endswith((".jpg", ".jpeg"))
        ]

    return list(set(main_dcim_photos + sync_photos))
