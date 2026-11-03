#!/usr/bin/env python3
"""
run_headless.py
═══════════════════════════════════════════════════════════════════════════════
Version sans interface graphique pour GitHub Actions.

  • Mocke tkinter  (indisponible sur les runners Linux sans affichage)
  • Appelle run_scraping() depuis recherche_minima_v5.py
  • Génère last_update.js  avec le timestamp JJ/MM/AAAA à HH:MM
  • achievements.js est déjà écrit par run_scraping(), on le laisse tel quel

Ce fichier ne modifie PAS recherche_minima_v5.py.
═══════════════════════════════════════════════════════════════════════════════
"""

import sys
from unittest.mock import MagicMock

# ── 1. Mock tkinter ────────────────────────────────────────────────────────
# tkinter n'est pas disponible sur les runners GitHub Actions (pas d'affichage).
# On le remplace par un objet fantôme AVANT tout import du module principal,
# ce qui évite l'ImportError sans toucher au code source original.
sys.modules["tkinter"]               = MagicMock()
sys.modules["tkinter.scrolledtext"]  = MagicMock()

# ── 2. Import de la fonction principale ────────────────────────────────────
from recherche_minima_v5 import run_scraping   # noqa: E402

from datetime import datetime

# ── 3. Lancement ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("═" * 62)
    print("  Démarrage en mode headless – GitHub Actions")
    print("═" * 62 + "\n")

    run_scraping()   # → écrit achievements.js (+ tente le fichier Excel)

    # ── 4. Génération de last_update.js ───────────────────────────────────
    # Ce fichier est chargé par index.html pour afficher la date/heure
    # de la dernière mise à jour dans le badge en haut à droite.
    now = datetime.now()
    ts  = now.strftime("%d/%m/%Y à %H:%M")

    with open("last_update.js", "w", encoding="utf-8") as f:
        f.write(f'const lastUpdate = "{ts}";')

    print(f"\n📅 last_update.js généré  :  {ts}")
    print("✅ Processus headless terminé avec succès.")
