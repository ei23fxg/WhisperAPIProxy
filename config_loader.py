"""Lädt die Konfiguration (``config.py``) unabhängig vom Arbeitsverzeichnis.

Damit die Konfiguration nicht mehr zwingend als einzelne Datei nach
``/app/config.py`` gemountet werden muss, kann sie über ``CONFIG_PATH`` an
beliebiger Stelle liegen (im Container: ``/app/config/config.py``). Das
Verzeichnis-Mount hat den Vorteil, dass der Entrypoint die Datei beim ersten
Start erzeugen kann.

Reihenfolge:

1. ``$CONFIG_PATH``
2. ``config.py`` neben diesem Modul (klassisch, z. B. ``/app/config.py``)
3. ``data/config.py`` neben diesem Modul (Fallback des Entrypoints)

Die Datei wird bewusst per ``importlib`` geladen und nicht als ``import
config`` gesucht: Docker legt bei einem Bind-Mount auf eine fehlende Datei ein
*Verzeichnis* gleichen Namens an. Ein normales ``import config`` würde dieses
Verzeichnis als Namespace-Paket importieren und dann mit kryptischen
``AttributeError``-Meldungen scheitern.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from types import ModuleType

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

# Pfade in der Reihenfolge, in der sie probiert werden.
CANDIDATES = (
    os.environ.get("CONFIG_PATH"),
    os.path.join(MODULE_DIR, "config.py"),
    os.path.join(MODULE_DIR, "data", "config.py"),
)


def _candidate_paths():
    seen = set()
    for raw in CANDIDATES:
        if not raw:
            continue
        path = os.path.abspath(os.path.expanduser(raw))
        if path in seen:
            continue
        seen.add(path)
        yield path


def load_config() -> ModuleType:
    """Importiert die erste gefundene ``config.py`` als Modul ``config``."""
    tried = []
    for path in _candidate_paths():
        tried.append(path)
        if not os.path.isfile(path):
            continue
        spec = importlib.util.spec_from_file_location("config", path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Andere Module, die ``import config`` machen, bekommen dasselbe Modul.
        sys.modules["config"] = module
        return module

    raise RuntimeError(
        "Keine config.py gefunden. Gesucht in:\n  "
        + "\n  ".join(tried)
        + "\n\nBitte config.example.py nach config.py kopieren und anpassen, "
        "oder CONFIG_PATH auf eine vorhandene Datei setzen."
    )


config = load_config()
