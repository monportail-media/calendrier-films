#!/usr/bin/env python3
"""
Calendrier Films & Series - Script v4
Sources: TVmaze (TOUT sans filtre), TMDb, Trakt, Showbizz, RC Presse, Bell Media, Illico+
Historique: 3 mois | Futur: 6 mois | Zero filtre de qualite
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
HISTORY_DAYS = 90   # 3 mois
FUTURE_DAYS  = 180  # 6 mois

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
    "Adult Swim":"https://www.adultswim.com",
    "Comedy Central":"https://www.cc.com",
    "Bravo":"https://www.bravotv.com",
    "CTV":"https://www.ctv.ca",
    "CBC":"https://www.cbc.ca",
    "Global":"https://globaltv.com",
    "TVA":"https://www.tva.ca",
    "TV5":"https://www.tv5unis.ca",
    "Unis":"https://unis.ca",
    "ARTV":"https://ici.artv.ca",
    "Syfy":"https://www.syfy.com",
    "USA Network":"https://www.usanetwork.com",
    "TNT":"https://www.tntdrama.com",
    "TBS":"https://www.tbs.com",
    "ITV":"https://www.itv.com",
    "Channel 4":"https://www.channel4.com",
    "Sky":"https://www.sky.com",
    "Canal+":"https://www.canalplus.com",
    "Arte":"https://www.arte.tv",
    "Max":"https://www.max.com",
    "Autre":"#",
}

NETWORK_TO_PLATFORM = {
    # Quebec / Canada
    "ICI Radio-Canada Tele":"ICI TOU.TV","ICI TOU.TV":"ICI TOU.TV",
    "Radio-Canada":"ICI TOU.TV","ARTV":"ICI TOU.TV","ICI ARTV":"ICI TOU.TV",
    "Tele-Quebec":"Tele-Quebec","Telequebec":"Tele-Quebec",
    "TVA":"TVA+","Noovo":"Noovo","Club Illico":"Club Illico",
    "Super Ecran":"Club Illico","Series+":"Club Illico",
    "Canal Vie":"Club Illico","Historia":"Club Illico",
    "Savoir Media":"Tele-Quebec","CTV":"CTV","CBC":"CBC",
    "Global":"Global","CTV Drama Channel":"CTV",
    "CTV Sci-Fi Channel":"CTV","W Network":"CTV",
    "Showcase":"CTV","Slice":"Club Illico","Crave":"Crave",
    "Z":"Club Illico","Prise 2":"Club Illico",
    "CASA":"Club Illico","Evasion":"Club Illico",
    "Canal D":"Club Illico","TV5":"TV5",
    "Unis":"Unis","TV5 Quebec Canada":"TV5",
    # USA
    "Netflix":"Netflix","HBO":"Crave","Max":"Max","HBO Max":"Crave",
    "Amazon":"Prime Video","Prime Video":"Prime Video",
    "Apple TV+":"Apple TV+","Disney+":"Disney+","Hulu":"Hulu",
    "Peacock":"Peacock","Paramount+":"Paramount+",
    "AMC":"AMC","FX":"FX","Showtime":"Showtime","Starz":"Starz",
    "Syfy":"Syfy","USA Network":"USA Network","TNT":"TNT",
    "TBS":"TBS","Adult Swim":"Adult Swim",
    "Comedy Central":"Comedy Central","Bravo":"Bravo",
    "NBC":"NBC","ABC":"ABC","CBS":"CBS","Fox":"Fox",
    "CW":"CW","Freeform":"Freeform","Lifetime":"Lifetime",
    "Hallmark":"Hallmark","OWN":"OWN","BET":"BET",
    "VH1":"VH1","MTV":"MTV","E!":"E!",
    # International
    "BBC One":"BBC","BBC Two":"BBC","BBC Three":"BBC",
    "ITV":"ITV","Channel 4":"Channel 4","Sky":"Sky",
    "Canal+":"Canal+","Arte":"Arte","TF1":"Autre",
    "France 2":"Autre","France 3":"Autre","M6":"Autre",
    "RTL":"Autre","ZDF":"Autre","ARD":"Autre",
    "NRK":"Autre","SVT":"Autre","DR":"Autre",
    "RAI":"Autre","Mediaset":"Autre",
}

QC_NETWORKS = {
    "ICI Radio-Canada Tele","ICI TOU.TV","Radio-Canada","ARTV","ICI ARTV",
    "Tele-Quebec","Telequebec","TVA","Noovo","Club Illico",
    "Super Ecran","Series+","Canal Vie","Historia","Savoir Media",
    "CTV","CBC","Global","Crave","Z","Prise 2","CASA","Evasion",
    "Canal D","TV5","Unis","TV5 Quebec Canada",
}

TMDB_NETWORK_MAP = {
    213:"Netflix",49:"Crave",2739:"Disney+",1024:"Prime Video",
    2552:"Apple TV+",453:"Hulu",4330:"Peacock",4353:"Paramount+",
    174:"AMC",88:"AMC",19:"Fox",2:"ABC",6:"NBC",16:"CBS",
    67:"Showtime",318:"Starz",73:"BBC",332:"BBC",56:"Crave",
    1556:"Crave",3353:"Disney+",359:"Hulu",1436:"Apple TV+",
    2087:"Max",3186:"Max",
}

LGBT_KEYWORDS = [
    "gay","lesbian","bisexual","transgender","queer","lgbt","lgbtq",
    "same-sex","homosexual","coming out","pride","drag queen","non-binary",
    "trans ","gender identity","gaie","lesbienne","homosexuel",
    "transgenre","fierte","diversite sexuelle","identite de genre",
]

COUNTRY_TAGS = {
    "CA":"CA","FR":"FR","GB":"UK","AU":"AU","DE":"EU",
    "ES":"EU","IT":"EU","JP":"JP","KR":"KR","US":"USA",
    "BE":"EU","NL":"EU","SE":"EU","NO":"EU","DK":"EU",
    "FI":"EU","PL":"EU","PT":"EU","CH":"EU","AT":"EU",
    "BR":"BR","MX":"MX","AR":"AR","IN":"IN","ZA":"ZA",
}

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

def log(m): print(f"  {m}", flush=True)

def safe_get(url, params=None, timeout=20, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout,
                           headers={"User-Agent":"Mozilla/5.0 (compatible; CalendrierBot/1.0)"})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i < retries-1:
                time.sleep(2)
            else:
                log(f"Erreur {url[:55]}: {e}")
    return None

def safe_get_html(url, timeout=20):
    try:
        r = requests.get(url, timeout=timeout,
                        headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        r.raise_for_status()
        return r.text
    except Exception as e:
        log(f"HTML erreur {url[:55]}: {e}")
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
    t = text.lower()
    return any(k in t for k in LGBT_KEYWORDS)

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

def get_country(show_or_data):
    # TVmaze
    for src in [show_or_data.get("network"), show_or_data.get("webChannel")]:
        if src:
            cc = (src.get("country") or {}).get("code","")
            if cc: return COUNTRY_TAGS.get(cc, cc)
    # TMDb
    for c in show_or_data.get("origin_country",[]):
        return COUNTRY_TAGS.get(c, c)
    return "USA"

def get_trailers(tid, media="tv"):
    if not TMDB_KEY: return []
    trailers = []
    for lang in ["fr-FR","en-US"]:
        vd = safe_get(f"{TMDB_BASE}/{media}/{tid}/videos",{"api_key":TMDB_KEY,"language":lang})
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
    data = safe_get(f"{TMDB_BASE}/{media}/{tid}/credits",{"api_key":TMDB_KEY,"language":"fr-FR"})
    if not data: return []
    return [c["name"] for c in data.get("cast",[])[:6] if c.get("name")]

def tmdb_platform_from_networks(networks):
    for n in networks:
        nid = n.get("id")
        name = n.get("name","")
        if nid in TMDB_NETWORK_MAP:
            return TMDB_NETWORK_MAP[nid]
        for k,v in NETWORK_TO_PLATFORM.items():
            if k.lower() in name.lower():
                return v
    return "Netflix"

def enrich_tmdb(title, media="tv", tmdb_id=None):
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

    return {
        "tmdb_id": rid,
        "note": f"{score:.1f}" if score and score>0 else None,
        "poster": img(detail.get("poster_path")),
        "backdrop": img(detail.get("backdrop_path"),"w780"),
        "desc": desc,
        "trailers": get_trailers(rid, media),
        "cast": get_cast(rid, media),
        "networks": networks,
        "total_eps": total_eps,
        "is_lgbt": is_lgbt(desc),
    }

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

# ── TVMAZE CANADA COMPLET ─────────────────────────────────────────────────────
def fetch_tvmaze_canada():
    log("TVmaze Canada — TOUT sans filtre...")
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
            if is_lgbt(desc) and "LGBT" not in tags: tags.append("LGBT")

            season_num = ep.get("season",1)
            ep_num = ep.get("number")
            rating = (show.get("rating") or {}).get("average")

            lang = ["FR"] if is_qc and any(
                x in (show.get("network") or show.get("webChannel") or {}).get("name","")
                for x in ["Radio-Canada","Tele","TVA","Noovo","Club","ARTV","ICI"]
            ) else ["FR","EN"]

            entry = {
                "id": uid("ca",sid),
                "date": air,
                "title": show.get("name",""),
                "saison": make_ep_label(season_num, ep_num),
                "saison_num": season_num,
                "ep_num": ep_num,
                "ep_status": ep_status(ep_num, None),
                "status": "sorti" if air<=TODAY_STR else "a-venir",
                "type": "serie",
                "platform": plat,
                "platformUrl": PLATFORM_URLS.get(plat,"#"),
                "lang": lang,
                "country": country,
                "tags": tags,
                "categories": map_tv(show.get("genres",[])),
                "cast": [],
                "desc": desc,
                "note": f"{rating:.1f}" if rating else None,
                "trailers": [],
                "poster": (show.get("image") or {}).get("medium"),
                "backdrop": (show.get("image") or {}).get("original"),
                "source": "tvmaze-ca",
                "isManual": False,
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

# ── TVMAZE US/INTERNATIONAL COMPLET ──────────────────────────────────────────
def fetch_tvmaze_world():
    log("TVmaze monde — TOUT sans filtre...")
    events, seen = [], set()
    start = TODAY - timedelta(days=HISTORY_DAYS)

    for country_code in ["US","GB","AU","FR","DE","JP","KR","CA"]:
        for offset in range(0, HISTORY_DAYS + FUTURE_DAYS, 1):
            d = (start + timedelta(days=offset)).strftime("%Y-%m-%d")
            eps = safe_get(f"{TVMAZE_BASE}/schedule?country={country_code}&date={d}") or []
            for ep in eps:
                show = ep.get("_embedded",{}).get("show") or ep.get("show") or {}
                sid = show.get("id")
                if not sid or sid in seen: continue
                air = ep.get("airdate","")
                if not in_window(air): continue
                seen.add(sid)

                plat, is_qc = get_platform(show)
                country = get_country(show)
                tags = [country] if country else ["USA"]
                if is_qc and "QC" not in tags: tags.insert(0,"QC")

                desc = clean(show.get("summary",""))
                if is_lgbt(desc) and "LGBT" not in tags: tags.append("LGBT")

                season_num = ep.get("season",1)
                ep_num = ep.get("number")
                rating = (show.get("rating") or {}).get("average")

                entry = {
                    "id": uid("world",sid),
                    "date": air,
                    "title": show.get("name",""),
                    "saison": make_ep_label(season_num, ep_num),
                    "saison_num": season_num,
                    "ep_num": ep_num,
                    "ep_status": ep_status(ep_num, None),
                    "status": "sorti" if air<=TODAY_STR else "a-venir",
                    "type": "serie",
                    "platform": plat,
                    "platformUrl": PLATFORM_URLS.get(plat,"#"),
                    "lang": ["FR","EN"],
                    "country": country,
                    "tags": tags,
                    "categories": map_tv(show.get("genres",[])),
                    "cast": [],
                    "desc": desc,
                    "note": f"{rating:.1f}" if rating else None,
                    "trailers": [],
                    "poster": (show.get("image") or {}).get("medium"),
                    "backdrop": (show.get("image") or {}).get("original"),
                    "source": "tvmaze-world",
                    "isManual": False,
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

    log(f"  -> {len(events)} series monde")
    return events

# ── SHOWBIZZ.NET ──────────────────────────────────────────────────────────────
def fetch_showbizz():
    log("Showbizz.net — calendriers QC...")
    events = []
    urls = [
        "https://showbizz.net/tele/rentree-tele-printemps-ete-2026-quand-commencent-vos-emissions",
        "https://showbizz.net/tele/rentree-tele-hiver-2026-quand-commencent-vos-emissions",
        "https://showbizz.net/tele",
    ]

    for url in urls:
        html = safe_get_html(url)
        if not html: continue

        # Chercher patterns: "Titre – Dès le DD mois à HH h"
        patterns = [
            r'([A-ZÀ-Ü][^–\n]{3,60})[–—]\s*[Dd]ès le (\d+)\s+(\w+)\s+(?:202[5-9])?',
            r'\*?([A-ZÀ-Ü][^,\n]{3,60}),\s+saison\s+(\d+)\s*[–—]\s*[Dd]ès le (\d+)\s+(\w+)',
            r'([A-ZÀ-Ü][^(\n]{3,60})\s+\(([^)]+)\)[–—]?\s*[Dd]ès le (\d+)\s+(\w+)',
        ]

        MONTHS_FR = {
            "janvier":1,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,
            "juillet":7,"aout":8,"septembre":9,"octobre":10,"novembre":11,"decembre":12,
            "févier":2,"août":8,"décembre":12,"février":2,
        }

        for pat in patterns:
            for m in re.finditer(pat, html, re.IGNORECASE):
                try:
                    title = m.group(1).strip().strip("*").strip()
                    if len(title) < 3: continue
                    day_str = m.group(2) if len(m.groups())>=2 else "1"
                    month_str = m.group(3) if len(m.groups())>=3 else "juin"
                    month_str = month_str.lower().replace("é","e").replace("û","u").replace("è","e")
                    month_num = MONTHS_FR.get(month_str)
                    if not month_num: continue
                    year = 2026 if month_num >= 1 else 2025
                    date_str = f"{year}-{str(month_num).zfill(2)}-{day_str.zfill(2)}"
                    if not in_window(date_str): continue

                    eid = uid("showbizz", title+date_str)
                    events.append({
                        "id": eid,
                        "date": date_str,
                        "title": title,
                        "saison": "Saison 1",
                        "saison_num": 1,
                        "ep_num": None,
                        "ep_status": "premiere",
                        "status": "sorti" if date_str<=TODAY_STR else "a-venir",
                        "type": "serie",
                        "platform": "ICI TOU.TV",
                        "platformUrl": PLATFORM_URLS["ICI TOU.TV"],
                        "lang": ["FR"],
                        "country": "CA",
                        "tags": ["QC","CA"],
                        "categories": ["Drame"],
                        "cast": [],
                        "desc": "",
                        "note": None,
                        "trailers": [],
                        "poster": None,
                        "backdrop": None,
                        "source": "showbizz",
                        "isManual": False,
                    })
                except: continue

    log(f"  -> {len(events)} entrees Showbizz")
    return events

# ── CENTRE DE PRESSE RADIO-CANADA ─────────────────────────────────────────────
def fetch_rc_presse():
    log("Centre de presse Radio-Canada...")
    events = []

    rss_urls = [
        "https://presse.radio-canada.ca/numerique/ici-tou-tv-extra",
        "https://presse.radio-canada.ca/numerique/ici-tou-tv",
        "https://presse.radio-canada.ca/television/ici-tele",
    ]

    date_patterns = [
        r'[Dd]ès le (\d+)\s+(\w+)\s+(?:202[5-9])',
        r'(\d+)\s+(\w+)\s+202[5-9]\s*[,:]\s',
        r'disponible[s]? dès le (\d+)\s+(\w+)',
    ]

    MONTHS_FR = {
        "janvier":1,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,
        "juillet":7,"aout":8,"septembre":9,"octobre":10,"novembre":11,"decembre":12,
        "février":2,"août":8,"décembre":12,
    }

    for url in rss_urls:
        html = safe_get_html(url)
        if not html: continue

        # Extraire les titres d'articles et les dates
        article_pat = r'href="(https://presse\.radio-canada\.ca/[^"]+)">([^<]+)</a>'
        for m in re.finditer(article_pat, html):
            link = m.group(1)
            title = clean(m.group(2))
            if len(title) < 5: continue

            # Chercher date dans le titre ou le contexte
            for dpat in date_patterns:
                dm = re.search(dpat, title, re.IGNORECASE)
                if dm:
                    try:
                        day = int(dm.group(1))
                        month_str = dm.group(2).lower()
                        month_num = MONTHS_FR.get(month_str)
                        if not month_num: continue
                        date_str = f"2026-{str(month_num).zfill(2)}-{str(day).zfill(2)}"
                        if not in_window(date_str): continue

                        events.append({
                            "id": uid("rc", title+date_str),
                            "date": date_str,
                            "title": title,
                            "saison": "Saison 1",
                            "saison_num": 1,
                            "ep_num": None,
                            "ep_status": "premiere",
                            "status": "sorti" if date_str<=TODAY_STR else "a-venir",
                            "type": "serie",
                            "platform": "ICI TOU.TV",
                            "platformUrl": PLATFORM_URLS["ICI TOU.TV"],
                            "lang": ["FR"],
                            "country": "CA",
                            "tags": ["QC","CA"],
                            "categories": ["Drame"],
                            "cast": [],
                            "desc": "",
                            "note": None,
                            "trailers": [],
                            "poster": None,
                            "backdrop": None,
                            "source": "rc-presse",
                            "isManual": False,
                        })
                    except: continue

    log(f"  -> {len(events)} entrees RC Presse")
    return events

# ── ILLICO+ BIENTOT DISPONIBLE ────────────────────────────────────────────────
def fetch_illico():
    log("Illico+ bientot disponible...")
    events = []

    for url in [
        "https://www.illicoplus.ca/bientot-disponible",
        "https://www.illico.com/bientot-disponible",
    ]:
        html = safe_get_html(url)
        if not html: continue

        # Chercher titres et dates dans le HTML
        title_pats = [
            r'"title"\s*:\s*"([^"]{3,80})"',
            r'<h[23][^>]*>([^<]{3,80})</h[23]>',
            r'data-title="([^"]{3,80})"',
        ]
        date_pats = [
            r'(\d{1,2})\s+(janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre)\s+202[5-9]',
        ]

        MONTHS_FR = {
            "janvier":1,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,
            "juillet":7,"aout":8,"septembre":9,"octobre":10,"novembre":11,"decembre":12,
            "février":2,"août":8,"décembre":12,"févier":2,
        }

        for dpat in date_pats:
            for m in re.finditer(dpat, html, re.IGNORECASE):
                try:
                    day = int(m.group(1))
                    month_str = m.group(2).lower().replace("é","e").replace("û","u")
                    month_num = MONTHS_FR.get(month_str)
                    if not month_num: continue

                    # Chercher le titre proche
                    pos = m.start()
                    context = html[max(0,pos-300):pos+300]
                    title = None
                    for tpat in title_pats:
                        tm = re.search(tpat, context)
                        if tm:
                            title = clean(tm.group(1))
                            break
                    if not title: continue

                    date_str = f"2026-{str(month_num).zfill(2)}-{str(day).zfill(2)}"
                    if not in_window(date_str): continue

                    events.append({
                        "id": uid("illico", title+date_str),
                        "date": date_str,
                        "title": title,
                        "saison": "Saison 1",
                        "saison_num": 1,
                        "ep_num": None,
                        "ep_status": "premiere",
                        "status": "sorti" if date_str<=TODAY_STR else "a-venir",
                        "type": "serie",
                        "platform": "Club Illico",
                        "platformUrl": PLATFORM_URLS["Club Illico"],
                        "lang": ["FR"],
                        "country": "CA",
                        "tags": ["QC","CA"],
                        "categories": ["Drame"],
                        "cast": [],
                        "desc": "",
                        "note": None,
                        "trailers": [],
                        "poster": None,
                        "backdrop": None,
                        "source": "illico",
                        "isManual": False,
                    })
                except: continue

        if events: break

    log(f"  -> {len(events)} entrees Illico+")
    return events

# ── BELL MEDIA / CRAVE ────────────────────────────────────────────────────────
def fetch_bell_media():
    log("Bell Media / Crave...")
    events = []
    html = safe_get_html("https://www.bellmedia.ca/the-lede/news/")
    if not html:
        log("  -> 0 entrees Bell Media")
        return events

    # Chercher articles Crave Streaming Overview
    art_pat = r'href="(https://www\.bellmedia\.ca/the-lede/[^"]+(?:crave|streaming)[^"]*)"[^>]*>([^<]+)</a>'
    for m in re.finditer(art_pat, html, re.IGNORECASE):
        article_url = m.group(1)
        art_html = safe_get_html(article_url)
        if not art_html: continue

        # Extraire titres et dates
        date_pats = [
            r'(\w+ \d+):\s+(.+?)(?:\n|<)',
            r'<strong>(\w+ \d+)</strong>[:\s]+([^<\n]+)',
        ]
        for dpat in date_pats:
            for dm in re.finditer(dpat, art_html):
                try:
                    title = clean(dm.group(2))
                    if len(title) < 3: continue
                    events.append({
                        "id": uid("bell", title),
                        "date": TODAY_STR,
                        "title": title,
                        "saison": "Saison 1",
                        "saison_num": 1,
                        "ep_num": None,
                        "ep_status": "premiere",
                        "status": "a-venir",
                        "type": "serie",
                        "platform": "Crave",
                        "platformUrl": PLATFORM_URLS["Crave"],
                        "lang": ["FR","EN"],
                        "country": "CA",
                        "tags": ["CA"],
                        "categories": ["Drame"],
                        "cast": [],
                        "desc": "",
                        "note": None,
                        "trailers": [],
                        "poster": None,
                        "backdrop": None,
                        "source": "bell-media",
                        "isManual": False,
                    })
                except: continue

    log(f"  -> {len(events)} entrees Bell Media")
    return events

# ── TMDB FILMS ────────────────────────────────────────────────────────────────
def fetch_films():
    if not TMDB_KEY: return []
    log("TMDb films — TOUT...")
    events, seen = [], set()

    for endpoint in ["upcoming","now_playing","popular","top_rated"]:
        for page in range(1, 10):
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

                trailers = get_trailers(mid, "movie")
                cast = get_cast(mid, "movie")
                desc = m.get("overview","")
                tags = []
                if is_lgbt(desc): tags.append("LGBT")
                score = m.get("vote_average",0)
                lang = m.get("original_language","en")
                if lang == "fr": tags.append("FR")

                events.append({
                    "id": uid("film",mid),
                    "date": release,
                    "title": m.get("title",""),
                    "saison": "Film",
                    "saison_num": 0,
                    "ep_num": None,
                    "ep_status": "normal",
                    "status": "sorti" if release<=TODAY_STR else "a-venir",
                    "type": "film",
                    "platform": "Cinema",
                    "platformUrl": f"https://www.themoviedb.org/movie/{mid}",
                    "lang": ["FR","EN"],
                    "country": COUNTRY_TAGS.get(m.get("original_language","en").upper(),"USA"),
                    "tags": tags,
                    "categories": map_tmdb(m.get("genre_ids",[])),
                    "cast": cast,
                    "desc": desc,
                    "note": f"{score:.1f}" if score>0 else None,
                    "trailers": trailers,
                    "poster": img(m.get("poster_path")),
                    "backdrop": img(m.get("backdrop_path"),"w780"),
                    "source": "tmdb-film",
                    "isManual": False,
                })

    log(f"  -> {len(events)} films")
    return events

# ── TMDB SERIES ───────────────────────────────────────────────────────────────
def fetch_series_tmdb():
    if not TMDB_KEY: return []
    log("TMDb series...")
    events, seen = [], set()

    for endpoint in ["popular","top_rated","on_the_air","airing_today"]:
        for page in range(1, 10):
            data = safe_get(f"{TMDB_BASE}/tv/{endpoint}",{
                "api_key":TMDB_KEY,"language":"fr-FR","page":page
            })
            if not data: break
            for s in data.get("results",[]):
                sid = s.get("id")
                if sid in seen: continue
                first_air = s.get("first_air_date","")
                if not first_air or not in_window(first_air): continue
                seen.add(sid)

                enriched = enrich_tmdb(s.get("name",""), "tv", sid)
                networks = enriched.get("networks",[])
                plat = tmdb_platform_from_networks(networks)
                desc = enriched.get("desc") or s.get("overview","")
                score = s.get("vote_average",0)
                total_eps = enriched.get("total_eps")

                tags = []
                if enriched.get("is_lgbt") or is_lgbt(desc): tags.append("LGBT")
                countries = s.get("origin_country",[])
                if countries:
                    tag = COUNTRY_TAGS.get(countries[0], countries[0])
                    tags.append(tag)

                events.append({
                    "id": uid("tmdb-serie",sid),
                    "date": first_air,
                    "title": s.get("name",""),
                    "saison": f"Saison 1" + (f" — {total_eps} ep." if total_eps else ""),
                    "saison_num": 1,
                    "ep_num": None,
                    "ep_status": "premiere",
                    "status": "sorti" if first_air<=TODAY_STR else "a-venir",
                    "type": "serie",
                    "platform": plat,
                    "platformUrl": PLATFORM_URLS.get(plat,"#"),
                    "lang": ["FR","EN"],
                    "country": COUNTRY_TAGS.get((s.get("origin_country") or ["US"])[0],"USA"),
                    "tags": tags,
                    "categories": map_tmdb(s.get("genre_ids",[])),
                    "cast": enriched.get("cast",[]),
                    "desc": desc,
                    "note": enriched.get("note") or (f"{score:.1f}" if score>0 else None),
                    "trailers": enriched.get("trailers",[]),
                    "poster": enriched.get("poster") or img(s.get("poster_path")),
                    "backdrop": enriched.get("backdrop") or img(s.get("backdrop_path"),"w780"),
                    "source": "tmdb-serie",
                    "isManual": False,
                })

    log(f"  -> {len(events)} series TMDb")
    return events

# ── FUSION ────────────────────────────────────────────────────────────────────
def merge(all_events):
    seen_keys = {}
    merged = {}
    for e in all_events:
        key = (e.get("title","").lower().strip(), e.get("date","")[:7])
        eid = e["id"]
        if key in seen_keys:
            # Garder la version la plus enrichie
            existing = merged[seen_keys[key]]
            if not existing.get("poster") and e.get("poster"):
                existing["poster"] = e["poster"]
            if not existing.get("desc") and e.get("desc"):
                existing["desc"] = e["desc"]
            if not existing.get("trailers") and e.get("trailers"):
                existing["trailers"] = e["trailers"]
            if not existing.get("cast") and e.get("cast"):
                existing["cast"] = e["cast"]
            # Fusionner les tags
            for tag in (e.get("tags") or []):
                if tag not in existing.get("tags",[]):
                    existing.setdefault("tags",[]).append(tag)
        else:
            seen_keys[key] = eid
            merged[eid] = e

    return list(merged.values())

def load_existing():
    if DATA_PATH.exists():
        with open(DATA_PATH,"r",encoding="utf-8") as f:
            return json.load(f).get("events",[])
    return []

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\nMise a jour v4 — {TODAY.strftime('%Y-%m-%d %H:%M')}")
    print(f"Cle TMDb: {'OK' if TMDB_KEY else 'MANQUANTE'}")
    print(f"Fenetres: {HISTORY_DAYS}j passes ({(TODAY-timedelta(days=HISTORY_DAYS)).strftime('%Y-%m-%d')}) + {FUTURE_DAYS}j futurs\n")

    all_new = []

    print("TVmaze Canada...")
    all_new.extend(fetch_tvmaze_canada())

    print("TVmaze Monde...")
    all_new.extend(fetch_tvmaze_world())

    print("Showbizz...")
    all_new.extend(fetch_showbizz())

    print("RC Presse...")
    all_new.extend(fetch_rc_presse())

    print("Illico+...")
    all_new.extend(fetch_illico())

    print("Bell Media...")
    all_new.extend(fetch_bell_media())

    print("Films TMDb...")
    all_new.extend(fetch_films())

    print("Series TMDb...")
    all_new.extend(fetch_series_tmdb())

    print("Fusion...")
    final = merge(all_new)
    final = [e for e in final if in_window(e.get("date",""))]
    final.sort(key=lambda e: e.get("date","9999"))

    output = {
        "version": "4.0",
        "generated_at": TODAY.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total": len(final),
        "events": final,
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
