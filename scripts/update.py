#!/usr/bin/env python3
"""
Script de mise à jour automatique du calendrier films & séries.
Version 2 — fenêtre élargie, plus de titres, historique 2025 complet.
"""

import json
import os
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

# ─── CONFIG ──────────────────────────────────────────────────────────────────
TMDB_KEY    = os.environ.get("TMDB_API_KEY", "")
TMDB_BASE   = "https://api.themoviedb.org/3"
TMDB_IMG    = "https://image.tmdb.org/t/p"
TVMAZE_BASE = "https://api.tvmaze.com"
RC_RSS      = "https://ici.radio-canada.ca/rss/4159"
DATA_PATH   = Path("data.json")
QC_PATH     = Path("data-qc.json")
TODAY       = datetime.now()

# Fenêtre : 18 mois d'historique + 6 mois futur
HISTORY_DAYS = 548   # ~18 mois
FUTURE_DAYS  = 180   # 6 mois

# Réseaux québécois/canadiens reconnus sur TVmaze
QC_NETWORKS = [
    "ICI Radio-Canada Télé", "ICI TOU.TV", "Radio-Canada",
    "Télé-Québec", "TVA", "Noovo", "Club Illico", "Crave",
    "Super Écran", "Séries+", "Canal Vie", "Historia",
    "Savoir Media", "ARTV", "CTV", "CBC", "Global",
    "CTV Drama Channel", "CTV Sci-Fi Channel", "W Network",
    "Showcase", "Slice", "Documentary Channel",
]

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
    "CTV":                   "Crave",
    "CBC":                   "ICI TOU.TV",
    "Global":                "Crave",
    "CTV Drama Channel":     "Crave",
    "CTV Sci-Fi Channel":    "Crave",
    "W Network":             "Crave",
    "Showcase":              "Crave",
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

# Plateformes internationales majeures
INTL_PLATFORMS = {
    "netflix":    "Netflix",
    "hbo":        "Crave",
    "max":        "Crave",
    "amazon":     "Prime Video",
    "prime":      "Prime Video",
    "apple":      "Apple TV+",
    "disney":     "Disney+",
    "hulu":       "Disney+",
    "peacock":    "Prime Video",
    "paramount":  "Prime Video",
}

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def log(msg): print(f"  {msg}", flush=True)

def safe_get(url, params=None, timeout=15):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"⚠ {url[:50]}... : {e}")
        return None

def date_in_window(date_str):
    if not date_str: return False
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        start = TODAY - timedelta(days=HISTORY_DAYS)
        end   = TODAY + timedelta(days=FUTURE_DAYS)
        return start <= d <= end
    except: return False

def tmdb_poster(path, size="w300"):
    return f"{TMDB_IMG}/{size}{path}" if path else None

def make_id(prefix, val):
    clean = re.sub(r'[^a-z0-9]', '-', str(val).lower())
    return f"{prefix}-{clean}"

def strip_html(text):
    if not text: return ""
    clean = re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\s+', ' ', clean).strip()[:800]

# ─── GENRES ──────────────────────────────────────────────────────────────────
GENRE_MAP = {
    "Drama":"Drame","Comedy":"Comédie","Thriller":"Thriller",
    "Action":"Action","Adventure":"Action","Horror":"Horreur",
    "Science-Fiction":"SF","Fantasy":"Fantasy","Crime":"Crime",
    "Mystery":"Policier","Documentary":"Documentaire","Romance":"Romance",
    "Animation":"Animation","Family":"Jeunesse","Children":"Jeunesse",
    "Reality":"Téléréalité","Soap":"Drame","Talk":"Divertissement",
    "Music":"Musique","History":"Drame","War":"Action","Western":"Action",
    "Espionage":"Thriller","Legal":"Drame","Medical":"Drame",
    "Sports":"Documentaire","Supernatural":"Horreur","Adult":"Drame",
}

TMDB_GENRE_IDS = {
    28:"Action",12:"Action",16:"Animation",35:"Comédie",80:"Crime",
    99:"Documentaire",18:"Drame",10751:"Jeunesse",14:"Fantasy",
    36:"Drame",27:"Horreur",10402:"Musique",9648:"Policier",
    10749:"Romance",878:"SF",10770:"Drame",53:"Thriller",
    10752:"Action",37:"Action",10759:"Action",10762:"Jeunesse",
    10763:"Documentaire",10764:"Téléréalité",10765:"SF",
    10766:"Drame",10767:"Divertissement",10768:"Action",
}

def map_genres(gl): return list({GENRE_MAP.get(g) for g in gl if GENRE_MAP.get(g)}) or ["Drame"]
def map_genre_ids(ids): return list({TMDB_GENRE_IDS.get(i) for i in ids if TMDB_GENRE_IDS.get(i)}) or ["Film"]

# ─── TMDB ENRICHISSEMENT ─────────────────────────────────────────────────────
def tmdb_enrich(title, media_type="tv", year=None):
    if not TMDB_KEY: return {}
    ep = f"{TMDB_BASE}/search/{'tv' if media_type=='tv' else 'movie'}"
    params = {"api_key": TMDB_KEY, "query": title, "language": "fr-FR"}
    if year: params["first_air_date_year" if media_type=="tv" else "year"] = year

    data = safe_get(ep, params)
    if not data or not data.get("results"):
        params["language"] = "en-US"
        data = safe_get(ep, params)
    if not data or not data.get("results"): return {}

    r = data["results"][0]
    tid = r.get("id")
    score = r.get("vote_average")
    note = f"{score:.1f}" if score and score > 0 else None

    trailers = []
    if tid:
        for lang in ["fr-FR", "en-US"]:
            vd = safe_get(f"{TMDB_BASE}/{'tv' if media_type=='tv' else 'movie'}/{tid}/videos",
                         {"api_key": TMDB_KEY, "language": lang})
            if vd:
                for v in vd.get("results", []):
                    if v.get("site")=="YouTube" and v.get("type") in ("Trailer","Teaser"):
                        trailers.append({
                            "lang": "VF" if lang=="fr-FR" else "VO",
                            "label": v.get("name", "Bande-annonce"),
                            "url": f"https://www.youtube.com/watch?v={v['key']}"
                        })
            if trailers: break

    return {
        "tmdb_id": tid, "note": note,
        "poster":   tmdb_poster(r.get("poster_path")),
        "backdrop": tmdb_poster(r.get("backdrop_path"), "w780"),
        "desc":     r.get("overview") or "",
        "trailers": trailers[:4],
    }

# ─── TVMAZE CANADA ───────────────────────────────────────────────────────────
def fetch_tvmaze_canada():
    log("TVmaze Canada — historique + futur...")
    events = []
    seen = set()

    # Calendrier CA : on couvre toute la fenêtre par tranches de 7 jours
    start = TODAY - timedelta(days=HISTORY_DAYS)
    total_days = HISTORY_DAYS + FUTURE_DAYS

    for offset in range(0, total_days, 7):
        d = (start + timedelta(days=offset)).strftime("%Y-%m-%d")
        url = f"{TVMAZE_BASE}/schedule?country=CA&date={d}"
        episodes = safe_get(url) or []

        for ep in episodes:
            show = ep.get("_embedded", {}).get("show") or ep.get("show") or {}
            show_id = show.get("id")
            if not show_id or show_id in seen: continue

            network = show.get("network") or show.get("webChannel") or {}
            net_name = network.get("name", "")
            country = (network.get("country") or {}).get("code", "")

            if net_name not in QC_NETWORKS and country not in ("CA",):
                continue

            air_date = ep.get("airdate", "")
            if not date_in_window(air_date): continue
            seen.add(show_id)

            platform = NETWORK_MAP.get(net_name, net_name)
            lang = ["FR"] if any(x in net_name for x in
                ["Radio-Canada","Télé","TVA","Noovo","Club","ARTV","ICI"]) else ["EN","FR"]

            tags = ["QC"] if net_name in QC_NETWORKS else ["CA"]
            cats = map_genres(show.get("genres", []))
            season_num = ep.get("season", 1)
            rating = (show.get("rating") or {}).get("average")

            entry = {
                "id":          make_id("tvmaze-ca", show_id),
                "date":        air_date,
                "title":       show.get("name", ""),
                "saison":      f"Saison {season_num}",
                "status":      "sorti" if air_date <= TODAY.strftime("%Y-%m-%d") else "a-venir",
                "type":        "serie",
                "platform":    platform,
                "platformUrl": PLATFORM_URLS.get(platform, "#"),
                "lang":        lang,
                "tags":        tags,
                "categories":  cats,
                "cast":        [],
                "desc":        strip_html(show.get("summary") or ""),
                "note":        f"{rating:.1f}" if rating else None,
                "trailers":    [],
                "poster":      (show.get("image") or {}).get("medium"),
                "backdrop":    (show.get("image") or {}).get("original"),
                "source":      "tvmaze",
                "isManual":    False,
            }

            if TMDB_KEY:
                enriched = tmdb_enrich(show.get("name",""), "tv")
                if enriched:
                    for k in ("note","trailers","desc","poster","backdrop"):
                        if enriched.get(k): entry[k] = enriched[k]

            events.append(entry)

    log(f"  → {len(events)} séries canadiennes")
    return events

# ─── TVMAZE INTERNATIONAL POPULAIRE ──────────────────────────────────────────
def fetch_tvmaze_international():
    log("TVmaze international — séries populaires 2025-2026...")
    events = []
    seen = set()

    # Stratégie 1 : Top shows TVmaze (les plus populaires tous temps)
    for page in range(0, 5):
        data = safe_get(f"{TVMAZE_BASE}/shows?page={page}") or []
        for show in data:
            show_id = show.get("id")
            if show_id in seen: continue

            # Filtre qualité
            rating = (show.get("rating") or {}).get("average") or 0
            weight = show.get("weight", 0)
            if rating < 7.5 and weight < 85: continue

            # Détermine la plateforme
            web_ch = (show.get("webChannel") or {}).get("name", "").lower()
            net_nm = (show.get("network") or {}).get("name", "").lower()
            plat_raw = web_ch or net_nm
            platform = None
            for k, v in INTL_PLATFORMS.items():
                if k in plat_raw: platform = v; break
            if not platform: continue

            # Date de première diffusion
            premiered = show.get("premiered", "")
            if not premiered or not date_in_window(premiered): continue
            seen.add(show_id)

            cats = map_genres(show.get("genres", []))
            entry = {
                "id":          make_id("tvm-intl", show_id),
                "date":        premiered,
                "title":       show.get("name", ""),
                "saison":      "Saison 1",
                "status":      "sorti" if premiered <= TODAY.strftime("%Y-%m-%d") else "a-venir",
                "type":        "serie",
                "platform":    platform,
                "platformUrl": PLATFORM_URLS.get(platform, "#"),
                "lang":        ["FR","EN"],
                "tags":        [],
                "categories":  cats,
                "cast":        [],
                "desc":        strip_html(show.get("summary") or ""),
                "note":        f"{rating:.1f}" if rating else None,
                "trailers":    [],
                "poster":      (show.get("image") or {}).get("medium"),
                "backdrop":    (show.get("image") or {}).get("original"),
                "source":      "tvmaze",
                "isManual":    False,
            }

            if TMDB_KEY:
                enriched = tmdb_enrich(show.get("name",""), "tv")
                if enriched:
                    for k in ("note","trailers","desc","poster","backdrop"):
                        if enriched.get(k): entry[k] = enriched[k]

            events.append(entry)

    # Stratégie 2 : Calendrier US récent (7 derniers mois + futur)
    for offset in range(-210, FUTURE_DAYS, 14):
        d = (TODAY + timedelta(days=offset)).strftime("%Y-%m-%d")
        episodes = safe_get(f"{TVMAZE_BASE}/schedule?country=US&date={d}") or []
        for ep in episodes:
            show = ep.get("_embedded", {}).get("show") or ep.get("show") or {}
            show_id = show.get("id")
            if not show_id or show_id in seen: continue

            rating = (show.get("rating") or {}).get("average") or 0
            weight = show.get("weight", 0)
            if rating < 7.0 and weight < 80: continue

            web_ch = (show.get("webChannel") or {}).get("name","").lower()
            net_nm = (show.get("network") or {}).get("name","").lower()
            plat_raw = web_ch or net_nm
            platform = None
            for k, v in INTL_PLATFORMS.items():
                if k in plat_raw: platform = v; break
            if not platform: continue

            air_date = ep.get("airdate","")
            if not date_in_window(air_date): continue
            seen.add(show_id)

            season_num = ep.get("season", 1)
            cats = map_genres(show.get("genres", []))

            entry = {
                "id":          make_id("tvm-us", show_id),
                "date":        air_date,
                "title":       show.get("name",""),
                "saison":      f"Saison {season_num}",
                "status":      "sorti" if air_date <= TODAY.strftime("%Y-%m-%d") else "a-venir",
                "type":        "serie",
                "platform":    platform,
                "platformUrl": PLATFORM_URLS.get(platform,"#"),
                "lang":        ["FR","EN"],
                "tags":        [],
                "categories":  cats,
                "cast":        [],
                "desc":        strip_html(show.get("summary") or ""),
                "note":        f"{rating:.1f}" if rating else None,
                "trailers":    [],
                "poster":      (show.get("image") or {}).get("medium"),
                "backdrop":    (show.get("image") or {}).get("original"),
                "source":      "tvmaze",
                "isManual":    False,
            }

            if TMDB_KEY:
                enriched = tmdb_enrich(show.get("name",""), "tv")
                if enriched:
                    for k in ("note","trailers","desc","poster","backdrop"):
                        if enriched.get(k): entry[k] = enriched[k]

            events.append(entry)

    log(f"  → {len(events)} séries internationales")
    return events

# ─── TMDB FILMS ──────────────────────────────────────────────────────────────
def fetch_tmdb_movies():
    if not TMDB_KEY:
        log("TMDb : clé manquante")
        return []

    log("TMDb films 2025-2026...")
    events = []
    seen = set()

    endpoints = [
        ("upcoming", {"region": "CA"}),
        ("now_playing", {"region": "CA"}),
        ("popular", {"region": "CA"}),
        ("top_rated", {"region": "CA"}),
    ]

    for endpoint, extra_params in endpoints:
        for page in range(1, 6):
            params = {"api_key": TMDB_KEY, "language": "fr-FR", "page": page}
            params.update(extra_params)
            data = safe_get(f"{TMDB_BASE}/movie/{endpoint}", params)
            if not data: break

            for movie in data.get("results", []):
                mid = movie.get("id")
                if mid in seen: continue
                release = movie.get("release_date","")
                if not release or not date_in_window(release): continue

                score = movie.get("vote_average",0)
                votes = movie.get("vote_count",0)
                if score < 4.0 and votes < 50: continue
                seen.add(mid)

                trailers = []
                for lang in ["fr-FR","en-US"]:
                    vd = safe_get(f"{TMDB_BASE}/movie/{mid}/videos",
                                 {"api_key":TMDB_KEY,"language":lang})
                    if vd:
                        for v in vd.get("results",[]):
                            if v.get("site")=="YouTube" and v.get("type") in ("Trailer","Teaser"):
                                trailers.append({
                                    "lang":"VF" if lang=="fr-FR" else "VO",
                                    "label":v.get("name","Bande-annonce"),
                                    "url":f"https://www.youtube.com/watch?v={v['key']}"
                                })
                    if trailers: break

                cats = map_genre_ids(movie.get("genre_ids",[]))
                events.append({
                    "id":          make_id("tmdb-film", mid),
                    "date":        release,
                    "title":       movie.get("title",""),
                    "saison":      "Film",
                    "status":      "sorti" if release <= TODAY.strftime("%Y-%m-%d") else "a-venir",
                    "type":        "film",
                    "platform":    "Cinéma",
                    "platformUrl": f"https://www.themoviedb.org/movie/{mid}",
                    "lang":        ["FR","EN"],
                    "tags":        [],
                    "categories":  cats,
                    "cast":        [],
                    "desc":        movie.get("overview",""),
                    "note":        f"{score:.1f}" if score>0 else None,
                    "trailers":    trailers[:4],
                    "poster":      tmdb_poster(movie.get("poster_path")),
                    "backdrop":    tmdb_poster(movie.get("backdrop_path"),"w780"),
                    "source":      "tmdb",
                    "isManual":    False,
                })

    log(f"  → {len(events)} films")
    return events

# ─── TMDB SÉRIES POPULAIRES ───────────────────────────────────────────────────
def fetch_tmdb_series():
    if not TMDB_KEY:
        return []

    log("TMDb séries populaires 2025-2026...")
    events = []
    seen = set()

    endpoints = ["popular","top_rated","on_the_air","airing_today"]

    for endpoint in endpoints:
        for page in range(1, 6):
            data = safe_get(f"{TMDB_BASE}/tv/{endpoint}",
                           {"api_key":TMDB_KEY,"language":"fr-FR","page":page})
            if not data: break

            for show in data.get("results",[]):
                sid = show.get("id")
                if sid in seen: continue

                first_air = show.get("first_air_date","")
                if not first_air or not date_in_window(first_air): continue

                score = show.get("vote_average",0)
                votes = show.get("vote_count",0)
                if score < 5.0 and votes < 100: continue
                seen.add(sid)

                trailers = []
                for lang in ["fr-FR","en-US"]:
                    vd = safe_get(f"{TMDB_BASE}/tv/{sid}/videos",
                                 {"api_key":TMDB_KEY,"language":lang})
                    if vd:
                        for v in vd.get("results",[]):
                            if v.get("site")=="YouTube" and v.get("type") in ("Trailer","Teaser"):
                                trailers.append({
                                    "lang":"VF" if lang=="fr-FR" else "VO",
                                    "label":v.get("name","Bande-annonce"),
                                    "url":f"https://www.youtube.com/watch?v={v['key']}"
                                })
                    if trailers: break

                cats = map_genre_ids(show.get("genre_ids",[]))

                # Détermine la plateforme depuis les networks TMDb
                platform = "Netflix"  # défaut
                networks = show.get("networks",[]) or show.get("origin_country",[])

                events.append({
                    "id":          make_id("tmdb-serie", sid),
                    "date":        first_air,
                    "title":       show.get("name",""),
                    "saison":      "Saison 1",
                    "status":      "sorti" if first_air <= TODAY.strftime("%Y-%m-%d") else "a-venir",
                    "type":        "serie",
                    "platform":    platform,
                    "platformUrl": PLATFORM_URLS.get(platform,"#"),
                    "lang":        ["FR","EN"],
                    "tags":        [],
                    "categories":  cats,
                    "cast":        [],
                    "desc":        show.get("overview",""),
                    "note":        f"{score:.1f}" if score>0 else None,
                    "trailers":    trailers[:4],
                    "poster":      tmdb_poster(show.get("poster_path")),
                    "backdrop":    tmdb_poster(show.get("backdrop_path"),"w780"),
                    "source":      "tmdb",
                    "isManual":    False,
                })

    log(f"  → {len(events)} séries TMDb")
    return events

# ─── RADIO-CANADA RSS ─────────────────────────────────────────────────────────
def fetch_rc_rss():
    log("Radio-Canada RSS...")
    keywords = ["série","saison","tou.tv","télé-québec","illico","crave","émission","diffusion","première"]
    items = []
    try:
        r = requests.get(RC_RSS, timeout=10)
        root = ET.fromstring(r.content)
        for item in (root.find("channel") or []):
            if item.tag != "item": continue
            t = (item.findtext("title") or "").lower()
            d = (item.findtext("description") or "").lower()
            if any(k in t+d for k in keywords):
                items.append({
                    "title": item.findtext("title") or "",
                    "link":  item.findtext("link") or "",
                    "date":  (item.findtext("pubDate") or "")[:16],
                })
        log(f"  → {len(items)} annonces RC")
    except Exception as e:
        log(f"  ⚠ RSS RC : {e}")
    return items

# ─── FUSION ──────────────────────────────────────────────────────────────────
def merge(existing, new_events, qc_manual):
    merged = {}

    # Entrées manuelles existantes
    for eid, e in existing.items():
        if e.get("isManual"): merged[eid] = e

    # Nouvelles entrées QC manuelles
    for e in qc_manual:
        eid = e.get("id", make_id("qc", e.get("title","")))
        e["id"] = eid
        e["isManual"] = True
        if not e.get("status"):
            d = e.get("date","")
            e["status"] = "sorti" if d and d <= TODAY.strftime("%Y-%m-%d") else "a-venir"
        merged[eid] = e

    # Nouvelles entrées automatiques — déduplication par titre + mois
    seen_keys = set()
    for e in merged.values():
        seen_keys.add((e.get("title","").lower(), e.get("date","")[:7]))

    for e in new_events:
        key = (e.get("title","").lower(), e.get("date","")[:7])
        if key in seen_keys: continue
        seen_keys.add(key)
        merged[e["id"]] = e

    return list(merged.values())

def load_existing():
    if DATA_PATH.exists():
        with open(DATA_PATH,"r",encoding="utf-8") as f:
            data = json.load(f)
            return {e["id"]:e for e in data.get("events",[])}
    return {}

def load_qc():
    if QC_PATH.exists():
        with open(QC_PATH,"r",encoding="utf-8") as f:
            return json.load(f)
    return []

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    print(f"\n🎬 Mise à jour calendrier — {TODAY.strftime('%Y-%m-%d %H:%M')}")
    print(f"   Clé TMDb : {'✓' if TMDB_KEY else '✗ MANQUANTE'}")
    print(f"   Fenêtre : {HISTORY_DAYS} jours passés + {FUTURE_DAYS} jours futurs\n")

    existing = load_existing()
    qc_manual = load_qc()
    log(f"Existant : {len(existing)} | QC manuel : {len(qc_manual)}")

    all_new = []

    print("\n📡 TVmaze Canada...")
    all_new.extend(fetch_tvmaze_canada())

    print("\n📡 TVmaze International...")
    all_new.extend(fetch_tvmaze_international())

    print("\n📡 TMDb Films...")
    all_new.extend(fetch_tmdb_movies())

    print("\n📡 TMDb Séries...")
    all_new.extend(fetch_tmdb_series())

    print("\n📡 RSS Radio-Canada...")
    rc = fetch_rc_rss()

    print("\n🔀 Fusion...")
    final = merge(existing, all_new, qc_manual)
    final = [e for e in final if date_in_window(e.get("date",""))]
    final.sort(key=lambda e: e.get("date","9999"))

    output = {
        "version":        "2.0",
        "generated_at":   TODAY.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total":          len(final),
        "rc_announcements": rc[:10],
        "events":         final,
    }

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_PATH,"w",encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ {len(final)} événements sauvegardés dans {DATA_PATH}")
    print(f"   Manuels QC : {sum(1 for e in final if e.get('isManual'))}")
    print(f"   À venir    : {sum(1 for e in final if e.get('status')=='a-venir')}")
    print(f"   Déjà sortis: {sum(1 for e in final if e.get('status')=='sorti')}\n")

if __name__ == "__main__":
    main()
