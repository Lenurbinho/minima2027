# Projet : Minima FFA — saison 2027 (hiver puis été)

## Objectif
Détecter automatiquement les athlètes français ayant réalisé un minima pour les
championnats internationaux 2027 et les afficher sur un site statique (GitHub Pages),
mis à jour chaque jour. Premier championnat : **Europe en salle, Valencia, 4–7 mars 2027**.
Les championnats jeunes de l'été 2027 s'ajouteront comme onglets supplémentaires.

- Dépôt : `Lenurbinho/minima2027` (public) — site : https://lenurbinho.github.io/minima2027/
- Projet de la saison précédente : `Lenurbinho/minima2026` (copie de référence locale
  dans `references/legacy_2026/`, avec son ancien CLAUDE.md).
- L'utilisateur est francophone : interface, commits et échanges **en français**.

## État au 03/11/2026
- ✅ Site (`index.html`) entièrement piloté par `data/championnats.json` + `data/achievements.json`.
- ✅ Standards European Athletics Valencia 2027 saisis (règlement d'avril 2026,
  `references/EA_EIC2027_Qualification_System_avril2026.pdf`).
- ⏳ **Minima et modalités FFA : pas encore publiés** — l'utilisateur les fournira.
  Champ `ffa: null` partout et `minima_ffa_publies: false`.
- ✅ `scraper.py` (03/11/2026) : WA + FFA, salle + plein air, testé en réel (~1 min,
  152 requêtes, 34 qualifiés sur les standards EA, perfs de l'été 2026 et de fin d'hiver 2026).
- ✅ Workflow quotidien GitHub Actions `mise-a-jour.yml` (03/11/2026), garde-fous et
  détection des nouveaux qualifiés.

## Architecture

```
data/championnats.json   ← SOURCE UNIQUE : championnats, épreuves, standards EA + FFA,
                            périodes, dates clés, règles, thème graphique
data/achievements.json   ← généré par scraper.py (ne pas éditer à la main)
scraper.py               ← WA + FFA → achievements.json (sources par épreuve : dict SOURCES)
index.html               ← site statique, lit les 2 JSON via fetch()
assets/                  ← visuels des championnats (bannière Valencia)
references/              ← règlements, dictionnaire des codes FFA, code 2026
```

**Règle d'or** : une épreuve, un minima ou une période n'existe qu'à un seul endroit,
`championnats.json`. Le scraper Python et le site le lisent tous les deux. En 2026, les
minima étaient dupliqués entre le Python (`MINIMA_FFA`) et le HTML (`DATA`), avec une
table `EVENT_MAPPING` pour réconcilier les noms : source de bugs, à ne pas reproduire.
Les `id` d'épreuve (`60m`, `60mH`, `hauteur`, `combines`…) sont les mêmes partout.

### Format de `achievements.json`
```json
{ "maj": "2027-01-15T07:30:00+01:00",
  "championnats": { "eic2027": { "m": { "60m": [
      { "nom": "Prénom NOM", "perf": "6.55", "date": "2027-02-14", "lieu": "Miramas (FRA)",
        "source": "WA", "condition": "salle", "epreuve_realisee": null } ] }, "f": {} } } }
```
- `perf` au **format WA** (`6.55`, `1:45.12`, `8.17`, `6250`) : c'est le site qui formate
  l'affichage (`6"55`, `1'45"12`, `8.17`, `6250 pts`). Garder les centièmes seulement
  si la source les donne.
- `condition` : `salle` ou `plein_air` ; `epreuve_realisee` renseigné quand la perf vient
  d'une épreuve équivalente (ex. `100 m` pour le 60 m, `Heptathlon` pour le pentathlon).
- `date` en ISO (`AAAA-MM-JJ`).

### Thème par championnat
Chaque championnat a un bloc `theme` (couleurs, polices Google Fonts, bannière). Le site
l'applique en variables CSS au changement d'onglet. Pour un nouveau championnat :
l'utilisateur fournit une image ou un site officiel, on en extrait la palette et une
police Google Fonts proche, on ajoute la bannière dans `assets/`.
Valencia 2027 : bleus `#0b2a8f / #1748d6 / #2b8cff`, jaune `#f6b400`, police Outfit.

## Règlement European Athletics — Valencia 2027 (avril 2026)
Déjà saisi dans `championnats.json`. Points qui comptent pour le scraper :
- **Périodes** : standards du 22/02/2026 au 21/02/2027 ; épreuves combinées du
  22/08/2025 au 21/02/2027 ; Top Lists du 01/11/2026 au 21/02/2027.
- La période des standards **inclut l'été 2026 en plein air** → il faut scraper le plein
  air 2026 **et** la salle (fin d'hiver 2026 + hiver 2027).
- **Équivalences plein air** : 60 m ← 100 m ; 60 m haies ← 110 m haies / 100 m haies ;
  400 m → 3 000 m ont un standard plein air distinct (plus dur) ; heptathlon H ← décathlon
  (8550) ; pentathlon F ← heptathlon (6600). Sauts et poids : un seul standard (salle ou
  plein air — à reconfirmer avec le règlement FFA).
- Courses ≥ 400 m : piste couverte surdimensionnée = standard plein air.
- Refusés : chronos manuels (60, 100, 400, 800, haies), vent > 2 m/s ou non mesuré,
  courses mixtes. Âge : nés en 2011 ou avant ; poids hommes : nés en 2009 ou avant.
- Les **minima FFA** peuvent être plus durs et/ou restreindre les périodes : ils priment
  sur le site dès qu'ils sont connus. Prévoir dans `championnats.json` les champs FFA
  (minima, période, éventuelle compétition de référence obligatoire).

## Leçons apprises en 2026 (ne pas réapprendre à la dure)

### World Athletics (toplists)
- URL type : `https://worldathletics.org/records/toplists/{famille}/{slug}/all/{men|women}/{senior|u20|u18}/{année}?regionType=countries&region=fra&timing=electronic&windReading=regular&page={n}&bestResultsOnly=false&maxResultsByCountry=all`
  - Bilans WA en **année civile** : novembre-décembre 2026 sont dans la liste 2026,
    janvier-février 2027 dans la liste 2027 → interroger les deux.
  - `bestResultsOnly=false` est **indispensable** : sinon seule la meilleure perf de
    l'année apparaît, et un athlète dont le record de saison est hors période mais qui a
    une perf qualifiante dans la période est oublié (cas Thibaut Collet à la perche, 2026).
  - La liste est triée par perf : **`break` dès qu'une perf ne passe plus le seuil**
    (le scraping est passé de 15 min à 6 min). Mais **`continue`** (pas `break`) quand
    seule la date est hors période : une perf moins bonne plus bas peut être dans la période.
  - Pages de 100 lignes : le scraper enchaîne les pages tant que la dernière perf passe
    encore le seuil (la page 2 existe bien, ex. 400 m hommes 2026).
- Vérifié le 03/11/2026 : les segments `indoor`, `outdoor` et `all` renvoient **la même
  liste** (salle + plein air mélangés). Seule la mention `(i)` à la fin du lieu dit si une
  perf est en salle : le scraper s'en sert (mode `auto`). Sans ça, des perfs plein air
  passaient avec le standard salle, plus facile (faux qualifiés au 400 m, 800 m, 1500 m).
- Noms WA déjà au format `Prénom NOM` (NOM en majuscules). Lieu : `Stade, Ville (PAYS) (i)`.
- 100 lignes par page, page 1 seulement : suffisant pour des standards de ce niveau.
- Combinées en salle (`combined-events/heptathlon` / `pentathlon` en `indoor`) : liste
  vide, même sans filtre pays. Le plein air (`decathlon`, `heptathlon`) fonctionne.
  En salle, on compte sur la FFA (codes 716 / 714).
- La liste WA 2027 est vide au 03/11/2026 (normal, année civile).
- WA peut renvoyer des tableaux vides tôt le matin (maintenance) : le run de 6h56 du
  26/06/2026 a raté une qualifiée que le run suivant a trouvée. → voir « Garde-fous ».

### Bilans FFA (athle.fr)
- `https://www.athle.fr/bases/liste.aspx?frmpostback=true&frmbase=bilans&frmmode=1&frmespace=0&frmannee={année}&frmepreuve={code}&frmsexe={M|F}&frmcategorie={''|JU|CA|ES}&frmnationalite=1&frmvent=VR`
  - `frmsexe=M` pour les hommes (`H` ne renvoie rien), `F` pour les femmes.
  - `frmcategorie` : vide = toutes, `JU` = U20, `CA` = U18, `ES` = U23.
  - `frmnationalite=1` : Français uniquement (indispensable).
  - `frmespace` n'a **aucun effet**. Salle et plein air partagent le code pour les courses
    du 400 m et plus ; les perfs en salle y sont suffixées `(i)` (`6''54 (i) (RP)`). Codes
    propres à la salle : 60 m 106, 60 m haies 354 (H) / 351 (F), 3000 m piste courte 231,
    sauts 511–514, poids 657 (H) / 654 (F), heptathlon H 716, pentathlon F 714.
  - **La mention `(i)` n'existe pas partout** : jamais sur les codes salle des combinées
    (716, 714), et un 60 m couru dehors n'en a pas. Elle ne sert donc qu'à départager les
    codes mixtes ; sur un code salle, toute perf est une perf de salle.
  - Les combinées s'écrivent avec une espace des milliers : `4 634 pts`.
  - **Une seule perf par athlète** (sa meilleure de la saison), contrairement à WA avec
    `bestResultsOnly=false` : seul WA rattrape une perf qualifiante qui n'est pas la meilleure.
  - L'année FFA n'est pas l'année civile : la liste « 2026 » contient des perfs de
    septembre 2025. Le filtre de période fait le tri ; le scraper interroge 2026 et 2027.
  - Les prénoms longs sont tronqués (`KOUNTA Muhammad Abdall`) : la clé de
    dédoublonnage n'utilise que le NOM et le premier prénom.
- Codes d'épreuve `frmepreuve` : `references/Dictionnaire_Epreuves_FFA.xlsx` (colonnes
  M-CA, M-JU, M-ES, F-CA… = catégories concernées). Les codes dépendent du **poids de
  l'engin / hauteur des haies** : un mauvais code ramène des seniors en U18 (bug 2026 :
  poids U18 F = 3 kg, code 603, et non 604 = 4 kg).
- Centièmes notés avec **deux apostrophes** : `1'44''68`. Lire tout le texte de la
  cellule (pas seulement le `<b>`) puis remplacer `''` par `"`.

### Fusion et dédoublonnage
- Clé de dédoublonnage insensible à l'ordre des mots (jetons triés) : WA donne
  `Prénom NOM`, la FFA `NOM Prénom`. **Jamais de comparaison de chaînes brutes.**
- À perf égale à moins d'une seconde près, garder la version **avec centièmes**
  (la FFA tronque parfois : `1'59` contre `1:59.21` chez WA).
- Exclure les chronos manuels (au dixième) des courses.
- Retirer vent et mentions de record (`(+0.0)`, `(RP)`, `(NR)`…) avant tout calcul.

### GitHub Actions
- Le `schedule` (cron) de GitHub est peu fiable (retards de plusieurs heures, runs sautés).
  Solution 2026 : tâche planifiée Claude Code à 7h30 qui déclenche `workflow_dispatch`,
  mais elle ne tourne que si l'application est ouverte sur le PC de l'utilisateur.
  **Solution 2027** (souhait de l'utilisateur : zéro PC, zéro action) : plusieurs créneaux
  cron ; chaque créneau s'arrête tout de suite si un créneau a réussi dans les 12 dernières
  heures. Ne pas revenir à une tâche planifiée locale.
  Constat (4-13/11/2026) : GitHub déclenche les crons de ce dépôt avec **7h30 à 10h30 de
  retard** (créneau de 06:35 UTC exécuté vers 14h30-15h30 UTC). Depuis le 14/11/2026, les
  créneaux sont donc la nuit (21:35, 22:35, 23:35 et 02:35 UTC) pour tomber le matin. Si la
  mise à jour arrive le soir ou l'après-midi, comparer `createdAt` des runs aux créneaux
  (`gh run list --workflow mise-a-jour.yml`) et recaler.
- Prévoir `timeout-minutes: 30`.
- Travailler avec **git normalement** (clone local, commit, push). En 2026 le dossier
  local n'était pas un dépôt git et on poussait via l'API GitHub fichier par fichier.

## Feuille de route (demandes de l'utilisateur, par ordre)
1. ✅ **Scraper 2027** (`scraper.py`). Choix d'affichage : courses et combinées → la perf
   en salle prime sur le plein air (c'est l'épreuve du championnat) ; concours (même
   standard) → la meilleure perf. Restent à faire : courses mixtes (non détectables
   aujourd'hui) et pistes surdimensionnées (pour l'instant traitées comme de la salle).
2. **Minima FFA** : intégrer dès que l'utilisateur les fournit (nouveaux champs dans
   `championnats.json`, colonne « Minima FFA » déjà prévue sur le site).
3. ✅ **Mise à jour quotidienne** : `.github/workflows/mise-a-jour.yml`, entièrement sur
   GitHub (4 créneaux de nuit, arrêt si un run a réussi depuis moins de 12 h, lancement
   manuel possible, ~1 min 15 s, résumé dans l'onglet Actions).
4. ✅ **Garde-fous** (`scraper.py`) : une source en erreur, ou une épreuve qui tombe à zéro
   qualifié alors qu'elle en avait, garde les athlètes du run précédent. Conséquence : un
   faux positif ne disparaît pas tout seul, il faut l'enlever de `achievements.json` à la
   main. Chaque run liste aussi les nouveaux qualifiés (ligne `🆕`).
5. **Noms harmonisés `Prénom NOM`** quelle que soit la source (NOM en majuscules ;
   attention aux noms composés et particules : `Le Clezio`, `De Oliveira`…).
6. **Doublons** : un athlète = une ligne par épreuve, avec sa meilleure perf valable.
7. **Notifications par e-mail** des nouveaux minima. Piste recommandée : générer un flux
   RSS (`feed.xml`) des nouveaux qualifiés à chaque run, et le brancher sur un service
   « RSS vers e-mail » (Buttondown, Mailchimp, Follow.it…) qui gère inscriptions et
   désinscriptions sans backend. À valider avec l'utilisateur.
8. ✅ **Fiche PDF speaker** (bouton « Fiche PDF (1 page) », remplace l'export Excel 2026).
   Exigences de l'utilisateur : 1 clic, A4 paysage, **jamais plus d'une page**, tout lisible
   d'un coup d'œil par un speaker, charte du championnat actif. Fonctionnement
   (`ficheHTML`, `ajusterFiche`, `canvasFiche` dans `index.html`) : fiche HTML de
   1123 × 794 px construite hors écran, colonnes Hommes / Femmes, une ligne par épreuve
   (standard, équivalent plein air, places) avec nom · perf · date · lieu · badge PA ; la
   taille de texte descend de 14 à 9 px pour tout faire tenir, puis mode condensé
   (2 athlètes par ligne sans date ni lieu, jusqu'à 7,5 px), puis réduction globale en
   dernier recours. Rendu par html2canvas puis jsPDF (chargés au premier clic, cdnjs) ;
   **pas de `color-mix()` dans les styles `.fx-*`**, html2canvas ne le lit pas. Mesuré :
   données réelles 11 px, 72 qualifiés 9,25 px, 144 qualifiés 8,25 px condensé.
9. **Championnats jeunes été 2027** : nouveaux onglets, chacun avec la charte graphique
   et la police de son championnat.

## Conventions
- Tester tout changement de format ou de dédoublonnage sur **toutes les familles**
  d'épreuves (sprint, demi-fond, haies, sauts, lancers, combinées), pas seulement celle
  qui a motivé le changement.
- Prévisualiser le site en local : `python -m http.server 8027` à la racine (le site lit
  ses JSON par `fetch()`, il ne marche pas en double-cliquant sur `index.html`).
- Après chaque modification validée : commit + push sur `main`, puis relancer le workflow
  (`gh workflow run mise-a-jour.yml --repo Lenurbinho/minima2027`).
