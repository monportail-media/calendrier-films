#!/usr/bin/env python3
"""
Calendrier Films & Series - Script v6
- Cache TMDb local (skip si deja en base)
- Seulement contenu avec version francaise
- Plateformes exclues: ABC AMC Adult Swim BBC BET Bravo CBC CBS CTV CW
  Channel 4 Comedy Central Fox Freeform Global ITV NBC Syfy TNT TBS
  Hallmark Lifetime MTV Sky Showtime Starz Paramount Network
- Plateformes acceptees: ICI TOU.TV TVA+ Noovo Tele-Quebec Crave Illico+
  Vrai Historia Series+ ONF CBC Gem Netflix Prime Video Disney+ Apple TV+
  Max Hulu Paramount+ Peacock TV5 ARTV Unis TV Explora
- Historique: 3 mois | Futur: 6 mois | Periode: 2026 seulement
- Etape 1: collecte rapide | Etape 2: enrichissement TMDb avec cache
"""

import json, os, re, time, requests, urllib3, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TMDB_KEY    = os.environ.get("TMDB_API_KEY", "")
TMDB_BASE   = "https://api.themoviedb.org/3"
TMDB_IMG    = "https://image.tmdb.org/t/p"
TVMAZE_BASE = "https://api.tvmaze.com"
DATA_PATH   = Path("data.json")
TODAY       = datetime.now()
TODAY_STR   = TODAY.strftime("%Y-%m-%d")
HISTORY_DAYS = 90
FUTURE_DAYS  = 180

# ── PLATEFORMES EXCLUES (anglais seulement) ───────────────────────────────────
EXCLUDED_PLATFORMS = {
    "ABC","AMC","Adult Swim","BBC","BBC One","BBC Two","BBC Three",
    "BET","Bravo","CBC","CBS","CTV","CTV Drama Channel","CTV Sci-Fi Channel",
    "CW","Channel 4","Comedy Central","Fox","Freeform","Global",
    "ITV","ITV2","NBC","Syfy","USA Network","TNT","TBS","Hallmark",
    "Hallmark Channel","Lifetime","MTV","VH1","E!","Sky","Sky One",
    "Showtime","Starz","Paramount Network","Channel 5","W Network",
    "Showcase","OWN","PBS","PBS Kids","Cartoon Network",
}

# ── PLATEFORMES ACCEPTEES ─────────────────────────────────────────────────────
ALLOWED_PLATFORMS = {
    # Quebec / Canada francais
    "ICI TOU.TV","TVA+","Noovo","Tele-Quebec","Crave","Club Illico",
    "Illico+","Vrai","Historia","Series+","ONF","CBC Gem","Viveo",
    "ARTV","Unis TV","TV5","TV5 Monde","Explora",
    # International avec contenu francais
    "Netflix","Prime Video","Disney+","Apple TV+","Max","Hulu",
    "Paramount+","Peacock",
    # Cinema
    "Cinema",
}

PLATFORM_LOGOS = {
    "Netflix":      "https://image.tmdb.org/t/p/original/wwemzKWzjKYJFfCeiB57q3r4Bcm.png",
    "Prime Video":  "https://image.tmdb.org/t/p/original/emthp39XA2YScoYL1p0sdbAH2WA.png",
    "Disney+":      "https://image.tmdb.org/t/p/original/7rwgEs15tFwyR9NPQ5vpzxTj19d.png",
    "Apple TV+":    "https://image.tmdb.org/t/p/original/6uhKBfmtzFqOcLousHwZuzcrScK.png",
    "Crave":        "https://upload.wikimedia.org/wikipedia/en/thumb/c/c0/Crave_logo.svg/200px-Crave_logo.svg.png",
    "ICI TOU.TV":   "https://upload.wikimedia.org/wikipedia/fr/thumb/6/61/ICI_TOU.TV_logo.svg/200px-ICI_TOU.TV_logo.svg.png",
    "Tele-Quebec":  "https://upload.wikimedia.org/wikipedia/fr/thumb/f/f7/T%C3%A9l%C3%A9-Qu%C3%A9bec_logo.svg/200px-T%C3%A9l%C3%A9-Qu%C3%A9bec_logo.svg.png",
    "TVA+":         "https://upload.wikimedia.org/wikipedia/fr/thumb/2/2a/TVA_logo_2013.svg/200px-TVA_logo_2013.svg.png",
    "Noovo":        "https://upload.wikimedia.org/wikipedia/fr/thumb/8/8d/Noovo_logo.svg/200px-Noovo_logo.svg.png",
    "Club Illico":  "https://upload.wikimedia.org/wikipedia/fr/thumb/b/b9/Club_illico_logo.svg/200px-Club_illico_logo.svg.png",
    "Max":          "https://image.tmdb.org/t/p/original/giwM8XX4V2AkroL84dMkQaAoDVj.png",
    "Hulu":         "https://image.tmdb.org/t/p/original/pqUTCleNUiTLAVlelGe6zxmSNST.png",
    "Paramount+":   "https://image.tmdb.org/t/p/original/h5DcR0J2EESLitnhR8xLG1QymTE.png",
    "Peacock":      "https://image.tmdb.org/t/p/original/xTHltMrZPAJFLQ6qyCBjAnXSmZt.png",
    "TV5":          "https://upload.wikimedia.org/wikipedia/fr/thumb/0/01/TV5_Monde_logo_2018.svg/200px-TV5_Monde_logo_2018.svg.png",
    "ARTV":         "https://upload.wikimedia.org/wikipedia/fr/thumb/4/4c/ICI_ARTV_logo.svg/200px-ICI_ARTV_logo.svg.png",
    "Unis TV":      "https://upload.wikimedia.org/wikipedia/fr/thumb/4/44/Unis_TV_logo.svg/200px-Unis_TV_logo.svg.png",
    "Cinema":       "",
}

PLATFORM_URLS = {
    "Netflix":"https://www.netflix.com","Prime Video":"https://www.primevideo.com",
    "Disney+":"https://www.disneyplus.com","Apple TV+":"https://tv.apple.com",
    "Crave":"https://www.crave.ca","ICI TOU.TV":"https://ici.tou.tv",
    "Tele-Quebec":"https://www.telequebec.tv","TVA+":"https://www.tvaplus.ca",
    "Noovo":"https://www.noovo.ca","Club Illico":"https://www.illico.com",
    "Illico+":"https://www.illico.com","Vrai":"https://www.vrai.ca",
    "Historia":"https://www.historia.ca","Series+":"https://www.seriesplus.com",
    "ONF":"https://www.onf.ca","CBC Gem":"https://gem.cbc.ca",
    "ARTV":"https://ici.artv.ca","Unis TV":"https://unis.ca",
    "TV5":"https://www.tv5unis.ca","Explora":"https://explora.ca",
    "Max":"https://www.max.com","Hulu":"https://www.hulu.com",
    "Paramount+":"https://www.paramountplus.com","Peacock":"https://www.peacocktv.com",
    "Cinema":"https://www.themoviedb.org",
}

NETWORK_TO_PLATFORM = {
    "ICI Radio-Canada Tele":"ICI TOU.TV","ICI TOU.TV":"ICI TOU.TV",
    "Radio-Canada":"ICI TOU.TV","ARTV":"ICI TOU.TV","ICI ARTV":"ARTV",
    "Tele-Quebec":"Tele-Quebec","Telequebec":"Tele-Quebec",
    "TVA":"TVA+","Noovo":"Noovo","Club Illico":"Club Illico",
    "Illico+":"Club Illico","Super Ecran":"Club Illico",
    "Series+":"Series+","Canal Vie":"Historia","Historia":"Historia",
    "Savoir Media":"Tele-Quebec","Crave":"Crave",
    "Z":"Club Illico","Prise 2":"Club Illico","CASA":"Club Illico",
    "Evasion":"Club Illico","Canal D":"Historia",
    "TV5":"TV5","Unis":"Unis TV","TV5 Quebec Canada":"TV5",
    "Vrai":"Vrai","ONF":"ONF","CBC Gem":"CBC Gem",
    "Netflix":"Netflix","HBO":"Crave","Max":"Max","HBO Max":"Crave",
    "Amazon":"Prime Video","Prime Video":"Prime Video",
    "Apple TV+":"Apple TV+","Disney+":"Disney+","Hulu":"Hulu",
    "Peacock":"Peacock","Paramount+":"Paramount+",
    "Canal+":"Cinema","Arte":"Cinema",
    "TF1":"Cinema","France 2":"Cinema","France 3":"Cinema",
    "M6":"Cinema","France 4":"Cinema","France 5":"Cinema",
}

QC_NETWORKS = {
    "ICI Radio-Canada Tele","ICI TOU.TV","Radio-Canada","ARTV","ICI ARTV",
    "Tele-Quebec","Telequebec","TVA","Noovo","Club Illico","Illico+",
    "Super Ecran","Series+","Canal Vie","Historia","Savoir Media",
    "Crave","Z","Prise 2","CASA","Evasion","Canal D",
    "TV5","Unis","TV5 Quebec Canada","Vrai","ONF",
}

TMDB_NETWORK_MAP = {
    213:"Netflix",49:"Crave",2739:"Disney+",1024:"Prime Video",
    2552:"Apple TV+",453:"Hulu",4330:"Peacock",4353:"Paramount+",
    56:"Crave",1556:"Crave",3353:"Disney+",359:"Hulu",
    1436:"Apple TV+",2087:"Max",3186:"Max",
    119:"Amazon",1024:"Prime Video",
}

COUNTRY_TAGS = {
    "CA":"CA","FR":"FR","GB":"UK","AU":"AU","DE":"EU",
    "ES":"EU","IT":"EU","JP":"JP","KR":"KR","US":"USA",
    "BE":"EU","NL":"EU","SE":"EU","CH":"EU",
}

FR_COUNTRIES = {"US","CA","GB","AU","FR","BE","CH","LU"}

LGBT_KEYWORDS = [
    "gay","lesbian","bisexual","transgender","queer","lgbt","lgbtq",
    "same-sex","homosexual","coming out","pride","drag queen","non-binary",
    "trans ","gender identity","gaie","lesbienne","homosexuel",
    "transgenre","fierté","diversité sexuelle",
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
    "Supernatural":"Horreur","Nature":"Documentaire",
    "Food":"Documentaire","Travel":"Documentaire",
    "Game Show":"Telerealite","Talk Show":"Divertissement",
    "Anime":"Animation","Soap":"Drame","DIY":"Telerealite",
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

# ── CACHE TMDB ────────────────────────────────────────────────────────────────
TMDB_CACHE = {}

def load_cache():
    global TMDB_CACHE
    if not DATA_PATH.exists(): return
    try:
        with open(DATA_PATH,"r",encoding="utf-8") as f:
            data = json.load(f)
        for e in data.get("events",[]):
            if e.get("poster") or e.get("desc") or e.get("cast"):
                key = e.get("title","").lower().strip()
                TMDB_CACHE[key] = {
                    "note":     e.get("note"),
                    "poster":   e.get("poster"),
                    "backdrop": e.get("backdrop"),
                    "desc":     e.get("desc"),
                    "trailers": e.get("trailers",[]),
                    "cast":     e.get("cast",[]),
                    "is_lgbt":  "LGBT" in (e.get("tags") or []),
                    "has_french": True,
                }
        print(f"  Cache: {len(TMDB_CACHE)} titres")
    except Exception as ex:
        print(f"  Erreur cache: {ex}")

# ── HELPERS ───────────────────────────────────────────────────────────────────
def log(m): print(f"  {m}", flush=True)

def safe_get(url, params=None, timeout=15, retries=2):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout,
                           headers={"User-Agent":"CalendrierBot/6.0"})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i < retries-1: time.sleep(1)
            else: log(f"Erreur {url[:50]}: {e}")
    return None

def safe_html(url, timeout=20):
    try:
        r = requests.get(url, timeout=timeout, verify=False, headers={
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0"
        })
        r.raise_for_status()
        return r.text
    except Exception as e:
        log(f"HTML {url[:50]}: {e}")
        return None

def in_window(date_str):
    if not date_str: return False
    try:
        d = datetime.strptime(date_str[:10],"%Y-%m-%d")
        # Seulement 2026
        if not date_str.startswith("2026"): return False
        return (TODAY - timedelta(days=HISTORY_DAYS)) <= d <= (TODAY + timedelta(days=FUTURE_DAYS))
    except: return False

def img(path, size="w300"):
    return f"{TMDB_IMG}/{size}{path}" if path else None

def uid(prefix, val):
    return f"{prefix}-{re.sub(r'[^a-z0-9]','-',str(val).lower())[:60]}"

def clean(text):
    if not text: return ""
    return re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',text)).strip()[:800]

def is_lgbt(text):
    if not text: return False
    return any(k in text.lower() for k in LGBT_KEYWORDS)

def is_platform_allowed(name):
    """Verifie si la plateforme est dans la liste blanche."""
    if not name: return False
    if name in EXCLUDED_PLATFORMS: return False
    if name in ALLOWED_PLATFORMS: return True
    # Verifie les variantes
    for excl in EXCLUDED_PLATFORMS:
        if excl.lower() in name.lower(): return False
    for allow in ALLOWED_PLATFORMS:
        if allow.lower() in name.lower(): return True
    return False

def get_platform(show):
    for src in [show.get("webChannel"), show.get("network")]:
        if not src: continue
        name = src.get("name","")
        if name in NETWORK_TO_PLATFORM:
            plat = NETWORK_TO_PLATFORM[name]
            return plat, name in QC_NETWORKS
        for k,v in NETWORK_TO_PLATFORM.items():
            if k.lower() in name.lower():
                return v, k in QC_NETWORKS
    return None, False

def get_country(show):
    for src in [show.get("network"), show.get("webChannel")]:
        if src:
            cc = (src.get("country") or {}).get("code","")
            if cc: return COUNTRY_TAGS.get(cc, cc)
    return "USA"

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
    if is_qc or lang in ("french","francais"): return ["FR"]
    return ["FR","EN"]

# ── ETAPE 1: ENRICHISSEMENT TMDB (avec cache) ──────────────────────────────────
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
                        "lang":"VF" if lang=="fr-FR" else "VO",
                        "label":v.get("name","Bande-annonce"),
                        "url":f"https://www.youtube.com/watch?v={v['key']}"
                    })
        if trailers: break
    return trailers[:4]

def get_cast(tid, media="tv"):
    if not TMDB_KEY: return []
    data = safe_get(f"{TMDB_BASE}/{media}/{tid}/credits",
                   {"api_key":TMDB_KEY,"language":"fr-FR"})
    if not data: return []
    return [c["name"] for c in data.get("cast",[])[:6] if c.get("name")]

def check_french_tmdb(tid, media="tv"):
    """Verifie via TMDb si le contenu a une version francaise."""
    if not TMDB_KEY: return True  # Si pas de cle, on accepte tout
    detail = safe_get(f"{TMDB_BASE}/{media}/{tid}",
                     {"api_key":TMDB_KEY,"language":"fr-FR"})
    if not detail: return False
    # Verifie spoken_languages
    langs = [l.get("iso_639_1","") for l in detail.get("spoken_languages",[])]
    if "fr" in langs: return True
    # Verifie si traduction francaise disponible (overview en francais)
    overview = detail.get("overview","")
    if overview and len(overview) > 20: return True
    # Verifie les translations
    trans = safe_get(f"{TMDB_BASE}/{media}/{tid}/translations",
                    {"api_key":TMDB_KEY})
    if trans:
        for t in trans.get("translations",[]):
            if t.get("iso_639_1") == "fr" and t.get("data",{}).get("overview"):
                return True
    return False

def enrich_tmdb(title, media="tv", tmdb_id=None):
    """Enrichit depuis TMDb avec cache — skip si deja connu."""
    cache_key = title.lower().strip()
    if cache_key in TMDB_CACHE:
        return TMDB_CACHE[cache_key]
    if not TMDB_KEY: return {}

    rid = tmdb_id
    if not rid:
        ep = f"{TMDB_BASE}/search/{'tv' if media=='tv' else 'movie'}"
        for lang in ["fr-FR","en-US"]:
            d = safe_get(ep,{"api_key":TMDB_KEY,"query":title,"language":lang})
            if d and d.get("results"):
                rid = d["results"][0].get("id")
                break
    if not rid: return {}

    # Verifie version francaise
    has_fr = check_french_tmdb(rid, media)

    detail = safe_get(f"{TMDB_BASE}/{'tv' if media=='tv' else 'movie'}/{rid}",
                     {"api_key":TMDB_KEY,"language":"fr-FR"}) or {}
    desc = detail.get("overview","")
    if not desc:
        d_en = safe_get(f"{TMDB_BASE}/{'tv' if media=='tv' else 'movie'}/{rid}",
                       {"api_key":TMDB_KEY,"language":"en-US"}) or {}
        desc = d_en.get("overview","")

    score = detail.get("vote_average")
    seasons = detail.get("seasons",[])
    total_eps = None
    if seasons:
        last = [s for s in seasons if s.get("season_number",0)>0]
        if last: total_eps = last[-1].get("episode_count")

    result = {
        "tmdb_id":    rid,
        "note":       f"{score:.1f}" if score and score>0 else None,
        "poster":     img(detail.get("poster_path")),
        "backdrop":   img(detail.get("backdrop_path"),"w780"),
        "desc":       desc,
        "trailers":   get_trailers(rid, media),
        "cast":       get_cast(rid, media),
        "networks":   detail.get("networks",[]),
        "total_eps":  total_eps,
        "is_lgbt":    is_lgbt(desc),
        "has_french": has_fr,
    }
    TMDB_CACHE[cache_key] = result
    return result

def tmdb_platform(networks):
    for n in networks:
        nid = n.get("id")
        name = n.get("name","")
        if nid in TMDB_NETWORK_MAP:
            plat = TMDB_NETWORK_MAP[nid]
            if is_platform_allowed(plat): return plat
        for k,v in NETWORK_TO_PLATFORM.items():
            if k.lower() in name.lower() and is_platform_allowed(v):
                return v
    return "Netflix"

# ── COLLECTE TVMAZE CANADA ─────────────────────────────────────────────────────
def fetch_canada():
    log("TVmaze Canada...")
    events, seen = [], set()
    start = TODAY - timedelta(days=HISTORY_DAYS)

    for offset in range(0, HISTORY_DAYS + FUTURE_DAYS, 1):
        d = (start + timedelta(days=offset)).strftime("%Y-%m-%d")
        if not d.startswith("2026"): continue
        eps = safe_get(f"{TVMAZE_BASE}/schedule?country=CA&date={d}") or []
        for ep in eps:
            show = ep.get("_embedded",{}).get("show") or ep.get("show") or {}
            sid = show.get("id")
            if not sid or sid in seen: continue
            air = ep.get("airdate","")
            if not in_window(air): continue

            plat, is_qc = get_platform(show)
            if not plat or not is_platform_allowed(plat): continue
            seen.add(sid)

            country = get_country(show)
            tags = []
            if is_qc: tags.append("QC")
            tags.append(country)

            desc = clean(show.get("summary",""))
            if is_lgbt(desc): tags.append("LGBT")

            season_num = ep.get("season",1)
            ep_num = ep.get("number")
            rating = (show.get("rating") or {}).get("average")

            events.append({
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
                "platformLogo":PLATFORM_LOGOS.get(plat,""),
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
                "_needs_enrichment": True,
            })

    log(f"  -> {len(events)} CA (avant enrichissement)")
    return events

# ── COLLECTE TVMAZE MONDE ─────────────────────────────────────────────────────
def fetch_world():
    log("TVmaze Monde (pays avec VF)...")
    events, seen = [], set()
    start = TODAY - timedelta(days=HISTORY_DAYS)

    for cc in ["US","GB","AU","FR","BE"]:
        for offset in range(0, HISTORY_DAYS + FUTURE_DAYS, 1):
            d = (start + timedelta(days=offset)).strftime("%Y-%m-%d")
            if not d.startswith("2026"): continue
            eps = safe_get(f"{TVMAZE_BASE}/schedule?country={cc}&date={d}") or []
            for ep in eps:
                show = ep.get("_embedded",{}).get("show") or ep.get("show") or {}
                sid = show.get("id")
                if not sid or sid in seen: continue
                air = ep.get("airdate","")
                if not in_window(air): continue

                plat, is_qc = get_platform(show)
                if not plat or not is_platform_allowed(plat): continue
                seen.add(sid)

                country = get_country(show)
                tags = [country] if country else ["USA"]
                if is_qc and "QC" not in tags: tags.insert(0,"QC")

                desc = clean(show.get("summary",""))
                if is_lgbt(desc): tags.append("LGBT")

                season_num = ep.get("season",1)
                ep_num = ep.get("number")
                rating = (show.get("rating") or {}).get("average")

                events.append({
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
                    "platformLogo":PLATFORM_LOGOS.get(plat,""),
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
                    "_needs_enrichment": True,
                })

    log(f"  -> {len(events)} monde (avant enrichissement)")
    return events

# ── SHOWBIZZ ──────────────────────────────────────────────────────────────────
def fetch_showbizz():
    log("Showbizz.net...")
    events = []
    MONTHS_FR = {
        "janvier":1,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,
        "juillet":7,"aout":8,"septembre":9,"octobre":10,"novembre":11,"decembre":12,
        "février":2,"août":8,"décembre":12,
    }
    PLAT_KW = {
        "ici tou.tv":"ICI TOU.TV","tou.tv":"ICI TOU.TV","radio-canada":"ICI TOU.TV",
        "tele-quebec":"Tele-Quebec","telequebec":"Tele-Quebec",
        "tva":"TVA+","noovo":"Noovo","illico":"Club Illico",
        "crave":"Crave","vrai":"Vrai","historia":"Historia",
        "series+":"Series+","unis":"Unis TV",
    }
    urls = [
        "https://showbizz.net/tele/rentree-tele-printemps-ete-2026-quand-commencent-vos-emissions",
        "https://showbizz.net/tele/rentree-tele-hiver-2026-quand-commencent-vos-emissions",
        "https://showbizz.net/tele",
    ]
    for url in urls:
        html = safe_html(url)
        if not html: continue
        pattern = r'\*?([A-ZÀ-Ÿa-zà-ÿ][^–—\n\r]{3,70}?)\s*[–—]\s*[Dd]ès le\s+(\d{1,2})\s+(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)(?:\s+2026)?'
        for m in re.finditer(pattern, html, re.IGNORECASE):
            try:
                title = clean(m.group(1)).strip("*").strip()
                if len(title) < 3 or len(title) > 80: continue
                day = int(m.group(2))
                month_str = m.group(3).lower().replace("é","e").replace("û","u").replace("è","e")
                month_num = MONTHS_FR.get(month_str)
                if not month_num: continue
                date_str = f"2026-{str(month_num).zfill(2)}-{str(day).zfill(2)}"
                if not in_window(date_str): continue
                pos = m.start()
                ctx = html[max(0,pos-500):pos+200].lower()
                plat = "ICI TOU.TV"
                for kw, p in PLAT_KW.items():
                    if kw in ctx: plat = p; break
                events.append({
                    "id":uid("showbizz",title+date_str),"date":date_str,
                    "title":title,"saison":"Saison 1","saison_num":1,
                    "ep_num":None,"ep_status":"premiere",
                    "status":"sorti" if date_str<=TODAY_STR else "a-venir",
                    "type":"serie","platform":plat,
                    "platformUrl":PLATFORM_URLS.get(plat,"#"),
                    "platformLogo":PLATFORM_LOGOS.get(plat,""),
                    "lang":["FR"],"country":"CA","tags":["QC","CA"],
                    "categories":["Drame"],"cast":[],"desc":"","note":None,
                    "trailers":[],"poster":None,"backdrop":None,
                    "source":"showbizz","isManual":False,
                    "_needs_enrichment":True,
                })
            except: continue
    log(f"  -> {len(events)} Showbizz")
    return events

# ── ILLICO+ ───────────────────────────────────────────────────────────────────
def fetch_illico():
    log("Illico+...")
    events = []
    MONTHS_FR = {
        "janvier":1,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,
        "juillet":7,"aout":8,"septembre":9,"octobre":10,"novembre":11,"decembre":12,
        "février":2,"août":8,"décembre":12,
    }
    for url in ["https://www.illicoplus.ca/bientot-disponible",
                "https://www.illicoplus.ca/series/nouveautes"]:
        html = safe_html(url)
        if not html: continue
        date_pat = r'(\d{1,2})\s+(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)(?:\s+2026)?'
        title_pats = [
            r'"name"\s*:\s*"([^"]{3,80})"',
            r'"title"\s*:\s*"([^"]{3,80})"',
            r'<h[23][^>]*>([^<]{3,80})</h[23]>',
            r'alt="([^"]{3,80})"',
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
                if any(x in title.lower() for x in ["illico","crave","club","abonnement"]): continue
                events.append({
                    "id":uid("illico",title+date_str),"date":date_str,
                    "title":title,"saison":"Saison 1","saison_num":1,
                    "ep_num":None,"ep_status":"premiere",
                    "status":"sorti" if date_str<=TODAY_STR else "a-venir",
                    "type":"serie","platform":"Club Illico",
                    "platformUrl":PLATFORM_URLS["Club Illico"],
                    "platformLogo":PLATFORM_LOGOS.get("Club Illico",""),
                    "lang":["FR"],"country":"CA","tags":["QC","CA"],
                    "categories":["Drame"],"cast":[],"desc":"","note":None,
                    "trailers":[],"poster":None,"backdrop":None,
                    "source":"illico","isManual":False,
                    "_needs_enrichment":True,
                })
            except: continue
        if events: break
    log(f"  -> {len(events)} Illico+")
    return events

# ── TMDB FILMS ────────────────────────────────────────────────────────────────
def fetch_films():
    if not TMDB_KEY: return []
    log("TMDb films...")
    events, seen = [], set()
    for endpoint in ["upcoming","now_playing","popular","top_rated"]:
        for page in range(1,8):
            data = safe_get(f"{TMDB_BASE}/movie/{endpoint}",{
                "api_key":TMDB_KEY,"language":"fr-FR","page":page,"region":"CA"
            })
            if not data: break
            for m in data.get("results",[]):
                mid = m.get("id")
                if mid in seen: continue
                release = m.get("release_date","")
                if not release or not in_window(release): continue
                seen.add(mid)
                score = m.get("vote_average",0)
                tags = []
                if is_lgbt(m.get("overview","")): tags.append("LGBT")
                events.append({
                    "id":uid("film",mid),"date":release,
                    "title":m.get("title",""),"saison":"Film",
                    "saison_num":0,"ep_num":None,"ep_status":"normal",
                    "status":"sorti" if release<=TODAY_STR else "a-venir",
                    "type":"film","platform":"Cinema",
                    "platformUrl":f"https://www.themoviedb.org/movie/{mid}",
                    "platformLogo":"",
                    "lang":["FR","EN"],"country":"USA","tags":tags,
                    "categories":map_tmdb(m.get("genre_ids",[])),
                    "cast":[],"desc":m.get("overview",""),
                    "note":f"{score:.1f}" if score>0 else None,
                    "trailers":[],"poster":img(m.get("poster_path")),
                    "backdrop":img(m.get("backdrop_path"),"w780"),
                    "source":"tmdb-film","isManual":False,
                    "_needs_enrichment":True,
                })
    log(f"  -> {len(events)} films")
    return events

# ── TMDB SERIES ───────────────────────────────────────────────────────────────
def fetch_series_tmdb():
    if not TMDB_KEY: return []
    log("TMDb series...")
    events, seen = [], set()
    for endpoint in ["popular","top_rated","on_the_air","airing_today"]:
        for page in range(1,8):
            data = safe_get(f"{TMDB_BASE}/tv/{endpoint}",{
                "api_key":TMDB_KEY,"language":"fr-FR","page":page
            })
            if not data: break
            for s in data.get("results",[]):
                sid = s.get("id")
                if sid in seen: continue
                first_air = s.get("first_air_date","")
                if not first_air or not in_window(first_air): continue
                countries = s.get("origin_country",[])
                if countries and countries[0] not in FR_COUNTRIES: continue
                seen.add(sid)
                score = s.get("vote_average",0)
                tags = []
                if is_lgbt(s.get("overview","")): tags.append("LGBT")
                if countries:
                    tags.append(COUNTRY_TAGS.get(countries[0], countries[0]))
                events.append({
                    "id":uid("tmdb-serie",sid),"date":first_air,
                    "title":s.get("name",""),"saison":"Saison 1",
                    "saison_num":1,"ep_num":None,"ep_status":"premiere",
                    "status":"sorti" if first_air<=TODAY_STR else "a-venir",
                    "type":"serie","platform":"Netflix",
                    "platformUrl":PLATFORM_URLS.get("Netflix","#"),
                    "platformLogo":PLATFORM_LOGOS.get("Netflix",""),
                    "lang":["FR","EN"],"country":COUNTRY_TAGS.get((countries or ["US"])[0],"USA"),
                    "tags":tags,"categories":map_tmdb(s.get("genre_ids",[])),
                    "cast":[],"desc":s.get("overview",""),
                    "note":f"{score:.1f}" if score>0 else None,
                    "trailers":[],"poster":img(s.get("poster_path")),
                    "backdrop":img(s.get("backdrop_path"),"w780"),
                    "source":"tmdb-serie","isManual":False,
                    "_needs_enrichment":True,
                })
    log(f"  -> {len(events)} series TMDb")
    return events

# ── ETAPE 2: ENRICHISSEMENT TMDB ──────────────────────────────────────────────
def enrich_all(events):
    """Enrichit les entrees qui ont besoin de l'API TMDb."""
    needs = [e for e in events if e.get("_needs_enrichment") and not TMDB_CACHE.get(e.get("title","").lower().strip())]
    log(f"Enrichissement TMDb: {len(needs)} nouveaux titres (cache: {len(TMDB_CACHE)} existants)")
    
    enriched_count = 0
    skipped_fr = 0
    
    for e in events:
        e.pop("_needs_enrichment", None)
        cache_key = e.get("title","").lower().strip()
        
        if cache_key in TMDB_CACHE:
            cached = TMDB_CACHE[cache_key]
            # Filtre francais depuis cache
            if not cached.get("has_french", True):
                skipped_fr += 1
                e["_skip"] = True
                continue
            for k in ("note","trailers","desc","poster","backdrop","cast"):
                if cached.get(k): e[k] = cached[k]
            if cached.get("is_lgbt") and "LGBT" not in e.get("tags",[]):
                e.setdefault("tags",[]).append("LGBT")
            if cached.get("total_eps") and e.get("saison_num"):
                e["saison"] = make_ep_label(e["saison_num"], e.get("ep_num"), cached["total_eps"])
                e["ep_status"] = ep_status(e.get("ep_num"), cached["total_eps"])
        elif TMDB_KEY:
            media = "movie" if e.get("type")=="film" else "tv"
            enriched = enrich_tmdb(e.get("title",""), media)
            if enriched:
                enriched_count += 1
                # Filtre francais
                if not enriched.get("has_french", True) and e.get("source") not in ("showbizz","illico","rc-presse"):
                    skipped_fr += 1
                    e["_skip"] = True
                    continue
                for k in ("note","trailers","desc","poster","backdrop","cast"):
                    if enriched.get(k): e[k] = enriched[k]
                if enriched.get("is_lgbt") and "LGBT" not in e.get("tags",[]):
                    e.setdefault("tags",[]).append("LGBT")
                if enriched.get("total_eps") and e.get("saison_num"):
                    e["saison"] = make_ep_label(e["saison_num"], e.get("ep_num"), enriched["total_eps"])
                    e["ep_status"] = ep_status(e.get("ep_num"), enriched["total_eps"])
                # Mise a jour plateforme depuis TMDb pour series TMDb
                if e.get("source")=="tmdb-serie" and enriched.get("networks"):
                    plat = tmdb_platform(enriched["networks"])
                    e["platform"] = plat
                    e["platformUrl"] = PLATFORM_URLS.get(plat,"#")
                    e["platformLogo"] = PLATFORM_LOGOS.get(plat,"")
    
    log(f"  Enrichis: {enriched_count} | Sans version FR: {skipped_fr} | Cache hits: {len(events)-enriched_count-skipped_fr}")
    return [e for e in events if not e.get("_skip")]

# ── FUSION ────────────────────────────────────────────────────────────────────
def merge(all_events):
    merged = {}
    seen_keys = {}
    for e in all_events:
        key = (e.get("title","").lower().strip(), e.get("date","")[:7])
        eid = e["id"]
        if key in seen_keys:
            ex = merged[seen_keys[key]]
            for f in ("poster","desc","trailers","cast","note","backdrop"):
                if not ex.get(f) and e.get(f): ex[f] = e[f]
            for tag in (e.get("tags") or []):
                if tag not in ex.get("tags",[]): ex.setdefault("tags",[]).append(tag)
        else:
            seen_keys[key] = eid
            merged[eid] = e
    return list(merged.values())

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\nMise a jour v6 — {TODAY.strftime('%Y-%m-%d %H:%M')}")
    print(f"Cle TMDb: {'OK' if TMDB_KEY else 'MANQUANTE'}")
    print(f"Fenetre: {(TODAY-timedelta(days=HISTORY_DAYS)).strftime('%Y-%m-%d')} a {(TODAY+timedelta(days=FUTURE_DAYS)).strftime('%Y-%m-%d')}\n")

    print("Chargement cache TMDb...")
    load_cache()

    # ETAPE 1: Collecte rapide
    print("\n=== ETAPE 1: COLLECTE ===")
    all_new = []
    print("TVmaze Canada...")
    all_new.extend(fetch_canada())
    print("TVmaze Monde...")
    all_new.extend(fetch_world())
    print("Showbizz...")
    all_new.extend(fetch_showbizz())
    print("Illico+...")
    all_new.extend(fetch_illico())
    print("Films TMDb...")
    all_new.extend(fetch_films())
    print("Series TMDb...")
    all_new.extend(fetch_series_tmdb())
    log(f"Total collecte: {len(all_new)} entrees brutes")

    # ETAPE 2: Enrichissement TMDb
    print("\n=== ETAPE 2: ENRICHISSEMENT TMDB ===")
    all_new = enrich_all(all_new)

    # Fusion et nettoyage
    print("\nFusion...")
    final = merge(all_new)
    final = [e for e in final if in_window(e.get("date","")) and not e.get("_skip")]
    final.sort(key=lambda e: e.get("date","9999"))

    output = {
        "version":      "6.0",
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

    print(f"\nTermine! {len(final)} evenements")
    print(f"  Series     : {series}")
    print(f"  Films      : {films}")
    print(f"  Disponibles: {sorti}")
    print(f"  A venir    : {avenir}")
    print(f"  QC         : {qc}")
    print(f"  LGBT+      : {lgbt}\n")

if __name__ == "__main__":
    main()
