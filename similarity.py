"""
similarity.py — Core data loading, processing, and similarity computation
for the Euroleague Similarity Explorer.
"""
import warnings, io, base64, gc, time, unicodedata
import requests
import pandas as pd
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib as mpl

warnings.filterwarnings("ignore")

# ─────────────────────── Config ───────────────────────────────
SEASON_CODE  = "E2025"
SEASON_LABEL = "2025/2026"
MIN_GAMES    = 5
_API_V3 = "https://api-live.euroleague.net/v3/competitions/E/statistics/players"
_API_V2 = "https://api-live.euroleague.net/v2/competitions/E/seasons"
_POS_MAP = {1: "G", 2: "F", 3: "C", None: np.nan,
            "Guard": "G", "Forward": "F", "Center": "C"}
_CACHE_TTL = 3600 * 6  # 6 hours

# ─────────────────────── Matplotlib style ─────────────────────
mpl.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "white",
    "savefig.facecolor": "white", "text.color": "black",
    "axes.labelcolor": "black", "xtick.color": "black",
    "ytick.color": "black", "axes.edgecolor": "black",
    "axes.grid": True, "grid.color": "#666666",
    "grid.linestyle": "--", "grid.linewidth": 0.6, "grid.alpha": 0.4,
})

# ─────────────────────── Team metadata ────────────────────────
_BASE_ABBREV = {
    "ALBA BERLIN": "BER", "ANADOLU EFES": "EFS", "AS MONACO": "ASM",
    "AS MONACO BASKET": "ASM", "ASVEL BASKET": "ASV", "ASVEL VILLEURBANNE": "ASV",
    "LDLC ASVEL": "ASV", "AX ARMANI EXCHANGE MILANO": "MIL",
    "OLIMPIA MILANO": "MIL", "EA7 EMPORIO ARMANI MILAN": "MIL",
    "EA7 EMPORIO ARMANI MILANO": "MIL", "BASKONIA": "BAS",
    "BASKONIA VITORIA-GASTEIZ": "BAS", "BAYERN MUNICH": "BAY",
    "FC BAYERN MUNICH": "BAY", "FC BARCELONA": "FCB",
    "FENERBAHCE BEKO": "FEN", "FENERBAHCE BEKO ISTANBUL": "FEN",
    "FENERBAHCE SK": "FEN", "KK CRVENA ZVEZDA": "CZV",
    "KK PARTIZAN": "PAR", "PARTIZAN MOZZART BET BELGRADE": "PAR",
    "MACCABI FOX TEL AVIV": "MAC", "MACCABI TEL AVIV BC": "MAC",
    "MACCABI TEL AVIV": "MAC", "MACCABI RAPYD TEL AVIV": "MAC",
    "OLYMPIACOS": "OLY", "OLYMPIACOS PIRAEUS": "OLY",
    "PANATHINAIKOS": "PAO", "PANATHINAIKOS AKTOR ATHENS": "PAO",
    "PARIS BASKETBALL": "PRS", "REAL MADRID": "RMB",
    "VIRTUS BOLOGNA": "VBO", "ZALGIRIS KAUNAS": "ZAL",
    "BC ZALGIRIS": "ZAL", "HAPOEL TEL AVIV": "HAP",
    "DUBAI BASKETBALL": "DUB", "VALENCIA BASKET": "VAL",
}
_BASE_COLORS = {
    "ALBA BERLIN": "#FFE135", "ANADOLU EFES": "#0074C8", "AS MONACO": "#CE1126",
    "AS MONACO BASKET": "#CE1126", "ASVEL BASKET": "#000000", "ASVEL VILLEURBANNE": "#000000",
    "LDLC ASVEL": "#000000", "AX ARMANI EXCHANGE MILANO": "#C8102E",
    "OLIMPIA MILANO": "#C8102E", "EA7 EMPORIO ARMANI MILAN": "#C8102E",
    "EA7 EMPORIO ARMANI MILANO": "#C8102E", "BASKONIA": "#841617",
    "BASKONIA VITORIA-GASTEIZ": "#841617", "BAYERN MUNICH": "#DC052D",
    "FC BAYERN MUNICH": "#DC052D", "FC BARCELONA": "#004D98",
    "FENERBAHCE BEKO": "#FFED00", "FENERBAHCE BEKO ISTANBUL": "#FFED00",
    "FENERBAHCE SK": "#FFED00", "KK CRVENA ZVEZDA": "#CC0000",
    "KK PARTIZAN": "#000000", "PARTIZAN MOZZART BET BELGRADE": "#000000",
    "MACCABI FOX TEL AVIV": "#FFD700", "MACCABI TEL AVIV BC": "#FFD700",
    "MACCABI TEL AVIV": "#FFD700", "MACCABI RAPYD TEL AVIV": "#FFD700",
    "OLYMPIACOS": "#DC143C", "OLYMPIACOS PIRAEUS": "#DC143C",
    "PANATHINAIKOS": "#006400", "PANATHINAIKOS AKTOR ATHENS": "#006400",
    "PARIS BASKETBALL": "#1A1AFF", "REAL MADRID": "#FABE00",
    "VIRTUS BOLOGNA": "#1C1C1C", "ZALGIRIS KAUNAS": "#007A33",
    "BC ZALGIRIS": "#007A33", "HAPOEL TEL AVIV": "#CC0000",
    "DUBAI BASKETBALL": "#003DA5", "VALENCIA BASKET": "#F47920",
}
_BASE_COLORS2 = {
    "ALBA BERLIN": "#000000", "ANADOLU EFES": "#FFFFFF", "AS MONACO": "#FFFFFF",
    "AS MONACO BASKET": "#FFFFFF", "ASVEL BASKET": "#C8A000", "ASVEL VILLEURBANNE": "#C8A000",
    "LDLC ASVEL": "#C8A000", "AX ARMANI EXCHANGE MILANO": "#000000",
    "OLIMPIA MILANO": "#000000", "EA7 EMPORIO ARMANI MILAN": "#000000",
    "EA7 EMPORIO ARMANI MILANO": "#000000", "BASKONIA": "#FFFFFF",
    "BASKONIA VITORIA-GASTEIZ": "#FFFFFF", "BAYERN MUNICH": "#0066B2",
    "FC BAYERN MUNICH": "#0066B2", "FC BARCELONA": "#A50044",
    "FENERBAHCE BEKO": "#002D62", "FENERBAHCE BEKO ISTANBUL": "#002D62",
    "FENERBAHCE SK": "#002D62", "KK CRVENA ZVEZDA": "#003087",
    "KK PARTIZAN": "#CFB53B", "PARTIZAN MOZZART BET BELGRADE": "#CFB53B",
    "MACCABI FOX TEL AVIV": "#003DA5", "MACCABI TEL AVIV BC": "#003DA5",
    "MACCABI TEL AVIV": "#003DA5", "MACCABI RAPYD TEL AVIV": "#003DA5",
    "OLYMPIACOS": "#FFFFFF", "OLYMPIACOS PIRAEUS": "#FFFFFF",
    "PANATHINAIKOS": "#000000", "PANATHINAIKOS AKTOR ATHENS": "#000000",
    "PARIS BASKETBALL": "#F4A300", "REAL MADRID": "#00529F",
    "VIRTUS BOLOGNA": "#C8A000", "ZALGIRIS KAUNAS": "#FFFFFF",
    "BC ZALGIRIS": "#FFFFFF", "HAPOEL TEL AVIV": "#000000",
    "DUBAI BASKETBALL": "#FFD700", "VALENCIA BASKET": "#000000",
}

# ─────────────────────── Module-level cache ───────────────────
_CACHE = {
    "df": None, "ts": 0.0,
    "col_player": None, "col_team": None, "col_age": None,
    "col_pos": None, "col_nat": None,
    "col_height": None, "col_weight": None,
    "stats_cols": [], "rate_cols": [], "per36_cols": [],
    "basic_num_cols": [],
    "team_abbrev": {}, "team_color": {}, "team_color2": {},
}

# ─────────────────────── API helpers ──────────────────────────
def _headers():
    return {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.euroleaguebasketball.net",
        "Referer": "https://www.euroleaguebasketball.net/euroleague/stats/",
    }

def _safe_float(v):
    try: return float(v)
    except: return np.nan

def _fmt_name(s):
    s = str(s).strip()
    if "," in s:
        parts = [p.strip() for p in s.split(",", 1)]
        return f"{parts[1]} {parts[0]}".title()
    return s.title()

def _clean_team(raw):
    return str(raw).split(";")[-1].strip().upper()

def _norm(s):
    return str(s).strip().lower().replace(" ", "").replace("\t", "")

def _find_col(df, aliases):
    for a in aliases:
        an = _norm(a)
        for c in df.columns:
            if _norm(c) == an: return c
    return None

def _present(df, cols):
    out = []
    for c in cols:
        r = _find_col(df, [c])
        if r: out.append(r)
    return out

def _unique_clean(series):
    s = series.astype(str).str.strip()
    s = s[~s.isin(["", "nan", "None", "NaN", "NONE"])]
    return sorted(pd.unique(s).tolist())

# ─────────────────────── Team helpers ─────────────────────────
def _norm_team(s):
    return " ".join(str(s).upper().split())

def _auto_abbrev(name):
    t = _norm_team(name)
    parts = [p for p in t.replace("-", " ").split() if p.isalpha()]
    if not parts: return (t[:3] + "XXX")[:3]
    skip = {"FC", "KK", "BC", "AS", "LDLC", "EA7", "AX"}
    core = [p for p in parts if p not in skip]
    return ((core[0] if core else parts[-1])[:3]).upper()

def _build_team_maps(teams):
    abbrev, color, color2 = {}, {}, {}
    for t in teams:
        tn = _norm_team(t)
        ab, co, co2 = None, None, None
        for alias, v in _BASE_ABBREV.items():
            an = _norm_team(alias)
            if an in tn or tn in an: ab = v; break
        for alias, v in _BASE_COLORS.items():
            an = _norm_team(alias)
            if an in tn or tn in an: co = v; break
        for alias, v in _BASE_COLORS2.items():
            an = _norm_team(alias)
            if an in tn or tn in an: co2 = v; break
        abbrev[t] = ab or _auto_abbrev(t)
        color[t]  = co or "#777777"
        color2[t] = co2 or "#AAAAAA"
    return abbrev, color, color2

def get_team_color(team):
    return _CACHE["team_color"].get(str(team), "#777777")

def get_team_color2(team):
    return _CACHE["team_color2"].get(str(team), "#AAAAAA")

def get_team_abbrev(team):
    return _CACHE["team_abbrev"].get(str(team), "UNK")

def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _color_dist(c1, c2):
    r1,g1,b1 = _hex_rgb(c1); r2,g2,b2 = _hex_rgb(c2)
    return ((r1-r2)**2+(g1-g2)**2+(b1-b2)**2)**0.5

def _pair_colors(team1, team2):
    c1 = get_team_color(team1); c2 = get_team_color(team2)
    if _color_dist(c1, c2) < 100:
        c2 = get_team_color2(team2)
    return c1, c2

# ─────────────────────── Data fetching ────────────────────────
def _fetch_accumulated(season_code, endpoint):
    resp = requests.get(
        f"{_API_V3}/{endpoint}",
        params={"SeasonCode": season_code, "SeasonMode": "Single",
                "statisticMode": "Accumulated", "limit": 500},
        headers=_headers(), timeout=30
    )
    resp.raise_for_status()
    return {p["player"]["code"]: p for p in resp.json().get("players", []) if "player" in p}

def _fetch_profiles(season_code):
    clubs_resp = requests.get(f"{_API_V2}/{season_code}/clubs", headers=_headers(), timeout=30)
    clubs_resp.raise_for_status()
    clubs_data = clubs_resp.json()
    clubs = clubs_data if isinstance(clubs_data, list) else clubs_data.get("data", clubs_data.get("clubs", []))
    club_codes = [c.get("code") or c.get("clubCode") for c in clubs if isinstance(c, dict)]
    club_codes = [c for c in club_codes if c]
    profiles = {}
    for code in club_codes:
        try:
            r = requests.get(f"{_API_V2}/{season_code}/clubs/{code}/people",
                             headers=_headers(), timeout=20)
            if r.status_code != 200: continue
            people = r.json()
            if isinstance(people, dict):
                people = people.get("data", people.get("people", people.get("players", [])))
            for entry in (people if isinstance(people, list) else []):
                person = entry.get("person", entry)
                pcode  = person.get("code", entry.get("code", ""))
                if not pcode: continue
                country = person.get("country", {})
                nat = country.get("code", "") if isinstance(country, dict) else str(country)
                h_raw = person.get("height", np.nan)
                try:
                    h = float(h_raw)
                    height_m = h / 100 if h > 10 else h
                except: height_m = np.nan
                pos_num  = entry.get("position")
                pos_name = entry.get("positionName", "")
                pos = _POS_MAP.get(pos_num, _POS_MAP.get(pos_name, np.nan))
                profiles[pcode] = {
                    "nat": str(nat).strip().upper() if nat else np.nan,
                    "pos": pos, "height_m": height_m,
                    "weight_kg": _safe_float(person.get("weight")),
                }
        except Exception: pass
    return profiles

def _fetch_players(season_code=SEASON_CODE, min_games=MIN_GAMES):
    trad = _fetch_accumulated(season_code, "traditional")
    try: adv     = _fetch_accumulated(season_code, "advanced")
    except: adv  = {}
    try: misc    = _fetch_accumulated(season_code, "misc")
    except: misc = {}
    try: scoring = _fetch_accumulated(season_code, "scoring")
    except: scoring = {}
    profiles = _fetch_profiles(season_code)
    records = []
    for code, p in trad.items():
        pl   = p.get("player", {}); team = pl.get("team", {})
        gp   = _safe_float(p.get("gamesPlayed"))
        if np.isnan(gp) or gp < min_games: continue
        def _pg(val):
            v = _safe_float(val); return v/gp if (not np.isnan(v) and gp > 0) else np.nan
        fg2  = _safe_float(p.get("twoPointersMade"))
        fg2a = _safe_float(p.get("twoPointersAttempted"))
        fg3  = _safe_float(p.get("threePointersMade"))
        fg3a = _safe_float(p.get("threePointersAttempted"))
        fg_t  = fg2+fg3 if not(np.isnan(fg2) or np.isnan(fg3)) else np.nan
        fga_t = fg2a+fg3a if not(np.isnan(fg2a) or np.isnan(fg3a)) else np.nan
        fgp   = fg_t/fga_t if (not np.isnan(fga_t) and fga_t > 0) else np.nan
        fg3p  = fg3/fg3a   if (not np.isnan(fg3a) and fg3a > 0) else np.nan
        fg2p  = fg2/fg2a   if (not np.isnan(fg2a) and fg2a > 0) else np.nan
        ft    = _safe_float(p.get("freeThrowsMade"))
        fta   = _safe_float(p.get("freeThrowsAttempted"))
        ftp   = ft/fta if (not np.isnan(fta) and fta > 0) else np.nan
        efgp  = (fg_t+0.5*fg3)/fga_t if (not np.isnan(fga_t) and fga_t > 0) else np.nan
        prof  = profiles.get(code, {})
        _h = prof.get("height_m", np.nan)
        _h_cm = round(_h * 100) if (not isinstance(_h, float) or not np.isnan(_h)) and _h and _h > 0 else np.nan
        pa = adv.get(code, {});  pm = misc.get(code, {});  ps = scoring.get(code, {})
        _w = _safe_float(pm.get("wins")); _l = _safe_float(pm.get("losses"))
        win_pct = _w/(_w+_l) if (not np.isnan(_w) and not np.isnan(_l) and (_w+_l)>0) else np.nan
        rec = {
            # ── Identity ──────────────────────────────────────────
            "Player": _fmt_name(pl.get("name", "")),
            "Team":   _clean_team(team.get("name", "")),
            "Age":    _safe_float(pl.get("age")),
            "Nationality": prof.get("nat", np.nan),
            "Pos":    prof.get("pos", np.nan),
            "Height": _h_cm,
            "Weight": prof.get("weight_kg", np.nan),
            # ── Traditional (box score per game) ──────────────────
            "G": gp, "GS": _safe_float(p.get("gamesStarted")),
            "MP": _pg(p.get("minutesPlayed")),
            "FG": _pg(fg_t), "FGA": _pg(fga_t), "FG%": fgp,
            "3P": _pg(fg3),  "3PA": _pg(fg3a),  "3P%": fg3p,
            "2P": _pg(fg2),  "2PA": _pg(fg2a),  "2P%": fg2p, "eFG%": efgp,
            "FT": _pg(ft),   "FTA": _pg(fta),   "FT%": ftp,
            "ORB": _pg(p.get("offensiveRebounds")), "DRB": _pg(p.get("defensiveRebounds")),
            "TRB": _pg(p.get("totalRebounds")),
            "AST": _pg(p.get("assists")), "STL": _pg(p.get("steals")),
            "BLK": _pg(p.get("blocks")),  "BKA": _pg(p.get("blocksAgainst")),
            "TOV": _pg(p.get("turnovers")), "PF": _pg(p.get("foulsCommited")),
            "FD":  _pg(p.get("foulsDrawn")), "PTS": _pg(p.get("pointsScored")),
            "PIR": _safe_float(p.get("pir")),
            # ── Advanced (possession-adjusted from API) ───────────
            "ORB%":  _safe_float(pa.get("offensiveReboundsPercentage")),
            "DRB%":  _safe_float(pa.get("defensiveReboundsPercentage")),
            "REB%":  _safe_float(pa.get("reboundsPercentage")),
            "AST%":  _safe_float(pa.get("assistsRatio")),
            "TOV%":  _safe_float(pa.get("turnoversRatio")),
            "A2T":   _safe_float(pa.get("assistsToTurnoversRatio")),
            "POSS":  _safe_float(pa.get("possesions")),
            # ── Misc ──────────────────────────────────────────────
            "WIN%":  win_pct,
            "DD":    _safe_float(pm.get("doubleDoubles")),
            "TD3":   _safe_float(pm.get("tripleDoubles")),
            # ── Scoring distribution ──────────────────────────────
            "PTS_2P%": _safe_float(ps.get("pointsFromTwoPointersPercentage")),
            "PTS_3P%": _safe_float(ps.get("pointsFromThreePointersPercentage")),
            "PTS_FT%": _safe_float(ps.get("pointsFromFreeThrowsPercentage")),
            "2PA_SH":  _safe_float(ps.get("twoPointAttemptsShare")),
            "3PA_SH":  _safe_float(ps.get("threePointAttemptsShare")),
            "2PT_R":   _safe_float(ps.get("twoPointRate")),
            "3PT_R":   _safe_float(ps.get("threePointRate")),
        }
        if rec["Player"]: records.append(rec)
    df = pd.DataFrame(records)
    del records; gc.collect()
    return df[df["Player"].str.strip().ne("")].reset_index(drop=True)

# ─────────────────────── Data processing ──────────────────────
def _process(df_raw):
    colmap = {c: _norm(c) for c in df_raw.columns}
    dt = df_raw.rename(columns=colmap).copy(); del df_raw; gc.collect()

    col_player = _find_col(dt, ["Player"])
    col_team   = _find_col(dt, ["Team"])
    col_age    = _find_col(dt, ["Age", "Edad"])
    col_pos    = _find_col(dt, ["Pos", "Position"])
    col_nat    = _find_col(dt, ["Nationality", "Country", "Nat"])
    col_height = _find_col(dt, ["Height"])
    col_weight = _find_col(dt, ["Weight"])

    if col_age:    dt[col_age]    = pd.to_numeric(dt[col_age], errors="coerce")
    if col_height: dt[col_height] = pd.to_numeric(dt[col_height], errors="coerce")
    if col_weight: dt[col_weight] = pd.to_numeric(dt[col_weight], errors="coerce")
    if col_pos:
        dt[col_pos] = dt[col_pos].astype(str).str.strip()
        dt.loc[dt[col_pos].isin(["nan","None","NONE","NaN"]), col_pos] = np.nan
    if col_nat:
        dt[col_nat] = dt[col_nat].astype(str).str.strip().str.upper()
        dt.loc[dt[col_nat].isin(["","NAN","NONE"]), col_nat] = np.nan

    basic_names = ["G","GS","MP","FG","FGA","FG%","3P","3PA","3P%","2P","2PA","2P%","EFG%",
                   "FT","FTA","FT%","ORB","DRB","TRB","AST","STL","BLK","BKA","TOV","PF","FD","PTS","PIR",
                   "ORB%","DRB%","REB%","AST%","TOV%","A2T","POSS","WIN%","DD","TD3",
                   "PTS_2P%","PTS_3P%","PTS_FT%","2PA_SH","3PA_SH","2PT_R","3PT_R"]
    for name in basic_names:
        c = _find_col(dt, [name])
        if c: dt[c] = pd.to_numeric(dt[c], errors="coerce")

    def _sdiv(a, b): return a / b.replace(0, np.nan)
    c_FG  = _find_col(dt, ["FG"]); c_3P  = _find_col(dt, ["3P"])
    c_FGA = _find_col(dt, ["FGA"]); c_PTS = _find_col(dt, ["PTS"])
    c_FTA = _find_col(dt, ["FTA"]); c_TOV = _find_col(dt, ["TOV"])
    c_MP  = _find_col(dt, ["MP"])

    if c_FG and c_3P and c_FGA and not _find_col(dt, ["EFG%"]):
        dt["EFG%"] = (dt[c_FG]+0.5*dt[c_3P]) / dt[c_FGA]
    if c_PTS and c_FGA and c_FTA:
        dt["TS%"] = dt[c_PTS] / (2*(dt[c_FGA]+0.44*dt[c_FTA]).replace(0, np.nan))
    if c_3P and c_FGA: dt["3PAR"] = _sdiv(dt[c_3P], dt[c_FGA])
    if c_FTA and c_FGA: dt["FTR"] = _sdiv(dt[c_FTA], dt[c_FGA])
    if c_TOV and c_FGA and c_FTA:
        dt["TOV%_SHOOT"] = dt[c_TOV]/((dt[c_FGA]+0.44*dt[c_FTA]+dt[c_TOV]).replace(0, np.nan))

    for c in ["FG%","3P%","2P%","EFG%","FT%","TS%","3PAR","FTR","TOV%_SHOOT"]:
        if c in dt.columns: dt[c] = dt[c].clip(0, 1)

    for base in ["FG","FGA","3P","3PA","2P","2PA","FT","FTA","ORB","DRB","TRB","AST","STL","BLK","BKA","TOV","PF","FD","PTS"]:
        cb = _find_col(dt, [base])
        if cb and c_MP: dt[f"{base}_per36"] = (dt[cb]*36)/dt[c_MP].replace(0, np.nan)

    # GS% (starter rate) — useful filter proxy
    c_GS = _find_col(dt, ["GS"]); c_G = _find_col(dt, ["G"])
    if c_GS and c_G: dt["GS%"] = (dt[c_GS] / dt[c_G].replace(0, np.nan)).clip(0, 1)

    _num = dt.select_dtypes("float64").columns
    dt[_num] = dt[_num].astype("float32"); gc.collect()

    rate_cols  = _present(dt, ["FG%","3P%","2P%","EFG%","FT%","TS%","3PAR","FTR","TOV%_SHOOT"])
    per36_cols = _present(dt, [f"{c}_per36" for c in ["PTS","AST","TRB","STL","BLK","BKA","TOV","3P","FTA","FD"]])
    adv_cols   = _present(dt, ["ORB%","DRB%","REB%","AST%","TOV%","A2T","GS%"])
    score_cols = _present(dt, ["PTS_2P%","PTS_3P%","PTS_FT%","2PA_SH","3PA_SH","2PT_R","3PT_R"])
    stats_cols = rate_cols + per36_cols + adv_cols + score_cols
    basic_num_cols = _present(dt, basic_names)

    dt["Team"]   = dt[col_team]
    dt["Player"] = dt[col_player]
    dt["Team3"]  = dt["Team"].map(lambda t: _CACHE["team_abbrev"].get(t, "UNK"))

    return dt, col_player, col_team, col_age, col_pos, col_nat, col_height, col_weight, stats_cols, rate_cols, per36_cols, basic_num_cols

# ─────────────────────── Public: load_data ────────────────────
def load_data(force=False):
    now = time.time()
    if not force and _CACHE["df"] is not None and (now - _CACHE["ts"]) < _CACHE_TTL:
        return
    print("Loading EuroLeague data…")
    df_raw = _fetch_players()
    teams = sorted(df_raw["Team"].dropna().unique().tolist())
    ab, co, co2 = _build_team_maps(teams)
    _CACHE["team_abbrev"] = ab; _CACHE["team_color"] = co; _CACHE["team_color2"] = co2
    dt, *rest = _process(df_raw)
    (_CACHE["col_player"], _CACHE["col_team"], _CACHE["col_age"],
     _CACHE["col_pos"], _CACHE["col_nat"],
     _CACHE["col_height"], _CACHE["col_weight"],
     _CACHE["stats_cols"], _CACHE["rate_cols"],
     _CACHE["per36_cols"], _CACHE["basic_num_cols"]) = rest
    _CACHE["df"] = dt
    _CACHE["ts"] = now
    print(f"Loaded {len(dt)} players.")

def _df():
    if _CACHE["df"] is None: load_data()
    return _CACHE["df"]

# ─────────────────────── Public: filter options ───────────────
def get_filter_options(team="", pos="", nat="", age_min=0, age_max=99,
                       height_min=0, height_max=999):
    dt = _df()
    cp = _CACHE["col_pos"]; cn = _CACHE["col_nat"]; ca = _CACHE["col_age"]
    ch = _CACHE["col_height"]
    teams         = sorted(dt["Team"].dropna().unique().tolist())
    positions     = _unique_clean(dt[cp]) if cp else []
    nationalities = _unique_clean(dt[cn]) if cn else []
    age_lo  = int(dt[ca].min()) if ca and dt[ca].notna().any() else 16
    age_hi  = int(dt[ca].max()) if ca and dt[ca].notna().any() else 45
    h_lo    = int(dt[ch].min()) if ch and dt[ch].notna().any() else 170
    h_hi    = int(dt[ch].max()) if ch and dt[ch].notna().any() else 220
    players = _filtered_players(dt, team, pos, nat,
                                age_min or age_lo, age_max or age_hi,
                                height_min or h_lo, height_max or h_hi)
    return {"teams": teams, "positions": positions, "nationalities": nationalities,
            "age_min": age_lo, "age_max": age_hi,
            "height_min": h_lo, "height_max": h_hi,
            "players": players}

def _filtered_players(dt, team, pos, nat, age_min, age_max, height_min=0, height_max=999):
    mask = pd.Series(True, index=dt.index)
    cp = _CACHE["col_pos"]; cn = _CACHE["col_nat"]; ca = _CACHE["col_age"]
    ch = _CACHE["col_height"]
    if team: mask &= (dt["Team"] == team)
    if pos and cp:  mask &= (dt[cp] == pos)
    if nat and cn:  mask &= (dt[cn] == nat)
    if ca:
        mask &= (dt[ca].fillna(0) >= age_min) & (dt[ca].fillna(999) <= age_max)
    if ch and height_min > 0:
        mask &= (dt[ch].fillna(0) >= height_min) & (dt[ch].fillna(999) <= height_max)
    return sorted(dt.loc[mask, "Player"].dropna().unique().tolist())

def _filtered_df_for_pca(dt, pos, nat, age_min, age_max, height_min=0, height_max=999):
    """PCA uses pos/nat/age/height filter but NOT team filter (wider population)."""
    mask = pd.Series(True, index=dt.index)
    cp = _CACHE["col_pos"]; cn = _CACHE["col_nat"]; ca = _CACHE["col_age"]
    ch = _CACHE["col_height"]
    if pos and cp:  mask &= (dt[cp] == pos)
    if nat and cn:  mask &= (dt[cn] == nat)
    if ca:
        mask &= (dt[ca].fillna(0) >= age_min) & (dt[ca].fillna(999) <= age_max)
    if ch and height_min > 0:
        mask &= (dt[ch].fillna(0) >= height_min) & (dt[ch].fillna(999) <= height_max)
    return dt[mask].copy()

# ─────────────────────── PCA similarity ───────────────────────
def _compute_sim(filtered_df):
    from sklearn.preprocessing import StandardScaler, normalize
    from sklearn.decomposition import PCA
    from sklearn.impute import SimpleImputer
    stats_cols = _CACHE["stats_cols"]
    use_cols = [c for c in stats_cols if c in filtered_df.columns]
    if not use_cols: raise ValueError("No feature columns available.")
    X = filtered_df[use_cols].values
    X = SimpleImputer(strategy="median").fit_transform(X)
    X = StandardScaler().fit_transform(X)
    ncomp = max(2, min(X.shape[1], int(max(2, 0.9*min(X.shape)))))
    Z = PCA(n_components=ncomp, svd_solver="randomized", random_state=42).fit_transform(X)
    Z = normalize(Z, norm="l2", axis=1)
    S = np.clip(Z @ Z.T, -1, 1); del Z
    sim = pd.DataFrame(S, index=filtered_df["Player"], columns=filtered_df["Player"]); del S
    gc.collect()
    return sim

# ─────────────────────── Public: compute_similar ──────────────
def compute_similar(player, team="", pos="", nat="", age_min=0, age_max=99,
                    height_min=0, height_max=999, k=5, include_same=False):
    dt = _df()
    if player not in dt["Player"].values:
        raise ValueError(f"Player '{player}' not found.")
    d = _filtered_df_for_pca(dt, pos, nat, age_min or 0, age_max or 99,
                              height_min or 0, height_max or 999)
    if player not in d["Player"].values:
        extra = dt[dt["Player"] == player]
        d = pd.concat([d, extra], ignore_index=True).drop_duplicates("Player")
    sim = _compute_sim(d)
    s = sim.loc[player].drop(labels=[player], errors="ignore").sort_values(ascending=False)
    if not include_same:
        team_map = d.drop_duplicates("Player").set_index("Player")["Team"]
        tp = team_map.get(player)
        if tp: s = s[s.index.map(lambda p: team_map.get(p) != tp)]
    top = s.head(k)
    uniq = dt.drop_duplicates("Player").set_index("Player")
    cp = _CACHE["col_pos"]; cn = _CACHE["col_nat"]; ca = _CACHE["col_age"]
    ch = _CACHE["col_height"]; cw = _CACHE["col_weight"]
    c_pir  = _find_col(dt, ["PIR"])
    c_gs   = _find_col(dt, ["GS%"])
    c_win  = _find_col(dt, ["WIN%"])

    def _val(col, pname, cast=float):
        if col and pname in uniq.index and pd.notna(uniq.loc[pname, col]):
            try: return cast(uniq.loc[pname, col])
            except: pass
        return None

    results = []
    for pname, corr in top.items():
        results.append({
            "player":          pname,
            "team":            uniq.loc[pname, "Team"] if pname in uniq.index else "",
            "position":        str(uniq.loc[pname, cp]) if (cp and pname in uniq.index) else "",
            "age":             _val(ca, pname),
            "nationality":     str(uniq.loc[pname, cn]) if (cn and pname in uniq.index) else "",
            "height":          _val(ch, pname, int),
            "weight":          _val(cw, pname, int),
            "pir":             round(_val(c_pir, pname) / _val(_find_col(dt,["G"]), pname), 2) if (_val(c_pir, pname) and _val(_find_col(dt,["G"]), pname)) else None,
            "starter_pct":     round(_val(c_gs, pname) * 100) if _val(c_gs, pname) is not None else None,
            "win_pct":         round(_val(c_win, pname) * 100) if _val(c_win, pname) is not None else None,
            "correlation_pct": float(np.clip(corr, -1, 1)) * 100.0,
        })
    return {"player": player, "similar": results}

# ─────────────────────── Public: get_player_stats ────────────
def get_player_stats(p1, p2):
    dt = _df()
    for p in [p1, p2]:
        if p not in dt["Player"].values:
            raise ValueError(f"Player '{p}' not found.")
    uniq = dt.drop_duplicates("Player").set_index("Player")

    def _v(player, col_aliases):
        c = _find_col(dt, col_aliases)
        if c and player in uniq.index and pd.notna(uniq.loc[player, c]):
            return float(uniq.loc[player, c])
        return None

    def _fmt(v, dec=1):
        return round(v, dec) if v is not None else None

    def _pct(v):
        return round(v * 100, 1) if v is not None else None

    def _pir_pg(player):
        pir = _v(player, ["PIR"]); g = _v(player, ["G"])
        return round(pir / g, 2) if (pir and g) else None

    rows = [
        # label, p1_val, p2_val, higher_is_better
        ("G",       _fmt(_v(p1,["G"]),0),    _fmt(_v(p2,["G"]),0),    True),
        ("MIN/G",   _fmt(_v(p1,["MP"])),     _fmt(_v(p2,["MP"])),     True),
        ("PTS",     _fmt(_v(p1,["PTS"])),    _fmt(_v(p2,["PTS"])),    True),
        ("AST",     _fmt(_v(p1,["AST"])),    _fmt(_v(p2,["AST"])),    True),
        ("TRB",     _fmt(_v(p1,["TRB"])),    _fmt(_v(p2,["TRB"])),    True),
        ("ORB",     _fmt(_v(p1,["ORB"])),    _fmt(_v(p2,["ORB"])),    True),
        ("DRB",     _fmt(_v(p1,["DRB"])),    _fmt(_v(p2,["DRB"])),    True),
        ("STL",     _fmt(_v(p1,["STL"])),    _fmt(_v(p2,["STL"])),    True),
        ("BLK",     _fmt(_v(p1,["BLK"])),    _fmt(_v(p2,["BLK"])),    True),
        ("TOV",     _fmt(_v(p1,["TOV"])),    _fmt(_v(p2,["TOV"])),    False),
        ("FD",      _fmt(_v(p1,["FD"])),     _fmt(_v(p2,["FD"])),     True),
        ("FG%",     _pct(_v(p1,["FG%"])),    _pct(_v(p2,["FG%"])),    True),
        ("3P%",     _pct(_v(p1,["3P%"])),    _pct(_v(p2,["3P%"])),    True),
        ("2P%",     _pct(_v(p1,["2P%"])),    _pct(_v(p2,["2P%"])),    True),
        ("FT%",     _pct(_v(p1,["FT%"])),    _pct(_v(p2,["FT%"])),    True),
        ("eFG%",    _pct(_v(p1,["EFG%","eFG%"])), _pct(_v(p2,["EFG%","eFG%"])), True),
        ("TS%",     _pct(_v(p1,["TS%"])),    _pct(_v(p2,["TS%"])),    True),
        ("AST%",    _pct(_v(p1,["AST%"])),   _pct(_v(p2,["AST%"])),   True),
        ("TOV%",    _pct(_v(p1,["TOV%"])),   _pct(_v(p2,["TOV%"])),   False),
        ("ORB%",    _pct(_v(p1,["ORB%"])),   _pct(_v(p2,["ORB%"])),   True),
        ("DRB%",    _pct(_v(p1,["DRB%"])),   _pct(_v(p2,["DRB%"])),   True),
        ("A/T",     _fmt(_v(p1,["A2T"]),2),  _fmt(_v(p2,["A2T"]),2),  True),
        ("PIR/G",   _pir_pg(p1),             _pir_pg(p2),             True),
        ("WIN%",    _pct(_v(p1,["WIN%"])),   _pct(_v(p2,["WIN%"])),   True),
        ("START%",  _pct(_v(p1,["GS%"])),    _pct(_v(p2,["GS%"])),    True),
    ]
    return {
        "p1": p1, "p2": p2,
        "rows": [{"label": r[0], "p1": r[1], "p2": r[2], "higher_is_better": r[3]} for r in rows]
    }

# ─────────────────────── Chart helpers ────────────────────────
def _fig_b64(fig, dpi=150):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")

def _pct_vec(row, population):
    out = []
    for c in row.index:
        col_pop = population[c].dropna().values
        if len(col_pop) == 0 or pd.isna(row[c]): out.append(np.nan)
        else: out.append((np.sum(col_pop <= row[c]) / len(col_pop)) * 100.0)
    return pd.Series(out, index=row.index)

def _pal(cols, dt):
    uniq = dt.drop_duplicates("Player").set_index("Player")
    return [get_team_color(uniq.loc[c, "Team"] if c in uniq.index else "") for c in cols]

# ─────────────────────── Public: get_correlation ──────────────
def get_correlation(p1, p2):
    """Return the PCA cosine similarity (0-100) between two players, no filters."""
    dt = _df()
    for p in [p1, p2]:
        if p not in dt["Player"].values:
            raise ValueError(f"Player '{p}' not found.")
    sim = _compute_sim(dt)
    if p1 in sim.index and p2 in sim.columns:
        return round(float(np.clip(sim.loc[p1, p2], -1, 1)) * 100.0, 2)
    return None

# ─────────────────────── Public: generate_charts ──────────────
def generate_charts(p1, p2):
    dt = _df()
    for p in [p1, p2]:
        if p not in dt["Player"].values:
            raise ValueError(f"Player '{p}' not found.")
    basic_names = ["G","MP","FG","FGA","FG%","3P","3PA","3P%","2P","2PA","2P%","EFG%",
                   "FT","FTA","FT%","ORB","DRB","TRB","AST","STL","BLK","TOV","PF","PTS"]
    basic_cols  = _present(dt, basic_names)
    rate_cols   = _CACHE["rate_cols"]
    per36_cols  = _CACHE["per36_cols"]

    uniq = dt.drop_duplicates("Player").set_index("Player")
    team1 = uniq.loc[p1, "Team"] if p1 in uniq.index else ""
    team2 = uniq.loc[p2, "Team"] if p2 in uniq.index else ""
    c1, c2 = _pair_colors(team1, team2)

    pair = dt[dt["Player"].isin([p1, p2])].drop_duplicates("Player").set_index("Player").reindex([p1, p2])
    pal = [c1, c2]
    charts = {}

    # 1. Games & Minutes
    gm_cols = _present(pair.reset_index().rename(columns={"index":"Player"}), ["G","MP"])
    if gm_cols:
        fig, ax = plt.subplots(figsize=(7, 3.5))
        sub = pair[gm_cols].T; sub.index = [c.upper() for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_title("Games & Minutes", pad=8); ax.set_ylim(0, sub.values.max()*1.15 if sub.size else 1)
        ax.legend([p1, p2], loc="upper right"); plt.xticks(rotation=0); plt.tight_layout()
        charts["games_minutes"] = _fig_b64(fig)

    # 2. Basic Percentages
    pct_targets = ["FG%","3P%","2P%","EFG%","FT%","TS%"]
    pct_cols = _present(pair.reset_index().rename(columns={"index":"Player"}), pct_targets)
    pct_cols = [c for c in pct_cols if c in pair.columns]
    if pct_cols:
        fig, ax = plt.subplots(figsize=(8, 3.8))
        sub = pair[pct_cols].T; sub.index = [c.upper() for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, 1.0); ax.set_title("Basic — Percentages", pad=8)
        ax.legend([p1, p2], loc="upper right"); plt.xticks(rotation=0); plt.tight_layout()
        charts["percentages"] = _fig_b64(fig)

    # 3. Per-game volumes
    vol_targets = ["FG","FGA","3P","3PA","FT","FTA","TRB","AST","STL","BLK","TOV","PF","PTS"]
    vol_cols = [c for c in _present(pair.reset_index().rename(columns={"index":"Player"}), vol_targets) if c in pair.columns]
    if vol_cols:
        fig, ax = plt.subplots(figsize=(9.5, 4))
        sub = pair[vol_cols].T; sub.index = [c.upper() for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, sub.values.max()*1.15 if sub.size else 1)
        ax.set_title("Basic — Per-game volumes", pad=8)
        ax.legend([p1, p2], loc="upper right"); plt.xticks(rotation=45, ha="right"); plt.tight_layout()
        charts["volumes"] = _fig_b64(fig)

    # 4. Advanced Ratios
    ratio_targets = ["3PAR","FTR","TOV%_SHOOT"]
    ratio_cols = [c for c in _present(pair.reset_index().rename(columns={"index":"Player"}), ratio_targets) if c in pair.columns]
    if ratio_cols:
        fig, ax = plt.subplots(figsize=(7, 3.5))
        sub = pair[ratio_cols].T; sub.index = [c.upper() for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, 1.0); ax.set_title("Advanced — Ratios", pad=8)
        ax.legend([p1, p2], loc="upper right"); plt.xticks(rotation=0); plt.tight_layout()
        charts["ratios"] = _fig_b64(fig)

    # 5. Per 36
    p36_cols = [c for c in per36_cols if c in pair.columns]
    if p36_cols:
        fig, ax = plt.subplots(figsize=(9, 3.8))
        sub = pair[p36_cols].T
        sub.index = [c[:-7].upper()+"_P36" for c in sub.index]
        sub.plot(kind="bar", ax=ax, color=pal)
        ax.set_ylim(0, sub.values.max()*1.15 if sub.size else 1)
        ax.set_title("Advanced — Per 36 minutes", pad=8)
        ax.legend([p1, p2], loc="upper right"); plt.xticks(rotation=45, ha="right"); plt.tight_layout()
        charts["per36"] = _fig_b64(fig)

    # 6. Radar — global percentiles
    radar_names = ["FG","FGA","3P","3PA","FT","FTA","TRB","STL","AST","TOV","BLK","PTS"]
    radar_cols = _present(pair.reset_index().rename(columns={"index":"Player"}), radar_names)
    radar_cols = [c for c in radar_cols if c in pair.columns and c in dt.columns]
    if radar_cols and len(radar_cols) >= 3:
        pop = dt[radar_cols]
        vals1 = _pct_vec(pair.loc[p1, radar_cols], pop).values.tolist()
        vals2 = _pct_vec(pair.loc[p2, radar_cols], pop).values.tolist()
        labels = [c.upper() for c in radar_cols]
        vals1 += [vals1[0]]; vals2 += [vals2[0]]
        angles = np.linspace(0, 2*np.pi, len(labels), endpoint=False).tolist() + [0]
        fig = plt.figure(figsize=(4.0, 4.0))
        ax  = plt.subplot(111, polar=True)
        ax.set_theta_offset(np.pi/2); ax.set_theta_direction(-1)
        ax.set_facecolor("#f4f6fa")
        ax.set_xticks(angles[:-1], labels)
        ax.set_ylim(0, 100); ax.set_yticks([0,20,40,60,80,100])
        ax.plot(angles, vals1, linewidth=2.5, color=c1, label=p1)
        ax.fill(angles, vals1, color=c1, alpha=0.25)
        ax.plot(angles, vals2, linewidth=2.5, color=c2, label=p2)
        ax.fill(angles, vals2, color=c2, alpha=0.25)
        ax.grid(color="gray", linestyle="dotted", alpha=0.5)
        ax.set_title("Radar — Global percentiles (0–100)", pad=10, fontweight="bold", fontsize=8)
        ax.tick_params(labelsize=6)
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.12), ncol=2, frameon=False, fontsize=7)
        plt.tight_layout()
        charts["radar"] = _fig_b64(fig)

    return {
        "player1": p1, "player2": p2,
        "team1": team1, "team2": team2,
        "charts": charts,
    }
