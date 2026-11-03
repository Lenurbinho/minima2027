# Projet : Suivi des minima FFA pour les championnats internationaux

## Objectif
Ce projet scrape plusieurs sources de résultats d'athlétisme pour détecter les
athlètes français ayant réalisé un minima FFA 2026 (CE Birmingham, CM U20 Eugene,
CE U18 Rieti), et affiche le résultat sur un site statique (`index.html` +
`achievements.js`), régénéré par une GitHub Action (`update-minima.yml`).

## Fichiers du projet
- `recherche_minima_v5.py` — le script principal de scraping/filtrage (~1300 lignes)
- `run_headless.py` — point d'entrée headless utilisé par la CI (GitHub Actions)
- `update-minima.yml` — workflow GitHub Actions qui exécute le script périodiquement
  et publie le site
- `index.html` / `achievements.js` / `last_update.js` — le site statique généré
  (achievements.js est écrasé par le script à chaque run)

## Architecture du script

### Sources de données (et leur ordre de priorité en cas de doublon)
1. **World Athletics** (`fetch_wa_event` / `_fetch_wa_slug`) — toplists piste pour
   toutes les épreuves. `MAP_WA_SLUGS` fait la correspondance épreuve → slug WA.
   `MAP_WA_SLUGS_SECONDAIRES` permet d'interroger un slug additionnel pour une
   même épreuve (actuellement : `10000m` → ajoute aussi `road-running/10-kilometres`,
   car le minima FFA CE "10000m" est explicitement libellé "10000m - 10km").
2. **Bilans FFA / athle.fr** (`fetch_ffa_10km_route`) — actuellement implémenté
   **seulement pour le 10km route** (épreuve `10000m`, code FFA `frmepreuve=261`).
   - La page `athle.fr/bases/liste.aspx?frmbase=bilans` est rendue côté serveur :
     un simple GET suffit (`frmpostback=true` est juste un nom de paramètre, pas
     un vrai mécanisme ASP.NET à `__VIEWSTATE`).
   - `frmnationalite=1` est **indispensable** pour ne garder que les Français
     (sans ce paramètre le classement mélange toutes nationalités).
   - **Pas encore généralisé aux autres épreuves** — voir TODO ci-dessous.
3. **Tilastopaja** (`fetch_tilastopaja_all`) — toplists Europe Top 20, utilisé pour
   toutes les épreuves comme complément à WA.

La fusion finale (`merge_and_filter_athletes`) reçoit `wa_list` (WA + sources
secondaires éventuelles) et `tila_list`, applique le filtre minima + période, puis
dédoublonne et garde la meilleure perf par athlète.

### Dédoublonnage par nom (`name_match_key`)
WA donne les noms en `Prénom Nom`, la FFA en `NOM Prénom`. Le dédoublonnage utilise
une clé insensible à l'ordre des mots (tokens triés alphabétiquement), pas la
chaîne brute. **Ne jamais revenir à une comparaison de chaîne brute** pour cette
logique, ça réintroduit des doublons (ex. "Yann Schrub" / "Schrub Yann").

### Format d'affichage des performances chronométrées
Format cible : `[Hh][M]'SS"[CC]` (heures optionnelles, centièmes optionnels selon
la source) :
- `< 60s` → `SS"[CC]` (ex. `10"05`)
- `< 1h` → `M'SS"[CC]` (ex. `3'37"50`, `26'43"`)
- `>= 1h` → `Hh MM'SS"[CC]` (ex. `2h05'58"`)
- Centièmes **uniquement si la source en fournissait** (détecté par
  `perf_has_centiseconds` : présence d'un point décimal suivi d'un chiffre dans
  le texte brut). Le 10km route et le marathon n'ont généralement pas de centièmes.

Géré par `format_running_perf(seconds, has_centiseconds)` + `perf_has_centiseconds(text)`,
appliqué en fin de `merge_and_filter_athletes` sur toutes les épreuves de course
(`is_running`). **Ne jamais appliquer un format fixe type `M:SS` à toutes les
épreuves** — ça casse les sprints (perd les centièmes, affiche des `0:XX`
absurdes) et le demi-fond/steeple (perte de précision).

### Périodes de réalisation (`PERIODES_MINIMA_DEFAUT` / `PERIODES_MINIMA_SPECIFIQUES`)
La période de qualification dépend de la catégorie d'épreuve, **pas seulement du
championnat** (cf. annexes 1 des modalités de sélection FFA 2026 : CE.pdf,
CMU20.pdf, CEU18.pdf, fournis par l'utilisateur, plus disponibles désormais que
sous forme de connaissance déjà extraite ici — si besoin de les revérifier,
demander à l'utilisateur de les re-fournir).
- **CE** : périodes différentes pour 5000m, 10000m, Heptathlon, Decathlon, Marathon
  et marches longues vs. le reste (cat. 1 générique : 1er mai-26 juillet 2026).
  Marathon CE : 1er sept 2025 - **19 avril 2026** (période très courte, vérifiée
  mais à reconfirmer si la FFA publie une mise à jour).
- **U20** : périodes différentes entre Minima A et Minima B ; le script utilise
  toujours la période du Minima B car c'est le seuil retenu pour le filtrage
  (`limit_to_check = limit_b if limit_b is not None else limit_a`).
- **U18** : une seule période sauf pour les épreuves combinées.
- `get_periode_minima(champ, gender, event)` résout la période applicable avec
  repli sur le défaut. Toute nouvelle dérogation détectée doit être ajoutée à
  `PERIODES_MINIMA_SPECIFIQUES`, jamais codée en dur ailleurs.

### Minima FFA (`MINIMA_FFA`)
Dict `champ -> genre -> épreuve -> (minima_A, minima_B_ou_None)`. Toutes les
valeurs ont été vérifiées une à une contre les annexes FFA lors d'une session
précédente (un seul bug trouvé et corrigé : `ce.m.Disque` Minima B était à 65.00
au lieu de 65.50).

## TODO / limites connues
1. **FFA non généralisé** : seul le 10km route (10000m CE) a une source FFA.
   Si on veut étendre à d'autres épreuves (ex. marche, semi-marathon), il faudra
   une fonction générique `fetch_ffa_event(epreuve_code, gender, champ)` avec un
   mapping épreuve FFA → code `frmepreuve` (le dropdown complet des codes a été vu
   une fois dans une page HTML fournie par l'utilisateur — lui redemander si besoin).
2. **Tests réseau impossibles dans l'environnement précédent** (sandbox sans accès
   à `worldathletics.org` ni `athle.fr`) : toute la logique de scraping a été
   validée par des tests unitaires sur des extraits HTML reconstitués à la main,
   **jamais en conditions réelles bout-en-bout**. Premier réflexe avec Claude Code :
   lancer `python run_headless.py` (ou équivalent) sur le vrai réseau et comparer
   le résultat à `achievements.js` actuel pour détecter d'éventuels écarts.
3. **Mention de restriction de copie sur athle.fr** ("La FFA n'autorise pas la
   copie des données affichées sur cette page") — point juridique non tranché,
   à clarifier avec l'utilisateur/la FFA si l'usage s'étend.
4. `code_tislatopaja.html` (non inclus dans cet export) était un fixture de debug
   pour le parseur Tilastopaja — le redemander à l'utilisateur si nécessaire pour
   écrire des tests.

## Conventions de travail
- Toujours tester les fonctions de parsing sur un extrait HTML reconstitué fidèle
  (mêmes classes/attributs que la vraie page) avant de considérer un correctif terminé,
  tant que l'accès réseau réel n'est pas confirmé disponible.
- Toute modification de format d'affichage ou de logique de dédoublonnage doit être
  re-testée sur **toutes les catégories d'épreuves** (sprint, demi-fond, steeple,
  marche, route/marathon, combinées), pas seulement l'épreuve qui a motivé le
  changement — c'est exactement le type de régression qui s'est produit une fois.
