#!/usr/bin/env python3
"""Scraper minima 2027.

Lit data/championnats.json (épreuves, standards, périodes), interroge les toplists
World Athletics et les bilans FFA, en salle et en plein air, puis écrit
data/achievements.json (format décrit dans CLAUDE.md).

Usage : python scraper.py
"""

import json
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

RACINE = Path(__file__).parent
CONFIG = RACINE / "data" / "championnats.json"
SORTIE = RACINE / "data" / "achievements.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "fr,fr-FR;q=0.8,en;q=0.5",
}

MOIS_EN = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}

# Épreuves où les chronos manuels sont refusés (règlement EA)
CHRONO_ELECTRONIQUE_OBLIGATOIRE = {"60m", "400m", "800m", "60mH"}


# ─────────────────────────────────────────────────────────────────────────────
# Sources par épreuve
#   mode "salle"        : épreuve ou code de salle (60 m, 60 m haies, codes FFA « Salle ») :
#                         toute perf compte avec le standard salle, mention (i) ou pas
#                         (la FFA ne la met pas sur ses codes salle d'épreuves combinées)
#   mode "plein_air"    : code FFA plein air d'un concours (seuil : standard unique)
#   mode "auto"         : salle et plein air dans la même liste, la mention "(i)" tranche :
#                         standard salle si (i), sinon standard plein air (ou standard
#                         unique pour les sauts et le poids)
#   mode "plein_air_eq" : épreuve équivalente (100 m pour le 60 m…), standard plein air
#
# WA : les segments indoor / outdoor / all de l'URL renvoient la même liste (vérifié le
# 03/11/2026) → une seule liste "all" par année civile, la salle se lit à "(i)" dans le lieu.
# ─────────────────────────────────────────────────────────────────────────────
def WA(slug, mode):
    return {"src": "WA", "slug": slug, "mode": mode}


def FFA(code, mode):
    return {"src": "FFA", "code": code, "mode": mode}


def _course_identique(slug_wa, codes_ffa):
    return [WA(slug_wa, "auto")] + [FFA(c, m) for c, m in codes_ffa]


def _concours(slug_wa, code_salle, code_plein_air):
    return [WA(slug_wa, "auto"), FFA(code_salle, "salle"), FFA(code_plein_air, "plein_air")]


SOURCES = {
    "60m": {g: [WA("sprints/60-metres", "salle"), WA("sprints/100-metres", "plein_air_eq"),
                FFA(106, "salle"), FFA(110, "plein_air_eq")] for g in ("m", "f")},
    "400m":  {g: _course_identique("sprints/400-metres", [(140, "auto")]) for g in ("m", "f")},
    "800m":  {g: _course_identique("middlelong/800-metres", [(208, "auto")]) for g in ("m", "f")},
    "1500m": {g: _course_identique("middlelong/1500-metres", [(215, "auto")]) for g in ("m", "f")},
    "3000m": {g: _course_identique("middlelong/3000-metres", [(230, "auto"), (231, "salle")]) for g in ("m", "f")},
    "60mH": {
        "m": [WA("hurdles/60-metres-hurdles", "salle"), WA("hurdles/110-metres-hurdles", "plein_air_eq"),
              FFA(354, "salle"), FFA(313, "plein_air_eq")],
        "f": [WA("hurdles/60-metres-hurdles", "salle"), WA("hurdles/100-metres-hurdles", "plein_air_eq"),
              FFA(351, "salle"), FFA(310, "plein_air_eq")],
    },
    "hauteur":  {g: _concours("jumps/high-jump", 511, 501) for g in ("m", "f")},
    "perche":   {g: _concours("jumps/pole-vault", 512, 502) for g in ("m", "f")},
    "longueur": {g: _concours("jumps/long-jump", 513, 503) for g in ("m", "f")},
    "triple":   {g: _concours("jumps/triple-jump", 514, 504) for g in ("m", "f")},
    "poids": {
        "m": _concours("throws/shot-put", 657, 607),   # 7,26 kg
        "f": _concours("throws/shot-put", 654, 604),   # 4 kg
    },
    "combines": {
        # WA n'a pas de liste française des combinées en salle : la FFA s'en charge (716 / 714)
        "m": [WA("combined-events/heptathlon", "salle"), WA("combined-events/decathlon", "plein_air_eq"),
              FFA(716, "salle"), FFA(710, "plein_air_eq")],
        "f": [WA("combined-events/pentathlon", "salle"), WA("combined-events/heptathlon", "plein_air_eq"),
              FFA(714, "salle"), FFA(717, "plein_air_eq")],
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Parsing des performances, dates et noms
# ─────────────────────────────────────────────────────────────────────────────
def valeur(perf_wa):
    """'6.58' → 6.58 · '1:45.60' → 105.6 · '1:02:30' → 3750 · '6250' → 6250."""
    if perf_wa is None:
        return None
    try:
        total = 0.0
        for partie in str(perf_wa).split(":"):
            total = total * 60 + float(partie)
        return total
    except ValueError:
        return None


def nettoyer_perf_wa(texte):
    """Perf WA brute ('6.54', '8.17 A', '1:45.60h') → format WA propre, ou None."""
    t = re.sub(r"[^0-9:.]", "", texte.split("(")[0])
    return t if valeur(t) is not None else None


def perf_ffa_vers_wa(texte, type_epreuve):
    """Perf FFA ("6''54 (i) (RP)", "1'45''60", "7m31 (+0.0)", "6250 pts") → (perf WA, salle?, manuel?)."""
    salle = "(i)" in texte
    sans_mentions = re.sub(r"\([^)]*\)", " ", texte).strip()
    if type_epreuve == "combines":   # "4 634 pts" : espace des milliers
        chiffres = re.sub(r"\D", "", sans_mentions)
        return (chiffres or None), salle, False
    t = sans_mentions.split()[0] if sans_mentions else ""
    t = t.replace("''", '"').replace("’", "'")
    if type_epreuve == "concours":
        m = re.match(r"^(\d+)[m.,](\d{1,2})$", t)
        return (f"{int(m.group(1))}.{int(m.group(2)):02d}" if m else None), salle, False
    m = re.match(r"^(?:(\d+)h)?(?:(\d+)')?(\d+)\"(\d*)$", t)
    if not m:
        return None, salle, False
    h, mi, s, cs = m.groups()
    manuel = len(cs) == 1
    cs = f".{cs}" if cs else ""
    if h:
        return f"{int(h)}:{int(mi or 0):02d}:{int(s):02d}{cs}", salle, manuel
    if mi:
        return f"{int(mi)}:{int(s):02d}{cs}", salle, manuel
    return f"{int(s)}{cs}", salle, manuel


def date_wa(texte):
    """'28 FEB 2026' ou '27-28 FEB 2026' → date."""
    m = re.search(r"(\d{1,2})\s+([A-Z]{3})\s+(\d{4})", texte.upper())
    return date(int(m.group(3)), MOIS_EN[m.group(2)], int(m.group(1))) if m else None


def date_ffa(texte):
    """'28/02/26' → date."""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{2,4})", texte)
    if not m:
        return None
    a = int(m.group(3))
    return date(a + 2000 if a < 100 else a, int(m.group(2)), int(m.group(1)))


def sans_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def est_nom_de_famille(jeton):
    lettres = [c for c in jeton if c.isalpha()]
    return bool(lettres) and all(c.isupper() for c in lettres)


def nom_depuis_ffa(texte):
    """'LE CLEZIO Corentin' → 'Corentin LE CLEZIO' (les jetons en majuscules forment le NOM)."""
    jetons = texte.split()
    i = 0
    while i < len(jetons) and est_nom_de_famille(jetons[i]):
        i += 1
    return " ".join(jetons[i:] + jetons[:i]) if 0 < i < len(jetons) else texte.strip()


def cle_athlete(nom_affiche):
    """Clé de dédoublonnage : NOM + premier prénom, sans accents ni casse.
    Résiste à l'ordre des mots et aux prénoms tronqués par la FFA ('Muhammad Abdall')."""
    jetons = nom_affiche.split()
    famille = sorted(sans_accents(j).casefold() for j in jetons if est_nom_de_famille(j))
    prenoms = [sans_accents(j).casefold() for j in jetons if not est_nom_de_famille(j)]
    if not famille:   # nom sans majuscules distinctives : repli sur tous les jetons triés
        return "|".join(sorted(sans_accents(j).casefold() for j in jetons))
    return "|".join(famille) + "#" + (prenoms[0] if prenoms else "")


def lieu_wa(texte):
    """'Stadium Jean-Pellez, Aubière (FRA) (i)' → 'Aubière (FRA)' ;
    'Track, Lexington, KY (USA)' → 'Lexington, KY (USA)'."""
    parties = [x.strip() for x in texte.replace("(i)", "").split(",")]
    if len(parties) >= 3 and re.match(r"^[A-Z]{2} \(", parties[-1]):
        return f"{parties[-2]}, {parties[-1]}"
    return parties[-1]


# ─────────────────────────────────────────────────────────────────────────────
# Récupération des données
# ─────────────────────────────────────────────────────────────────────────────
def passe_seuil(v, seuil, type_epreuve):
    return v <= seuil if type_epreuve == "course" else v >= seuil


def fetch_wa(slug, genre, annee, seuil_large, type_epreuve, pages_max=10):
    """Toplist WA d'une année civile : France, salle + plein air, toutes les perfs (pas
    seulement la meilleure par athlète). Pages de 100 lignes : on les enchaîne et on
    s'arrête dès qu'une perf ne passe plus le seuil (liste triée par valeur)."""
    resultats = []
    for page in range(1, pages_max + 1):
        lignes, fini = _page_wa(slug, genre, annee, page, seuil_large, type_epreuve)
        resultats += lignes
        if fini:
            break
    return resultats


def _page_wa(slug, genre, annee, page, seuil_large, type_epreuve):
    """Lit une page de toplist WA. Retourne (perfs, fini) ; fini = rien d'utile après."""
    sexe = "women" if genre == "f" else "men"
    url = (f"https://worldathletics.org/records/toplists/{slug}/all/{sexe}/senior/{annee}"
           "?regionType=countries&region=fra&timing=electronic&windReading=regular"
           f"&page={page}&bestResultsOnly=false&maxResultsByCountry=all")
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.content, "html.parser")
    table = soup.find("table", {"class": "records-table"})
    if not table or not table.find("tbody"):
        return [], True
    entetes = [th.get_text(strip=True).lower() for th in table.find("thead").find_all("th")]
    col = {nom: entetes.index(nom) for nom in ("mark", "competitor", "dob", "venue", "date") if nom in entetes}

    resultats = []
    lignes = table.find("tbody").find_all("tr")
    for ligne in lignes:
        cells = ligne.find_all("td")
        if len(cells) <= max(col.values()):
            continue
        lieu_brut = cells[col["venue"]].get_text(" ", strip=True)
        perf = nettoyer_perf_wa(cells[col["mark"]].get_text(strip=True))
        v = valeur(perf)
        if v is None:
            continue
        if not passe_seuil(v, seuil_large, type_epreuve):
            return resultats, True
        dob = re.search(r"(19|20)\d{2}", cells[col["dob"]].get_text()) if "dob" in col else None
        resultats.append({
            "nom": " ".join(cells[col["competitor"]].get_text(" ", strip=True).split()),
            "perf": perf,
            "valeur": v,
            "date": date_wa(cells[col["date"]].get_text(strip=True)),
            "lieu": lieu_wa(lieu_brut),
            "naissance": int(dob.group(0)) if dob else None,
            "source": "WA",
            "salle": "(i)" in lieu_brut,
            "manuel": False,
        })
    return resultats, len(lignes) < 100


def fetch_ffa(code, genre, annee, seuil_large, type_epreuve):
    """Bilans FFA (Français uniquement, vent régulier). Même logique d'arrêt anticipé.
    Attention : la FFA ne donne que la meilleure perf de la saison par athlète."""
    url = ("https://www.athle.fr/bases/liste.aspx?frmpostback=true&frmbase=bilans&frmmode=1&frmespace=0"
           f"&frmannee={annee}&frmepreuve={code}&frmsexe={'F' if genre == 'f' else 'M'}"
           "&frmcategorie=&frmdepartement=&frmligue=&frmnationalite=1&frmvent=VR&frmamaxi=")
    r = requests.get(url, headers=HEADERS, timeout=40)
    r.raise_for_status()
    table = BeautifulSoup(r.content, "html.parser").find("table", {"id": "ctnBilans"})
    if not table:
        return []

    resultats = []
    for ligne in table.find_all("tr"):
        if "detail-row" in (ligne.get("class") or []):
            continue
        cells = ligne.find_all("td")
        if len(cells) < 9:
            continue
        perf, salle, manuel = perf_ffa_vers_wa(cells[1].get_text(" ", strip=True), type_epreuve)
        v = valeur(perf)
        if v is None:
            continue
        if not passe_seuil(v, seuil_large, type_epreuve):
            break
        lien = cells[2].find("a")
        naissance = re.search(r"/\s*(\d{2})", cells[6].get_text())
        aa = int(naissance.group(1)) if naissance else None
        resultats.append({
            "nom": nom_depuis_ffa((lien or cells[2]).get_text(" ", strip=True)),
            "perf": perf,
            "valeur": v,
            "date": date_ffa(cells[7].get_text(strip=True)),
            "lieu": cells[8].get_text(" ", strip=True),
            "naissance": (2000 + aa if aa <= 30 else 1900 + aa) if aa is not None else None,
            "source": "FFA",
            "salle": salle,
            "manuel": manuel,
        })
    return resultats


# ─────────────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────────────
def seuils(standard, mode):
    """Retourne (seuil salle, seuil plein air) applicables pour une source."""
    pa = (standard.get("ea_plein_air") or {}).get("valeur", standard["ea"])
    return valeur(standard["ea"]), valeur(pa)


def taches_pour(champ):
    """Liste des requêtes à faire : (épreuve, genre, source, année)."""
    taches = []
    for ep in champ["epreuves"]:
        combine = ep["type"] == "combines"
        for genre in ("m", "f"):
            if not ep.get(genre) or ep["id"] not in SOURCES:
                continue
            for src in SOURCES[ep["id"]][genre]:
                # WA : année civile (novembre-décembre 2026 dans la liste 2026) ;
                # FFA : année de saison (la liste 2026 commence dès septembre 2025)
                annees = [2025, 2026, 2027] if combine else [2026, 2027]
                taches += [(ep, genre, src, a) for a in annees]
    return taches


def executer(tache):
    ep, genre, src, annee = tache
    s_salle, s_pa = seuils(ep[genre], src["mode"])
    # Seuil le plus permissif pour l'arrêt anticipé, le tri fin se fait ensuite
    candidats = {"salle": [s_salle], "plein_air": [s_pa], "plein_air_eq": [s_pa], "auto": [s_salle, s_pa]}[src["mode"]]
    large = max(candidats) if ep["type"] == "course" else min(candidats)
    try:
        if src["src"] == "WA":
            lignes = fetch_wa(src["slug"], genre, annee, large, ep["type"])
        else:
            lignes = fetch_ffa(src["code"], genre, annee, large, ep["type"])
        return tache, lignes, None
    except Exception as e:  # réseau, HTTP, page inattendue
        return tache, [], f"{type(e).__name__}: {e}"


def qualifiant(ligne, ep, genre, src, periode):
    """Applique seuil exact, période, chrono électronique et règles d'âge."""
    standard = ep[genre]
    s_salle, s_pa = seuils(standard, src["mode"])
    mode = src["mode"]
    # La mention (i) n'est fiable que dans les listes mixtes (mode auto) : les codes FFA
    # « Salle » des combinées ne l'ont jamais, et un 60 m couru dehors reste un 60 m.
    if mode == "auto":
        mode = "salle" if ligne["salle"] else "plein_air"
    elif mode == "plein_air_eq" and ligne["salle"]:
        return None   # ex. 100 m couru en salle : ce n'est pas l'équivalence prévue
    seuil = s_salle if mode == "salle" else s_pa
    if not passe_seuil(ligne["valeur"], seuil, ep["type"]):
        return None
    if not ligne["date"] or not (periode[0] <= ligne["date"] <= periode[1]):
        return None
    if ligne["manuel"] and ep["id"] in CHRONO_ELECTRONIQUE_OBLIGATOIRE:
        return None
    naissance = ligne["naissance"]
    if naissance and (naissance > 2011 or (ep["id"] == "poids" and genre == "m" and naissance > 2009)):
        return None
    return {
        "nom": ligne["nom"],
        "perf": ligne["perf"],
        "valeur": ligne["valeur"],
        "date": ligne["date"].isoformat(),
        "lieu": ligne["lieu"],
        "source": ligne["source"],
        "condition": "salle" if mode == "salle" else "plein_air",
        "epreuve_realisee": standard["ea_plein_air"]["epreuve"] if mode == "plein_air_eq" else None,
    }


def meilleure(a, b, type_epreuve):
    """Entre deux perfs d'un même athlète : aux concours (même standard salle et plein air),
    la meilleure valeur ; sinon la salle prime (c'est l'épreuve du championnat), puis la
    meilleure valeur, puis WA (nom complet, lieu détaillé) à égalité."""
    if type_epreuve == "concours" and abs(a["valeur"] - b["valeur"]) > 1e-9:
        return a if a["valeur"] > b["valeur"] else b
    if a["condition"] != b["condition"]:
        return a if a["condition"] == "salle" else b
    if a["epreuve_realisee"] == b["epreuve_realisee"] and abs(a["valeur"] - b["valeur"]) > 1e-9:
        meilleur_a = a["valeur"] < b["valeur"] if type_epreuve == "course" else a["valeur"] > b["valeur"]
        return a if meilleur_a else b
    if a["source"] != b["source"]:
        return a if a["source"] == "WA" else b
    return a


def main():
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    ancien = json.loads(SORTIE.read_text(encoding="utf-8")) if SORTIE.exists() else {}
    sortie = {"maj": datetime.now().astimezone().isoformat(timespec="minutes"), "championnats": {}}
    erreurs, avertissements, nouveaux = [], [], []

    for champ in config["championnats"]:
        taches = taches_pour(champ)
        print(f"▶ {champ['nom']} {champ['ville']} : {len(taches)} requêtes WA/FFA")
        with ThreadPoolExecutor(max_workers=6) as pool:
            reponses = list(pool.map(executer, taches))

        par_epreuve = {}   # (genre, id épreuve) → {clé athlète: perf}
        en_echec = set()
        for (ep, genre, src, annee), lignes, erreur in reponses:
            cle_ep = (genre, ep["id"])
            if erreur:
                ref = src.get("slug") or src.get("code")
                erreurs.append(f"{champ['id']} {genre} {ep['id']} {src['src']} {ref} {annee} → {erreur}")
                en_echec.add(cle_ep)
                continue
            nom_periode = "standards_combines" if ep["type"] == "combines" else "standards"
            p = champ["periodes"][nom_periode]
            periode = (date.fromisoformat(p["debut"]), date.fromisoformat(p["fin"]))
            athletes = par_epreuve.setdefault(cle_ep, {})
            for ligne in lignes:
                q = qualifiant(ligne, ep, genre, src, periode)
                if q:
                    cle = cle_athlete(q["nom"])
                    athletes[cle] = meilleure(athletes[cle], q, ep["type"]) if cle in athletes else q

        # Garde-fous : on réintègre les athlètes du run précédent pour une épreuve si une
        # source a échoué, ou si l'épreuve tombe à zéro qualifié alors qu'elle en avait.
        # La période de qualification est fixe : un qualifié ne perd pas son standard, une
        # chute à zéro vient d'une source qui a mal répondu (ex. WA en maintenance le matin).
        # Pour retirer volontairement un athlète (faux positif corrigé), éditer achievements.json.
        precedent = ancien.get("championnats", {}).get(champ["id"], {})
        tombees_a_zero = {(g, id_ep) for g in ("m", "f") for id_ep, liste in precedent.get(g, {}).items()
                          if liste and not par_epreuve.get((g, id_ep))}
        for genre, id_ep in sorted(tombees_a_zero - en_echec):
            avertissements.append(f"{champ['id']} {genre} {id_ep} : 0 qualifié au lieu de "
                                  f"{len(precedent[genre][id_ep])}, données précédentes conservées")
        for genre, id_ep in en_echec | tombees_a_zero:
            athletes = par_epreuve.setdefault((genre, id_ep), {})
            for a in precedent.get(genre, {}).get(id_ep, []):
                a = {**a, "valeur": valeur(a["perf"])}
                athletes.setdefault(cle_athlete(a["nom"]), a)

        types = {ep["id"]: ep["type"] for ep in champ["epreuves"]}
        resultat = {"m": {}, "f": {}}
        for (genre, id_ep), athletes in sorted(par_epreuve.items()):
            if not athletes:
                continue
            sens = 1 if types[id_ep] == "course" else -1
            # Concours : classement à la perf ; courses et combinées : la salle d'abord
            salle_dabord = types[id_ep] != "concours"
            liste = sorted(athletes.values(), key=lambda a: (salle_dabord and a["condition"] != "salle", sens * a["valeur"]))
            resultat[genre][id_ep] = [{k: v for k, v in a.items() if k != "valeur"} for a in liste]
            print(f"  {genre.upper()} {id_ep:<9} {len(liste)} qualifié(s) : "
                  + ", ".join(f"{a['nom']} {a['perf']}" for a in liste))
            deja = {cle_athlete(a["nom"]) for a in precedent.get(genre, {}).get(id_ep, [])}
            nouveaux += [f"{a['nom']} ({id_ep} {'H' if genre == 'm' else 'F'}, {a['perf']})"
                         for a in liste if cle_athlete(a["nom"]) not in deja]
        sortie["championnats"][champ["id"]] = resultat

    SORTIE.write_text(json.dumps(sortie, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\n✅ {SORTIE.relative_to(RACINE)} écrit ({sortie['maj']})")
    print(f"🆕 Nouveaux qualifiés : {', '.join(nouveaux)}" if nouveaux else "🆕 Aucun nouveau qualifié")
    for a in avertissements:
        print(f"⚠️ {a}")
    if erreurs:
        print(f"⚠️ {len(erreurs)} requête(s) en échec (données précédentes conservées pour ces épreuves) :")
        for e in erreurs:
            print("   " + e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
