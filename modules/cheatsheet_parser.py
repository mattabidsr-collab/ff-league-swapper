import pdfplumber
import pandas as pd
import re

CLEAN_TEAM = {
    "JAX":"JAC","JAX.":"JAC","WSH":"WAS","LA":"LAR","LAC":"LAC","LV":"LV","SF":"SF","TB":"TB",
    "NE":"NE","NO":"NO","NYJ":"NYJ","NYG":"NYG","GB":"GB","KC":"KC","BUF":"BUF","MIA":"MIA","DAL":"DAL",
    "PHI":"PHI","MIN":"MIN","DET":"DET","CHI":"CHI","ATL":"ATL","CAR":"CAR","SEA":"SEA","ARI":"ARI",
    "CLE":"CLE","CIN":"CIN","PIT":"PIT","BAL":"BAL","TEN":"TEN","HOU":"HOU","IND":"IND","DEN":"DEN",
    "LAR":"LAR","WAS":"WAS"
}

POS_RE  = re.compile(r'\b(QB|RB|WR|TE|K|DST|D/ST)\b')
TEAM_RE = re.compile(r'\b([A-Z]{2,3})\b')
BYE_RE  = re.compile(r'\b(?:Bye|BYE)\s*(\d{1,2})\b')

def _clean_cell(x):
    if x is None: return ""
    return str(x).strip().replace("\n", " ")

def _normalize_team(tok):
    tok = tok.strip(".").upper()
    return CLEAN_TEAM.get(tok, tok)

# ---------------------------
# TEXT-MODE FALLBACK PARSER
# ---------------------------
# Tries to match lines like:
#  12  Bijan Robinson  ATL  RB  Bye 5  56
#  Ja'Marr Chase  CIN  WR  Bye 10  (no value)
LINE_RE = re.compile(
    r"""
    ^\s*
    (?:(?P<rank>\d{1,3})\s+)?                         # optional rank at line start
    (?P<name>[A-Za-z][A-Za-z\.\- '\u2019]+?)\s+       # player name (allow apostrophes/hyphens)
    (?P<team>[A-Z]{2,3})\s+                           # NFL team code
    (?P<pos>QB|RB|WR|TE|K|DST|D/ST)\b                 # position
    (?:.*?\b(?:Bye|BYE)\s*(?P<bye>\d{1,2}))?          # optional Bye
    (?:.*?\b(?P<value>\d{1,3}(?:\.\d+)?))?            # optional trailing numeric (auction/value)
    \s*$
    """, re.VERBOSE
)

def _parse_text_block(text: str, assume_has_value: bool=False) -> pd.DataFrame:
    rows = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        m = LINE_RE.search(line)
        if not m:
            # Looser heuristic: require pos token somewhere and at least a team token
            if POS_RE.search(line) and TEAM_RE.search(line):
                # crude token pass
                pos_m = POS_RE.search(line)
                pos = pos_m.group(1).replace("D/ST","DST")
                team = None
                for cand in TEAM_RE.findall(line):
                    cand2 = _normalize_team(cand)
                    if cand2 in CLEAN_TEAM.values():
                        team = cand2
                # name: largest non-numeric chunk before team token
                name = None
                for chunk in [c.strip() for c in line.split()]:
                    if chunk.isdigit(): continue
                    if chunk.upper() in CLEAN_TEAM: continue
                    if chunk.upper() in CLEAN_TEAM.values(): continue
                    if chunk.upper() in ("QB","RB","WR","TE","K","DST","D/ST","BYE"): continue
                    name = chunk if not name else f"{name} {chunk}"
                if name and team:
                    bye_m = BYE_RE.search(line)
                    bye = int(bye_m.group(1)) if bye_m else None
                    value = None
                    if assume_has_value:
                        tail_nums = re.findall(r'(\d{1,3}(?:\.\d+)?)\s*$', line)
                        if tail_nums:
                            try:
                                v = float(tail_nums[-1])
                                if 0 < v < 1000: value = v
                            except: pass
                    # rank (optional) at start
                    rank = None
                    start_num = re.match(r'^\s*(\d{1,3})\b', line)
                    if start_num:
                        try: rank = int(start_num.group(1))
                        except: pass
                    rows.append({"rank":rank,"name":name,"team":team,"pos":pos,"bye":bye,"value":value})
            continue
        gd = m.groupdict()
        pos = gd["pos"].replace("D/ST","DST")
        team = _normalize_team(gd["team"])
        rank = int(gd["rank"]) if gd["rank"] else None
        bye  = int(gd["bye"])  if gd["bye"]  else None
        value = float(gd["value"]) if (assume_has_value and gd["value"]) else None
        rows.append({"rank":rank,"name":gd["name"].strip(),"team":team,"pos":pos,"bye":bye,"value":value})
    df = pd.DataFrame(rows).drop_duplicates(subset=["name","team","pos"])
    return df

# ---------------------------
# TABLE PARSER (existing)
# ---------------------------
def parse_cheatsheet_pdf(path: str, assume_has_value: bool=False) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            try:
                tables = page.extract_tables() or []
            except Exception:
                tables = []
            for tbl in tables:
                if not tbl or len(tbl) < 3:
                    continue
                for r in tbl:
                    cells = [_clean_cell(c) for c in r]
                    line = " | ".join(cells)
                    mpos = POS_RE.search(line)
                    if not mpos:
                        continue
                    rank = None
                    for c in cells:
                        if c.isdigit():
                            rank = int(c); break
                    name, team, bye, value = None, None, None, None
                    mt = TEAM_RE.findall(line)
                    if mt:
                        for cand in mt:
                            cand2 = _normalize_team(cand)
                            if cand2 in CLEAN_TEAM.values():
                                team = cand2
                    mb = BYE_RE.search(line)
                    if mb:
                        try: bye = int(mb.group(1))
                        except: bye = None
                    pos = mpos.group(1).replace("D/ST","DST")
                    for c in cells:
                        if not c or c.isdigit(): continue
                        if POS_RE.search(c): continue
                        if "Bye" in c or "BYE" in c: continue
                        if len(c.split())>=2:
                            name = c; break
                    if assume_has_value:
                        for c in reversed(cells):
                            try:
                                if c and c.replace('.','',1).isdigit():
                                    valf = float(c)
                                    if 0 < valf < 1000:
                                        value = valf; break
                            except: pass
                    if name and pos and team:
                        rows.append({"rank":rank,"name":name,"team":team,"pos":pos,"bye":bye,"value":value})
    df = pd.DataFrame(rows).drop_duplicates(subset=["name","team","pos"])

    # >>> FALLBACK: if table parse failed, try text parse
    if df.empty:
        with pdfplumber.open(path) as pdf:
            text = "\n".join([p.extract_text() or "" for p in pdf.pages])
        df = _parse_text_block(text, assume_has_value=assume_has_value)
    return df
