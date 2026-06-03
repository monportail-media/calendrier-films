#!/usr/bin/env python3
"""
Calendrier Films & Series - Script v9
Architecture Gemini - Propre et efficace

SOURCES:
  Niveau A - QC (priorite max):
    - TVmaze CA: series canadiennes/quebecoises
    - Showbizz.net: calendriers saisonniers QC (BeautifulSoup)
    - Bell Media The Lede: Crave mensuel
    - Centre de presse Radio-Canada

  Niveau B - International avec vraie VF:
    - TVmaze US/UK/AU: filtré par validation VF stricte
    - TMDb: films + validation VF

VALIDATION VF (algorithme Gemini):
  1. Langue originale = francais -> inclusion immediate
  2. Translation FR presente ET synopsis FR non vide
  3. Plateforme streaming majeure (Netflix, Apple, Disney, etc.) -> inclusion
  4. Popularite TMDb > 15.0 pour series de networks locaux

LOGOS: assets/logos/*.svg (locaux, pas de hotlinking)
CACHE: par tmdb_id (stable) + nom+annee (fallback)
CIBLE: ~1200 episodes par fenetre 9 mois
"""

import json, os, re, time, requests, urllib3
from datetime import datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── CONFIG ────────────────────────────────────────────────────────────────────
TMDB_KEY     = os.environ.get("TMDB_API_KEY", "")
TMDB_BASE    = "https://api.themoviedb.org/3"
TMDB_IMG     = "https://image.tmdb.org/t/p"
TVMAZE_BASE  = "https://api.tvmaze.com"
DATA_PATH    = Path("data.json")
TODAY        = datetime.now()
TODAY_STR    = TODAY.strftime("%Y-%m-%d")
YEAR         = TODAY.year
HISTORY_DAYS = 90
FUTURE_DAYS  = 180

# ── LOGOS LOCAUX (Gemini Partie 4) ────────────────────────────────────────────
LOGO_MAP = {
    "Netflix":      "assets/logos/netflix.svg",
    "Prime Video":  "assets/logos/prime.svg",
    "Disney+":      "assets/logos/disney.svg",
    "Apple TV+":    "assets/logos/apple.svg",
    "Hulu":         "assets/logos/hulu.svg",
    "Paramount+":   "assets/logos/paramount.svg",
    "Peacock":      "assets/logos/peacock.svg",
    "Crave":        "assets/logos/crave.svg",
    "ICI TOU.TV":   "assets/logos/toutv.svg",
    "TVA+":         "assets/logos/tva.svg",
    "Noovo":        "assets/logos/noovo.svg",
    "Tele-Quebec":  "assets/logos/telequebec.svg",
    "Club Illico":  "assets/logos/illico.svg",
    "Vrai":         "assets/logos/vrai.svg",
    "Historia":     "assets/logos/historia.svg",
    "Series+":      "assets/logos/seriesplus.svg",
    "ARTV":         "assets/logos/artv.svg",
    "TV5":          "assets/logos/tv5.svg",
    "Unis TV":      "assets/logos/unis.svg",
    "ONF":          "assets/logos/onf.svg",
    "Cinema":       "assets/logos/cinema.svg",
}

def get_logo(platform):
    return LOGO_MAP.get(platform, "assets/logos/default.svg")

# ── PLATEFORMES ───────────────────────────────────────────────────────────────
# Plateformes streaming qui doublent SYSTEMATIQUEMENT en francais au Quebec
STREAMING_GIANTS = {
    "netflix", "apple tv+", "disney+", "amazon", "prime video",
    "paramount+", "hulu", "peacock", "crave",
    "apple", "disney", "amazon prime",
    # HBO inclus car disponible via Crave avec VF
    "hbo",
}

# Reseaux QC/CA -> plateforme normalisee
QC_NETWORK_MAP = {
    "ICI Radio-Canada Tele": "ICI TOU.TV",
    "ICI TOU.TV":            "ICI TOU.TV",
    "Radio-Canada":          "ICI TOU.TV",
    "ARTV":                  "ARTV",
    "ICI ARTV":              "ARTV",
    "Tele-Quebec":           "Tele-Quebec",
    "Telequebec":            "Tele-Quebec",
    "TVA":                   "TVA+",
    "Noovo":                 "Noovo",
    "Club Illico":           "Club Illico",
    "Illico+":               "Club Illico",
    "Super Ecran":           "Club Illico",
    "Series+":               "Series+",
    "Canal Vie":             "Historia",
    "Historia":              "Historia",
    "Canal D":               "Historia",
    "Savoir Media":          "Tele-Quebec",
    "CTV":                   "Crave",
    "CBC":                   "ICI TOU.TV",
    "Global":                "Crave",
    "Crave":                 "Crave",
    "TV5":                   "TV5",
    "Unis":                  "Unis TV",
    "TV5 Quebec Canada":     "TV5",
    "Vrai":                  "Vrai",
    "ONF":                   "ONF",
}

# Reseaux streaming UNIQUEMENT avec contenu double en francais au Quebec
# REGLE: Seulement les plateformes qui ont contractuellement la VF pour leurs originaux
STREAMING_NETWORK_MAP = {
    # Plateformes qui doublent TOUS leurs originaux en francais au Quebec
    "Netflix":          "Netflix",
    "Apple TV+":        "Apple TV+",
    "Disney+":          "Disney+",
    "Amazon":           "Prime Video",
    "Prime Video":      "Prime Video",
    # HBO/Crave: originaux HBO disponibles en VF sur Crave
    "HBO":              "Crave",
    # Hulu: originaux disponibles en VF via Disney+ au Canada
    "Hulu":             "Disney+",
    # FX: originaux sur Disney+ en VF
    "FX":               "Disney+",
    # National Geographic: sur Disney+ en VF
    "National Geographic": "Disney+",
    # Peacock: originaux Peacock disponibles en VF sur Prime Video CA
    "Peacock":          "Peacock",
    # Paramount+: seulement les ORIGINAUX Paramount+ (pas CBS)
    "Paramount+":       "Paramount+",
    # Crunchyroll: anime souvent double en francais
    "Crunchyroll":      "Prime Video",
}

PLATFORM_URLS = {
    "Netflix":      "https://www.netflix.com",
    "Prime Video":  "https://www.primevideo.com",
    "Disney+":      "https://www.disneyplus.com",
    "Apple TV+":    "https://tv.apple.com",
    "Hulu":         "https://www.hulu.com",
    "Paramount+":   "https://www.paramountplus.com",
    "Peacock":      "https://www.peacocktv.com",
    "Crave":        "https://www.crave.ca",
    "ICI TOU.TV":   "https://ici.tou.tv",
    "TVA+":         "https://www.tvaplus.ca",
    "Noovo":        "https://www.noovo.ca",
    "Tele-Quebec":  "https://www.telequebec.tv",
    "Club Illico":  "https://www.illico.com",
    "Vrai":         "https://www.vrai.ca",
    "Historia":     "https://www.historia.ca",
    "Series+":      "https://www.seriesplus.com",
    "ARTV":         "https://ici.artv.ca",
    "TV5":          "https://www.tv5unis.ca",
    "Unis TV":      "https://unis.ca",
    "ONF":          "https://www.onf.ca",
    "Cinema":       "https://www.themoviedb.org",
}

# Chaines TV locales europeennes a exclure completement
EXCLUDED_EU_NETWORKS = {
    "TF1","France 2","France 3","France 4","France 5","M6","W9","TMC","Arte France",
    "RTL-TVI","La Une","La Deux","RTS Un","RTS Deux",
    "ARD","ZDF","RTL","Sat.1","ProSieben","Das Erste",
    "TVE","TVE 1","Antena 3","Telecinco","Cuatro","La Sexta",
    "RAI 1","RAI 2","RAI 3","Canale 5","Italia 1",
    "NPO 1","NPO 2","SVT1","SVT2","NRK1","NRK2","DR1","DR2",
    "RTP1","RTP2","ORF 1","ORF 2","ERT",
}

# Pays QC/CA
QC_NETWORKS_SET = set(QC_NETWORK_MAP.keys())

COUNTRY_TAGS = {
    "CA":"CA","FR":"FR","GB":"UK","AU":"AU","DE":"EU","ES":"EU",
    "IT":"EU","JP":"JP","KR":"KR","US":"USA","BE":"EU","NL":"EU",
    "SE":"EU","CH":"EU","NO":"EU","DK":"EU","PL":"EU","MX":"MX",
    "BR":"BR","IN":"IN","NZ":"AU","IL":"IL","TR":"TR","AR":"AR",
}

GENRE_MAP = {
    "Drama":"Drame","Comedy":"Comedie","Thriller":"Thriller",
    "Action":"Action","Adventure":"Action","Horror":"Horreur",
    "Science-Fiction":"SF","Fantasy":"Fantasy","Crime":"Crime",
    "Mystery":"Policier","Documentary":"Documentaire","Romance":"Romance",
    "Animation":"Animation","Family":"Jeunesse","Children":"Jeunesse",
    "Reality":"Telerealite","Music":"Musique","History":"Drame",
    "War":"Action","Western":"Action","Espionage":"Thriller",
    "Legal":"Drame","Medical":"Drame","Sports":"Documentaire",
    "Supernatural":"Horreur","Nature":"Documentaire",
    "Game Show":"Telerealite","Talk Show":"Divertissement",
    "Anime":"Animation","Soap":"Drame",
}

TMDB_GENRES = {
    28:"Action",12:"Action",16:"Animation",35:"Comedie",80:"Crime",
    99:"Documentaire",18:"Drame",10751:"Jeunesse",14:"Fantasy",
    27:"Horreur",10402:"Musique",9648:"Policier",10749:"Romance",
    878:"SF",53:"Thriller",10752:"Action",37:"Action",
    10759:"Action",10762:"Jeunesse",10763:"Documentaire",
    10764:"Telerealite",10765:"SF",10767:"Divertissement",
}

LGBT_KW = [
    "gay","lesbian","bisexual","transgender","queer","lgbt",
    "same-sex","homosexual","coming out","pride","drag queen",
    "non-binary","trans ","gender identity","gaie","lesbienne",
    "homosexuel","transgenre","fierte",
]

MONTHS_FR = {
    "janvier":1,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,
    "juillet":7,"aout":8,"septembre":9,"octobre":10,"novembre":11,"decembre":12,
    "février":2,"août":8,"décembre":12,"févier":2,
}

def map_tv_genres(gl):
    return list(dict.fromkeys([GENRE_MAP[g] for g in gl if g in GENRE_MAP])) or ["Drame"]

def map_tmdb_genres(ids):
    return list(dict.fromkeys([TMDB_GENRES[i] for i in ids if i in TMDB_GENRES])) or ["Film"]

# ── CACHE TMDB (Gemini Partie 3) ──────────────────────────────────────────────
# Index par tmdb_id (int) ET par "titre_annee" (fallback)
CACHE_BY_ID   = {}  # tmdb_id -> data
CACHE_BY_NAME = {}  # "titre_annee" -> data
VF_CACHE      = {}  # tmdb_id -> bool

def load_cache():
    """Charge le cache depuis data.json avec double indexation."""
    if not DATA_PATH.exists():
        return
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        count = 0
        for e in data.get("events", []):
            tmdb_id = e.get("tmdb_id")
            title   = e.get("title", "").lower().strip()
            date    = e.get("date", "")
            year    = date[:4] if date else str(YEAR)

            cached = {
                "note":     e.get("note"),
                "poster":   e.get("poster"),
                "backdrop": e.get("backdrop"),
                "desc":     e.get("desc"),
                "trailers": e.get("trailers", []),
                "cast":     e.get("cast", []),
                "is_lgbt":  "LGBT" in (e.get("tags") or []),
                "total_eps": e.get("_total_eps"),
                "platform": e.get("platform"),
            }

            if tmdb_id:
                CACHE_BY_ID[int(tmdb_id)] = cached
                VF_CACHE[int(tmdb_id)]    = True
                count += 1

            # Indexation par nom+annee (fallback)
            name_key = f"{title}_{year}"
            CACHE_BY_NAME[name_key] = cached

        print(f"  Cache: {count} par ID | {len(CACHE_BY_NAME)} par nom")
    except Exception as ex:
        print(f"  Erreur cache: {ex}")

def get_from_cache(tmdb_id=None, title=None, year=None):
    """Recupere du cache par ID ou par nom+annee."""
    if tmdb_id and tmdb_id in CACHE_BY_ID:
        return CACHE_BY_ID[tmdb_id]
    if title and year:
        key = f"{title.lower().strip()}_{year}"
        if key in CACHE_BY_NAME:
            return CACHE_BY_NAME[key]
    return None

# ── HELPERS ───────────────────────────────────────────────────────────────────
def log(m): print(f"  {m}", flush=True)

def get(url, params=None, timeout=15, retries=2):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout,
                           headers={"User-Agent":"CalendrierBot/9.0"})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i < retries-1: time.sleep(1)
            else: log(f"API {url[:55]}: {e}")
    return None

def get_html(url, timeout=20):
    try:
        r = requests.get(url, timeout=timeout, verify=False, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-CA,fr;q=0.9",
            "Referer": "https://www.google.com/",
        })
        r.raise_for_status()
        return r.text
    except Exception as e:
        log(f"HTML {url[:55]}: {e}")
        return None

def in_window(date_str):
    if not date_str: return False
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        if not date_str.startswith("2026"): return False
        return (TODAY - timedelta(days=HISTORY_DAYS)) <= d <= (TODAY + timedelta(days=FUTURE_DAYS))
    except:
        return False

def tmdb_img(path, size="w300"):
    return f"{TMDB_IMG}/{size}{path}" if path else None

def mkid(prefix, val):
    return f"{prefix}-{re.sub(r'[^a-z0-9]', '-', str(val).lower())[:60]}"

def clean(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', text)).strip()[:800]

def is_lgbt(text):
    if not text: return False
    return any(k in text.lower() for k in LGBT_KW)

def ep_status(ep_num, total_eps):
    if not ep_num: return "premiere"
    if ep_num <= 3: return "premiere"
    if total_eps and ep_num >= total_eps - 2: return "finale"
    return "normal"

def make_saison(season, ep_num, total_eps=None):
    if ep_num:
        return f"S{str(season).zfill(2)}E{str(ep_num).zfill(2)}"
    if total_eps:
        return f"Saison {season} — {total_eps} ep."
    return f"Saison {season}"

def get_qc_platform(net_name):
    """Retourne (plateforme, is_qc) pour un reseau TVmaze."""
    if net_name in QC_NETWORK_MAP:
        return QC_NETWORK_MAP[net_name], net_name in QC_NETWORKS_SET
    name_l = net_name.lower()
    for k, v in QC_NETWORK_MAP.items():
        if k.lower() in name_l:
            return v, k in QC_NETWORKS_SET
    return None, False

def get_streaming_platform(net_name):
    """Retourne la plateforme si c'est un reseau streaming connu."""
    if net_name in STREAMING_NETWORK_MAP:
        return STREAMING_NETWORK_MAP[net_name]
    name_l = net_name.lower()
    for k, v in STREAMING_NETWORK_MAP.items():
        if k.lower() in name_l:
            return v
    return None

def get_country(show):
    for src in [show.get("network"), show.get("webChannel")]:
        if src:
            cc = (src.get("country") or {}).get("code", "")
            if cc:
                return cc, COUNTRY_TAGS.get(cc, cc)
    return "US", "USA"

# ── VALIDATION VF STRICTE (Algorithme Gemini Partie 1) ────────────────────────
def valider_vraie_vf(tmdb_id, type_contenu="tv"):
    """
    Valide qu'une oeuvre internationale beneficie d'un VRAI doublage francophone.
    Algoritme Gemini - 4 regles strictes.
    """
    if not tmdb_id or not TMDB_KEY:
        return True  # Sans cle: inclure par defaut

    # Verifier le cache
    if tmdb_id in VF_CACHE:
        return VF_CACHE[tmdb_id]

    try:
        url = f"{TMDB_BASE}/{type_contenu}/{tmdb_id}"
        params = {"api_key": TMDB_KEY, "append_to_response": "translations"}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code != 200:
            VF_CACHE[tmdb_id] = True  # En cas d'erreur: inclure
            return True

        data = r.json()

        # REGLE 1: Langue originale = francais -> inclusion immediate
        if data.get("original_language") == "fr":
            VF_CACHE[tmdb_id] = True
            return True

        # REGLE 2: Analyse des traductions
        translations = data.get("translations", {}).get("translations", [])
        has_fr = any(t.get("iso_639_1") == "fr" for t in translations)

        if not has_fr:
            VF_CACHE[tmdb_id] = False
            return False

        # Verifier que le contenu FR n'est pas vide (faux positif)
        fr_content = next(
            (t.get("data", {}) for t in translations if t.get("iso_639_1") == "fr"),
            {}
        )
        has_fr_content = (
            fr_content.get("overview") or
            fr_content.get("title") or
            fr_content.get("name")
        )

        if not has_fr_content:
            VF_CACHE[tmdb_id] = False
            return False

        # REGLE 3: Plateformes streaming majeurs -> doublage contractuel au Quebec
        networks = [n.get("name", "").lower() for n in data.get("networks", [])]
        networks_str = " ".join(networks)
        if any(giant in networks_str for giant in STREAMING_GIANTS):
            VF_CACHE[tmdb_id] = True
            return True

        # REGLE 4: Popularite > 5.0 = visible internationalement = doublage probable
        # (seuil abaisse de 15 a 5 - Gemini etait trop restrictif)
        if data.get("popularity", 0) < 5.0:
            VF_CACHE[tmdb_id] = False
            return False

        VF_CACHE[tmdb_id] = True
        return True

    except Exception as e:
        log(f"VF validation erreur {tmdb_id}: {e}")
        VF_CACHE[tmdb_id] = True
        return True

# ── ENRICHISSEMENT TMDB ───────────────────────────────────────────────────────
# Cache des show_id TVmaze -> tmdb_id pour eviter les recherches repetees
SHOW_TO_TMDB = {}  # tvmaze_show_id -> tmdb_id

def get_tmdb_id(title, year=None, media="tv"):
    """Trouve le TMDB ID par recherche de titre."""
    if not TMDB_KEY:
        return None
    ep = f"{TMDB_BASE}/search/{'tv' if media == 'tv' else 'movie'}"
    for lang in ["fr-FR", "en-US"]:
        d = get(ep, {"api_key": TMDB_KEY, "query": title, "language": lang})
        if d and d.get("results"):
            return d["results"][0].get("id")
    return None

def enrich(tmdb_id, media="tv"):
    """Enrichit depuis TMDb - poster, desc, cast, trailers, note."""
    if not TMDB_KEY or not tmdb_id:
        return {}

    # Cache par ID
    if tmdb_id in CACHE_BY_ID:
        return CACHE_BY_ID[tmdb_id]

    try:
        detail = get(
            f"{TMDB_BASE}/{'tv' if media == 'tv' else 'movie'}/{tmdb_id}",
            {"api_key": TMDB_KEY, "language": "fr-FR"}
        ) or {}

        desc = detail.get("overview", "")
        if not desc:
            d_en = get(
                f"{TMDB_BASE}/{'tv' if media == 'tv' else 'movie'}/{tmdb_id}",
                {"api_key": TMDB_KEY, "language": "en-US"}
            ) or {}
            desc = d_en.get("overview", "")

        score = detail.get("vote_average")

        # Total episodes (derniere saison)
        seasons = detail.get("seasons", [])
        total_eps = None
        if seasons:
            real = [s for s in seasons if s.get("season_number", 0) > 0]
            if real:
                total_eps = real[-1].get("episode_count")

        # Trailers
        trailers = []
        for lang in ["fr-FR", "en-US"]:
            vd = get(
                f"{TMDB_BASE}/{'tv' if media == 'tv' else 'movie'}/{tmdb_id}/videos",
                {"api_key": TMDB_KEY, "language": lang}
            )
            if vd:
                for v in vd.get("results", []):
                    if v.get("site") == "YouTube" and v.get("type") in ("Trailer", "Teaser"):
                        trailers.append({
                            "lang":  "VF" if lang == "fr-FR" else "VO",
                            "label": v.get("name", "Bande-annonce"),
                            "url":   f"https://www.youtube.com/watch?v={v['key']}"
                        })
            if trailers:
                break

        # Cast
        cast = []
        cd = get(
            f"{TMDB_BASE}/{'tv' if media == 'tv' else 'movie'}/{tmdb_id}/credits",
            {"api_key": TMDB_KEY, "language": "fr-FR"}
        )
        if cd:
            cast = [c["name"] for c in cd.get("cast", [])[:6] if c.get("name")]

        result = {
            "note":      f"{score:.1f}" if score and score > 0 else None,
            "poster":    tmdb_img(detail.get("poster_path")),
            "backdrop":  tmdb_img(detail.get("backdrop_path"), "w780"),
            "desc":      desc,
            "trailers":  trailers[:4],
            "cast":      cast,
            "is_lgbt":   is_lgbt(desc),
            "total_eps": total_eps,
            "networks":  detail.get("networks", []),
            "popularity": detail.get("popularity", 0),
        }

        CACHE_BY_ID[tmdb_id] = result
        return result

    except Exception as e:
        log(f"Enrich {tmdb_id}: {e}")
        return {}

# ── SOURCE A1: TVMAZE CANADA (Gemini Partie 2) ────────────────────────────────
def fetch_tvmaze_qc():
    """
    TVmaze schedule CA - serie par serie avec langue francaise prioritaire.
    Boucle sur toute la fenetre (pas seulement 7 jours).
    """
    log("TVmaze Canada (francais prioritaire)...")
    events = []
    seen_ep = set()
    start = TODAY - timedelta(days=HISTORY_DAYS)
    total_days = HISTORY_DAYS + FUTURE_DAYS

    for offset in range(0, total_days, 1):
        d = (start + timedelta(days=offset)).strftime("%Y-%m-%d")
        if not d.startswith("2026"):
            continue

        eps = get(f"{TVMAZE_BASE}/schedule?country=CA&date={d}") or []

        for ep in eps:
            ep_id = ep.get("id")
            if ep_id and ep_id in seen_ep:
                continue

            show = ep.get("_embedded", {}).get("show") or ep.get("show") or {}
            if not show:
                continue

            air = ep.get("airdate", "")
            if not in_window(air):
                continue

            network = show.get("network") or show.get("webChannel") or {}
            net_name = (network.get("name") or "")

            # Obtenir plateforme QC
            plat, is_qc = get_qc_platform(net_name)
            if not plat:
                continue  # Reseau CA non reconnu -> ignorer

            if ep_id:
                seen_ep.add(ep_id)

            cc, country_tag = get_country(show)
            show_lang = (show.get("language") or "").lower()
            is_fr = show_lang in ("french", "francais") or is_qc

            tags = []
            if is_qc:
                tags.append("QC")
            tags.append(country_tag)

            desc = clean(show.get("summary", ""))
            if is_lgbt(desc):
                tags.append("LGBT")

            season_num = ep.get("season", 1)
            ep_num     = ep.get("number")
            rating     = (show.get("rating") or {}).get("average")

            entry = {
                "id":          f"ca-ep-{ep_id}" if ep_id else mkid("ca", f"{show.get('id')}{air}{ep_num}"),
                "_show_id":    show.get("id"),
                "_ep_id":      ep_id,
                "date":        air,
                "title":       show.get("name", ""),
                "ep_title":    ep.get("name", ""),
                "saison":      make_saison(season_num, ep_num),
                "saison_num":  season_num,
                "ep_num":      ep_num,
                "ep_status":   ep_status(ep_num, None),
                "status":      "sorti" if air <= TODAY_STR else "a-venir",
                "type":        "serie",
                "platform":    plat,
                "platformUrl": PLATFORM_URLS.get(plat, "#"),
                "platformLogo": get_logo(plat),
                "lang":        ["FR"] if is_fr else ["FR", "EN"],
                "country":     country_tag,
                "tags":        tags,
                "categories":  map_tv_genres(show.get("genres", [])),
                "cast":        [],
                "desc":        desc,
                "note":        f"{rating:.1f}" if rating else None,
                "trailers":    [],
                "poster":      (show.get("image") or {}).get("medium"),
                "backdrop":    (show.get("image") or {}).get("original"),
                "source":      "tvmaze-ca",
                "isManual":    False,
                "tmdb_id":     None,
                "_needs_enrich": True,
            }
            events.append(entry)

    log(f"  -> {len(events)} episodes CA")
    return events

# ── SOURCE A2: TVMAZE STREAMING (Gemini Partie 1 — Validation VF stricte) ─────
def fetch_tvmaze_intl():
    """
    TVmaze streaming international:
    1. Schedule US/CA/GB/AU jour par jour - filtre webChannel streaming
    2. Schedule global (/schedule/web) pour toutes les plateformes streaming
    Les deux combinés pour couvrir Netflix, Disney+, Apple TV+, Prime, etc.
    """
    log("TVmaze streaming international (schedule + web)...")
    events   = []
    seen_ep  = set()
    start    = TODAY - timedelta(days=HISTORY_DAYS)
    total_days = HISTORY_DAYS + FUTURE_DAYS

    # APPROCHE 1: Schedule pays US/GB/AU jour par jour
    for cc in ["US", "GB", "AU"]:
        for offset in range(0, total_days, 1):
            d = (start + timedelta(days=offset)).strftime("%Y-%m-%d")
            if not d.startswith("2026"):
                continue

            eps = get(f"{TVMAZE_BASE}/schedule?country={cc}&date={d}") or []

            for ep in eps:
                ep_id = ep.get("id")
                if ep_id and ep_id in seen_ep:
                    continue

                show = ep.get("_embedded", {}).get("show") or ep.get("show") or {}
                if not show:
                    continue

                air = ep.get("airdate", "")
                if not in_window(air):
                    continue

                network  = show.get("network") or {}
                webchan  = show.get("webChannel") or {}
                net_name = webchan.get("name") or network.get("name") or ""

                if net_name in EXCLUDED_EU_NETWORKS:
                    continue

                plat = get_streaming_platform(net_name)
                if not plat:
                    continue

                if ep_id:
                    seen_ep.add(ep_id)

                show_id = show.get("id")
                _, country_tag = get_country(show)
                season_num = ep.get("season", 1)
                ep_num     = ep.get("number")
                rating     = (show.get("rating") or {}).get("average")
                desc       = clean(show.get("summary", ""))
                tags       = [country_tag]
                if is_lgbt(desc):
                    tags.append("LGBT")

                events.append({
                    "id":           f"intl-ep-{ep_id}" if ep_id else mkid(f"tvm-{cc.lower()}", f"{show_id}{air}{ep_num}"),
                    "_show_id":     show_id,
                    "_ep_id":       ep_id,
                    "date":         air,
                    "title":        show.get("name", ""),
                    "ep_title":     ep.get("name", ""),
                    "saison":       make_saison(season_num, ep_num),
                    "saison_num":   season_num,
                    "ep_num":       ep_num,
                    "ep_status":    ep_status(ep_num, None),
                    "status":       "sorti" if air <= TODAY_STR else "a-venir",
                    "type":         "serie",
                    "platform":     plat,
                    "platformUrl":  PLATFORM_URLS.get(plat, "#"),
                    "platformLogo": get_logo(plat),
                    "lang":         ["FR", "EN"],
                    "country":      country_tag,
                    "tags":         tags,
                    "categories":   map_tv_genres(show.get("genres", [])),
                    "cast":         [],
                    "desc":         desc,
                    "note":         f"{rating:.1f}" if rating else None,
                    "trailers":     [],
                    "poster":       (show.get("image") or {}).get("medium"),
                    "backdrop":     (show.get("image") or {}).get("original"),
                    "source":       f"tvmaze-{cc.lower()}",
                    "isManual":     False,
                    "tmdb_id":      None,
                    "_needs_enrich": True,
                })

    # APPROCHE 2: Schedule web global (/schedule/web) - couvre Netflix/Apple/Disney
    # C'est l'endpoint cle pour les plateformes streaming mondiales
    log("  Schedule web global (Netflix/Disney+/Apple TV+/Prime)...")
    for offset in range(0, total_days, 1):
        d = (start + timedelta(days=offset)).strftime("%Y-%m-%d")
        if not d.startswith("2026"):
            continue

        eps = get(f"{TVMAZE_BASE}/schedule/web?date={d}") or []

        for ep in eps:
            ep_id = ep.get("id")
            if ep_id and ep_id in seen_ep:
                continue

            show = ep.get("_embedded", {}).get("show") or ep.get("show") or {}
            if not show:
                continue

            air = ep.get("airdate", "")
            if not in_window(air):
                continue

            webchan  = show.get("webChannel") or {}
            net_name = webchan.get("name") or ""

            if not net_name or net_name in EXCLUDED_EU_NETWORKS:
                continue

            plat = get_streaming_platform(net_name)
            if not plat:
                continue

            if ep_id:
                seen_ep.add(ep_id)

            show_id = show.get("id")
            _, country_tag = get_country(show)
            season_num = ep.get("season", 1)
            ep_num     = ep.get("number")
            rating     = (show.get("rating") or {}).get("average")
            desc       = clean(show.get("summary", ""))
            tags       = [country_tag]
            if is_lgbt(desc):
                tags.append("LGBT")

            events.append({
                "id":           f"web-ep-{ep_id}" if ep_id else mkid("web", f"{show_id}{air}{ep_num}"),
                "_show_id":     show_id,
                "_ep_id":       ep_id,
                "date":         air,
                "title":        show.get("name", ""),
                "ep_title":     ep.get("name", ""),
                "saison":       make_saison(season_num, ep_num),
                "saison_num":   season_num,
                "ep_num":       ep_num,
                "ep_status":    ep_status(ep_num, None),
                "status":       "sorti" if air <= TODAY_STR else "a-venir",
                "type":         "serie",
                "platform":     plat,
                "platformUrl":  PLATFORM_URLS.get(plat, "#"),
                "platformLogo": get_logo(plat),
                "lang":         ["FR", "EN"],
                "country":      country_tag,
                "tags":         tags,
                "categories":   map_tv_genres(show.get("genres", [])),
                "cast":         [],
                "desc":         desc,
                "note":         f"{rating:.1f}" if rating else None,
                "trailers":     [],
                "poster":       (show.get("image") or {}).get("medium"),
                "backdrop":     (show.get("image") or {}).get("original"),
                "source":       "tvmaze-web",
                "isManual":     False,
                "tmdb_id":      None,
                "_needs_enrich": True,
            })

    log(f"  -> {len(events)} episodes streaming (avant validation VF)")
    return events

# ── SOURCE A3: SHOWBIZZ.NET (BeautifulSoup — Gemini Partie 2) ─────────────────
def fetch_showbizz():
    """
    Showbizz.net avec BeautifulSoup - scraping resilient des calendriers QC.
    """
    log("Showbizz.net QC (BeautifulSoup)...")
    events = []
    seen   = set()

    PLAT_KW = {
        "ici tou.tv": "ICI TOU.TV", "tou.tv": "ICI TOU.TV",
        "radio-canada": "ICI TOU.TV", "ici tele": "ICI TOU.TV",
        "ici télé": "ICI TOU.TV", "télé-québec": "Tele-Quebec",
        "tele-quebec": "Tele-Quebec", "telequebec": "Tele-Quebec",
        "tva": "TVA+", "noovo": "Noovo",
        "illico": "Club Illico", "club illico": "Club Illico",
        "crave": "Crave", "vrai": "Vrai", "historia": "Historia",
        "séries+": "Series+", "series+": "Series+",
        "unis": "Unis TV", "tv5": "TV5", "artv": "ARTV",
        "netflix": "Netflix", "amazon": "Prime Video",
        "disney": "Disney+", "apple": "Apple TV+", "max": "Max",
    }

    MOIS_LIST = list(MONTHS_FR.keys())

    urls = [
        f"https://showbizz.net/tele/rentree-tele-hiver-{YEAR}-quand-commencent-vos-emissions",
        f"https://showbizz.net/tele/rentree-tele-printemps-ete-{YEAR}-quand-commencent-vos-emissions",
        f"https://showbizz.net/tele/rentree-tele-automne-{YEAR}-quand-commencent-vos-emissions",
        f"https://showbizz.net/tele/rentree-tele-hiver-{YEAR}-quand-commencent-vos-emissions-doublees",
        f"https://showbizz.net/tele/rentree-tele-printemps-ete-{YEAR}-quand-commencent-vos-emissions-doublees",
        f"https://showbizz.net/tele/rentree-tele-automne-{YEAR}-quand-commencent-vos-emissions-doublees",
    ]

    for url in urls:
        html = get_html(url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")

        # Detecter la plateforme courante par les titres H2/H3
        current_plat = "ICI TOU.TV"

        for el in soup.find_all(["h2", "h3", "h4", "li", "p"]):
            text = el.get_text(separator=" ").strip()

            # Detecter changement de plateforme (H2/H3)
            if el.name in ("h2", "h3", "h4"):
                text_l = text.lower()
                for kw, plat in PLAT_KW.items():
                    if kw in text_l:
                        current_plat = plat
                        break
                continue

            # Chercher pattern de date dans le texte
            text_l = text.lower()
            has_date = any(m in text_l for m in MOIS_LIST)
            has_des  = "dès le" in text_l or "dès " in text_l

            if not (has_date and has_des):
                continue

            # Extraire le titre (balise strong ou debut de ligne)
            strong = el.find("strong")
            titre  = None

            if strong:
                titre = clean(strong.get_text()).strip("*[]():- ")
            else:
                # Prendre le texte avant le tiret "–" ou "Dès"
                match_titre = re.match(r'^([^–—\*\[\]]{3,60}?)\s*[–—]', text)
                if match_titre:
                    titre = clean(match_titre.group(1)).strip()

            if not titre or len(titre) < 3 or len(titre) > 80:
                continue

            # Ignorer les elements de navigation
            if any(x in titre.lower() for x in [
                "calendrier", "saison doublée", "acquisitions",
                "voir", "suivant", "rechercher", "connexion", "abonnement"
            ]):
                continue

            # Extraire la date
            date_match = re.search(
                r'(\d{1,2})\s+(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)',
                text_l
            )
            if not date_match:
                continue

            try:
                day = int(date_match.group(1))
                month_raw = date_match.group(2).replace("é", "e").replace("û", "u").replace("è", "e")
                month_num = MONTHS_FR.get(month_raw)
                if not month_num:
                    continue

                date_str = f"2026-{str(month_num).zfill(2)}-{str(day).zfill(2)}"
                if not in_window(date_str):
                    continue

                # Detecter plateforme depuis le contexte du texte
                plat = current_plat
                for kw, p in PLAT_KW.items():
                    if kw in text_l:
                        plat = p
                        break

                key = (titre.lower(), date_str)
                if key in seen:
                    continue
                seen.add(key)

                events.append({
                    "id":           mkid("showbizz", titre + date_str),
                    "_show_id":     None,
                    "_ep_id":       None,
                    "date":         date_str,
                    "title":        titre,
                    "ep_title":     "",
                    "saison":       "Saison 1",
                    "saison_num":   1,
                    "ep_num":       1,
                    "ep_status":    "premiere",
                    "status":       "sorti" if date_str <= TODAY_STR else "a-venir",
                    "type":         "serie",
                    "platform":     plat,
                    "platformUrl":  PLATFORM_URLS.get(plat, "#"),
                    "platformLogo": get_logo(plat),
                    "lang":         ["FR"],
                    "country":      "CA",
                    "tags":         ["QC", "CA"],
                    "categories":   ["Drame"],
                    "cast":         [],
                    "desc":         "",
                    "note":         None,
                    "trailers":     [],
                    "poster":       None,
                    "backdrop":     None,
                    "source":       "showbizz",
                    "isManual":     False,
                    "tmdb_id":      None,
                    "_needs_enrich": True,
                })
            except:
                continue

    log(f"  -> {len(events)} emissions QC Showbizz")
    return events

# ── SOURCE A4: BELL MEDIA / CRAVE ─────────────────────────────────────────────
def fetch_bell_media():
    """Bell Media The Lede - Crave streaming overview mensuel."""
    log("Bell Media / Crave...")
    events = []
    seen   = set()

    MONTH_EN = ["january","february","march","april","may","june",
                "july","august","september","october","november","december"]
    MONTH_PREFIX = {m: f"2026-{str(i+1).zfill(2)}" for i, m in enumerate(MONTH_EN)}

    # Couvrir les 6 prochains mois
    months_to_try = []
    for offset in range(0, 7):
        d = (TODAY.replace(day=1) + timedelta(days=32 * offset)).replace(day=1)
        if d.year == 2026:
            slug = f"{MONTH_EN[d.month-1]}-{d.year}"
            if slug not in months_to_try:
                months_to_try.append(slug)

    for month_slug in months_to_try:
        url = f"https://www.bellmedia.ca/the-lede/press/{month_slug}-crave-streaming-overview/"
        html = get_html(url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        content = (soup.find("article") or
                   soup.find("div", class_="entry-content") or
                   soup.find("main") or soup)

        if not content:
            continue

        month_name = month_slug.split("-")[0]
        year_prefix = MONTH_PREFIX.get(month_name, "2026-06")

        # Pattern: "JUNE 15 – New Series Name" ou "JUNE 15 – Series Name, Season X"
        text = content.get_text(separator="\n")
        pat  = r'([A-Z]+)\s+(\d{1,2})\s*[–—]\s*(?:New\s+)?(?:Season\s+\d+\s+of\s+)?([A-Z][A-Za-z0-9\s\':&!\-,\.\(\)]{2,80}?)(?:\s*[\(\*\n]|\s*Season|\s*,\s*S\d|\s*Ep\b)'

        for m in re.finditer(pat, text):
            try:
                month_en = m.group(1).lower()
                day      = int(m.group(2))
                title    = clean(m.group(3)).strip().rstrip(",:- ")

                if len(title) < 2:
                    continue

                mp       = MONTH_PREFIX.get(month_en, year_prefix)
                date_str = f"{mp}-{str(day).zfill(2)}"
                if not in_window(date_str):
                    continue

                key = (title.lower(), date_str[:7])
                if key in seen:
                    continue
                seen.add(key)

                events.append({
                    "id":           mkid("bell", title + date_str),
                    "_show_id":     None,
                    "_ep_id":       None,
                    "date":         date_str,
                    "title":        title.title(),
                    "ep_title":     "",
                    "saison":       "Saison 1",
                    "saison_num":   1,
                    "ep_num":       1,
                    "ep_status":    "premiere",
                    "status":       "sorti" if date_str <= TODAY_STR else "a-venir",
                    "type":         "serie",
                    "platform":     "Crave",
                    "platformUrl":  PLATFORM_URLS["Crave"],
                    "platformLogo": get_logo("Crave"),
                    "lang":         ["FR", "EN"],
                    "country":      "USA",
                    "tags":         [],
                    "categories":   ["Drame"],
                    "cast":         [],
                    "desc":         "",
                    "note":         None,
                    "trailers":     [],
                    "poster":       None,
                    "backdrop":     None,
                    "source":       "bell-media",
                    "isManual":     False,
                    "tmdb_id":      None,
                    "_needs_enrich": True,
                })
            except:
                continue

    log(f"  -> {len(events)} titres Bell Media")
    return events

# ── SOURCE B: TMDB FILMS ──────────────────────────────────────────────────────
def fetch_films():
    if not TMDB_KEY:
        return []
    log("TMDb films...")
    events = []
    seen   = set()

    for endpoint in ["upcoming", "now_playing", "popular", "top_rated"]:
        for page in range(1, 6):
            data = get(f"{TMDB_BASE}/movie/{endpoint}", {
                "api_key": TMDB_KEY, "language": "fr-FR",
                "page": page, "region": "CA"
            })
            if not data:
                break
            for m in data.get("results", []):
                mid     = m.get("id")
                release = m.get("release_date", "")
                if not mid or mid in seen or not in_window(release):
                    continue
                seen.add(mid)

                # Validation VF pour les films
                if not valider_vraie_vf(mid, "movie"):
                    continue

                score = m.get("vote_average", 0)
                desc  = m.get("overview", "")
                tags  = []
                if is_lgbt(desc):
                    tags.append("LGBT")

                events.append({
                    "id":           f"film-{mid}",
                    "_show_id":     None,
                    "_ep_id":       None,
                    "date":         release,
                    "title":        m.get("title", ""),
                    "ep_title":     "",
                    "saison":       "Film",
                    "saison_num":   0,
                    "ep_num":       None,
                    "ep_status":    "normal",
                    "status":       "sorti" if release <= TODAY_STR else "a-venir",
                    "type":         "film",
                    "platform":     "Cinema",
                    "platformUrl":  f"https://www.themoviedb.org/movie/{mid}",
                    "platformLogo": get_logo("Cinema"),
                    "lang":         ["FR", "EN"],
                    "country":      "USA",
                    "tags":         tags,
                    "categories":   map_tmdb_genres(m.get("genre_ids", [])),
                    "cast":         [],
                    "desc":         desc,
                    "note":         f"{score:.1f}" if score > 0 else None,
                    "trailers":     [],
                    "poster":       tmdb_img(m.get("poster_path")),
                    "backdrop":     tmdb_img(m.get("backdrop_path"), "w780"),
                    "source":       "tmdb-film",
                    "isManual":     False,
                    "tmdb_id":      mid,
                    "_needs_enrich": True,
                })

    log(f"  -> {len(events)} films")
    return events

# ── ENRICHISSEMENT PAR LOTS ───────────────────────────────────────────────────
def enrich_all(events):
    """
    Enrichissement TMDb:
    - 1 recherche par show (pas par episode)
    - Validation VF stricte pour series intl
    - Cache par tmdb_id
    """
    log("Enrichissement TMDb (1 par show)...")

    processed_shows = {}  # show_id -> {tmdb_id, validated, data}
    skipped_vf      = 0
    enriched_new    = 0
    qc_sources      = {"showbizz", "bell-media", "tvmaze-ca"}

    for e in events:
        e.pop("_needs_enrich", None)

        # Films: enrichissement direct
        if e.get("type") == "film":
            tid = e.get("tmdb_id")
            if tid:
                cached = get_from_cache(tmdb_id=tid)
                if not cached:
                    cached = enrich(tid, "movie")
                    enriched_new += 1
                if cached:
                    for k in ("note", "poster", "backdrop", "desc", "trailers", "cast"):
                        if cached.get(k) and not e.get(k):
                            e[k] = cached[k]
                    if cached.get("is_lgbt") and "LGBT" not in e.get("tags", []):
                        e["tags"].append("LGBT")
            continue

        # Series: grouper par show_id
        show_id = e.get("_show_id")
        if not show_id:
            # Source sans show_id (showbizz, bell): enrichir par titre
            title = e.get("title", "")
            year  = e.get("date", "2026")[:4]
            cached = get_from_cache(title=title, year=year)
            if cached:
                for k in ("note", "poster", "backdrop", "desc", "trailers", "cast"):
                    if cached.get(k) and not e.get(k):
                        e[k] = cached[k]
                if cached.get("is_lgbt") and "LGBT" not in e.get("tags", []):
                    e["tags"].append("LGBT")
            elif TMDB_KEY:
                tid = get_tmdb_id(title, year)
                if tid:
                    e["tmdb_id"] = tid
                    enriched = enrich(tid, "tv")
                    enriched_new += 1
                    if enriched:
                        for k in ("note", "poster", "backdrop", "desc", "trailers", "cast"):
                            if enriched.get(k) and not e.get(k):
                                e[k] = enriched[k]
                        if enriched.get("is_lgbt") and "LGBT" not in e.get("tags", []):
                            e["tags"].append("LGBT")
            continue

        # Show deja traite
        if show_id in processed_shows:
            info = processed_shows[show_id]
            if info.get("skip"):
                e["_skip"] = True
                skipped_vf += 1
                continue
            tid = info.get("tmdb_id")
            if tid:
                e["tmdb_id"] = tid
            cached = info.get("data")
            if cached:
                for k in ("note", "poster", "backdrop", "desc", "trailers", "cast"):
                    if cached.get(k) and not e.get(k):
                        e[k] = cached[k]
                if cached.get("is_lgbt") and "LGBT" not in e.get("tags", []):
                    e["tags"].append("LGBT")
                if cached.get("total_eps"):
                    e["saison"]    = make_saison(e.get("saison_num", 1), e.get("ep_num"), cached["total_eps"])
                    e["ep_status"] = ep_status(e.get("ep_num"), cached["total_eps"])
            continue

        # Nouveau show a traiter
        title   = e.get("title", "")
        year    = e.get("date", "2026")[:4]
        source  = e.get("source", "")
        is_qc   = source in qc_sources

        # Trouver le TMDB ID
        tid = None
        if TMDB_KEY:
            tid = get_tmdb_id(title, year, "tv")

        if not tid:
            processed_shows[show_id] = {"tmdb_id": None, "skip": False, "data": None}
            continue

        e["tmdb_id"] = tid

        # Validation VF pour series internationales (pas QC)
        if not is_qc and source != "showbizz" and source != "bell-media":
            if not valider_vraie_vf(tid, "tv"):
                processed_shows[show_id] = {"tmdb_id": tid, "skip": True, "data": None}
                e["_skip"] = True
                skipped_vf += 1
                continue

        # Enrichir
        cached = get_from_cache(tmdb_id=tid)
        if not cached:
            cached = enrich(tid, "tv")
            enriched_new += 1

        processed_shows[show_id] = {"tmdb_id": tid, "skip": False, "data": cached}

        if cached:
            for k in ("note", "poster", "backdrop", "desc", "trailers", "cast"):
                if cached.get(k) and not e.get(k):
                    e[k] = cached[k]
            if cached.get("is_lgbt") and "LGBT" not in e.get("tags", []):
                e["tags"].append("LGBT")
            if cached.get("total_eps"):
                e["saison"]    = make_saison(e.get("saison_num", 1), e.get("ep_num"), cached["total_eps"])
                e["ep_status"] = ep_status(e.get("ep_num"), cached["total_eps"])

    log(f"  Nouveaux enrichis: {enriched_new} | Exclus sans VF: {skipped_vf}")
    return [e for e in events if not e.get("_skip")]

# ── FUSION ET DEDUPLICATION ───────────────────────────────────────────────────
def merge(events):
    """
    Deduplication intelligente:
    - Episodes TVmaze: par ep_id unique
    - Autres sources: par (titre, date)
    - Priorite aux sources QC
    """
    by_ep_id    = {}   # ep_id -> entry
    by_title_date = {} # (titre_norm, date) -> entry_id
    final       = {}

    for e in events:
        ep_id  = e.get("_ep_id")
        eid    = e["id"]
        title  = e.get("title", "").lower().strip()
        date   = e.get("date", "")

        # Deduplication par episode ID TVmaze
        if ep_id:
            if ep_id in by_ep_id:
                ex = by_ep_id[ep_id]
                for f in ("poster", "desc", "trailers", "cast", "note", "backdrop"):
                    if not ex.get(f) and e.get(f):
                        ex[f] = e[f]
                continue
            by_ep_id[ep_id] = e
            final[eid] = e
            continue

        # Deduplication par titre + date
        td_key = (title, date)
        if td_key in by_title_date:
            ex_id = by_title_date[td_key]
            ex    = final.get(ex_id)
            if ex:
                for f in ("poster", "desc", "trailers", "cast", "note", "backdrop"):
                    if not ex.get(f) and e.get(f):
                        ex[f] = e[f]
                for tag in (e.get("tags") or []):
                    if tag not in ex.get("tags", []):
                        ex["tags"].append(tag)
                # Preferer source QC
                if e.get("source") in {"showbizz", "bell-media", "tvmaze-ca"}:
                    if ex.get("source") not in {"showbizz", "bell-media", "tvmaze-ca"}:
                        ex["lang"]         = e.get("lang", ex["lang"])
                        ex["platformLogo"] = e.get("platformLogo", ex["platformLogo"])
        else:
            by_title_date[td_key] = eid
            final[eid] = e

    return list(final.values())

# ── NETTOYAGE FINAL ───────────────────────────────────────────────────────────
def cleanup(events):
    """Supprime les champs internes avant sauvegarde."""
    internal = {"_show_id", "_ep_id", "_needs_enrich", "_vf_validated",
                "_skip", "_total_eps"}
    cleaned = []
    for e in events:
        e_clean = {k: v for k, v in e.items() if k not in internal}
        cleaned.append(e_clean)
    return cleaned

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\nMise a jour v9 — {TODAY.strftime('%Y-%m-%d %H:%M')}")
    print(f"Cle TMDb : {'OK' if TMDB_KEY else 'MANQUANTE'}")
    print(f"Fenetre  : {(TODAY-timedelta(days=HISTORY_DAYS)).strftime('%Y-%m-%d')} "
          f"a {(TODAY+timedelta(days=FUTURE_DAYS)).strftime('%Y-%m-%d')}")
    print(f"Cible    : ~1200 episodes avec vraie VF\n")

    # Charger le cache
    print("Chargement cache...")
    load_cache()

    # ── ETAPE 1: COLLECTE ────────────────────────────────────────────────────
    print("\n=== ETAPE 1: COLLECTE ===")
    all_events = []

    print("TVmaze Canada (QC prioritaire)...")
    all_events.extend(fetch_tvmaze_qc())

    print("TVmaze US/UK/AU (streaming seulement)...")
    all_events.extend(fetch_tvmaze_intl())

    print("Showbizz.net (BeautifulSoup)...")
    all_events.extend(fetch_showbizz())

    print("Bell Media / Crave...")
    all_events.extend(fetch_bell_media())

    print("Films TMDb...")
    all_events.extend(fetch_films())

    log(f"Total brut: {len(all_events)}")

    # ── ETAPE 2: ENRICHISSEMENT + VALIDATION VF ──────────────────────────────
    print("\n=== ETAPE 2: ENRICHISSEMENT + VALIDATION VF STRICTE ===")
    all_events = enrich_all(all_events)

    # ── ETAPE 3: FUSION ET NETTOYAGE ─────────────────────────────────────────
    print("\nFusion et deduplication...")
    final = merge(all_events)
    final = [e for e in final if in_window(e.get("date", "")) and not e.get("_skip")]
    final.sort(key=lambda e: (e.get("date", "9999"), e.get("title", ""), e.get("ep_num") or 0))
    final = cleanup(final)

    # ── SAUVEGARDE ───────────────────────────────────────────────────────────
    output = {
        "version":      "9.0",
        "generated_at": TODAY.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total":        len(final),
        "events":       final,
    }

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # ── RAPPORT ──────────────────────────────────────────────────────────────
    sorti   = sum(1 for e in final if e.get("status") == "sorti")
    avenir  = sum(1 for e in final if e.get("status") == "a-venir")
    qc      = sum(1 for e in final if "QC" in (e.get("tags") or []))
    lgbt    = sum(1 for e in final if "LGBT" in (e.get("tags") or []))
    films   = sum(1 for e in final if e.get("type") == "film")
    series  = sum(1 for e in final if e.get("type") == "serie")
    sources = {}
    for e in final:
        s = e.get("source", "?")
        sources[s] = sources.get(s, 0) + 1

    print(f"\n{'='*40}")
    print(f"TERMINE: {len(final)} entrees sauvegardees")
    print(f"{'='*40}")
    print(f"  Episodes series : {series}")
    print(f"  Films           : {films}")
    print(f"  Disponibles     : {sorti}")
    print(f"  A venir         : {avenir}")
    print(f"  QC              : {qc}")
    print(f"  LGBT+           : {lgbt}")
    print(f"  Par source:")
    for s, n in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"    {s:20s}: {n}")
    print()

if __name__ == "__main__":
    main()
