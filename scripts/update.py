#!/usr/bin/env python3
"""
Calendrier Films & Series - Script v8
CHANGEMENT MAJEUR: 1 entree PAR EPISODE (comme Spin-off.fr)
Sources:
  - TVmaze schedule US/CA/UK/AU: 1 episode = 1 entree
  - Showbizz.net: calendriers saisonniers QC
  - Bell Media The Lede: Crave mensuel
  - TMDb: films + validation VF + enrichissement (avec cache)
Regles VF:
  - Chaines QC/CA: toujours inclus
  - Plateformes streaming (Netflix, HBO, Disney+, etc.): inclus + validation TMDb
  - Chaines TV europeennes (RTL, TF1, ARD, etc.): exclues
  - Validation VF via TMDb /translations
"""

import json, os, re, time, requests, urllib3
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

# ── CHAINES EXCLUES (TV europeennes sans streaming) ───────────────────────────
EXCLUDED_NETWORKS = {
    # France
    "TF1","France 2","France 3","France 4","France 5","M6","W9","TMC",
    "TFX","C8","CNews","CStar","Gulli","6ter","RMC Story","RMC Decouverte",
    "Cherie 25","Numero 23","Arte France","NRJ 12","Comedie+","MCM",
    # Belgique
    "RTL-TVI","La Une","La Deux","La Trois","Club RTL","Plug RTL","Be TV",
    # Suisse
    "RTS Un","RTS Deux","SRF 1","SRF 2",
    # Allemagne
    "ARD","ZDF","RTL","Sat.1","ProSieben","VOX","Kabel Eins","RTL2",
    "RTLZWEI","Das Erste","3sat","Arte","Sixx","Pro7","Tele 5",
    # Espagne
    "TVE","TVE 1","TVE 2","Antena 3","Telecinco","Cuatro","La Sexta",
    "Neox","Nova","Energy","Mega","Trece",
    # Italie
    "RAI 1","RAI 2","RAI 3","Canale 5","Italia 1","Rete 4","La7",
    "Real Time","DMAX","TV8",
    # Pays-Bas
    "NPO 1","NPO 2","NPO 3","RTL 4","RTL 5","SBS 6",
    # Pologne
    "TVP1","TVP2","Polsat","TVN","TV4","TVN7",
    # Scandinavie
    "SVT1","SVT2","NRK1","NRK2","DR1","DR2","TV2 Norge","TV4 Sweden",
    "TV3 Sweden","TV3 Norway","TV 2 Denmark",
    # Portugal
    "RTP1","RTP2","SIC","TVI",
    # Autriche
    "ORF 1","ORF 2","ATV","Puls 4",
    # Autres EU non-streaming
    "ERT","Mega Channel","Alpha TV","ANT1","Star Channel",
    "TV Republika","Polsat","TVN","TV4 Poland",
    # Israel (chaines locales)
    "Yes","Keshet","Reshet","HOT",
    # Turquie
    "TRT 1","ATV Turkey","Show TV","Kanal D","Star TV Turkey",
    # Corée (chaines locales - pas streaming)
    "KBS1","KBS2","MBC","SBS","tvN","OCN","jTBC","Channel A",
    # Japon (chaines locales)
    "NHK","Fuji TV","TBS Japan","TV Asahi","TV Tokyo","NTV",
    # Brésil
    "TV Globo","SBT","Record TV","Band","RedeTV",
}

# ── PLATEFORMES STREAMING INCLUSES ────────────────────────────────────────────
STREAMING_NETWORKS = {
    # International
    "Netflix","HBO","Max","HBO Max","Amazon","Prime Video",
    "Apple TV+","Disney+","Hulu","Peacock","Paramount+",
    "AMC+","Shudder","MUBI","Starz","BritBox","Acorn TV",
    "Sundance Now","Crunchyroll","Funimation","Tubi",
    "Discovery+","ESPN+","Showtime","MGM+","Hallmark Movies Now",
    "Plex","Pluto TV","Kanopy","Hoopla",
    # Canada/Quebec
    "Crave","ICI TOU.TV","Club Illico","Illico+","Tele-Quebec",
    "TVA","Noovo","CBC Gem","Vrai","Historia","Series+",
    "ARTV","Unis TV","TV5","ONF","Explora","Super Ecran",
    # UK streaming
    "BBC iPlayer","ITVX","Channel 4","All 4","My5","Sky Go",
    "NOW TV","BritBox UK","UKTV Play",
    # US Networks (ont VF disponible via streaming au Quebec)
    "CBS","ABC","NBC","Fox","CW","AMC","FX","Showtime",
    "Adult Swim","Comedy Central","Bravo","USA Network",
    "TNT","TBS","Syfy","E!","Lifetime","Hallmark Channel",
    "OWN","BET","VH1","MTV","Freeform","National Geographic",
}

# ── CHAINES QC/CA ─────────────────────────────────────────────────────────────
QC_CA_NETWORKS = {
    "ICI Radio-Canada Tele","ICI TOU.TV","Radio-Canada","ARTV","ICI ARTV",
    "Tele-Quebec","Telequebec","TVA","Noovo","Club Illico","Illico+",
    "Super Ecran","Series+","Canal Vie","Historia","Savoir Media",
    "CTV","CBC","Global","CTV Drama Channel","CTV Sci-Fi Channel",
    "Crave","Z","Canal D","TV5","Unis","W Network","Showcase","Slice",
}

NETWORK_TO_PLATFORM = {
    # QC/CA
    "ICI Radio-Canada Tele":"ICI TOU.TV","ICI TOU.TV":"ICI TOU.TV",
    "Radio-Canada":"ICI TOU.TV","ARTV":"ARTV","ICI ARTV":"ARTV",
    "Tele-Quebec":"Tele-Quebec","Telequebec":"Tele-Quebec",
    "TVA":"TVA+","Noovo":"Noovo","Club Illico":"Club Illico",
    "Illico+":"Club Illico","Super Ecran":"Club Illico",
    "Series+":"Series+","Canal Vie":"Historia","Historia":"Historia",
    "Savoir Media":"Tele-Quebec","CTV":"Crave","CBC":"CBC Gem",
    "Global":"Crave","CTV Drama Channel":"Crave",
    "CTV Sci-Fi Channel":"Crave","W Network":"Crave",
    "Showcase":"Crave","Slice":"Club Illico","Crave":"Crave",
    "Canal D":"Historia","TV5":"TV5","Unis":"Unis TV",
    # Streaming US/Int
    "Netflix":"Netflix","HBO":"Crave","Max":"Max","HBO Max":"Crave",
    "Amazon":"Prime Video","Prime Video":"Prime Video",
    "Apple TV+":"Apple TV+","Disney+":"Disney+","Hulu":"Hulu",
    "Peacock":"Peacock","Paramount+":"Paramount+",
    "AMC+":"AMC+","Shudder":"AMC+","MUBI":"MUBI",
    "Starz":"Prime Video","BritBox":"Prime Video",
    "Showtime":"Crave","CBS":"Paramount+","ABC":"Disney+",
    "NBC":"Peacock","Fox":"Disney+","CW":"Max",
    "AMC":"AMC+","FX":"Disney+","Adult Swim":"Max",
    "Comedy Central":"Paramount+","Bravo":"Peacock",
    "USA Network":"Peacock","TNT":"Max","TBS":"Max",
    "Syfy":"Peacock","Freeform":"Disney+",
    "Crunchyroll":"Prime Video","Funimation":"Prime Video",
    "BBC One":"BritBox","BBC Two":"BritBox","BBC Three":"BritBox",
    "ITV":"BritBox","ITVX":"BritBox",
    "Channel 4":"Prime Video","All 4":"Prime Video",
    "Sky":"Prime Video","Sky One":"Prime Video",
    "Discovery+":"Discovery+","National Geographic":"Disney+",
    "Cartoon Network":"Max","Adult Swim":"Max",
    "Hallmark Channel":"Hallmark Movies Now",
    "Lifetime":"Prime Video","BET":"Paramount+",
    "OWN":"Discovery+","MTV":"Paramount+","VH1":"Paramount+",
}

PLATFORM_URLS = {
    "Netflix":"https://www.netflix.com","Prime Video":"https://www.primevideo.com",
    "Disney+":"https://www.disneyplus.com","Apple TV+":"https://tv.apple.com",
    "Crave":"https://www.crave.ca","ICI TOU.TV":"https://ici.tou.tv",
    "Tele-Quebec":"https://www.telequebec.tv","TVA+":"https://www.tvaplus.ca",
    "Noovo":"https://www.noovo.ca","Club Illico":"https://www.illico.com",
    "Vrai":"https://www.vrai.ca","Historia":"https://www.historia.ca",
    "Series+":"https://www.seriesplus.com","ONF":"https://www.onf.ca",
    "CBC Gem":"https://gem.cbc.ca","ARTV":"https://ici.artv.ca",
    "Unis TV":"https://unis.ca","TV5":"https://www.tv5unis.ca",
    "Max":"https://www.max.com","Hulu":"https://www.hulu.com",
    "Paramount+":"https://www.paramountplus.com",
    "Peacock":"https://www.peacocktv.com","AMC+":"https://www.amc.com",
    "BritBox":"https://www.britbox.com","MUBI":"https://mubi.com",
    "Discovery+":"https://www.discoveryplus.com",
    "Hallmark Movies Now":"https://www.hallmarkmoviesandmysteries.com",
    "Cinema":"https://www.themoviedb.org",
}

PLATFORM_LOGOS = {
    "Netflix":"https://image.tmdb.org/t/p/original/wwemzKWzjKYJFfCeiB57q3r4Bcm.png",
    "Prime Video":"https://image.tmdb.org/t/p/original/emthp39XA2YScoYL1p0sdbAH2WA.png",
    "Disney+":"https://image.tmdb.org/t/p/original/7rwgEs15tFwyR9NPQ5vpzxTj19d.png",
    "Apple TV+":"https://image.tmdb.org/t/p/original/6uhKBfmtzFqOcLousHwZuzcrScK.png",
    "Max":"https://image.tmdb.org/t/p/original/giwM8XX4V2AkroL84dMkQaAoDVj.png",
    "Hulu":"https://image.tmdb.org/t/p/original/pqUTCleNUiTLAVlelGe6zxmSNST.png",
    "Paramount+":"https://image.tmdb.org/t/p/original/h5DcR0J2EESLitnhR8xLG1QymTE.png",
    "Peacock":"https://image.tmdb.org/t/p/original/xTHltMrZPAJFLQ6qyCBjAnXSmZt.png",
    "Crave":"https://upload.wikimedia.org/wikipedia/en/thumb/c/c0/Crave_logo.svg/200px-Crave_logo.svg.png",
    "ICI TOU.TV":"https://upload.wikimedia.org/wikipedia/fr/thumb/6/61/ICI_TOU.TV_logo.svg/200px-ICI_TOU.TV_logo.svg.png",
    "Tele-Quebec":"https://upload.wikimedia.org/wikipedia/fr/thumb/f/f7/T%C3%A9l%C3%A9-Qu%C3%A9bec_logo.svg/200px-T%C3%A9l%C3%A9-Qu%C3%A9bec_logo.svg.png",
    "TVA+":"https://upload.wikimedia.org/wikipedia/fr/thumb/2/2a/TVA_logo_2013.svg/200px-TVA_logo_2013.svg.png",
    "Noovo":"https://upload.wikimedia.org/wikipedia/fr/thumb/8/8d/Noovo_logo.svg/200px-Noovo_logo.svg.png",
    "Club Illico":"https://upload.wikimedia.org/wikipedia/fr/thumb/b/b9/Club_illico_logo.svg/200px-Club_illico_logo.svg.png",
}

TMDB_NETWORK_MAP = {
    213:"Netflix",49:"Crave",2739:"Disney+",1024:"Prime Video",
    2552:"Apple TV+",453:"Hulu",4330:"Peacock",4353:"Paramount+",
    56:"Crave",1556:"Crave",3353:"Disney+",359:"Hulu",
    1436:"Apple TV+",2087:"Max",3186:"Max",119:"Prime Video",
    174:"AMC+",88:"AMC+",67:"Crave",318:"Prime Video",
}

COUNTRY_TAGS = {
    "CA":"CA","FR":"FR","GB":"UK","AU":"AU","DE":"EU","ES":"EU",
    "IT":"EU","JP":"JP","KR":"KR","US":"USA","BE":"EU","NL":"EU",
    "SE":"EU","CH":"EU","NO":"EU","DK":"EU","PL":"EU","PT":"EU",
    "AT":"EU","GR":"EU","BR":"BR","MX":"MX","IN":"IN","IL":"IL",
    "TR":"TR","AR":"AR","ZA":"ZA","NZ":"AU",
}

# Pays dont les series ont quasi toujours une VF au Quebec
ALWAYS_FR_COUNTRIES = {"US","CA","GB","AU"}

LGBT_KEYWORDS = [
    "gay","lesbian","bisexual","transgender","queer","lgbt","lgbtq",
    "same-sex","homosexual","coming out","pride","drag queen","non-binary",
    "trans ","gender identity","gaie","lesbienne","homosexuel",
    "transgenre","fierte","diversite sexuelle",
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
    "Game Show":"Telerealite","Talk Show":"Divertissement",
    "Anime":"Animation","Soap":"Drame","Food":"Documentaire",
    "Travel":"Documentaire","DIY":"Telerealite",
}

TMDB_GENRE_IDS = {
    28:"Action",12:"Action",16:"Animation",35:"Comedie",80:"Crime",
    99:"Documentaire",18:"Drame",10751:"Jeunesse",14:"Fantasy",
    36:"Drame",27:"Horreur",10402:"Musique",9648:"Policier",
    10749:"Romance",878:"SF",10770:"Drame",53:"Thriller",
    10752:"Action",37:"Action",10759:"Action",10762:"Jeunesse",
    10763:"Documentaire",10764:"Telerealite",10765:"SF",
    10766:"Drame",10767:"Divertissement",
}

def map_tv(gl):
    return list(dict.fromkeys([TVMAZE_GENRE_MAP[g] for g in gl if g in TVMAZE_GENRE_MAP])) or ["Drame"]

def map_tmdb_ids(ids):
    return list(dict.fromkeys([TMDB_GENRE_IDS[i] for i in ids if i in TMDB_GENRE_IDS])) or ["Film"]

# ── CACHE TMDB ────────────────────────────────────────────────────────────────
TMDB_CACHE = {}  # key: show_id (int) -> enriched data
TMDB_FR_CACHE = {}  # key: show_id (int) -> bool (has french)

def load_cache():
    """Charge le cache depuis data.json existant."""
    if not DATA_PATH.exists(): return
    try:
        with open(DATA_PATH,"r",encoding="utf-8") as f:
            data = json.load(f)
        count = 0
        for e in data.get("events",[]):
            tmdb_id = e.get("tmdb_id")
            if tmdb_id:
                key = int(tmdb_id)
                if e.get("poster") or e.get("desc"):
                    TMDB_CACHE[key] = {
                        "note":e.get("note"),"poster":e.get("poster"),
                        "backdrop":e.get("backdrop"),"desc":e.get("desc"),
                        "trailers":e.get("trailers",[]),"cast":e.get("cast",[]),
                        "is_lgbt":"LGBT" in (e.get("tags") or []),
                        "genres":e.get("categories",[]),
                        "total_eps":e.get("total_eps"),
                    }
                    TMDB_FR_CACHE[key] = True
                    count += 1
        print(f"  Cache TMDb: {count} titres avec TMDB ID")
    except Exception as ex:
        print(f"  Erreur cache: {ex}")

# ── HELPERS ───────────────────────────────────────────────────────────────────
def log(m): print(f"  {m}", flush=True)

def safe_get(url, params=None, timeout=15, retries=2):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout,
                           headers={"User-Agent":"CalendrierBot/8.0"})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            if i < retries-1: time.sleep(1)
            else: log(f"Erreur {url[:55]}: {e}")
    return None

def safe_html(url, timeout=20):
    try:
        r = requests.get(url, timeout=timeout, verify=False, headers={
            "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0"
        })
        r.raise_for_status()
        return r.text
    except Exception as e:
        log(f"HTML {url[:55]}: {e}")
        return None

def in_window(date_str):
    if not date_str: return False
    try:
        d = datetime.strptime(date_str[:10],"%Y-%m-%d")
        if not date_str.startswith("2026"): return False
        return (TODAY - timedelta(days=HISTORY_DAYS)) <= d <= (TODAY + timedelta(days=FUTURE_DAYS))
    except: return False

def tmdb_img(path, size="w300"):
    return f"{TMDB_IMG}/{size}{path}" if path else None

def uid(prefix, val):
    return f"{prefix}-{re.sub(r'[^a-z0-9]','-',str(val).lower())[:60]}"

def clean(text):
    if not text: return ""
    return re.sub(r'\s+',' ',re.sub(r'<[^>]+>','',text)).strip()[:800]

def is_lgbt(text):
    if not text: return False
    return any(k in text.lower() for k in LGBT_KEYWORDS)

def get_platform(net_name):
    """Retourne (plateforme, is_qc) depuis un nom de reseau TVmaze."""
    if net_name in NETWORK_TO_PLATFORM:
        plat = NETWORK_TO_PLATFORM[net_name]
        return plat, net_name in QC_CA_NETWORKS
    name_l = net_name.lower()
    for k,v in NETWORK_TO_PLATFORM.items():
        if k.lower() in name_l:
            return v, k in QC_CA_NETWORKS
    return None, False

def is_network_included(net_name, country_code="US"):
    """
    Determine si un reseau doit etre inclus:
    - QC/CA: toujours oui
    - Streaming connu: oui
    - Chaine TV europeenne: non
    - Autre US/UK/AU: oui (VF validee apres)
    """
    if not net_name: return False
    if net_name in QC_CA_NETWORKS: return True
    if net_name in EXCLUDED_NETWORKS: return False
    # Streaming international connu
    if net_name in STREAMING_NETWORKS: return True
    # Verification par sous-chaine
    name_l = net_name.lower()
    for excl in EXCLUDED_NETWORKS:
        if excl.lower() == name_l: return False
    for stream in STREAMING_NETWORKS:
        if stream.lower() in name_l: return True
    # Pays US/CA/UK/AU: inclure par defaut (validation VF ensuite)
    if country_code in ALWAYS_FR_COUNTRIES: return True
    return False

def get_country_tag(show):
    for src in [show.get("network"), show.get("webChannel")]:
        if src:
            cc = (src.get("country") or {}).get("code","")
            if cc: return cc, COUNTRY_TAGS.get(cc, cc)
    return "US", "USA"

def ep_status(ep_num, total_eps):
    if not ep_num: return "premiere"
    if ep_num <= 3: return "premiere"
    if total_eps and ep_num >= total_eps - 2: return "finale"
    return "normal"

def make_ep_label(season, ep_num, total_eps=None):
    if ep_num:
        return f"S{str(season).zfill(2)}E{str(ep_num).zfill(2)}"
    elif total_eps:
        return f"Saison {season} — {total_eps} ep."
    return f"Saison {season}"

# ── TMDB: VALIDATION VF ET ENRICHISSEMENT ─────────────────────────────────────
def check_has_french(tmdb_id, media="tv"):
    """Verifie via /translations si contenu disponible en francais."""
    if tmdb_id in TMDB_FR_CACHE:
        return TMDB_FR_CACHE[tmdb_id]
    if not TMDB_KEY:
        TMDB_FR_CACHE[tmdb_id] = True
        return True
    try:
        r = requests.get(
            f"{TMDB_BASE}/{media}/{tmdb_id}/translations",
            params={"api_key":TMDB_KEY}, timeout=10
        )
        if r.status_code == 200:
            langs = [t.get("iso_639_1","") for t in r.json().get("translations",[])]
            has_fr = "fr" in langs or "fr-CA" in langs
            TMDB_FR_CACHE[tmdb_id] = has_fr
            return has_fr
    except: pass
    TMDB_FR_CACHE[tmdb_id] = True  # Par defaut: inclure
    return True

def get_tmdb_id_for_show(show_name, show_tvmaze_id=None, media="tv"):
    """Trouve le TMDB ID depuis le nom TVmaze."""
    if not TMDB_KEY: return None
    try:
        # Cherche via TVmaze external IDs
        if show_tvmaze_id:
            ext = safe_get(f"{TVMAZE_BASE}/shows/{show_tvmaze_id}?embed=externals")
            if ext:
                externals = ext.get("externals") or ext.get("_embedded",{}).get("externals",{})
                tmdb = externals.get("thetvdb") if not externals else None
                # Essai via recherche TMDb
        # Recherche directe TMDb
        ep = f"{TMDB_BASE}/search/{'tv' if media=='tv' else 'movie'}"
        for lang in ["fr-FR","en-US"]:
            d = safe_get(ep, {"api_key":TMDB_KEY,"query":show_name,"language":lang})
            if d and d.get("results"):
                return d["results"][0].get("id")
    except: pass
    return None

def enrich_show(tmdb_id, media="tv"):
    """Enrichit depuis TMDb avec cache par ID."""
    if tmdb_id in TMDB_CACHE:
        return TMDB_CACHE[tmdb_id]
    if not TMDB_KEY or not tmdb_id:
        return {}

    try:
        detail = safe_get(f"{TMDB_BASE}/{'tv' if media=='tv' else 'movie'}/{tmdb_id}",
                         {"api_key":TMDB_KEY,"language":"fr-FR"}) or {}
        desc = detail.get("overview","")
        if not desc:
            d_en = safe_get(f"{TMDB_BASE}/{'tv' if media=='tv' else 'movie'}/{tmdb_id}",
                           {"api_key":TMDB_KEY,"language":"en-US"}) or {}
            desc = d_en.get("overview","")

        score = detail.get("vote_average")
        seasons = detail.get("seasons",[])
        total_eps = None
        if seasons:
            last = [s for s in seasons if s.get("season_number",0)>0]
            if last: total_eps = last[-1].get("episode_count")

        # Trailers
        trailers = []
        for lang in ["fr-FR","en-US"]:
            vd = safe_get(f"{TMDB_BASE}/{'tv' if media=='tv' else 'movie'}/{tmdb_id}/videos",
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

        # Cast
        cast = []
        cdata = safe_get(f"{TMDB_BASE}/{'tv' if media=='tv' else 'movie'}/{tmdb_id}/credits",
                        {"api_key":TMDB_KEY,"language":"fr-FR"})
        if cdata:
            cast = [c["name"] for c in cdata.get("cast",[])[:6] if c.get("name")]

        networks = detail.get("networks",[])
        result = {
            "note":f"{score:.1f}" if score and score>0 else None,
            "poster":tmdb_img(detail.get("poster_path")),
            "backdrop":tmdb_img(detail.get("backdrop_path"),"w780"),
            "desc":desc,"trailers":trailers[:4],"cast":cast,
            "networks":networks,"total_eps":total_eps,
            "is_lgbt":is_lgbt(desc),
            "genres":map_tmdb_ids(detail.get("genre_ids",[])),
        }
        TMDB_CACHE[tmdb_id] = result
        return result
    except Exception as e:
        log(f"Erreur enrich {tmdb_id}: {e}")
        return {}

def tmdb_platform_from_networks(networks):
    for n in networks:
        nid = n.get("id")
        name = n.get("name","")
        if nid in TMDB_NETWORK_MAP:
            return TMDB_NETWORK_MAP[nid]
        plat, _ = get_platform(name)
        if plat: return plat
    return None

# Cache des shows TVmaze -> TMDB ID pour eviter les recherches repetees
SHOW_TMDB_MAP = {}  # tvmaze_show_id -> tmdb_id

def get_show_tmdb_id(show):
    """Trouve le TMDB ID d'un show TVmaze, avec cache."""
    sid = show.get("id")
    if sid in SHOW_TMDB_MAP:
        return SHOW_TMDB_MAP[sid]

    # Chercher dans les externals TVmaze
    tmdb_id = None
    ext_ids = show.get("externals") or {}
    # TVmaze ne donne pas directement TMDB ID, mais parfois via embed
    # On cherche via le nom
    if TMDB_KEY:
        name = show.get("name","")
        if name:
            ep = f"{TMDB_BASE}/search/tv"
            for lang in ["fr-FR","en-US"]:
                d = safe_get(ep, {"api_key":TMDB_KEY,"query":name,"language":lang})
                if d and d.get("results"):
                    tmdb_id = d["results"][0].get("id")
                    break

    SHOW_TMDB_MAP[sid] = tmdb_id
    return tmdb_id

# ── SOURCE 1: TVMAZE SCHEDULE (1 episode par entree) ─────────────────────────
def fetch_tvmaze_episodes():
    """
    Recupere 1 entree PAR EPISODE depuis TVmaze.
    Pays: US, CA, UK, AU - sans filtre de qualite.
    """
    log("TVmaze episodes — US/CA/UK/AU (1 par episode)...")
    events = []
    seen_episode_ids = set()

    # Pour chaque pays et chaque jour
    countries = ["US","CA","GB","AU"]
    start = TODAY - timedelta(days=HISTORY_DAYS)
    total_days = HISTORY_DAYS + FUTURE_DAYS

    for country_code in countries:
        log(f"  Pays: {country_code}...")
        ep_count = 0

        for offset in range(0, total_days, 1):
            d = (start + timedelta(days=offset)).strftime("%Y-%m-%d")
            if not d.startswith("2026"): continue

            eps = safe_get(f"{TVMAZE_BASE}/schedule?country={country_code}&date={d}") or []

            for ep in eps:
                ep_id = ep.get("id")
                if ep_id and ep_id in seen_episode_ids: continue

                show = ep.get("_embedded",{}).get("show") or ep.get("show") or {}
                if not show: continue

                air = ep.get("airdate","")
                if not in_window(air): continue

                # Reseau
                network = show.get("network") or show.get("webChannel") or {}
                net_name = network.get("name","")
                net_country = (network.get("country") or {}).get("code", country_code)

                # Filtre: inclure ou exclure
                if not is_network_included(net_name, net_country):
                    continue

                if ep_id: seen_episode_ids.add(ep_id)

                # Plateforme
                plat, is_qc = get_platform(net_name)
                if not plat:
                    plat = "Netflix" if country_code in ("US","CA") else "Prime Video"

                cc, country_tag = get_country_tag(show)
                tags = []
                if is_qc: tags.append("QC")
                tags.append(country_tag)

                season_num = ep.get("season", 1)
                ep_num = ep.get("number")
                ep_name = ep.get("name","")
                rating = (show.get("rating") or {}).get("average")
                desc = clean(show.get("summary",""))
                if is_lgbt(desc): tags.append("LGBT")

                # Langue
                show_lang = show.get("language","").lower()
                if is_qc or show_lang in ("french","francais"):
                    lang = ["FR"]
                else:
                    lang = ["FR","EN"]

                entry = {
                    "id": f"ep-{ep_id}" if ep_id else uid(f"tvm-{country_code.lower()}", f"{show.get('id',0)}{air}{ep_num}"),
                    "show_id": show.get("id"),
                    "ep_id": ep_id,
                    "date": air,
                    "title": show.get("name",""),
                    "ep_title": ep_name,
                    "saison": make_ep_label(season_num, ep_num),
                    "saison_num": season_num,
                    "ep_num": ep_num,
                    "ep_status": ep_status(ep_num, None),
                    "status": "sorti" if air<=TODAY_STR else "a-venir",
                    "type": "serie",
                    "platform": plat,
                    "platformUrl": PLATFORM_URLS.get(plat,"#"),
                    "platformLogo": PLATFORM_LOGOS.get(plat,""),
                    "lang": lang,
                    "country": country_tag,
                    "tags": tags,
                    "categories": map_tv(show.get("genres",[])),
                    "cast": [],
                    "desc": desc,
                    "note": f"{rating:.1f}" if rating else None,
                    "trailers": [],
                    "poster": (show.get("image") or {}).get("medium"),
                    "backdrop": (show.get("image") or {}).get("original"),
                    "source": f"tvmaze-{country_code.lower()}",
                    "isManual": False,
                    "tmdb_id": None,
                    "_needs_enrichment": True,
                }
                events.append(entry)
                ep_count += 1

        log(f"    -> {ep_count} episodes {country_code}")

    log(f"  -> Total TVmaze: {len(events)} episodes")
    return events

# ── SOURCE 2: SHOWBIZZ QC ─────────────────────────────────────────────────────
def fetch_showbizz():
    log("Showbizz.net QC...")
    events = []

    MONTHS_FR = {
        "janvier":1,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,
        "juillet":7,"aout":8,"septembre":9,"octobre":10,"novembre":11,"decembre":12,
        "février":2,"août":8,"décembre":12,
    }

    PLAT_KW = {
        "ici tou.tv":"ICI TOU.TV","tou.tv":"ICI TOU.TV","radio-canada":"ICI TOU.TV",
        "ici tele":"ICI TOU.TV","ici télé":"ICI TOU.TV",
        "tele-quebec":"Tele-Quebec","télé-québec":"Tele-Quebec",
        "tva":"TVA+","noovo":"Noovo","illico":"Club Illico",
        "crave":"Crave","vrai":"Vrai","historia":"Historia",
        "series+":"Series+","séries+":"Series+",
        "unis":"Unis TV","tv5":"TV5","artv":"ARTV",
        "netflix":"Netflix","amazon":"Prime Video","disney":"Disney+",
        "apple":"Apple TV+","max":"Max",
    }

    urls = [
        "https://showbizz.net/tele/rentree-tele-hiver-2026-quand-commencent-vos-emissions",
        "https://showbizz.net/tele/rentree-tele-printemps-ete-2026-quand-commencent-vos-emissions",
        "https://showbizz.net/tele/rentree-tele-automne-2026-quand-commencent-vos-emissions",
        "https://showbizz.net/tele/rentree-tele-hiver-2026-quand-commencent-vos-emissions-doublees",
        "https://showbizz.net/tele/rentree-tele-printemps-ete-2026-quand-commencent-vos-emissions-doublees",
        "https://showbizz.net/tele/rentree-tele-automne-2026-quand-commencent-vos-emissions-doublees",
    ]

    seen = set()
    for url in urls:
        html = safe_html(url)
        if not html: continue

        pattern = r'\*?\s*([^\n–—\*\[\]]{3,70}?)\s*[–—]\s*[Dd]ès le\s+(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)?\s*(\d{1,2})\s+(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)(?:\s+2026)?'

        for m in re.finditer(pattern, html, re.IGNORECASE):
            try:
                raw = clean(m.group(1)).strip("*[]() ").strip()
                raw = re.sub(r'<[^>]+>','',raw).strip()
                if len(raw) < 3 or len(raw) > 80: continue
                if any(x in raw.lower() for x in ["calendrier","saison doublée","acquisitions","suivant","clique"]): continue

                day = int(m.group(2))
                month_str = m.group(3).lower().replace("é","e").replace("û","u").replace("è","e").replace("ê","e")
                month_num = MONTHS_FR.get(month_str)
                if not month_num: continue

                date_str = f"2026-{str(month_num).zfill(2)}-{str(day).zfill(2)}"
                if not in_window(date_str): continue

                key = (raw.lower(), date_str)
                if key in seen: continue
                seen.add(key)

                # Plateforme depuis contexte
                pos = html.find(m.group(0))
                ctx = html[max(0,pos-400):pos+200].lower()
                plat = "ICI TOU.TV"
                for kw, p in PLAT_KW.items():
                    if kw in ctx: plat = p; break

                tags = ["QC","CA"]
                events.append({
                    "id": uid("showbizz", raw+date_str),
                    "show_id": None,"ep_id": None,
                    "date": date_str,
                    "title": raw,
                    "ep_title": "",
                    "saison": "Saison 1",
                    "saison_num": 1,"ep_num": 1,
                    "ep_status": "premiere",
                    "status": "sorti" if date_str<=TODAY_STR else "a-venir",
                    "type": "serie",
                    "platform": plat,
                    "platformUrl": PLATFORM_URLS.get(plat,"#"),
                    "platformLogo": PLATFORM_LOGOS.get(plat,""),
                    "lang": ["FR"],"country": "CA","tags": tags,
                    "categories": ["Drame"],"cast": [],"desc": "",
                    "note": None,"trailers": [],"poster": None,"backdrop": None,
                    "source": "showbizz","isManual": False,"tmdb_id": None,
                    "_needs_enrichment": True,
                })
            except: continue

    log(f"  -> {len(events)} emissions QC Showbizz")
    return events

# ── SOURCE 3: BELL MEDIA / CRAVE ──────────────────────────────────────────────
def fetch_bell_media():
    log("Bell Media / Crave...")
    events = []

    MONTH_NAMES_EN = ["january","february","march","april","may","june",
                      "july","august","september","october","november","december"]
    MONTH_MAP = {m:f"2026-{str(i+1).zfill(2)}" for i,m in enumerate(MONTH_NAMES_EN)}

    months_to_try = []
    for offset in range(0, 7):
        d = TODAY.replace(day=1) + timedelta(days=32*offset)
        d = d.replace(day=1)
        if d.year == 2026:
            months_to_try.append(MONTH_NAMES_EN[d.month-1]+f"-{d.year}")
    months_to_try = list(dict.fromkeys(months_to_try))

    seen = set()
    for month_slug in months_to_try:
        url = f"https://www.bellmedia.ca/the-lede/press/{month_slug}-crave-streaming-overview/"
        html = safe_html(url)
        if not html: continue

        month_name = month_slug.split("-")[0]
        year_prefix = MONTH_MAP.get(month_name,"2026-06")

        # Pattern: "JUNE 1 – Title Series"
        pat = r'([A-Z]+)\s+(\d{1,2})\s*[–—]\s*(?:New |Season \d+ of )?([A-Z][A-Z\s\':&!\-,\(\)\.]+?)(?:\s*\(|\s*\*|\s*<|\s*\n|\s*Season|\s*Ep\b)'

        for m in re.finditer(pat, html):
            try:
                month_en = m.group(1).lower()
                day = int(m.group(2))
                title = clean(m.group(3)).strip().rstrip(",:- ")
                if len(title) < 2: continue

                mp = MONTH_MAP.get(month_en, year_prefix)
                date_str = f"{mp}-{str(day).zfill(2)}"
                if not in_window(date_str): continue

                key = (title.lower(), date_str[:7])
                if key in seen: continue
                seen.add(key)

                events.append({
                    "id": uid("bell", title+date_str),
                    "show_id": None,"ep_id": None,
                    "date": date_str,
                    "title": title.title(),
                    "ep_title": "",
                    "saison": "Saison 1","saison_num": 1,"ep_num": 1,
                    "ep_status": "premiere",
                    "status": "sorti" if date_str<=TODAY_STR else "a-venir",
                    "type": "serie","platform": "Crave",
                    "platformUrl": PLATFORM_URLS["Crave"],
                    "platformLogo": PLATFORM_LOGOS.get("Crave",""),
                    "lang": ["FR","EN"],"country": "USA","tags": [],
                    "categories": ["Drame"],"cast": [],"desc": "",
                    "note": None,"trailers": [],"poster": None,"backdrop": None,
                    "source": "bell-media","isManual": False,"tmdb_id": None,
                    "_needs_enrichment": True,
                })
            except: continue

    log(f"  -> {len(events)} titres Bell Media/Crave")
    return events

# ── SOURCE 4: TMDB FILMS ──────────────────────────────────────────────────────
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
                desc = m.get("overview","")
                tags = []
                if is_lgbt(desc): tags.append("LGBT")
                events.append({
                    "id": f"film-{mid}",
                    "show_id": None,"ep_id": None,
                    "date": release,
                    "title": m.get("title",""),
                    "ep_title": "",
                    "saison": "Film","saison_num": 0,"ep_num": None,
                    "ep_status": "normal",
                    "status": "sorti" if release<=TODAY_STR else "a-venir",
                    "type": "film","platform": "Cinema",
                    "platformUrl": f"https://www.themoviedb.org/movie/{mid}",
                    "platformLogo": "",
                    "lang": ["FR","EN"],"country": "USA","tags": tags,
                    "categories": map_tmdb_ids(m.get("genre_ids",[])),
                    "cast": [],"desc": desc,
                    "note": f"{score:.1f}" if score>0 else None,
                    "trailers": [],"poster": tmdb_img(m.get("poster_path")),
                    "backdrop": tmdb_img(m.get("backdrop_path"),"w780"),
                    "source": "tmdb-film","isManual": False,"tmdb_id": mid,
                    "_needs_enrichment": True,
                })

    log(f"  -> {len(events)} films TMDb")
    return events

# ── ENRICHISSEMENT PAR LOTS ───────────────────────────────────────────────────
def enrich_all(events):
    """
    Enrichit tous les evenements avec TMDb.
    - Utilise le cache par TMDB ID (plus precis que par titre)
    - Valide la VF pour les series non-QC
    - 1 appel API par show (pas par episode)
    """
    log("Enrichissement TMDb (par show, pas par episode)...")

    # Grouper par show_id pour eviter les appels dupliques
    show_ids_done = set()  # tvmaze show IDs deja traites
    skipped_no_fr = 0
    enriched_count = 0
    qc_sources = {"showbizz","bell-media","tvmaze-ca"}

    for e in events:
        e.pop("_needs_enrichment", None)

        # Films: enrichissement direct par TMDB ID
        if e.get("type") == "film" and e.get("tmdb_id"):
            tid = e["tmdb_id"]
            if tid in TMDB_CACHE:
                cached = TMDB_CACHE[tid]
            else:
                cached = enrich_show(tid, "movie")
                enriched_count += 1
            if cached:
                for k in ("note","poster","backdrop","desc","trailers","cast"):
                    if cached.get(k): e[k] = cached[k]
                if cached.get("is_lgbt") and "LGBT" not in e.get("tags",[]): e["tags"].append("LGBT")
            continue

        # Series: 1 enrichissement par show TVmaze
        show_id = e.get("show_id")
        if not show_id: continue

        if show_id in show_ids_done:
            # Appliquer le cache si disponible
            tmdb_id = SHOW_TMDB_MAP.get(show_id)
            if tmdb_id and tmdb_id in TMDB_CACHE:
                cached = TMDB_CACHE[tmdb_id]
                if cached:
                    for k in ("note","poster","backdrop","desc","trailers","cast"):
                        if cached.get(k) and not e.get(k): e[k] = cached[k]
                    if cached.get("is_lgbt") and "LGBT" not in e.get("tags",[]): e["tags"].append("LGBT")
                    if cached.get("total_eps"):
                        e["saison"] = make_ep_label(e.get("saison_num",1), e.get("ep_num"), cached["total_eps"])
                        e["ep_status"] = ep_status(e.get("ep_num"), cached["total_eps"])
            # Verifier si skip
            if e.get("_skip"): skipped_no_fr += 1
            continue

        show_ids_done.add(show_id)

        if not TMDB_KEY:
            continue

        # Trouver le TMDB ID
        title = e.get("title","")
        tmdb_id = SHOW_TMDB_MAP.get(show_id)
        if not tmdb_id:
            # Recherche TMDb par nom
            for lang in ["fr-FR","en-US"]:
                d = safe_get(f"{TMDB_BASE}/search/tv",{"api_key":TMDB_KEY,"query":title,"language":lang})
                if d and d.get("results"):
                    tmdb_id = d["results"][0].get("id")
                    break
            SHOW_TMDB_MAP[show_id] = tmdb_id

        if not tmdb_id: continue

        e["tmdb_id"] = tmdb_id

        # Validation VF pour series non-QC
        country_code = next((k for k,v in COUNTRY_TAGS.items() if v==e.get("country","USA")), "US")
        is_qc_source = e.get("source") in qc_sources
        always_fr = country_code in ALWAYS_FR_COUNTRIES

        if not is_qc_source and not always_fr:
            has_fr = check_has_french(tmdb_id, "tv")
            if not has_fr:
                # Marquer TOUS les episodes de ce show pour exclusion
                e["_skip"] = True
                skipped_no_fr += 1
                continue

        # Enrichir
        if tmdb_id in TMDB_CACHE:
            cached = TMDB_CACHE[tmdb_id]
        else:
            cached = enrich_show(tmdb_id, "tv")
            enriched_count += 1

        if cached:
            for k in ("note","poster","backdrop","desc","trailers","cast"):
                if cached.get(k) and not e.get(k): e[k] = cached[k]
            if cached.get("is_lgbt") and "LGBT" not in e.get("tags",[]): e["tags"].append("LGBT")
            if cached.get("total_eps"):
                e["saison"] = make_ep_label(e.get("saison_num",1), e.get("ep_num"), cached["total_eps"])
                e["ep_status"] = ep_status(e.get("ep_num"), cached["total_eps"])
            # Mise a jour plateforme depuis networks TMDb
            if cached.get("networks"):
                plat = tmdb_platform_from_networks(cached["networks"])
                if plat:
                    e["platform"] = plat
                    e["platformUrl"] = PLATFORM_URLS.get(plat,"#")
                    e["platformLogo"] = PLATFORM_LOGOS.get(plat,"")

    log(f"  Enrichissements TMDb: {enriched_count} nouveaux | Sans VF exclus: {skipped_no_fr}")
    return [e for e in events if not e.get("_skip")]

# ── FUSION ────────────────────────────────────────────────────────────────────
def merge(events):
    """
    Deduplication:
    - Pour TVmaze: garder chaque episode unique (par ep_id)
    - Eviter les doublons titre+date entre sources
    """
    final = {}
    title_date_seen = {}  # (titre_norm, date) -> id

    for e in events:
        eid = e["id"]

        # Deduplication par episode ID TVmaze
        ep_id = e.get("ep_id")
        if ep_id:
            key = f"ep_{ep_id}"
            if key in final:
                # Enrichir l'existant
                ex = final[key]
                for f in ("poster","desc","trailers","cast","note","backdrop"):
                    if not ex.get(f) and e.get(f): ex[f] = e[f]
                continue
            final[key] = e
            continue

        # Pour les autres sources: dedup par titre+date
        title_norm = e.get("title","").lower().strip()
        date = e.get("date","")
        td_key = (title_norm, date)

        if td_key in title_date_seen:
            ex_id = title_date_seen[td_key]
            ex = final.get(ex_id) or final.get(f"ep_{ex_id}")
            if ex:
                for f in ("poster","desc","trailers","cast","note","backdrop"):
                    if not ex.get(f) and e.get(f): ex[f] = e[f]
                for tag in (e.get("tags") or []):
                    if tag not in ex.get("tags",[]): ex.setdefault("tags",[]).append(tag)
                # Preferer source QC
                if e.get("source") in {"showbizz","bell-media"} and ex.get("source") not in {"showbizz","bell-media"}:
                    ex["lang"] = e.get("lang", ex["lang"])
        else:
            title_date_seen[td_key] = eid
            final[eid] = e

    return list(final.values())

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\nMise a jour v8 — {TODAY.strftime('%Y-%m-%d %H:%M')}")
    print(f"Cle TMDb: {'OK' if TMDB_KEY else 'MANQUANTE'}")
    print(f"Fenetre: {(TODAY-timedelta(days=HISTORY_DAYS)).strftime('%Y-%m-%d')} a {(TODAY+timedelta(days=FUTURE_DAYS)).strftime('%Y-%m-%d')}")
    print(f"Mode: 1 entree PAR EPISODE (comme Spin-off.fr)\n")

    print("Chargement cache TMDb...")
    load_cache()

    print("\n=== ETAPE 1: COLLECTE ===")
    all_events = []

    print("TVmaze episodes (US/CA/UK/AU)...")
    all_events.extend(fetch_tvmaze_episodes())

    print("Showbizz QC...")
    all_events.extend(fetch_showbizz())

    print("Bell Media / Crave...")
    all_events.extend(fetch_bell_media())

    print("Films TMDb...")
    all_events.extend(fetch_films())

    log(f"Total brut: {len(all_events)} entrees")

    print("\n=== ETAPE 2: ENRICHISSEMENT + VALIDATION VF ===")
    all_events = enrich_all(all_events)

    print("\nFusion et nettoyage...")
    final = merge(all_events)
    final = [e for e in final if in_window(e.get("date","")) and not e.get("_skip")]
    final.sort(key=lambda e: (e.get("date","9999"), e.get("title",""), e.get("ep_num") or 0))

    # Nettoyer champs internes
    for e in final:
        e.pop("_skip", None)
        e.pop("_needs_enrichment", None)
        e.pop("show_id", None)
        e.pop("ep_id", None)
        e.pop("total_eps", None)

    output = {
        "version": "8.0",
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
    sources = {}
    for e in final:
        s = e.get("source","?")
        sources[s] = sources.get(s,0)+1

    print(f"\nTermine! {len(final)} entrees")
    print(f"  Episodes series: {series}")
    print(f"  Films          : {films}")
    print(f"  Disponibles    : {sorti}")
    print(f"  A venir        : {avenir}")
    print(f"  QC             : {qc}")
    print(f"  LGBT+          : {lgbt}")
    print(f"  Par source:")
    for s,n in sorted(sources.items(), key=lambda x:-x[1]):
        print(f"    {s}: {n}")
    print()

if __name__ == "__main__":
    main()
