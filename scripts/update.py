#!/usr/bin/env python3
"""
Calendrier Films & Series - Script v5
- Cache TMDb local (skip si deja en base)
- Filtre: series avec version francaise uniquement
- Historique 3 mois | Futur 6 mois
- Sources: TVmaze, TMDb, Showbizz, RC Presse, Illico+
- Zero filtre de qualite
"""

import json, os, re, time, requests, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

TMDB_KEY    = os.environ.get("TMDB_API_KEY", "")
TMDB_BASE   = "https://api.themoviedb.org/3"
TMDB_IMG    = "https://image.tmdb.org/t/p"
TVMAZE_BASE = "https://api.tvmaze.com"
DATA_PATH   = Path("data.json")
TODAY       = datetime.now()
TODAY_STR   = TODAY.strftime("%Y-%m-%d")
HISTORY_DAYS = 90
FUTURE_DAYS  = 180

# ── CACHE TMDB LOCAL ──────────────────────────────────────────────────────────
# Charge les donnees existantes pour eviter les appels API redondants
TMDB_CACHE = {}

def load_tmdb_cache():
    """Charge le cache depuis data.json existant."""
    global TMDB_CACHE
    if not DATA_PATH.exists():
        return
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        for e in data.get("events", []):
            if e.get("poster") or e.get("desc") or e.get("cast"):
                key = e.get("title","").lower().strip()
                TMDB_CACHE[key] = {
                    "note":     e.get("note"),
                    "poster":   e.get("poster"),
                    "backdrop": e.get("backdrop"),
                    "desc":     e.get("desc"),
                    "trailers": e.get("trailers", []),
                    "cast":     e.get("cast", []),
                    "is_lgbt":  "LGBT" in (e.get("tags") or []),
                    "total_eps": None,
                }
        print(f"  Cache TMDb charge: {len(TMDB_CACHE)} titres existants")
    except Exception as e:
        print(f"  Erreur chargement cache: {e}")

# ── PLATEFORMES ───────────────────────────────────────────────────────────────
PLATFORM_URLS = {
    "Netflix":"https://www.netflix.com",
    "Prime Video":"https://www.primevideo.com",
    "Disney+":"https://www.disneyplus.com",
    "Apple TV+":"https://tv.apple.com",
    "Crave":"https://www.crave.ca",
    "ICI TOU.TV":"https://ici.tou.tv",
    "Tele-Quebec":"https://www.telequebec.tv",
    "TVA+":"https://www.tvaplus.ca",
    "Club Illico":"https://www.illico.com",
    "Noovo":"https://www.noovo.ca",
    "Cinema":"https://www.themoviedb.org",
    "AMC":"https://www.amc.com",
    "CBS":"https://www.cbs.com",
    "ABC":"https://abc.com",
    "NBC":"https://www.nbc.com",
    "Fox":"https://www.fox.com",
    "Peacock":"https://www.peacocktv.com",
    "Paramount+":"https://www.paramountplus.com",
    "Hulu":"https://www.hulu.com",
    "Showtime":"https://www.showtime.com",
    "Starz":"https://www.starz.com",
    "FX":"https://www.fxnetworks.com",
    "BBC":"https://www.bbc.co.uk",
    "HBO":"https://www.hbo.com",
    "Max":"https://www.max.com",
    "Adult Swim":"https://www.adultswim.com",
    "CTV":"https://www.ctv.ca",
    "CBC":"https://www.cbc.ca",
    "Global":"https://globaltv.com",
    "TVA":"https://www.tva.ca",
    "TV5":"https://www.tv5unis.ca",
    "Unis":"https://unis.ca",
    "ARTV":"https://ici.artv.ca",
    "ITV":"https://www.itv.com",
    "Channel 4":"https://www.channel4.com",
    "Sky":"https://www.sky.com",
    "Canal+":"https://www.canalplus.com",
    "Arte":"https://www.arte.tv",
    "Syfy":"https://www.syfy.com",
    "TNT":"https://www.tntdrama.com",
    "TBS":"https://www.tbs.com",
    "Comedy Central":"https://www.cc.com",
    "Bravo":"https://www.bravotv.com",
    "CW":"https://www.cwtv.com",
    "Freeform":"https://freeform.go.com",
    "Hallmark":"https://www.hallmarkchannel.com",
    "BET":"https://www.bet.com",
    "Autre":"#",
}

NETWORK_TO_PLATFORM = {
    "ICI Radio-Canada Tele":"ICI TOU.TV","ICI TOU.TV":"ICI TOU.TV",
    "Radio-Canada":"ICI TOU.TV","ARTV":"ICI TOU.TV","ICI ARTV":"ICI TOU.TV",
    "Tele-Quebec":"Tele-Quebec","Telequebec":"Tele-Quebec",
    "TVA":"TVA+","Noovo":"Noovo","Club Illico":"Club Illico",
    "Illico+":"Club Illico","Super Ecran":"Club Illico",
    "Series+":"Club Illico","Canal Vie":"Club Illico",
    "Historia":"Club Illico","Savoir Media":"Tele-Quebec",
    "CTV":"CTV","CBC":"CBC","Global":"Global",
    "CTV Drama Channel":"CTV","CTV Sci-Fi Channel":"CTV",
    "W Network":"CTV","Showcase":"CTV","Slice":"Club Illico",
    "Crave":"Crave","Z":"Club Illico","Prise 2":"Club Illico",
    "CASA":"Club Illico","Evasion":"Club Illico","Canal D":"Club Illico",
    "TV5":"TV5","Unis":"Unis","TV5 Quebec Canada":"TV5",
    "Netflix":"Netflix","HBO":"Crave","Max":"Max","HBO Max":"Crave",
    "Amazon":"Prime Video","Prime Video":"Prime Video",
    "Apple TV+":"Apple TV+","Disney+":"Disney+","Hulu":"Hulu",
    "Peacock":"Peacock","Paramount+":"Paramount+",
    "AMC":"AMC","FX":"FX","Showtime":"Showtime","Starz":"Starz",
    "Syfy":"Syfy","USA Network":"Syfy","TNT":"TNT","TBS":"TBS",
    "Adult Swim":"Adult Swim","Comedy Central":"Comedy Central",
    "Bravo":"Bravo","NBC":"NBC","ABC":"ABC","CBS":"CBS","Fox":"Fox",
    "CW":"CW","Freeform":"Freeform","Hallmark Channel":"Hallmark",
    "BET":"BET","BBC One":"BBC","BBC Two":"BBC","BBC Three":"BBC",
    "ITV":"ITV","Channel 4":"Channel 4","Sky":"Sky",
    "Canal+":"Canal+","Arte":"Arte","TF1":"Autre",
    "France 2":"Autre","France 3":"Autre","M6":"Autre",
}

QC_NETWORKS = {
    "ICI Radio-Canada Tele","ICI TOU.TV","Radio-Canada","ARTV","ICI ARTV",
    "Tele-Quebec","Telequebec","TVA","Noovo","Club Illico","Illico+",
    "Super Ecran","Series+","Canal Vie","Historia","Savoir Media",
    "CTV","CBC","Global","Crave","Z","Prise 2","CASA","Evasion",
    "Canal D","TV5","Unis","TV5 Quebec Canada",
}

# Reseaux qui diffusent en francais ou avec VF disponible au Quebec
FR_NETWORKS = {
    # QC/CA francais
    "ICI Radio-Canada Tele","ICI TOU.TV","Radio-Canada","ARTV",
    "Tele-Quebec","TVA","Noovo","Club Illico","Illico+",
    "Super Ecran","Series+","Canal Vie","Historia","Savoir Media",
    "TV5","Unis","TV5 Quebec Canada","Crave",
    # Plateformes qui offrent VF au Quebec
    "Netflix","HBO","Max","HBO Max","Amazon","Prime Video",
    "Apple TV+","Disney+","Hulu","Peacock","Paramount+",
    "CBC","CTV","Global",
    # France / Europe francophone
    "Canal+","Arte","TF1","France 2","France 3","M6",
    # Reseaux US majeurs avec VF disponible
    "AMC","FX","Showtime","Starz","NBC","ABC","CBS","Fox",
    "CW","Adult Swim","Comedy Central","Bravo","Syfy",
}

TMDB_NETWORK_MAP = {
    213:"Netflix",49:"Crave",2739:"Disney+",1024:"Prime Video",
    2552:"Apple TV+",453:"Hulu",4330:"Peacock",4353:"Paramount+",
    174:"AMC",88:"AMC",19:"Fox",2:"ABC",6:"NBC",16:"CBS",
    67:"Showtime",318:"Starz",73:"BBC",332:"BBC",
    56:"Crave",1556:"Crave",3353:"Disney+",359:"Hulu",
    1436:"Apple TV+",2087:"Max",3186:"Max",
    2552:"Apple TV+",4330:"Peacock",
}

# Pays dont les series ont generalement une VF disponible
FR_COUNTRIES = {"US","CA","GB","AU","FR","BE","CH","LU","MC"}

COUNTRY_TAGS = {
    "CA":"CA","FR":"FR","GB":"UK","AU":"AU","DE":"EU",
    "ES":"EU","IT":"EU","JP":"JP","KR":"KR","US":"USA",
    "BE":"EU","NL":"EU","SE":"EU","NO":"EU","DK":"EU",
}

LGBT_KEYWORDS = [
    "gay","lesbian","bisexual","transgender","queer","lgbt","lgbtq",
    "same-sex","homosexual","coming out","pride","drag queen","non-binary",
    "trans ","gender identity","gaie","lesbienne","homosexuel",
    "transgenre","fierté","diversité sexuelle","identité de genre",
]

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
    "Talk Show":"Divertissement","Anime":"Animation","Soap":"Drame",
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

def map_tv(gl):
    return list(dict.fromkeys([TVMAZE_GENRE_MAP[g] for g in gl if g in TVMAZE_GENRE_MAP])) or ["Drame"]

def map_tmdb(ids):
    return list(dict.fromkeys([TMDB_GENRE_IDS[i] for i in ids if i in TMDB_GENRE_IDS])) or ["Film"]

# ── HELPERS ───────────────────────────────────────────────────────────────────
def log(m): print(f"  {m}", flush=True)

def safe_get(url, params=None, timeout=20, retries=2):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout,
                           headers={"User-Agent":"CalendrierBot/5.0"})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i < retries-1: time.sleep(1)
            else: log(f"Erreur {url[:50]}: {e}")
    return None

def safe_html(url, timeout=20):
    try:
        r = requests.get(url, timeout=timeout, headers={
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0"
        })
        r.raise_for_status()
        return r.text
    except Exception as e:
        log(f"HTML erreur {url[:50]}: {e}")
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
    return f"{prefix}-{re.sub(r'[^a-z0-9]', '-', str(val).lower())[:60]}"

def clean(text):
    if not text: return ""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', text)).strip()[:800]

def is_lgbt(text):
    if not text: return False
    return any(k in text.lower() for k in LGBT_KEYWORDS)

def has_french(show):
    """Determine si une serie a une version francaise disponible."""
    network = show.get("network") or show.get("webChannel") or {}
    net_name = network.get("name","")
    country = (network.get("country") or {}).get("code","")
    
    # Reseau francophone ou diffuseur avec VF
    if net_name in FR_NETWORKS: return True
    if country in FR_COUNTRIES: return True
    
    # Langue originale francaise
    if show.get("language","").lower() in ("french","francais"): return True
    
    return False

def get_platform(show):
    for src in [show.get("webChannel"), show.get("network")]:
        if not src: continue
        name = src.get("name","")
        if name in NETWORK_TO_PLATFORM:
            return NETWORK_TO_PLATFORM[name], name in QC_NETWORKS
        for k,v in NETWORK_TO_PLATFORM.items():
            if k.lower() in name.lower():
                return v, k in QC_NETWORKS
    return "Autre", False

def get_country(show):
    for src in [show.get("network"), show.get("webChannel")]:
        if src:
            cc = (src.get("country") or {}).get("code","")
            if cc: return COUNTRY_TAGS.get(cc, cc)
    return "USA"

def get_trailers(tid, media="tv"):
    if not TMDB_KEY: return []
    trailers = []
    for lang in ["fr-FR","en-US"]:
        vd = safe_get(f"{TMDB_BASE}/{media}/{tid}/videos",
                     {"api_key":TMDB_KEY,"language":lang})
        if vd:
            for v in vd.get("results",[]):
                if v.get("site")=="YouTube" and v.get("type") in ("Trailer","Teaser"):
                    trailers.append({
                        "lang": "VF" if lang=="fr-FR" else "VO",
                        "label": v.get("name","Bande-annonce"),
                        "url": f"https://www.youtube.com/watch?v={v['key']}"
                    })
        if trailers: break
    return trailers[:4]

def get_cast(tid, media="tv"):
    if not TMDB_KEY: return []
    data = safe_get(f"{TMDB_BASE}/{media}/{tid}/credits",
                   {"api_key":TMDB_KEY,"language":"fr-FR"})
    if not data: return []
    return [c["name"] for c in data.get("cast",[])[:6] if c.get("name")]

def enrich_tmdb(title, media="tv", tmdb_id=None):
    """Enrichit depuis TMDb avec cache local."""
    cache_key = title.lower().strip()
    
    # SKIP si deja en cache
    if cache_key in TMDB_CACHE:
        return TMDB_CACHE[cache_key]
    
    if not TMDB_KEY: return {}
    
    rid = tmdb_id
    if not rid:
        ep = f"{TMDB_BASE}/search/{'tv' if media=='tv' else 'movie'}"
        for lang in ["fr-FR","en-US"]:
            d = safe_get(ep, {"api_key":TMDB_KEY,"query":title,"language":lang})
            if d and d.get("results"):
                rid = d["results"][0].get("id")
                break
    if not rid: return {}

    detail = safe_get(f"{TMDB_BASE}/{'tv' if media=='tv' else 'movie'}/{rid}",
                     {"api_key":TMDB_KEY,"language":"fr-FR"}) or {}
    
    desc = detail.get("overview","")
    if not desc:
        d_en = safe_get(f"{TMDB_BASE}/{'tv' if media=='tv' else 'movie'}/{rid}",
                       {"api_key":TMDB_KEY,"language":"en-US"}) or {}
        desc = d_en.get("overview","")

    score = detail.get("vote_average")
    networks = detail.get("networks",[])
    seasons = detail.get("seasons",[])
    total_eps = None
    if seasons:
        last = [s for s in seasons if s.get("season_number",0)>0]
        if last: total_eps = last[-1].get("episode_count")

    result = {
        "tmdb_id":  rid,
        "note":     f"{score:.1f}" if score and score>0 else None,
        "poster":   img(detail.get("poster_path")),
        "backdrop": img(detail.get("backdrop_path"),"w780"),
        "desc":     desc,
        "trailers": get_trailers(rid, media),
        "cast":     get_cast(rid, media),
        "networks": networks,
        "total_eps": total_eps,
        "is_lgbt":  is_lgbt(desc),
    }
    
    # Sauvegarde dans cache pour les prochains runs
    TMDB_CACHE[cache_key] = result
    return result

def tmdb_platform(networks):
    for n in networks:
        nid = n.get("id")
        name = n.get("name","")
        if nid in TMDB_NETWORK_MAP:
            return TMDB_NETWORK_MAP[nid]
        for k,v in NETWORK_TO_PLATFORM.items():
            if k.lower() in name.lower(): return v
    return "Netflix"

def make_ep_label(season, ep_num=None, total_eps=None):
    if ep_num:
        return f"S{str(season).zfill(2)}E{str(ep_num).zfill(2)}"
    elif total_eps:
        return f"Saison {season} — {total_eps} ep."
    return f"Saison {season}"

def ep_status(ep_num, total_eps):
    if not ep_num: return "normal"
    if ep_num <= 3: return "premiere"
    if total_eps and ep_num >= total_eps - 2: return "finale"
    return "normal"

def make_lang(show, is_qc):
    lang = show.get("language","").lower()
    if is_qc or lang in ("french","francais"):
        return ["FR"]
    return ["FR","EN"]

# ── TVMAZE CANADA ─────────────────────────────────────────────────────────────
def fetch_canada():
    log("TVmaze Canada — 3 mois...")
    events, seen = [], set()
    start = TODAY - timedelta(days=HISTORY_DAYS)

    for offset in range(0, HISTORY_DAYS + FUTURE_DAYS, 1):
        d = (start + timedelta(days=offset)).strftime("%Y-%m-%d")
        eps = safe_get(f"{TVMAZE_BASE}/schedule?country=CA&date={d}") or []
        for ep in eps:
            show = ep.get("_embedded",{}).get("show") or ep.get("show") or {}
            sid = show.get("id")
            if not sid or sid in seen: continue
            air = ep.get("airdate","")
            if not in_window(air): continue
            seen.add(sid)

            plat, is_qc = get_platform(show)
            country = get_country(show)
            tags = []
            if is_qc: tags.append("QC")
            tags.append(country)

            desc = clean(show.get("summary",""))
            if is_lgbt(desc): tags.append("LGBT")

            season_num = ep.get("season",1)
            ep_num = ep.get("number")
            rating = (show.get("rating") or {}).get("average")

            entry = {
                "id":         uid("ca",sid),
                "date":       air,
                "title":      show.get("name",""),
                "saison":     make_ep_label(season_num, ep_num),
                "saison_num": season_num,
                "ep_num":     ep_num,
                "ep_status":  ep_status(ep_num, None),
                "status":     "sorti" if air<=TODAY_STR else "a-venir",
                "type":       "serie",
                "platform":   plat,
                "platformUrl":PLATFORM_URLS.get(plat,"#"),
                "lang":       make_lang(show, is_qc),
                "country":    country,
                "tags":       tags,
                "categories": map_tv(show.get("genres",[])),
                "cast":       [],
                "desc":       desc,
                "note":       f"{rating:.1f}" if rating else None,
                "trailers":   [],
                "poster":     (show.get("image") or {}).get("medium"),
                "backdrop":   (show.get("image") or {}).get("original"),
                "source":     "tvmaze-ca",
                "isManual":   False,
            }
            if TMDB_KEY:
                e = enrich_tmdb(show.get("name",""), "tv")
                for k in ("note","trailers","desc","poster","backdrop","cast"):
                    if e.get(k): entry[k] = e[k]
                if e.get("is_lgbt") and "LGBT" not in entry["tags"]:
                    entry["tags"].append("LGBT")
                if e.get("total_eps"):
                    entry["saison"] = make_ep_label(season_num, ep_num, e["total_eps"])
                    entry["ep_status"] = ep_status(ep_num, e["total_eps"])
            events.append(entry)

    log(f"  -> {len(events)} series CA")
    return events

# ── TVMAZE MONDE (series avec VF) ─────────────────────────────────────────────
def fetch_world():
    log("TVmaze Monde — series avec version francaise...")
    events, seen = [], set()
    start = TODAY - timedelta(days=HISTORY_DAYS)

    # Pays avec VF disponible au Quebec
    for cc in ["US","GB","AU","FR","BE","CA"]:
        for offset in range(0, HISTORY_DAYS + FUTURE_DAYS, 1):
            d = (start + timedelta(days=offset)).strftime("%Y-%m-%d")
            eps = safe_get(f"{TVMAZE_BASE}/schedule?country={cc}&date={d}") or []
            for ep in eps:
                show = ep.get("_embedded",{}).get("show") or ep.get("show") or {}
                sid = show.get("id")
                if not sid or sid in seen: continue
                air = ep.get("airdate","")
                if not in_window(air): continue
                
                # Filtre: seulement series avec VF disponible
                if not has_french(show): continue
                
                seen.add(sid)
                plat, is_qc = get_platform(show)
                country = get_country(show)
                tags = [country] if country else ["USA"]
                if is_qc and "QC" not in tags: tags.insert(0,"QC")

                desc = clean(show.get("summary",""))
                if is_lgbt(desc): tags.append("LGBT")

                season_num = ep.get("season",1)
                ep_num = ep.get("number")
                rating = (show.get("rating") or {}).get("average")

                entry = {
                    "id":         uid("world",sid),
                    "date":       air,
                    "title":      show.get("name",""),
                    "saison":     make_ep_label(season_num, ep_num),
                    "saison_num": season_num,
                    "ep_num":     ep_num,
                    "ep_status":  ep_status(ep_num, None),
                    "status":     "sorti" if air<=TODAY_STR else "a-venir",
                    "type":       "serie",
                    "platform":   plat,
                    "platformUrl":PLATFORM_URLS.get(plat,"#"),
                    "lang":       ["FR","EN"],
                    "country":    country,
                    "tags":       tags,
                    "categories": map_tv(show.get("genres",[])),
                    "cast":       [],
                    "desc":       desc,
                    "note":       f"{rating:.1f}" if rating else None,
                    "trailers":   [],
                    "poster":     (show.get("image") or {}).get("medium"),
                    "backdrop":   (show.get("image") or {}).get("original"),
                    "source":     "tvmaze-world",
                    "isManual":   False,
                }
                if TMDB_KEY:
                    e = enrich_tmdb(show.get("name",""), "tv")
                    for k in ("note","trailers","desc","poster","backdrop","cast"):
                        if e.get(k): entry[k] = e[k]
                    if e.get("is_lgbt") and "LGBT" not in entry["tags"]:
                        entry["tags"].append("LGBT")
                    if e.get("total_eps"):
                        entry["saison"] = make_ep_label(season_num, ep_num, e["total_eps"])
                        entry["ep_status"] = ep_status(ep_num, e["total_eps"])
                events.append(entry)

    log(f"  -> {len(events)} series monde avec VF")
    return events

# ── SHOWBIZZ.NET ──────────────────────────────────────────────────────────────
def fetch_showbizz():
    log("Showbizz.net — calendriers QC...")
    events = []
    
    MONTHS_FR = {
        "janvier":1,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,
        "juillet":7,"aout":8,"septembre":9,"octobre":10,"novembre":11,"decembre":12,
        "février":2,"août":8,"décembre":12,"février":2,
    }

    PLAT_KEYWORDS = {
        "ici tou.tv":"ICI TOU.TV","tou.tv":"ICI TOU.TV","radio-canada":"ICI TOU.TV",
        "tele-quebec":"Tele-Quebec","telequebec":"Tele-Quebec",
        "tva":"TVA+","noovo":"Noovo","illico":"Club Illico",
        "crave":"Crave","club illico":"Club Illico",
        "canal vie":"Club Illico","historia":"Club Illico",
    }

    urls = [
        "https://showbizz.net/tele/rentree-tele-printemps-ete-2026-quand-commencent-vos-emissions",
        "https://showbizz.net/tele/rentree-tele-hiver-2026-quand-commencent-vos-emissions",
        "https://showbizz.net/series",
    ]

    for url in urls:
        html = safe_html(url)
        if not html: continue

        # Pattern principal: "Titre – Dès le DD mois" ou "Titre, saison X – Dès le DD mois"
        pattern = r'\*?([A-ZÀ-Ÿa-zà-ÿ][^–—\n\r]{3,70}?)\s*[–—]\s*[Dd]ès le\s+(\d{1,2})\s+(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)(?:\s+202[5-9])?'
        
        for m in re.finditer(pattern, html, re.IGNORECASE):
            try:
                title = clean(m.group(1)).strip("*").strip()
                if len(title) < 3 or len(title) > 80: continue
                # Ignorer les lignes de navigation
                if any(x in title.lower() for x in ["saisons","episodes","clique","voir","suivant","precedent"]): continue
                
                day = int(m.group(2))
                month_str = m.group(3).lower().replace("é","e").replace("û","u").replace("è","e").replace("ê","e")
                month_num = MONTHS_FR.get(month_str)
                if not month_num: continue
                
                year = 2026
                date_str = f"{year}-{str(month_num).zfill(2)}-{str(day).zfill(2)}"
                if not in_window(date_str): continue

                # Detecter la plateforme depuis le contexte
                pos = m.start()
                ctx = html[max(0,pos-500):pos+200].lower()
                plat = "ICI TOU.TV"
                for kw, p in PLAT_KEYWORDS.items():
                    if kw in ctx:
                        plat = p
                        break

                eid = uid("showbizz", title+date_str)
                # Enrichissement TMDb
                enriched = enrich_tmdb(title, "tv") if TMDB_KEY else {}
                
                events.append({
                    "id":         eid,
                    "date":       date_str,
                    "title":      title,
                    "saison":     "Saison 1",
                    "saison_num": 1,
                    "ep_num":     None,
                    "ep_status":  "premiere",
                    "status":     "sorti" if date_str<=TODAY_STR else "a-venir",
                    "type":       "serie",
                    "platform":   plat,
                    "platformUrl":PLATFORM_URLS.get(plat,"#"),
                    "lang":       ["FR"],
                    "country":    "CA",
                    "tags":       ["QC","CA"],
                    "categories": ["Drame"],
                    "cast":       enriched.get("cast",[]),
                    "desc":       enriched.get("desc",""),
                    "note":       enriched.get("note"),
                    "trailers":   enriched.get("trailers",[]),
                    "poster":     enriched.get("poster"),
                    "backdrop":   enriched.get("backdrop"),
                    "source":     "showbizz",
                    "isManual":   False,
                })
            except: continue

    log(f"  -> {len(events)} entrees Showbizz")
    return events

# ── CENTRE DE PRESSE RADIO-CANADA ─────────────────────────────────────────────
def fetch_rc_presse():
    log("Centre de presse Radio-Canada...")
    events = []
    
    MONTHS_FR = {
        "janvier":1,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,
        "juillet":7,"aout":8,"septembre":9,"octobre":10,"novembre":11,"decembre":12,
        "février":2,"août":8,"décembre":12,
    }

    pages = [
        "https://presse.radio-canada.ca/numerique/ici-tou-tv-extra",
        "https://presse.radio-canada.ca/numerique/ici-tou-tv",
        "https://presse.radio-canada.ca/television/ici-tele",
        "https://presse.radio-canada.ca/",
    ]

    for url in pages:
        html = safe_html(url)
        if not html: continue

        # Pattern: liens d'articles avec titres
        # Ex: "À voir en juin sur ICI TOU.TV - Plan B..."
        link_pat = r'href="(https://presse\.radio-canada\.ca/[^"]+)"[^>]*>\s*([^<]{10,120})</a>'
        
        for m in re.finditer(link_pat, html, re.IGNORECASE):
            art_url = m.group(1)
            art_title = clean(m.group(2))
            
            # Charger l'article pour extraire les details
            art_html = safe_html(art_url)
            if not art_html: continue

            # Chercher "Dès le DD mois" dans l'article
            date_pat = r'[Dd]ès le (\d{1,2})\s+(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)(?:\s+202[5-9])?'
            title_pat = r'<h[12][^>]*>([^<]{5,100})</h[12]>'
            
            # Extraire les titres de series mentionnes
            titles_found = re.findall(title_pat, art_html)
            
            for dm in re.finditer(date_pat, art_html, re.IGNORECASE):
                try:
                    day = int(dm.group(1))
                    month_str = dm.group(2).lower().replace("é","e").replace("û","u")
                    month_num = MONTHS_FR.get(month_str)
                    if not month_num: continue
                    
                    date_str = f"2026-{str(month_num).zfill(2)}-{str(day).zfill(2)}"
                    if not in_window(date_str): continue

                    # Titre = contexte avant la date
                    pos = dm.start()
                    ctx = clean(art_html[max(0,pos-300):pos])
                    # Chercher le dernier titre en gras ou important
                    bold = re.findall(r'<(?:strong|b|h[234])[^>]*>([^<]{3,80})</(?:strong|b|h[234])>', 
                                    art_html[max(0,pos-400):pos])
                    title = bold[-1] if bold else art_title
                    title = clean(title)
                    if len(title) < 3: continue

                    enriched = enrich_tmdb(title, "tv") if TMDB_KEY else {}
                    
                    events.append({
                        "id":         uid("rc", title+date_str),
                        "date":       date_str,
                        "title":      title,
                        "saison":     "Saison 1",
                        "saison_num": 1,
                        "ep_num":     None,
                        "ep_status":  "premiere",
                        "status":     "sorti" if date_str<=TODAY_STR else "a-venir",
                        "type":       "serie",
                        "platform":   "ICI TOU.TV",
                        "platformUrl":PLATFORM_URLS["ICI TOU.TV"],
                        "lang":       ["FR"],
                        "country":    "CA",
                        "tags":       ["QC","CA"],
                        "categories": ["Drame"],
                        "cast":       enriched.get("cast",[]),
                        "desc":       enriched.get("desc",""),
                        "note":       enriched.get("note"),
                        "trailers":   enriched.get("trailers",[]),
                        "poster":     enriched.get("poster"),
                        "backdrop":   enriched.get("backdrop"),
                        "source":     "rc-presse",
                        "isManual":   False,
                    })
                except: continue

    log(f"  -> {len(events)} entrees RC Presse")
    return events

# ── ILLICO+ ───────────────────────────────────────────────────────────────────
def fetch_illico():
    log("Illico+ bientot disponible...")
    events = []
    
    MONTHS_FR = {
        "janvier":1,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,
        "juillet":7,"aout":8,"septembre":9,"octobre":10,"novembre":11,"decembre":12,
        "février":2,"août":8,"décembre":12,
    }

    for url in [
        "https://www.illicoplus.ca/bientot-disponible",
        "https://www.illicoplus.ca/series/nouveautes",
        "https://www.illico.com/bientot-disponible",
    ]:
        html = safe_html(url)
        if not html: continue

        # Chercher titres et dates
        date_pat = r'(\d{1,2})\s+(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)(?:\s+202[5-9])?'
        title_pats = [
            r'"name"\s*:\s*"([^"]{3,80})"',
            r'<h[23][^>]*class="[^"]*title[^"]*"[^>]*>([^<]{3,80})</h[23]>',
            r'data-title="([^"]{3,80})"',
            r'alt="([^"]{3,80})"',
            r'"title"\s*:\s*"([^"]{3,80})"',
        ]

        for dm in re.finditer(date_pat, html, re.IGNORECASE):
            try:
                day = int(dm.group(1))
                month_str = dm.group(2).lower().replace("é","e").replace("û","u")
                month_num = MONTHS_FR.get(month_str)
                if not month_num: continue

                date_str = f"2026-{str(month_num).zfill(2)}-{str(day).zfill(2)}"
                if not in_window(date_str): continue

                pos = dm.start()
                ctx = html[max(0,pos-400):pos+100]
                title = None
                for tpat in title_pats:
                    tm = re.search(tpat, ctx, re.IGNORECASE)
                    if tm:
                        title = clean(tm.group(1))
                        if 3 < len(title) < 80: break
                
                if not title: continue
                if any(x in title.lower() for x in ["illico","crave","club","abonnement","connexion"]): continue

                enriched = enrich_tmdb(title, "tv") if TMDB_KEY else {}

                events.append({
                    "id":         uid("illico", title+date_str),
                    "date":       date_str,
                    "title":      title,
                    "saison":     "Saison 1",
                    "saison_num": 1,
                    "ep_num":     None,
                    "ep_status":  "premiere",
                    "status":     "sorti" if date_str<=TODAY_STR else "a-venir",
                    "type":       "serie",
                    "platform":   "Club Illico",
                    "platformUrl":PLATFORM_URLS["Club Illico"],
                    "lang":       ["FR"],
                    "country":    "CA",
                    "tags":       ["QC","CA"],
                    "categories": ["Drame"],
                    "cast":       enriched.get("cast",[]),
                    "desc":       enriched.get("desc",""),
                    "note":       enriched.get("note"),
                    "trailers":   enriched.get("trailers",[]),
                    "poster":     enriched.get("poster"),
                    "backdrop":   enriched.get("backdrop"),
                    "source":     "illico",
                    "isManual":   False,
                })
            except: continue

        if events: break

    log(f"  -> {len(events)} entrees Illico+")
    return events

# ── TMDB FILMS ────────────────────────────────────────────────────────────────
def fetch_films():
    if not TMDB_KEY: return []
    log("TMDb films — avec VF...")
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
                seen.add(mid)

                cache_key = m.get("title","").lower().strip()
                if cache_key in TMDB_CACHE:
                    cached = TMDB_CACHE[cache_key]
                    trailers = cached.get("trailers",[])
                    cast = cached.get("cast",[])
                    desc = cached.get("desc","") or m.get("overview","")
                    note = cached.get("note")
                    poster = cached.get("poster") or img(m.get("poster_path"))
                    backdrop = cached.get("backdrop") or img(m.get("backdrop_path"),"w780")
                else:
                    trailers = get_trailers(mid, "movie")
                    cast = get_cast(mid, "movie")
                    desc = m.get("overview","")
                    score = m.get("vote_average",0)
                    note = f"{score:.1f}" if score>0 else None
                    poster = img(m.get("poster_path"))
                    backdrop = img(m.get("backdrop_path"),"w780")

                tags = []
                if is_lgbt(desc): tags.append("LGBT")
                score = m.get("vote_average",0)

                events.append({
                    "id":         uid("film",mid),
                    "date":       release,
                    "title":      m.get("title",""),
                    "saison":     "Film",
                    "saison_num": 0,
                    "ep_num":     None,
                    "ep_status":  "normal",
                    "status":     "sorti" if release<=TODAY_STR else "a-venir",
                    "type":       "film",
                    "platform":   "Cinema",
                    "platformUrl":f"https://www.themoviedb.org/movie/{mid}",
                    "lang":       ["FR","EN"],
                    "country":    "USA",
                    "tags":       tags,
                    "categories": map_tmdb(m.get("genre_ids",[])),
                    "cast":       cast,
                    "desc":       desc,
                    "note":       note or (f"{score:.1f}" if score>0 else None),
                    "trailers":   trailers,
                    "poster":     poster,
                    "backdrop":   backdrop,
                    "source":     "tmdb-film",
                    "isManual":   False,
                })

    log(f"  -> {len(events)} films")
    return events

# ── TMDB SERIES ───────────────────────────────────────────────────────────────
def fetch_series_tmdb():
    if not TMDB_KEY: return []
    log("TMDb series...")
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
                
                # Seulement series des pays avec VF
                countries = s.get("origin_country",[])
                if countries and countries[0] not in FR_COUNTRIES: continue
                
                seen.add(sid)
                enriched = enrich_tmdb(s.get("name",""), "tv", sid)
                networks = enriched.get("networks",[])
                plat = tmdb_platform(networks)
                desc = enriched.get("desc") or s.get("overview","")
                score = s.get("vote_average",0)
                total_eps = enriched.get("total_eps")

                tags = []
                if enriched.get("is_lgbt") or is_lgbt(desc): tags.append("LGBT")
                if countries:
                    tag = COUNTRY_TAGS.get(countries[0], countries[0])
                    tags.append(tag)

                events.append({
                    "id":         uid("tmdb-serie",sid),
                    "date":       first_air,
                    "title":      s.get("name",""),
                    "saison":     f"Saison 1" + (f" — {total_eps} ep." if total_eps else ""),
                    "saison_num": 1,
                    "ep_num":     None,
                    "ep_status":  "premiere",
                    "status":     "sorti" if first_air<=TODAY_STR else "a-venir",
                    "type":       "serie",
                    "platform":   plat,
                    "platformUrl":PLATFORM_URLS.get(plat,"#"),
                    "lang":       ["FR","EN"],
                    "country":    COUNTRY_TAGS.get((countries or ["US"])[0],"USA"),
                    "tags":       tags,
                    "categories": map_tmdb(s.get("genre_ids",[])),
                    "cast":       enriched.get("cast",[]),
                    "desc":       desc,
                    "note":       enriched.get("note") or (f"{score:.1f}" if score>0 else None),
                    "trailers":   enriched.get("trailers",[]),
                    "poster":     enriched.get("poster") or img(s.get("poster_path")),
                    "backdrop":   enriched.get("backdrop") or img(s.get("backdrop_path"),"w780"),
                    "source":     "tmdb-serie",
                    "isManual":   False,
                })

    log(f"  -> {len(events)} series TMDb")
    return events

# ── FUSION ────────────────────────────────────────────────────────────────────
def merge(all_events):
    merged = {}
    seen_keys = {}
    
    for e in all_events:
        key = (e.get("title","").lower().strip(), e.get("date","")[:7])
        eid = e["id"]
        
        if key in seen_keys:
            # Enrichir l'entree existante
            existing = merged[seen_keys[key]]
            if not existing.get("poster") and e.get("poster"):
                existing["poster"] = e["poster"]
            if not existing.get("desc") and e.get("desc"):
                existing["desc"] = e["desc"]
            if not existing.get("trailers") and e.get("trailers"):
                existing["trailers"] = e["trailers"]
            if not existing.get("cast") and e.get("cast"):
                existing["cast"] = e["cast"]
            if not existing.get("note") and e.get("note"):
                existing["note"] = e["note"]
            for tag in (e.get("tags") or []):
                if tag not in existing.get("tags",[]):
                    existing.setdefault("tags",[]).append(tag)
        else:
            seen_keys[key] = eid
            merged[eid] = e

    return list(merged.values())

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\nMise a jour v5 — {TODAY.strftime('%Y-%m-%d %H:%M')}")
    print(f"Cle TMDb: {'OK' if TMDB_KEY else 'MANQUANTE'}")
    print(f"Fenetres: {HISTORY_DAYS}j ({(TODAY-timedelta(days=HISTORY_DAYS)).strftime('%Y-%m-%d')}) a {(TODAY+timedelta(days=FUTURE_DAYS)).strftime('%Y-%m-%d')}\n")

    # Charge le cache AVANT tout
    print("Chargement cache TMDb...")
    load_tmdb_cache()

    all_new = []

    print("\nTVmaze Canada...")
    all_new.extend(fetch_canada())

    print("\nTVmaze Monde (avec VF)...")
    all_new.extend(fetch_world())

    print("\nShowbizz QC...")
    all_new.extend(fetch_showbizz())

    print("\nRC Presse...")
    all_new.extend(fetch_rc_presse())

    print("\nIllico+...")
    all_new.extend(fetch_illico())

    print("\nFilms TMDb...")
    all_new.extend(fetch_films())

    print("\nSeries TMDb...")
    all_new.extend(fetch_series_tmdb())

    print("\nFusion et deduplication...")
    final = merge(all_new)
    final = [e for e in final if in_window(e.get("date",""))]
    final.sort(key=lambda e: e.get("date","9999"))

    output = {
        "version":      "5.0",
        "generated_at": TODAY.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total":        len(final),
        "events":       final,
    }

    with open(DATA_PATH,"w",encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    sorti  = sum(1 for e in final if e.get("status")=="sorti")
    avenir = sum(1 for e in final if e.get("status")=="a-venir")
    qc     = sum(1 for e in final if "QC" in (e.get("tags") or []))
    lgbt   = sum(1 for e in final if "LGBT" in (e.get("tags") or []))
    films  = sum(1 for e in final if e.get("type")=="film")
    series = sum(1 for e in final if e.get("type")=="serie")
    cached = sum(1 for e in final if e.get("title","").lower().strip() in TMDB_CACHE)

    print(f"\nTermine! {len(final)} evenements")
    print(f"  Series     : {series}")
    print(f"  Films      : {films}")
    print(f"  Disponibles: {sorti}")
    print(f"  A venir    : {avenir}")
    print(f"  QC         : {qc}")
    print(f"  LGBT+      : {lgbt}")
    print(f"  Depuis cache TMDb: {cached}\n")

if __name__ == "__main__":
    main()
