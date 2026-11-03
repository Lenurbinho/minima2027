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
- ⏳ Scraper 2027 pas encore écrit (voir Feuille de route). Pas encore de workflow GitHub Actions.

## Architecture

```
data/championnats.json   ← SOURCE UNIQUE : championnats, épreuves, standards EA + FFA,
                            périodes, dates clés, règles, thème graphique
data/achievements.json   ← généré par le scraper (ne pas éditer à la main)
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
- URL type : `https://worldathletics.org/records/toplists/{famille}/{slug}/{environnement}/{men|women}/{senior|u20|u18}/{année}?regionType=countries&region=fra&timing=electronic&windReading=regular&page=1&bestResultsOnly=false&maxResultsByCountry=all`
  - `bestResultsOnly=false` est **indispensable** : sinon seule la meilleure perf de
    l'année apparaît, et un athlète dont le record de saison est hors période mais qui a
    une perf qualifiante dans la période est oublié (cas Thibaut Collet à la perche, 2026).
  - La liste est triée par perf : **`break` dès qu'une perf ne passe plus le seuil**
    (le scraping est passé de 15 min à 6 min). Mais **`continue`** (pas `break`) quand
    seule la date est hors période : une perf moins bonne plus bas peut être dans la période.
  - Ne lire que `page=1` fonctionnait en 2026 pour la France ; à vérifier si des épreuves
    très fournies (60 m) dépassent une page.
- **À vérifier pour l'hiver** : segment `{environnement}` (`indoor` / `outdoor` / `all`),
  slugs salle (`sprints/60-metres`, `hurdles/60-metres-hurdles`, `combined-events/heptathlon`,
  `combined-events/pentathlon`), et ce que couvre l'année « 2027 » en salle
  (les meetings de décembre 2026 sont-ils dans la liste 2027 ?).
- WA peut renvoyer des tableaux vides tôt le matin (maintenance) : le run de 6h56 du
  26/06/2026 a raté une qualifiée que le run suivant a trouvée. → voir « Garde-fous ».

### Bilans FFA (athle.fr)
- `https://www.athle.fr/bases/liste.aspx?frmpostback=true&frmbase=bilans&frmmode=1&frmespace=0&frmannee={année}&frmepreuve={code}&frmsexe={M|F}&frmcategorie={''|JU|CA|ES}&frmnationalite=1&frmvent=VR`
  - `frmsexe=M` pour les hommes (`H` ne renvoie rien), `F` pour les femmes.
  - `frmcategorie` : vide = toutes, `JU` = U20, `CA` = U18, `ES` = U23.
  - `frmnationalite=1` : Français uniquement (indispensable).
  - **À vérifier pour l'hiver** : `frmespace` semble choisir salle/plein air ; et l'année
    FFA d'une perf de décembre 2026.
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
  Solution 2026 : tâche planifiée Claude Code à 7h30 qui déclenche `workflow_dispatch`.
  Alternative robuste : un service de cron externe (ex. cron-job.org) qui appelle l'API
  `workflow_dispatch` avec un jeton à droits limités.
- Prévoir `timeout-minutes: 30`.
- Travailler avec **git normalement** (clone local, commit, push). En 2026 le dossier
  local n'était pas un dépôt git et on poussait via l'API GitHub fichier par fichier.

## Feuille de route (demandes de l'utilisateur, par ordre)
1. **Scraper 2027** (`scraper/` ou `recherche_minima.py`) qui lit `championnats.json`,
   interroge WA (salle + plein air équivalent) et la FFA, et écrit `achievements.json`.
   Réutiliser les fonctions éprouvées de `references/legacy_2026/recherche_minima_v5.py`
   (parsing des temps, dates, dédoublonnage) plutôt que de tout réécrire.
2. **Minima FFA** : intégrer dès que l'utilisateur les fournit (nouveaux champs dans
   `championnats.json`, colonne « Minima FFA » déjà prévue sur le site).
3. **Mise à jour quotidienne fiable** + workflow GitHub Actions.
4. **Garde-fous** : ne jamais écraser `achievements.json` par un résultat plus pauvre
   (ex. si une épreuve qui avait des qualifiés en renvoie zéro, ou si WA renvoie trop de
   tableaux vides) : réessayer plus tard et garder les anciennes données.
5. **Noms harmonisés `Prénom NOM`** quelle que soit la source (NOM en majuscules ;
   attention aux noms composés et particules : `Le Clezio`, `De Oliveira`…).
6. **Doublons** : un athlète = une ligne par épreuve, avec sa meilleure perf valable.
7. **Notifications par e-mail** des nouveaux minima. Piste recommandée : générer un flux
   RSS (`feed.xml`) des nouveaux qualifiés à chaque run, et le brancher sur un service
   « RSS vers e-mail » (Buttondown, Mailchimp, Follow.it…) qui gère inscriptions et
   désinscriptions sans backend. À valider avec l'utilisateur.
8. **Résumé exportable** : remplacer l'export Excel 2026 (jugé peu satisfaisant) par un
   résumé exploitable sur une page, probablement en PDF. À concevoir avec l'utilisateur.
9. **Championnats jeunes été 2027** : nouveaux onglets, chacun avec la charte graphique
   et la police de son championnat.

## Conventions
- Tester tout changement de format ou de dédoublonnage sur **toutes les familles**
  d'épreuves (sprint, demi-fond, haies, sauts, lancers, combinées), pas seulement celle
  qui a motivé le changement.
- Prévisualiser le site en local : `python -m http.server 8027` à la racine (le site lit
  ses JSON par `fetch()`, il ne marche pas en double-cliquant sur `index.html`).
- Après chaque modification validée : commit + push sur `main`, et relancer le workflow
  de mise à jour quand il existera.
