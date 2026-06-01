#!/usr/bin/env python3
"""
Calendrier Films & Series — Script de mise a jour complet v3
Sources : TVmaze (CA + US), TMDb (films + series), RSS Radio-Canada
"""

import json, os, re, requests, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

TMDB_KEY     = os.environ.get("TMDB_API_KEY", "")
TMDB_BASE    = "https://api.themoviedb.org/3"
TMDB_IMG     = "https://image.tmdb.org/t/p"
TVMAZE_BASE  = "https://api.tvmaze.com"
RC_RSS       = "https://ici.radio-canada.ca/rss/4159"
DATA_PATH    = Path("data.json")
QC_PATH      = Path("data-qc.json")
TODAY        = datetime.now()
TODAY_STR    = TODAY.strftime("%Y-%m-%d")
HISTORY_DAYS = 548
FUTURE_DAYS  = 180

# ── PLATEFORMES ───────────────────────────────────────────────────────────────
PLATFORM_URLS = {
    "Netflix":      "https://www.netflix.com",
    "Prime Video":  "https://www.primevideo.com",
    "Disney+":      "https://www.disneyplus.com",
    "Apple TV+":    "https://tv.apple.com",
    "Crave":        "https://www.crave.ca",
    "ICI TOU.TV":   "https://ici.tou.tv",
    "Tele-Quebec":  "https://www.telequebec.tv",
    "TVA+":         "https://www.tvaplus.ca",
    "Club Illico":  "https://www.illico.com",
    "Cinema":       "https://www.themoviedb.org",
    "AMC":          "https://www.amc.com",
    "CBS":          "https://www.cbs.com",
    "ABC":          "https://abc.com",
    "NBC":          "https://www.nbc.com",
    "Fox":          "https://www.fox.com",
    "Peacock":      "https://www.peacocktv.com",
    "Paramount+":   "https://www.paramountplus.com",
    "Hulu":         "https://www.hulu.com",
    "Showtime":     "https://www.showtime.com",
    "Starz":        "https://www.starz.com",
    "FX":           "https://www.fxnetworks.com",
    "BBC":          "https://www.bbc.co.uk",
    "HBO":          "https://www.hbo.com",
    "Noovo":        "https://www.noovo.ca",
    "TVA":          "https://www.tva.ca",
}

# Reseau TVmaze/TMDb -> plateforme
NETWORK_TO_PLATFORM = {
    # Quebec / Canada
    "ICI Radio-Canada Tele": "ICI TOU.TV",
    "ICI TOU.TV":            "ICI TOU.TV",
    "Radio-Canada":          "ICI TOU.TV",
    "ARTV":                  "ICI TOU.TV",
    "Tele-Quebec":           "Tele-Quebec",
    "TVA":                   "TVA+",
    "Noovo":                 "Noovo",
    "Club Illico":           "Club Illico",
    "Super Ecran":           "Club Illico",
    "Series+":               "Club Illico",
    "Canal Vie":             "Club Illico",
    "Historia":              "Club Illico",
    "Savoir Media":          "Tele-Quebec",
    "CTV":                   "Crave",
    "CBC":                   "ICI TOU.TV",
    "Global":                "Crave",
    "CTV Drama Channel":     "Crave",
    "CTV Sci-Fi Channel":    "Crave",
    "W Network":             "Crave",
    "Showcase":              "Crave",
    "Slice":                 "Club Illico",
    "Crave":                 "Crave",
    # USA / International
    "Netflix":               "Netflix",
    "HBO":                   "Crave",
    "Max":                   "Crave",
    "HBO Max":               "Crave",
    "Amazon":                "Prime Video",
    "Prime Video":           "Prime Video",
    "Apple TV+":             "Apple TV+",
    "Disney+":               "Disney+",
    "Hulu":                  "Hulu",
    "Peacock":               "Peacock",
    "Paramount+":            "Paramount+",
    "AMC":                   "AMC",
    "FX":                    "FX",
    "Showtime":              "Showtime",
    "Starz":                 "Starz",
    "Syfy":                  "NBC",
    "USA Network":           "NBC",
    "TNT":                   "AMC",
    "TBS":                   "AMC",
    "Adult Swim":            "AMC",
    "Comedy Central":        "Paramount+",
    "Bravo":                 "Peacock",
    "NBC":                   "NBC",
    "ABC":                   "ABC",
    "CBS":                   "CBS",
    "Fox":                   "Fox",
    "BBC One":               "BBC",
    "BBC Two":               "BBC",
    "BBC Three":             "BBC",
    "ITV":                   "BBC",
    "Channel 4":             "BBC",
}

# Reseaux quebecois pour le tag QC
QC_NETWORKS = {
    "ICI Radio-Canada Tele","ICI TOU.TV","Radio-Canada","Tele-Quebec",
    "TVA","Noovo","Club Illico","Crave","Super Ecran","Series+",
    "Canal Vie","Historia","Savoir Media","ARTV","CTV","CBC","Global",
    "CTV Drama Channel","CTV Sci-Fi Channel","W Network","Showcase","Slice",
}

# Pays -> tag pays
COUNTRY_TAGS = {
    "CA": "CA", "FR": "FR", "GB": "UK", "AU": "AU",
    "DE": "EU", "ES": "EU", "IT": "EU", "JP": "JP",
    "KR": "KR", "US": "USA",
}

# TMDb network_id -> plateforme
TMDB_NETWORK_MAP = {
    213: "Netflix",    49: "Crave",      2739: "Disney+",
    1024: "Prime Video", 2552: "Apple TV+", 453: "Hulu",
    4330: "Peacock",   4353: "Paramount+", 174: "AMC",
    88: "AMC",         19: "Fox",          2: "ABC",
    6: "NBC",          16: "CBS",          67: "Showtime",
    318: "Starz",      73: "BBC",          332: "BBC",
    56: "Crave",       1556: "Crave",      3353: "Disney+",
    2: "ABC",          359: "Hulu",        1436: "Apple TV+",
}

# Mots-cles LGBT pour auto-tagging
LGBT_KEYWORDS = [
    "gay","lesbian","bisexual","transgender","queer","lgbt","lgbtq",
    "same-sex","homosexual","coming out","pride","drag","non-binary",
    "genderqueer","intersex","asexual","same sex","gay couple",
    "lesbian couple","gay marriage","trans","gender identity",
    "gaie","lesbienne","homosexuel","transgenre","fierté",
    "identité de genre","diversité sexuelle",
]

# ── GENRES ────────────────────────────────────────────────────────────────────
TVMAZE_GENRE_MAP = {
    "Drama":"Drame","Comedy":"Comedie","Thriller":"Thriller",
    "Action":"Action","Adventure":"Action","Horror":"Horreur",
    "Science-Fiction":"SF","Fantasy":"Fantasy","Crime":"Crime",
    "Mystery":"Policier","Documentary":"Documentaire","Romance":"Romance",
    "Animation":"Animation","Family":"Jeunesse","Children":"Jeunesse",
    "Reality":"Telerealite","Music":"Musique","History":"Drame",
    "War":"Action","Western":"Action","Espionage":"Thriller",
    "Legal":"Drame","Medical":"Drame","Sports":"Documentaire",
    "Supernatural":"Horreur","Nature":"Documentaire","Food":"Documentaire",
    "Travel":"Documentaire","DIY":"Telerealite","Game Show":"Telerealite",
    "Talk Show":"Divertissement","Anime":"Animation",
}

TMDB_GENRE_IDS = {
    28:"Action",12:"Action",16:"Animation",35:"Comedie",80:"Crime",
    99:"Documentaire",18:"Drame",10751:"Jeunesse",14:"Fantasy",
    36:"Drame",27:"Horreur",10402:"Musique",9648:"Policier",
    10749:"Romance",878:"SF",10770:"Drame",53:"Thriller",
    10752:"Action",37:"Action",10759:"Action",10762:"Jeunesse",
    10763:"Documentaire",10764:"Telerealite",10765:"SF",
    10766:"Drame",10767:"Divertissement",10768:"Action",
}

def map_tvmaze_genres(gl):
    return list(dict.fromkeys([TVMAZE_GENRE_MAP[g] for g in gl if g in TVMAZE_GENRE_MAP])) or ["Drame"]

def map_tmdb_genre_ids(ids):
    return list(dict.fromkeys([TMDB_GENRE_IDS[i] for i in ids if i in TMDB_GENRE_IDS])) or ["Film"]

# ── HELPERS ───────────────────────────────────────────────────────────────────
def log(msg): print(f"  {msg}", flush=True)

def safe_get(url, params=None, timeout=15):
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"Erreur {url[:50]}... : {e}")
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

def detect_lgbt(text, keywords_list=None):
    """Detecte si le contenu est LGBT+ base sur la description."""
    if not text: return False
    text_lower = text.lower()
    return any(kw in text_lower for kw in LGBT_KEYWORDS)

def format_episode_label(season, episode_count=None, episode_num=None, is_premiere=False, is_finale=False):
    """
    Formate le label de saison/episode:
    - S01E01 pour un episode
    - Saison 1 — 8 episodes pour une saison complete
    - Saison 2 pour une nouvelle saison
    """
    if episode_num:
        return f"S{str(season).zfill(2)}E{str(episode_num).zfill(2)}"
    elif episode_count:
        return f"Saison {season} — {episode_count} episodes"
    else:
        return f"Saison {season}"

def get_episode_status(season, episode_num, total_episodes, is_web_release=False):
    """
    Determine le statut de l'episode pour le codage couleur:
    - premiere: vert (1er episode ou 3 premiers)
    - finale: rouge (dernier ou 3 derniers)
    - milieu: normal
    """
    if not total_episodes or not episode_num:
        return "normal"
    if episode_num <= 3:
        return "premiere"
    if episode_num >= total_episodes - 2:
        return "finale"
    return "normal"

def get_trailers(tmdb_id, media="tv"):
    trailers = []
    if not TMDB_KEY: return trailers
    for lang in ["fr-FR", "en-US"]:
        vd = safe_get(f"{TMDB_BASE}/{media}/{tmdb_id}/videos",
                      {"api_key": TMDB_KEY, "language": lang})
        if vd:
            for v in vd.get("results", []):
                if v.get("site") == "YouTube" and v.get("type") in ("Trailer", "Teaser"):
                    trailers.append({
                        "lang":  "VF" if lang == "fr-FR" else "VO",
                        "label": v.get("name", "Bande-annonce"),
                        "url":   f"https://www.youtube.com/watch?v={v['key']}"
                    })
        if trailers: break
    return trailers[:4]

def get_cast(tmdb_id, media="tv"):
    """Recupere les acteurs principaux depuis TMDb."""
    if not TMDB_KEY: return []
    data = safe_get(f"{TMDB_BASE}/{media}/{tmdb_id}/credits",
                    {"api_key": TMDB_KEY, "language": "fr-FR"})
    if not data: return []
    cast = data.get("cast", [])
    return [c["name"] for c in cast[:6] if c.get("name")]

def tmdb_platform_from_networks(networks):
    for n in networks:
        nid = n.get("id")
        name = n.get("name", "")
        if nid in TMDB_NETWORK_MAP:
            return TMDB_NETWORK_MAP[nid]
        for key, plat in NETWORK_TO_PLATFORM.items():
            if key.lower() in name.lower():
                return plat
    return "Netflix"

def tvmaze_platform(show):
    for src in [show.get("webChannel"), show.get("network")]:
        if not src: continue
        name = src.get("name", "")
        if name in NETWORK_TO_PLATFORM:
            return NETWORK_TO_PLATFORM[name], name in QC_NETWORKS
        for key, plat in NETWORK_TO_PLATFORM.items():
            if key.lower() in name.lower():
                return plat, key in QC_NETWORKS
    return None, False

def get_country_tag(show_data):
    """Determine le pays d'origine."""
    # TVmaze
    network = show_data.get("network") or show_data.get("webChannel") or {}
    country_code = (network.get("country") or {}).get("code", "")
    if country_code:
        return COUNTRY_TAGS.get(country_code, country_code)
    # TMDb
    countries = show_data.get("origin_country", [])
    if countries:
        return COUNTRY_TAGS.get(countries[0], countries[0])
    return "USA"

def tmdb_enrich(title, media="tv", tmdb_id=None):
    if not TMDB_KEY: return {}
    result_id = tmdb_id
    if not result_id:
        ep = f"{TMDB_BASE}/search/{'tv' if media=='tv' else 'movie'}"
        for lang in ["fr-FR", "en-US"]:
            data = safe_get(ep, {"api_key": TMDB_KEY, "query": title, "language": lang})
            if data and data.get("results"):
                r = data["results"][0]
                result_id = r.get("id")
                break
    if not result_id: return {}

    # Detail
    detail = safe_get(f"{TMDB_BASE}/{'tv' if media=='tv' else 'movie'}/{result_id}",
                      {"api_key": TMDB_KEY, "language": "fr-FR"}) or {}
    score = detail.get("vote_average")
    desc = detail.get("overview") or ""
    # Desc anglaise si vide
    if not desc:
        detail_en = safe_get(f"{TMDB_BASE}/{'tv' if media=='tv' else 'movie'}/{result_id}",
                             {"api_key": TMDB_KEY, "language": "en-US"}) or {}
        desc = detail_en.get("overview") or ""

    trailers = get_trailers(result_id, media)
    cast = get_cast(result_id, media)
    networks = detail.get("networks", [])
    episode_count = detail.get("number_of_episodes")
    season_count = detail.get("number_of_seasons")
    total_eps_per_season = None
    if detail.get("seasons"):
        seasons = detail["seasons"]
        if seasons:
            last_season = seasons[-1]
            total_eps_per_season = last_season.get("episode_count")

    is_lgbt = detect_lgbt(desc)

    return {
        "tmdb_id":          result_id,
        "note":             f"{score:.1f}" if score and score > 0 else None,
        "poster":           img(detail.get("poster_path")),
        "backdrop":         img(detail.get("backdrop_path"), "w780"),
        "desc":             desc,
        "trailers":         trailers,
        "cast":             cast,
        "networks":         networks,
        "episode_count":    episode_count,
        "season_count":     season_count,
        "total_eps_season": total_eps_per_season,
        "is_lgbt":          is_lgbt,
    }

# ── TVMAZE CANADA ─────────────────────────────────────────────────────────────
def fetch_canada():
    log("TVmaze Canada — historique 18 mois + 6 mois futur...")
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

            rating = (show.get("rating") or {}).get("average")
            country_tag = get_country_tag(show)
            tags = []
            if is_qc: tags.append("QC")
            tags.append(country_tag if country_tag else "CA")

            desc = clean_html(show.get("summary", ""))
            is_lgbt = detect_lgbt(desc)
            if is_lgbt: tags.append("LGBT")

            lang_list = ["FR"] if is_qc and any(
                x in (show.get("network") or show.get("webChannel") or {}).get("name", "")
                for x in ["Radio-Canada", "Tele", "TVA", "Noovo", "Club", "ARTV", "ICI"]
            ) else ["FR", "EN"]

            season_num = ep.get("season", 1)
            ep_num = ep.get("number")
            ep_label = f"S{str(season_num).zfill(2)}E{str(ep_num).zfill(2)}" if ep_num else f"Saison {season_num}"

            entry = {
                "id":           uid("ca", sid),
                "date":         air,
                "title":        show.get("name", ""),
                "saison":       ep_label,
                "saison_num":   season_num,
                "ep_num":       ep_num,
                "ep_status":    "premiere" if ep_num and ep_num <= 3 else "normal",
                "status":       "sorti" if air <= TODAY_STR else "a-venir",
                "type":         "serie",
                "platform":     plat,
                "platformUrl":  PLATFORM_URLS.get(plat, "#"),
                "lang":         lang_list,
                "country":      country_tag,
                "tags":         tags,
                "categories":   map_tvmaze_genres(show.get("genres", [])),
                "cast":         [],
                "desc":         desc,
                "note":         f"{rating:.1f}" if rating else None,
                "trailers":     [],
                "poster":       (show.get("image") or {}).get("medium"),
                "backdrop":     (show.get("image") or {}).get("original"),
                "source":       "tvmaze-ca",
                "isManual":     False,
            }
            if TMDB_KEY:
                e = tmdb_enrich(show.get("name", ""), "tv")
                for k in ("note","trailers","desc","poster","backdrop","cast"):
                    if e.get(k): entry[k] = e[k]
                if e.get("is_lgbt") and "LGBT" not in entry["tags"]:
                    entry["tags"].append("LGBT")
                if e.get("total_eps_season"):
                    entry["saison"] = f"S{str(season_num).zfill(2)}E{str(ep_num).zfill(2)}" if ep_num else f"Saison {season_num} — {e['total_eps_season']} ep."
            events.append(entry)

    log(f"  -> {len(events)} series canadiennes/quebecoises")
    return events

# ── TVMAZE US POPULAIRE ───────────────────────────────────────────────────────
def fetch_us_popular():
    log("TVmaze US — series populaires...")
    events, seen = [], set()

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
            premiered = show.get("premiered", "")
            if not premiered or not in_window(premiered): continue
            seen.add(sid)
            entry = _make_show_entry(show, premiered, plat, "tvmaze-top", 1)
            if TMDB_KEY:
                e = tmdb_enrich(show.get("name", ""), "tv")
                for k in ("note","trailers","desc","poster","backdrop","cast"):
                    if e.get(k): entry[k] = e[k]
                if e.get("is_lgbt") and "LGBT" not in entry["tags"]:
                    entry["tags"].append("LGBT")
            events.append(entry)

    for offset in range(-210, FUTURE_DAYS, 14):
        d = (TODAY + timedelta(days=offset)).strftime("%Y-%m-%d")
        eps = safe_get(f"{TVMAZE_BASE}/schedule?country=US&date={d}") or []
        for ep in eps:
            show = ep.get("_embedded", {}).get("show") or ep.get("show") or {}
            sid = show.get("id")
            if not sid or sid in seen: continue
            rating = (show.get("rating") or {}).get("average") or 0
            weight = show.get("weight", 0)
            if rating < 6.5 and weight < 75: continue
            plat, _ = tvmaze_platform(show)
            if not plat: continue
            air = ep.get("airdate", "")
            if not in_window(air): continue
            seen.add(sid)
            entry = _make_show_entry(show, air, plat, "tvmaze-us", ep.get("season", 1), ep.get("number"))
            if TMDB_KEY:
                e = tmdb_enrich(show.get("name", ""), "tv")
                for k in ("note","trailers","desc","poster","backdrop","cast"):
                    if e.get(k): entry[k] = e[k]
                if e.get("is_lgbt") and "LGBT" not in entry["tags"]:
                    entry["tags"].append("LGBT")
            events.append(entry)

    log(f"  -> {len(events)} series US/internationales")
    return events

def _make_show_entry(show, date, plat, source, season_num=1, ep_num=None):
    rating = (show.get("rating") or {}).get("average")
    desc = clean_html(show.get("summary", ""))
    is_lgbt = detect_lgbt(desc)
    country_tag = get_country_tag(show)
    tags = [country_tag] if country_tag else ["USA"]
    if is_lgbt: tags.append("LGBT")
    ep_label = f"S{str(season_num).zfill(2)}E{str(ep_num).zfill(2)}" if ep_num else f"Saison {season_num}"
    return {
        "id":           uid(source, show.get("id", "")),
        "date":         date,
        "title":        show.get("name", ""),
        "saison":       ep_label,
        "saison_num":   season_num,
        "ep_num":       ep_num,
        "ep_status":    "premiere" if ep_num and ep_num <= 3 else "normal",
        "status":       "sorti" if date <= TODAY_STR else "a-venir",
        "type":         "serie",
        "platform":     plat,
        "platformUrl":  PLATFORM_URLS.get(plat, "#"),
        "lang":         ["FR", "EN"],
        "country":      country_tag,
        "tags":         tags,
        "categories":   map_tvmaze_genres(show.get("genres", [])),
        "cast":         [],
        "desc":         desc,
        "note":         f"{rating:.1f}" if rating else None,
        "trailers":     [],
        "poster":       (show.get("image") or {}).get("medium"),
        "backdrop":     (show.get("image") or {}).get("original"),
        "source":       source,
        "isManual":     False,
    }

# ── TMDB FILMS ────────────────────────────────────────────────────────────────
def fetch_films():
    if not TMDB_KEY: return []
    log("TMDb films...")
    events, seen = [], set()

    for endpoint in ["upcoming", "now_playing", "popular", "top_rated"]:
        for page in range(1, 8):
            data = safe_get(f"{TMDB_BASE}/movie/{endpoint}", {
                "api_key": TMDB_KEY, "language": "fr-FR", "page": page, "region": "CA"
            })
            if not data: break
            for m in data.get("results", []):
                mid = m.get("id")
                if mid in seen: continue
                release = m.get("release_date", "")
                if not release or not in_window(release): continue
                score = m.get("vote_average", 0)
                if score < 4.0 and m.get("vote_count", 0) < 50: continue
                seen.add(mid)

                trailers = get_trailers(mid, "movie")
                cast = get_cast(mid, "movie")
                desc = m.get("overview", "")
                is_lgbt = detect_lgbt(desc)
                tags = []
                if is_lgbt: tags.append("LGBT")
                # Pays d'origine
                origin = m.get("original_language", "en")
                if origin == "fr": tags.append("FR")

                events.append({
                    "id":          uid("film", mid),
                    "date":        release,
                    "title":       m.get("title", ""),
                    "saison":      "Film",
                    "saison_num":  0,
                    "ep_status":   "normal",
                    "status":      "sorti" if release <= TODAY_STR else "a-venir",
                    "type":        "film",
                    "platform":    "Cinema",
                    "platformUrl": f"https://www.themoviedb.org/movie/{mid}",
                    "lang":        ["FR", "EN"],
                    "country":     "USA",
                    "tags":        tags,
                    "categories":  map_tmdb_genre_ids(m.get("genre_ids", [])),
                    "cast":        cast,
                    "desc":        desc,
                    "note":        f"{score:.1f}" if score > 0 else None,
                    "trailers":    trailers,
                    "poster":      img(m.get("poster_path")),
                    "backdrop":    img(m.get("backdrop_path"), "w780"),
                    "source":      "tmdb-film",
                    "isManual":    False,
                })

    log(f"  -> {len(events)} films")
    return events

# ── TMDB SERIES ───────────────────────────────────────────────────────────────
def fetch_series_tmdb():
    if not TMDB_KEY: return []
    log("TMDb series populaires...")
    events, seen = [], set()

    for endpoint in ["popular", "top_rated", "on_the_air", "airing_today"]:
        for page in range(1, 8):
            data = safe_get(f"{TMDB_BASE}/tv/{endpoint}", {
                "api_key": TMDB_KEY, "language": "fr-FR", "page": page
            })
            if not data: break
            for s in data.get("results", []):
                sid = s.get("id")
                if sid in seen: continue
                first_air = s.get("first_air_date", "")
                if not first_air or not in_window(first_air): continue
                score = s.get("vote_average", 0)
                if score < 5.0 and s.get("vote_count", 0) < 100: continue
                seen.add(sid)

                enriched = tmdb_enrich(s.get("name", ""), "tv", sid)
                networks = enriched.get("networks", [])
                plat = tmdb_platform_from_networks(networks)
                desc = enriched.get("desc") or s.get("overview", "")
                is_lgbt = enriched.get("is_lgbt") or detect_lgbt(desc)
                total_eps = enriched.get("total_eps_season")
                ep_count_label = f" — {total_eps} ep." if total_eps else ""

                tags = []
                if is_lgbt: tags.append("LGBT")
                countries = s.get("origin_country", [])
                if countries:
                    tag = COUNTRY_TAGS.get(countries[0], countries[0])
                    tags.append(tag)
                else:
                    tags.append("USA")

                events.append({
                    "id":          uid("tmdb-serie", sid),
                    "date":        first_air,
                    "title":       s.get("name", ""),
                    "saison":      f"Saison 1{ep_count_label}",
                    "saison_num":  1,
                    "ep_status":   "premiere",
                    "status":      "sorti" if first_air <= TODAY_STR else "a-venir",
                    "type":        "serie",
                    "platform":    plat,
                    "platformUrl": PLATFORM_URLS.get(plat, "#"),
                    "lang":        ["FR", "EN"],
                    "country":     COUNTRY_TAGS.get((s.get("origin_country") or ["US"])[0], "USA"),
                    "tags":        tags,
                    "categories":  map_tmdb_genre_ids(s.get("genre_ids", [])),
                    "cast":        enriched.get("cast", []),
                    "desc":        desc,
                    "note":        enriched.get("note") or (f"{score:.1f}" if score > 0 else None),
                    "trailers":    enriched.get("trailers", []),
                    "poster":      enriched.get("poster") or img(s.get("poster_path")),
                    "backdrop":    enriched.get("backdrop") or img(s.get("backdrop_path"), "w780"),
                    "source":      "tmdb-serie",
                    "isManual":    False,
                })

    log(f"  -> {len(events)} series TMDb")
    return events

# ── RSS RADIO-CANADA ──────────────────────────────────────────────────────────
def fetch_rss():
    log("Radio-Canada RSS...")
    kw = ["serie","saison","tou.tv","tele-quebec","illico","crave","emission","diffusion","premiere"]
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
        log(f"  -> {len(items)} annonces RC")
    except Exception as e:
        log(f"  Erreur RSS: {e}")
    return items

# ── CHARGEMENT / FUSION ───────────────────────────────────────────────────────
def load_existing():
    if DATA_PATH.exists():
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return {e["id"]: e for e in json.load(f).get("events", [])}
    return {}

def load_qc():
    if QC_PATH.exists():
        with open(QC_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def merge(existing, new_events, qc_manual):
    merged = {}
    for eid, e in existing.items():
        if e.get("isManual"): merged[eid] = e

    for e in qc_manual:
        eid = e.get("id", uid("qc", e.get("title", "")))
        e["id"] = eid
        e["isManual"] = True
        if not e.get("status"):
            e["status"] = "sorti" if e.get("date", "") <= TODAY_STR else "a-venir"
        if not e.get("country"): e["country"] = "CA"
        if "QC" not in (e.get("tags") or []): e.setdefault("tags", []).append("QC")
        merged[eid] = e

    seen_keys = {(e.get("title","").lower(), e.get("date","")[:7]) for e in merged.values()}
    for e in new_events:
        key = (e.get("title","").lower(), e.get("date","")[:7])
        if key in seen_keys: continue
        seen_keys.add(key)
        merged[e["id"]] = e

    return list(merged.values())

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\nMise a jour calendrier — {TODAY.strftime('%Y-%m-%d %H:%M')}")
    print(f"Cle TMDb : {'OK' if TMDB_KEY else 'MANQUANTE'}\n")

    existing = load_existing()
    qc_manual = load_qc()
    log(f"Existant: {len(existing)} | QC manuel: {len(qc_manual)}")

    all_new = []
    print("\nCanada...")
    all_new.extend(fetch_canada())
    print("\nUS/International...")
    all_new.extend(fetch_us_popular())
    print("\nFilms TMDb...")
    all_new.extend(fetch_films())
    print("\nSeries TMDb...")
    all_new.extend(fetch_series_tmdb())
    print("\nRSS Radio-Canada...")
    rc = fetch_rss()

    print("\nFusion...")
    final = merge(existing, all_new, qc_manual)
    final = [e for e in final if in_window(e.get("date", ""))]
    final.sort(key=lambda e: e.get("date", "9999"))

    output = {
        "version":          "3.0",
        "generated_at":     TODAY.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total":            len(final),
        "rc_announcements": rc[:10],
        "events":           final,
    }

    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    sorti  = sum(1 for e in final if e.get("status") == "sorti")
    avenir = sum(1 for e in final if e.get("status") == "a-venir")
    lgbt   = sum(1 for e in final if "LGBT" in (e.get("tags") or []))
    qc     = sum(1 for e in final if "QC" in (e.get("tags") or []))

    print(f"\nTermine! {len(final)} evenements dans {DATA_PATH}")
    print(f"  Disponibles : {sorti}")
    print(f"  A venir     : {avenir}")
    print(f"  QC          : {qc}")
    print(f"  LGBT+       : {lgbt}\n")

if __name__ == "__main__":
    main()
