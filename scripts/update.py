#!/usr/bin/env python3
"""
Script de mise à jour automatique du calendrier films & séries.
Sources :
  - TVmaze API  : séries canadiennes (sans clé API)
  - TMDb API    : films + séries, affiches, descriptions, notes
  - Radio-Canada RSS : annonces nouvelles séries québécoises
  - data-qc.json : entrées québécoises ajoutées manuellement
"""

import json
import os
import re
import sys
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

# ─── CONFIG ──────────────────────────────────────────────────────────────────
TMDB_KEY      = os.environ.get("TMDB_API_KEY", "")
TMDB_BASE     = "https://api.themoviedb.org/3"
TMDB_IMG      = "https://image.tmdb.org/t/p"
TVMAZE_BASE   = "https://api.tvmaze.com"
RC_RSS        = "https://ici.radio-canada.ca/rss/4159"   # RSS Arts & Spectacles
DATA_PATH     = Path("data.json")
QC_PATH       = Path("data-qc.json")
TODAY         = datetime.now()
WINDOW_DAYS   = 180   # 6 mois avant + après aujourd'hui

# Plateformes québécoises connues sur TVmaze
QC_NETWORKS = [
    "ICI Radio-Canada Télé", "ICI TOU.TV", "Radio-Canada",
    "Télé-Québec", "TVA", "Noovo", "Club Illico", "Crave",
    "Super Écran", "Séries+", "Canal Vie", "Historia",
    "Savoir Media", "ARTV"
]

# Correspondance réseau TVmaze → nom plateforme dans notre app
NETWORK_MAP = {
    "ICI Radio-Canada Télé": "ICI TOU.TV",
    "ICI TOU.TV":            "ICI TOU.TV",
    "Radio-Canada":          "ICI TOU.TV",
    "Télé-Québec":           "Télé-Québec",
    "TVA":                   "TVA+",
    "Noovo":                 "Club Illico",
    "Club Illico":           "Club Illico",
    "Super Écran":           "Club Illico",
    "Crave":                 "Crave",
    "Séries+":               "Club Illico",
    "Canal Vie":             "Club Illico",
    "Historia":              "Club Illico",
    "Savoir Media":          "Télé-Québec",
    "ARTV":                  "ICI TOU.TV",
}

PLATFORM_URLS = {
    "ICI TOU.TV":   "https://ici.tou.tv",
    "Télé-Québec":  "https://www.telequebec.tv",
    "TVA+":         "https://www.tvaplus.ca",
    "Club Illico":  "https://www.illico.com",
    "Crave":        "https://www.crave.ca",
    "Netflix":      "https://www.netflix.com",
    "Prime Video":  "https://www.primevideo.com",
    "Disney+":      "https://www.disneyplus.com",
    "Apple TV+":    "https://tv.apple.com",
}

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def log(msg):
    print(f"  {msg}", flush=True)

def safe_get(url, params=None, timeout=10):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"⚠ Erreur requête {url[:60]}... : {e}")
        return None

def date_in_window(date_str):
    """Retourne True si la date est dans notre fenêtre d'affichage."""
    if not date_str:
        return False
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        start = TODAY - timedelta(days=365)   # 1 an d'historique
        end   = TODAY + timedelta(days=WINDOW_DAYS)
        return start <= d <= end
    except:
        return False

def tmdb_poster(path, size="w300"):
    if path:
        return f"{TMDB_IMG}/{size}{path}"
    return None

def make_id(prefix, val):
    """Génère un ID unique stable."""
    clean = re.sub(r'[^a-z0-9]', '-', str(val).lower())
    return f"{prefix}-{clean}"

# ─── CHARGE LES DONNÉES EXISTANTES ───────────────────────────────────────────
def load_existing():
    if DATA_PATH.exists():
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {e["id"]: e for e in data.get("events", [])}
    return {}

def load_qc_manual():
    if QC_PATH.exists():
        with open(QC_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# ─── TMDB : enrichissement d'une entrée ──────────────────────────────────────
def tmdb_enrich(title, media_type="tv", year=None):
    """Cherche un titre sur TMDb et retourne les détails enrichis."""
    if not TMDB_KEY:
        return {}

    endpoint = f"{TMDB_BASE}/search/{'tv' if media_type == 'tv' else 'movie'}"
    params = {"api_key": TMDB_KEY, "query": title, "language": "fr-FR"}
    if year:
        params["first_air_date_year" if media_type == "tv" else "year"] = year

    data = safe_get(endpoint, params)
    if not data or not data.get("results"):
        # Essai en anglais
        params["language"] = "en-US"
        data = safe_get(endpoint, params)
    if not data or not data.get("results"):
        return {}

    result = data["results"][0]
    tmdb_id = result.get("id")
    score = result.get("vote_average")
    note = f"{score:.1f}" if score and score > 0 else None

    # Détails supplémentaires (trailers)
    trailers = []
    if tmdb_id:
        detail_url = f"{TMDB_BASE}/{'tv' if media_type == 'tv' else 'movie'}/{tmdb_id}/videos"
        vdata = safe_get(detail_url, {"api_key": TMDB_KEY, "language": "fr-FR"})
        if vdata and vdata.get("results"):
            for v in vdata["results"]:
                if v.get("site") == "YouTube" and v.get("type") in ("Trailer", "Teaser"):
                    trailers.append({
                        "lang": "VF",
                        "label": v.get("name", "Bande-annonce VF"),
                        "url": f"https://www.youtube.com/watch?v={v['key']}"
                    })
        # Trailers anglais si pas de VF
        if not trailers:
            vdata_en = safe_get(detail_url, {"api_key": TMDB_KEY, "language": "en-US"})
            if vdata_en and vdata_en.get("results"):
                for v in vdata_en["results"][:2]:
                    if v.get("site") == "YouTube" and v.get("type") in ("Trailer", "Teaser"):
                        trailers.append({
                            "lang": "VO",
                            "label": v.get("name", "Trailer VO"),
                            "url": f"https://www.youtube.com/watch?v={v['key']}"
                        })

    return {
        "tmdb_id":  tmdb_id,
        "note":     note,
        "poster":   tmdb_poster(result.get("poster_path")),
        "backdrop": tmdb_poster(result.get("backdrop_path"), "w780"),
        "desc":     result.get("overview") or "",
        "trailers": trailers,
        "votes":    result.get("vote_count", 0),
    }

# ─── TVMAZE : séries canadiennes ─────────────────────────────────────────────
def fetch_tvmaze_canada():
    """Récupère les nouvelles séries des réseaux québécois/canadiens via TVmaze."""
    log("TVmaze : récupération des séries canadiennes...")
    events = []

    # Calendrier CA pour les 30 prochains jours
    for offset in range(0, 60, 7):
        d = (TODAY + timedelta(days=offset)).strftime("%Y-%m-%d")
        url = f"{TVMAZE_BASE}/schedule?country=CA&date={d}"
        episodes = safe_get(url)
        if not episodes:
            continue

        seen_shows = set()
        for ep in episodes:
            show = ep.get("_embedded", {}).get("show") or ep.get("show", {})
            if not show:
                continue

            show_id = show.get("id")
            if show_id in seen_shows:
                continue

            network = show.get("network") or show.get("webChannel") or {}
            net_name = network.get("name", "")
            country = (network.get("country") or {}).get("code", "")

            # Filtre : réseaux QC/CA seulement
            if net_name not in QC_NETWORKS and country not in ("CA",):
                continue

            seen_shows.add(show_id)
            air_date = ep.get("airdate", "")
            if not date_in_window(air_date):
                continue

            platform = NETWORK_MAP.get(net_name, net_name)
            lang_code = (network.get("country") or {}).get("code", "CA")
            lang = ["FR"] if any(x in net_name for x in ["Radio-Canada", "Télé", "TVA", "Noovo", "Club", "Crave", "ICI"]) else ["EN", "FR"]

            # Genres TVmaze → catégories
            genres = show.get("genres", [])
            cats = map_genres(genres)

            # Tags QC
            tags = []
            if net_name in QC_NETWORKS:
                tags.append("QC")

            event_id = make_id("tvmaze", show_id)
            season_num = ep.get("season", 1)

            entry = {
                "id":           event_id,
                "date":         air_date,
                "title":        show.get("name", ""),
                "saison":       f"Saison {season_num}",
                "status":       "sorti" if air_date <= TODAY.strftime("%Y-%m-%d") else "a-venir",
                "type":         "serie",
                "platform":     platform,
                "platformUrl":  PLATFORM_URLS.get(platform, "#"),
                "lang":         lang,
                "tags":         tags,
                "categories":   cats,
                "cast":         [],
                "desc":         strip_html(show.get("summary") or ""),
                "note":         None,
                "trailers":     [],
                "poster":       (show.get("image") or {}).get("medium"),
                "backdrop":     (show.get("image") or {}).get("original"),
                "source":       "tvmaze",
                "isManual":     False,
            }

            # Enrichissement TMDb
            if TMDB_KEY:
                enriched = tmdb_enrich(show.get("name", ""), "tv")
                if enriched:
                    entry["note"]     = enriched.get("note") or entry["note"]
                    entry["trailers"] = enriched.get("trailers") or entry["trailers"]
                    entry["desc"]     = enriched.get("desc") or entry["desc"]
                    if enriched.get("poster"):
                        entry["poster"] = enriched["poster"]
                    if enriched.get("backdrop"):
                        entry["backdrop"] = enriched["backdrop"]

            events.append(entry)

    log(f"  → {len(events)} entrées TVmaze Canada trouvées")
    return events

# ─── TVMAZE : grandes séries internationales ─────────────────────────────────
def fetch_tvmaze_upcoming():
    """Récupère les grandes séries à venir (hors CA) depuis TVmaze."""
    log("TVmaze : séries internationales populaires à venir...")
    events = []

    # On cherche les séries les plus attendues par réseau populaire
    popular_networks = [
        "Netflix", "HBO", "Amazon", "Apple TV+",
        "Disney+", "Hulu", "Prime Video"
    ]

    # Calendrier US pour les 90 prochains jours
    seen = set()
    for offset in range(0, 90, 7):
        d = (TODAY + timedelta(days=offset)).strftime("%Y-%m-%d")
        url = f"{TVMAZE_BASE}/schedule?country=US&date={d}"
        episodes = safe_get(url)
        if not episodes:
            continue

        for ep in episodes:
            show = ep.get("_embedded", {}).get("show") or ep.get("show", {})
            if not show:
                continue
            show_id = show.get("id")
            if show_id in seen:
                continue

            # Filtre : seulement les séries avec une bonne note ou connues
            rating = (show.get("rating") or {}).get("average") or 0
            if rating < 7.0 and show.get("weight", 0) < 80:
                continue

            web_channel = (show.get("webChannel") or {}).get("name", "")
            network_name = (show.get("network") or {}).get("name", "")
            plat_raw = web_channel or network_name

            # Correspondance plateformes internationales
            plat_map = {
                "Netflix": "Netflix", "HBO": "Crave",
                "Amazon": "Prime Video", "Prime Video": "Prime Video",
                "Apple TV+": "Apple TV+", "Disney+": "Disney+",
                "Hulu": "Hulu", "Max": "Crave",
            }
            platform = None
            for k, v in plat_map.items():
                if k.lower() in plat_raw.lower():
                    platform = v
                    break
            if not platform:
                continue

            seen.add(show_id)
            air_date = ep.get("airdate", "")
            if not date_in_window(air_date):
                continue

            genres = show.get("genres", [])
            cats = map_genres(genres)
            season_num = ep.get("season", 1)

            entry = {
                "id":          make_id("tvm-intl", show_id),
                "date":        air_date,
                "title":       show.get("name", ""),
                "saison":      f"Saison {season_num}",
                "status":      "sorti" if air_date <= TODAY.strftime("%Y-%m-%d") else "a-venir",
                "type":        "serie",
                "platform":    platform,
                "platformUrl": PLATFORM_URLS.get(platform, "#"),
                "lang":        ["FR", "EN"],
                "tags":        [],
                "categories":  cats,
                "cast":        [],
                "desc":        strip_html(show.get("summary") or ""),
                "note":        str(round(rating, 1)) if rating else None,
                "trailers":    [],
                "poster":      (show.get("image") or {}).get("medium"),
                "backdrop":    (show.get("image") or {}).get("original"),
                "source":      "tvmaze",
                "isManual":    False,
            }

            # Enrichissement TMDb
            if TMDB_KEY:
                enriched = tmdb_enrich(show.get("name", ""), "tv")
                if enriched:
                    entry["note"]     = enriched.get("note") or entry["note"]
                    entry["trailers"] = enriched.get("trailers") or entry["trailers"]
                    entry["desc"]     = enriched.get("desc") or entry["desc"]
                    if enriched.get("poster"):
                        entry["poster"] = enriched["poster"]
                    if enriched.get("backdrop"):
                        entry["backdrop"] = enriched["backdrop"]

            events.append(entry)

    log(f"  → {len(events)} séries internationales trouvées")
    return events

# ─── TMDB : films à venir ─────────────────────────────────────────────────────
def fetch_tmdb_movies():
    """Récupère les films à venir depuis TMDb."""
    if not TMDB_KEY:
        log("TMDb : clé API manquante, films ignorés")
        return []

    log("TMDb : films à venir...")
    events = []
    seen = set()

    # Films populaires à venir
    for page in range(1, 4):
        data = safe_get(f"{TMDB_BASE}/movie/upcoming", {
            "api_key": TMDB_KEY,
            "language": "fr-FR",
            "region": "CA",
            "page": page
        })
        if not data:
            break

        for movie in data.get("results", []):
            mid = movie.get("id")
            if mid in seen:
                continue
            release = movie.get("release_date", "")
            if not date_in_window(release):
                continue
            seen.add(mid)

            score = movie.get("vote_average", 0)
            # Filtre qualité minimal
            if score < 5.0 and movie.get("vote_count", 0) < 100:
                continue

            # Trailers
            trailers = []
            vdata = safe_get(f"{TMDB_BASE}/movie/{mid}/videos", {
                "api_key": TMDB_KEY, "language": "fr-FR"
            })
            if vdata:
                for v in vdata.get("results", []):
                    if v.get("site") == "YouTube" and v.get("type") in ("Trailer", "Teaser"):
                        trailers.append({
                            "lang": "VF",
                            "label": v.get("name", "Bande-annonce VF"),
                            "url": f"https://www.youtube.com/watch?v={v['key']}"
                        })
            if not trailers:
                vdata_en = safe_get(f"{TMDB_BASE}/movie/{mid}/videos", {
                    "api_key": TMDB_KEY, "language": "en-US"
                })
                if vdata_en:
                    for v in vdata_en.get("results", [])[:2]:
                        if v.get("site") == "YouTube":
                            trailers.append({
                                "lang": "VO",
                                "label": v.get("name", "Trailer VO"),
                                "url": f"https://www.youtube.com/watch?v={v['key']}"
                            })

            genres_ids = movie.get("genre_ids", [])
            cats = map_genre_ids(genres_ids)

            events.append({
                "id":          make_id("tmdb-movie", mid),
                "date":        release,
                "title":       movie.get("title", ""),
                "saison":      "Film",
                "status":      "sorti" if release <= TODAY.strftime("%Y-%m-%d") else "a-venir",
                "type":        "film",
                "platform":    "Cinéma",
                "platformUrl": f"https://www.themoviedb.org/movie/{mid}",
                "lang":        ["FR", "EN"],
                "tags":        [],
                "categories":  cats,
                "cast":        [],
                "desc":        movie.get("overview") or "",
                "note":        f"{score:.1f}" if score > 0 else None,
                "trailers":    trailers,
                "poster":      tmdb_poster(movie.get("poster_path")),
                "backdrop":    tmdb_poster(movie.get("backdrop_path"), "w780"),
                "source":      "tmdb",
                "isManual":    False,
            })

    log(f"  → {len(events)} films trouvés")
    return events

# ─── RADIO-CANADA RSS ─────────────────────────────────────────────────────────
def fetch_rc_rss():
    """Scrape le RSS Radio-Canada pour détecter les annonces de séries QC."""
    log("Radio-Canada RSS : vérification des annonces...")
    keywords = [
        "série", "saison", "tou.tv", "télé-québec", "illico",
        "crave", "émission", "diffusion", "première"
    ]
    announcements = []

    try:
        r = requests.get(RC_RSS, timeout=10)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        channel = root.find("channel")
        if not channel:
            return []

        for item in channel.findall("item"):
            title = (item.findtext("title") or "").lower()
            desc  = (item.findtext("description") or "").lower()
            link  = item.findtext("link") or ""
            pub   = item.findtext("pubDate") or ""

            combined = title + " " + desc
            if any(kw in combined for kw in keywords):
                announcements.append({
                    "title": item.findtext("title") or "",
                    "link":  link,
                    "date":  pub[:10] if pub else TODAY.strftime("%Y-%m-%d"),
                })

        log(f"  → {len(announcements)} annonces RC trouvées (info seulement, pas ajoutées automatiquement)")
    except Exception as e:
        log(f"  ⚠ RSS Radio-Canada indisponible : {e}")

    return announcements

# ─── UTILITAIRES GENRES ──────────────────────────────────────────────────────
GENRE_MAP = {
    "Drama":          "Drame",
    "Comedy":         "Comédie",
    "Thriller":       "Thriller",
    "Action":         "Action",
    "Adventure":      "Action",
    "Horror":         "Horreur",
    "Science-Fiction":"SF",
    "Fantasy":        "Fantasy",
    "Crime":          "Crime",
    "Mystery":        "Policier",
    "Documentary":    "Documentaire",
    "Romance":        "Romance",
    "Animation":      "Animation",
    "Family":         "Jeunesse",
    "Children":       "Jeunesse",
    "Reality":        "Téléréalité",
    "Soap":           "Drame",
    "Talk":           "Divertissement",
    "Music":          "Musique",
    "History":        "Drame",
    "War":            "Action",
    "Western":        "Action",
}

TMDB_GENRE_IDS = {
    28: "Action", 12: "Action", 16: "Animation", 35: "Comédie",
    80: "Crime", 99: "Documentaire", 18: "Drame", 10751: "Jeunesse",
    14: "Fantasy", 36: "Drame", 27: "Horreur", 10402: "Musique",
    9648: "Policier", 10749: "Romance", 878: "SF", 10770: "Drame",
    53: "Thriller", 10752: "Action", 37: "Action",
}

def map_genres(genres_list):
    cats = []
    for g in genres_list:
        mapped = GENRE_MAP.get(g)
        if mapped and mapped not in cats:
            cats.append(mapped)
    return cats or ["Drame"]

def map_genre_ids(ids):
    cats = []
    for gid in ids:
        mapped = TMDB_GENRE_IDS.get(gid)
        if mapped and mapped not in cats:
            cats.append(mapped)
    return cats or ["Film"]

def strip_html(text):
    """Enlève les balises HTML d'une description."""
    if not text:
        return ""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean[:600]  # Limite à 600 caractères

# ─── FUSION ET DÉDUPLICATION ─────────────────────────────────────────────────
def merge_events(existing, new_events, qc_manual):
    """
    Fusionne les nouvelles données avec les existantes.
    - Garde les entrées manuelles (isManual=True) telles quelles
    - Met à jour les entrées automatiques
    - Déduplique par titre + date approximative
    """
    merged = {}

    # 1. Garde toutes les entrées manuelles existantes
    for eid, entry in existing.items():
        if entry.get("isManual"):
            merged[eid] = entry

    # 2. Ajoute les données QC manuelles du fichier data-qc.json
    for entry in qc_manual:
        eid = entry.get("id", make_id("qc", entry.get("title", "")))
        entry["id"] = eid
        entry["isManual"] = True
        if not entry.get("status"):
            d = entry.get("date", "")
            entry["status"] = "sorti" if d and d <= TODAY.strftime("%Y-%m-%d") else "a-venir"
        merged[eid] = entry

    # 3. Ajoute les nouvelles entrées automatiques (avec déduplication par titre)
    title_date_seen = set()
    # D'abord les entrées manuelles existantes
    for e in merged.values():
        key = (e.get("title", "").lower(), e.get("date", "")[:7])  # titre + mois
        title_date_seen.add(key)

    for entry in new_events:
        key = (entry.get("title", "").lower(), entry.get("date", "")[:7])
        if key in title_date_seen:
            continue
        title_date_seen.add(key)
        eid = entry["id"]
        merged[eid] = entry

    return list(merged.values())

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print("\n🎬 Mise à jour du calendrier films & séries")
    print(f"   Date : {TODAY.strftime('%Y-%m-%d %H:%M')}")
    print(f"   Clé TMDb : {'✓ présente' if TMDB_KEY else '✗ manquante (ajoutez TMDB_API_KEY dans les secrets GitHub)'}")
    print()

    # Charge les données existantes
    existing = load_existing()
    qc_manual = load_qc_manual()
    log(f"Données existantes : {len(existing)} entrées")
    log(f"Entrées QC manuelles : {len(qc_manual)} entrées")
    print()

    # Récupère les nouvelles données
    all_new = []

    print("📡 Récupération TVmaze Canada...")
    all_new.extend(fetch_tvmaze_canada())

    print("\n📡 Récupération TVmaze international...")
    all_new.extend(fetch_tvmaze_upcoming())

    print("\n📡 Récupération TMDb films...")
    all_new.extend(fetch_tmdb_movies())

    print("\n📡 Vérification RSS Radio-Canada...")
    rc_items = fetch_rc_rss()  # Info seulement, pas ajouté auto

    # Fusionne
    print("\n🔀 Fusion des données...")
    final_events = merge_events(existing, all_new, qc_manual)

    # Trie par date
    final_events.sort(key=lambda e: e.get("date", "9999"))

    # Filtre la fenêtre de dates
    final_events = [e for e in final_events if date_in_window(e.get("date", ""))]

    # Construit le JSON final
    output = {
        "version":      "2.0",
        "generated_at": TODAY.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total":        len(final_events),
        "rc_announcements": rc_items[:10],  # Garde les 10 dernières annonces RC
        "events":       final_events,
    }

    # Sauvegarde
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Terminé ! {len(final_events)} événements sauvegardés dans {DATA_PATH}")
    print(f"   dont {sum(1 for e in final_events if e.get('isManual'))} entrées manuelles QC")
    print(f"   dont {sum(1 for e in final_events if e.get('status') == 'a-venir')} à venir\n")

if __name__ == "__main__":
    main()
