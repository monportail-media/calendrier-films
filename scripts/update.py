#!/usr/bin/env python3
"""
Script de mise a jour automatique du calendrier films & series.
Version finale — fenetre elargie, vraies plateformes, historique 2025 complet.
Sources : TVmaze (CA + US), TMDb (films + series), RSS Radio-Canada
"""

import json, os, re, requests, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

# ── CONFIG ────────────────────────────────────────────────────────────────────
TMDB_KEY    = os.environ.get("TMDB_API_KEY", "")
TMDB_BASE   = "https://api.themoviedb.org/3"
TMDB_IMG    = "https://image.tmdb.org/t/p"
TVMAZE_BASE = "https://api.tvmaze.com"
RC_RSS      = "https://ici.radio-canada.ca/rss/4159"
DATA_PATH   = Path("data.json")
QC_PATH     = Path("data-qc.json")
TODAY       = datetime.now()
TODAY_STR   = TODAY.strftime("%Y-%m-%d")
HISTORY_DAYS = 548  # 18 mois
FUTURE_DAYS  = 180  # 6 mois

# ── RESEAUX QUEBECOIS / CANADIENS ─────────────────────────────────────────────
QC_NETWORKS = {
    "ICI Radio-Canada Télé","ICI TOU.TV","Radio-Canada","Télé-Québec",
    "TVA","Noovo","Club Illico","Crave","Super Écran","Séries+",
    "Canal Vie","Historia","Savoir Media","ARTV","CTV","CBC","Global",
    "CTV Drama Channel","CTV Sci-Fi Channel","W Network","Showcase","Slice",
}

NETWORK_TO_PLATFORM = {
    "ICI Radio-Canada Télé":"ICI TOU.TV","ICI TOU.TV":"ICI TOU.TV",
    "Radio-Canada":"ICI TOU.TV","Télé-Québec":"Télé-Québec",
    "TVA":"TVA+","Noovo":"Club Illico","Club Illico":"Club Illico",
    "Super Écran":"Club Illico","Séries+":"Club Illico",
    "Canal Vie":"Club Illico","Historia":"Club Illico",
    "Savoir Media":"Télé-Québec","ARTV":"ICI TOU.TV",
    "CTV":"Crave","CBC":"ICI TOU.TV","Global":"Crave",
    "CTV Drama Channel":"Crave","CTV Sci-Fi Channel":"Crave",
    "W Network":"Crave","Showcase":"Crave","Slice":"Club Illico",
    # Plateformes américaines
    "Netflix":"Netflix","HBO":"Crave","Max":"Crave","HBO Max":"Crave",
    "Amazon":"Prime Video","Prime Video":"Prime Video",
    "Apple TV+":"Apple TV+","Disney+":"Disney+","Hulu":"Disney+",
    "Peacock":"Prime Video","Paramount+":"Prime Video",
    "AMC":"Prime Video","FX":"Disney+","Showtime":"Crave",
    "Starz":"Prime Video","Syfy":"Prime Video","USA Network":"Prime Video",
    "TNT":"Prime Video","TBS":"Prime Video","Adult Swim":"Prime Video",
    "Comedy Central":"Prime Video","Bravo":"Prime Video",
    "NBC":"Prime Video","ABC":"Disney+","CBS":"Prime Video","Fox":"Disney+",
}

PLATFORM_URLS = {
    "Netflix":"https://www.netflix.com",
    "Prime Video":"https://www.primevideo.com",
    "Disney+":"https://www.disneyplus.com",
    "Apple TV+":"https://tv.apple.com",
    "Crave":"https://www.crave.ca",
    "ICI TOU.TV":"https://ici.tou.tv",
    "Télé-Québec":"https://www.telequebec.tv",
    "TVA+":"https://www.tvaplus.ca",
    "Club Illico":"https://www.illico.com",
    "Cinéma":"https://www.themoviedb.org",
}

# Correspondance TMDb network_id → plateforme
TMDB_NETWORK_MAP = {
    213:"Netflix", 49:"HBO", 2739:"Disney+", 1024:"Amazon",
    2552:"Apple TV+", 453:"Hulu", 4330:"Peacock", 4353:"Paramount+",
    174:"AMC", 88:"AMC", 19:"FOX", 2:"ABC", 6:"NBC", 16:"CBS",
    67:"Showtime", 318:"Starz", 73:"BBC One", 332:"BBC Two",
    56:"Crave", 1556:"Crave",
}

# ── GENRES ───────────────────────────────────────────────────────────────────
TVMAZE_GENRE_MAP = {
    "Drama":"Drame","Comedy":"Comédie","Thriller":"Thriller",
    "Action":"Action","Adventure":"Action","Horror":"Horreur",
    "Science-Fiction":"SF","Fantasy":"Fantasy","Crime":"Crime",
    "Mystery":"Policier","Documentary":"Documentaire","Romance":"Romance",
    "Animation":"Animation","Family":"Jeunesse","Children":"Jeunesse",
    "Reality":"Téléréalité","Music":"Musique","History":"Drame",
    "War":"Action","Western":"Action","Espionage":"Thriller",
    "Legal":"Drame","Medical":"Drame","Sports":"Documentaire",
    "Supernatural":"Horreur","Nature":"Documentaire","Food":"Documentaire",
    "Travel":"Documentaire","DIY":"Téléréalité","Game Show":"Téléréalité",
    "Talk Show":"Divertissement","Anime":"Animation",
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

def map_tvmaze_genres(gl):
    cats = [TVMAZE_GENRE_MAP[g] for g in gl if g in TVMAZE_GENRE_MAP]
    return list(dict.fromkeys(cats)) or ["Drame"]

def map_tmdb_genre_ids(ids):
    cats = [TMDB_GENRE_IDS[i] for i in ids if i in TMDB_GENRE_IDS]
    return list(dict.fromkeys(cats)) or ["Film"]

# ── HELPERS ───────────────────────────────────────────────────────────────────
def log(msg): print(f"  {msg}", flush=True)

def safe_get(url, params=None, timeout=15):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"⚠ {url[:55]}... : {e}")
        return None

def in_window(date_str):
    if not date_str: return False
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return (TODAY - timedelta(days=HISTORY_DAYS)) <= d <= (TODAY + timedelta(days=FUTURE_DAYS))
    except: return False

def img(path, size="w300"):
    return f"{TMDB_IMG}/{size}{path}" if path else None

def uid(prefix, val):
    return f"{prefix}-{re.sub(r'[^a-z0-9]', '-', str(val).lower())}"

def clean_html(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', text)).strip()[:800]

def get_trailers(tmdb_id, media="tv"):
    trailers = []
    for lang in ["fr-FR", "en-US"]:
        vd = safe_get(f"{TMDB_BASE}/{media}/{tmdb_id}/videos",
                      {"api_key": TMDB_KEY, "language": lang})
        if vd:
            for v in vd.get("results", []):
                if v.get("site") == "YouTube" and v.get("type") in ("Trailer","Teaser"):
                    trailers.append({
                        "lang": "VF" if lang == "fr-FR" else "VO",
                        "label": v.get("name", "Bande-annonce"),
                        "url": f"https://www.youtube.com/watch?v={v['key']}"
                    })
        if trailers: break
    return trailers[:4]

def tmdb_platform_from_networks(networks):
    """Détermine la plateforme depuis les networks TMDb."""
    for n in networks:
        nid = n.get("id")
        name = n.get("name", "")
        if nid in TMDB_NETWORK_MAP:
            return TMDB_NETWORK_MAP[nid]
        # Cherche par nom
        for key, plat in NETWORK_TO_PLATFORM.items():
            if key.lower() in name.lower():
                return plat
    return "Netflix"  # défaut

def tvmaze_platform(show):
    """Détermine la plateforme depuis un show TVmaze."""
    for src in [show.get("webChannel"), show.get("network")]:
        if not src: continue
        name = src.get("name", "")
        if name in NETWORK_TO_PLATFORM:
            return NETWORK_TO_PLATFORM[name], name in QC_NETWORKS
        for key, plat in NETWORK_TO_PLATFORM.items():
            if key.lower() in name.lower():
                return plat, name in QC_NETWORKS
    return None, False

def tmdb_enrich(title, media="tv"):
    """Enrichit avec poster, note, desc, trailers depuis TMDb."""
    if not TMDB_KEY: return {}
    ep = f"{TMDB_BASE}/search/{'tv' if media=='tv' else 'movie'}"
    for lang in ["fr-FR", "en-US"]:
        data = safe_get(ep, {"api_key": TMDB_KEY, "query": title, "language": lang})
        if data and data.get("results"):
            r = data["results"][0]
            tid = r.get("id")
            score = r.get("vote_average")
            trailers = get_trailers(tid, media) if tid else []
            return {
                "note":     f"{score:.1f}" if score and score > 0 else None,
                "poster":   img(r.get("poster_path")),
                "backdrop": img(r.get("backdrop_path"), "w780"),
                "desc":     r.get("overview") or "",
                "trailers": trailers,
            }
    return {}

# ── TVMAZE CANADA ─────────────────────────────────────────────────────────────
def fetch_canada():
    log("TVmaze Canada — 18 mois d'historique + 6 mois futur...")
    events, seen = [], set()
    start = TODAY - timedelta(days=HISTORY_DAYS)

    for offset in range(0, HISTORY_DAYS + FUTURE_DAYS, 7):
        d = (start + timedelta(days=offset)).strftime("%Y-%m-%d")
        eps = safe_get(f"{TVMAZE_BASE}/schedule?country=CA&date={d}") or []

        for ep in eps:
            show = ep.get("_embedded", {}).get("show") or ep.get("show") or {}
            sid = show.get("id")
            if not sid or sid in seen: continue

            plat, is_qc = tvmaze_platform(show)
            if not plat: continue

            air = ep.get("airdate", "")
            if not in_window(air): continue
            seen.add(sid)

            lang_qc = ["FR"] if is_qc and any(
                x in (show.get("network") or show.get("webChannel") or {}).get("name","")
                for x in ["Radio-Canada","Télé","TVA","Noovo","Club","ARTV","ICI"]
            ) else ["FR","EN"]

            tags = ["QC"] if is_qc else ["CA"]
            rating = (show.get("rating") or {}).get("average")
            entry = {
                "id":          uid("ca", sid),
                "date":        air,
                "title":       show.get("name",""),
                "saison":      f"Saison {ep.get('season',1)}",
                "status":      "sorti" if air <= TODAY_STR else "a-venir",
                "type":        "serie",
                "platform":    plat,
                "platformUrl": PLATFORM_URLS.get(plat,"#"),
                "lang":        lang_qc,
                "tags":        tags,
                "categories":  map_tvmaze_genres(show.get("genres",[])),
                "cast":        [],
                "desc":        clean_html(show.get("summary","")),
                "note":        f"{rating:.1f}" if rating else None,
                "trailers":    [],
                "poster":      (show.get("image") or {}).get("medium"),
                "backdrop":    (show.get("image") or {}).get("original"),
                "source":      "tvmaze-ca",
                "isManual":    False,
            }
            if TMDB_KEY:
                e = tmdb_enrich(show.get("name",""), "tv")
                for k in ("note","trailers","desc","poster","backdrop"):
                    if e.get(k): entry[k] = e[k]
            events.append(entry)

    log(f"  → {len(events)} séries canadiennes/québécoises")
    return events

# ── TVMAZE US POPULAIRE ───────────────────────────────────────────────────────
def fetch_us_popular():
    log("TVmaze US — séries populaires...")
    events, seen = [], set()

    # Top shows tous temps
    for page in range(0, 8):
        shows = safe_get(f"{TVMAZE_BASE}/shows?page={page}") or []
        for show in shows:
            sid = show.get("id")
            if sid in seen: continue
            rating = (show.get("rating") or {}).get("average") or 0
            weight = show.get("weight", 0)
            if rating < 7.5 and weight < 85: continue
            plat, _ = tvmaze_platform(show)
            if not plat: continue
            premiered = show.get("premiered","")
            if not premiered or not in_window(premiered): continue
            seen.add(sid)
            entry = _make_show_entry(show, premiered, plat, "tvmaze-top", ep_season=1)
            if TMDB_KEY:
                e = tmdb_enrich(show.get("name",""), "tv")
                for k in ("note","trailers","desc","poster","backdrop"):
                    if e.get(k): entry[k] = e[k]
            events.append(entry)

    # Calendrier US — 7 mois passés + futur
    for offset in range(-210, FUTURE_DAYS, 14):
        d = (TODAY + timedelta(days=offset)).strftime("%Y-%m-%d")
        eps = safe_get(f"{TVMAZE_BASE}/schedule?country=US&date={d}") or []
        for ep in eps:
            show = ep.get("_embedded",{}).get("show") or ep.get("show") or {}
            sid = show.get("id")
            if not sid or sid in seen: continue
            rating = (show.get("rating") or {}).get("average") or 0
            weight = show.get("weight",0)
            if rating < 6.5 and weight < 75: continue
            plat, _ = tvmaze_platform(show)
            if not plat: continue
            air = ep.get("airdate","")
            if not in_window(air): continue
            seen.add(sid)
            entry = _make_show_entry(show, air, plat, "tvmaze-us", ep.get("season",1))
            if TMDB_KEY:
                e = tmdb_enrich(show.get("name",""), "tv")
                for k in ("note","trailers","desc","poster","backdrop"):
                    if e.get(k): entry[k] = e[k]
            events.append(entry)

    log(f"  → {len(events)} séries US/internationales")
    return events

def _make_show_entry(show, date, plat, source, ep_season=1):
    rating = (show.get("rating") or {}).get("average")
    return {
        "id":          uid(source, show.get("id","")),
        "date":        date,
        "title":       show.get("name",""),
        "saison":      f"Saison {ep_season}",
        "status":      "sorti" if date <= TODAY_STR else "a-venir",
        "type":        "serie",
        "platform":    plat,
        "platformUrl": PLATFORM_URLS.get(plat,"#"),
        "lang":        ["FR","EN"],
        "tags":        [],
        "categories":  map_tvmaze_genres(show.get("genres",[])),
        "cast":        [],
        "desc":        clean_html(show.get("summary","")),
        "note":        f"{rating:.1f}" if rating else None,
        "trailers":    [],
        "poster":      (show.get("image") or {}).get("medium"),
        "backdrop":    (show.get("image") or {}).get("original"),
        "source":      source,
        "isManual":    False,
    }

# ── TMDB FILMS ────────────────────────────────────────────────────────────────
def fetch_films():
    if not TMDB_KEY: return []
    log("TMDb films 2025-2026...")
    events, seen = [], set()

    for endpoint in ["upcoming","now_playing","popular","top_rated"]:
        for page in range(1, 8):
            data = safe_get(f"{TMDB_BASE}/movie/{endpoint}", {
                "api_key":TMDB_KEY,"language":"fr-FR","page":page,"region":"CA"
            })
            if not data: break
            for m in data.get("results",[]):
                mid = m.get("id")
                if mid in seen: continue
                release = m.get("release_date","")
                if not release or not in_window(release): continue
                score = m.get("vote_average",0)
                if score < 4.0 and m.get("vote_count",0) < 50: continue
                seen.add(mid)
                trailers = get_trailers(mid, "movie")
                events.append({
                    "id":          uid("film", mid),
                    "date":        release,
                    "title":       m.get("title",""),
                    "saison":      "Film",
                    "status":      "sorti" if release <= TODAY_STR else "a-venir",
                    "type":        "film",
                    "platform":    "Cinéma",
                    "platformUrl": f"https://www.themoviedb.org/movie/{mid}",
                    "lang":        ["FR","EN"],
                    "tags":        [],
                    "categories":  map_tmdb_genre_ids(m.get("genre_ids",[])),
                    "cast":        [],
                    "desc":        m.get("overview",""),
                    "note":        f"{score:.1f}" if score > 0 else None,
                    "trailers":    trailers,
                    "poster":      img(m.get("poster_path")),
                    "backdrop":    img(m.get("backdrop_path"),"w780"),
                    "source":      "tmdb-film",
                    "isManual":    False,
                })

    log(f"  → {len(events)} films")
    return events

# ── TMDB SERIES ───────────────────────────────────────────────────────────────
def fetch_series_tmdb():
    if not TMDB_KEY: return []
    log("TMDb séries populaires...")
    events, seen = [], set()

    for endpoint in ["popular","top_rated","on_the_air","airing_today"]:
        for page in range(1, 8):
            data = safe_get(f"{TMDB_BASE}/tv/{endpoint}", {
                "api_key":TMDB_KEY,"language":"fr-FR","page":page
            })
            if not data: break
            for s in data.get("results",[]):
                sid = s.get("id")
                if sid in seen: continue
                first_air = s.get("first_air_date","")
                if not first_air or not in_window(first_air): continue
                score = s.get("vote_average",0)
                if score < 5.0 and s.get("vote_count",0) < 100: continue
                seen.add(sid)

                # Détail pour avoir les vrais networks
                detail = safe_get(f"{TMDB_BASE}/tv/{sid}",
                                  {"api_key":TMDB_KEY,"language":"fr-FR"})
                networks = (detail or {}).get("networks", [])
                plat = tmdb_platform_from_networks(networks)
                trailers = get_trailers(sid, "tv")
                cats = map_tmdb_genre_ids(s.get("genre_ids",[]))

                events.append({
                    "id":          uid("tmdb-serie", sid),
                    "date":        first_air,
                    "title":       s.get("name",""),
                    "saison":      "Saison 1",
                    "status":      "sorti" if first_air <= TODAY_STR else "a-venir",
                    "type":        "serie",
                    "platform":    plat,
                    "platformUrl": PLATFORM_URLS.get(plat,"#"),
                    "lang":        ["FR","EN"],
                    "tags":        [],
                    "categories":  cats,
                    "cast":        [],
                    "desc":        s.get("overview",""),
                    "note":        f"{score:.1f}" if score > 0 else None,
                    "trailers":    trailers,
                    "poster":      img(s.get("poster_path")),
                    "backdrop":    img(s.get("backdrop_path"),"w780"),
                    "source":      "tmdb-serie",
                    "isManual":    False,
                })

    log(f"  → {len(events)} séries TMDb")
    return events

# ── RSS RADIO-CANADA ──────────────────────────────────────────────────────────
def fetch_rss():
    log("Radio-Canada RSS...")
    kw = ["série","saison","tou.tv","télé-québec","illico","crave","émission","diffusion","première"]
    items = []
    try:
        r = requests.get(RC_RSS, timeout=10)
        root = ET.fromstring(r.content)
        for item in (root.find("channel") or []):
            if item.tag != "item": continue
            t = (item.findtext("title") or "").lower()
            d = (item.findtext("description") or "").lower()
            if any(k in t+d for k in kw):
                items.append({
                    "title": item.findtext("title") or "",
                    "link":  item.findtext("link") or "",
                    "date":  (item.findtext("pubDate") or "")[:16],
                })
        log(f"  → {len(items)} annonces RC")
    except Exception as e:
        log(f"  ⚠ {e}")
    return items

# ── CHARGEMENT ────────────────────────────────────────────────────────────────
def load_existing():
    if DATA_PATH.exists():
        with open(DATA_PATH,"r",encoding="utf-8") as f:
            return {e["id"]:e for e in json.load(f).get("events",[])}
    return {}

def load_qc():
    if QC_PATH.exists():
        with open(QC_PATH,"r",encoding="utf-8") as f:
            return json.load(f)
    return []

# ── FUSION ────────────────────────────────────────────────────────────────────
def merge(existing, new_events, qc_manual):
    merged = {}

    # Garde les entrées manuelles existantes
    for eid, e in existing.items():
        if e.get("isManual"): merged[eid] = e

    # Entrées QC manuelles du fichier data-qc.json
    for e in qc_manual:
        eid = e.get("id", uid("qc", e.get("title","")))
        e["id"] = eid
        e["isManual"] = True
        if not e.get("status"):
            e["status"] = "sorti" if e.get("date","") <= TODAY_STR else "a-venir"
        merged[eid] = e

    # Nouvelles entrées automatiques — déduplication par titre + mois
    seen_keys = {(e.get("title","").lower(), e.get("date","")[:7]) for e in merged.values()}

    for e in new_events:
        key = (e.get("title","").lower(), e.get("date","")[:7])
        if key in seen_keys: continue
        seen_keys.add(key)
        merged[e["id"]] = e

    return list(merged.values())

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n🎬 Mise a jour calendrier — {TODAY.strftime('%Y-%m-%d %H:%M')}")
    print(f"   Cle TMDb : {'OK' if TMDB_KEY else 'MANQUANTE'}")
    print(f"   Fenetres : {HISTORY_DAYS}j passes + {FUTURE_DAYS}j futurs\n")

    existing = load_existing()
    qc_manual = load_qc()
    log(f"Existant : {len(existing)} | QC manuel : {len(qc_manual)}")

    all_new = []
    print("\n Canada...")
    all_new.extend(fetch_canada())

    print("\n US/International...")
    all_new.extend(fetch_us_popular())

    print("\n Films TMDb...")
    all_new.extend(fetch_films())

    print("\n Series TMDb...")
    all_new.extend(fetch_series_tmdb())

    print("\n RSS Radio-Canada...")
    rc = fetch_rss()

    print("\n Fusion...")
    final = merge(existing, all_new, qc_manual)
    final = [e for e in final if in_window(e.get("date",""))]
    final.sort(key=lambda e: e.get("date","9999"))

    output = {
        "version":          "2.0",
        "generated_at":     TODAY.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total":            len(final),
        "rc_announcements": rc[:10],
        "events":           final,
    }

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_PATH,"w",encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    sorti  = sum(1 for e in final if e.get("status")=="sorti")
    avenir = sum(1 for e in final if e.get("status")=="a-venir")
    manuel = sum(1 for e in final if e.get("isManual"))

    print(f"\n Termine ! {len(final)} evenements sauvegardes dans {DATA_PATH}")
    print(f"   Disponibles : {sorti}")
    print(f"   A venir     : {avenir}")
    print(f"   QC manuels  : {manuel}\n")

if __name__ == "__main__":
    main()
