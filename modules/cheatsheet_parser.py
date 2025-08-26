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

POS_RE = re.compile(r'\b(QB|RB|WR|TE|K|DST|D/ST)\b')
TEAM_RE = re.compile(r'\b([A-Z]{2,3})\b')
BYE_RE = re.compile(r'\b(?:Bye|BYE)\s*(\d{1,2})\b')

def _clean_cell(x):
    if x is None: return ""
    return str(x).strip().replace('\n', ' ')

def _normalize_team(tok):
    tok = tok.strip('.').upper()
    return CLEAN_TEAM.get(tok, tok)

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
                    if not mpos: continue
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
                        rows.append({"rank": rank,"name": name,"team": team,"pos": pos,"bye": bye,"value": value})
    df = pd.DataFrame(rows).drop_duplicates(subset=["name","team","pos"])
    return df

def merge_and_dedupe(top_df: pd.DataFrame, beg_df: pd.DataFrame) -> pd.DataFrame:
    for d in (top_df, beg_df):
        if "rank" not in d.columns: d["rank"] = None
        if "value" not in d.columns: d["value"] = None
        if "bye" not in d.columns: d["bye"] = None
    top_df["source"] = "Top300"
    beg_df["source"] = "Beginner"
    both = pd.concat([top_df, beg_df], ignore_index=True)
    both = both.sort_values(["name","pos","source"], ascending=[True, True, True])
    def combine(g):
        row = g.iloc[0].copy()
        for col in ["rank","team","bye","value"]:
            if pd.isna(row.get(col)) or row.get(col) in ("", None):
                for _, r in g.iterrows():
                    if pd.notna(r.get(col)) and r.get(col) not in ("", None):
                        row[col] = r.get(col); break
        row["source"] = ",".join(sorted(set(g["source"])))
        return row
    master = both.groupby(["name","pos"], as_index=False).apply(combine).reset_index(drop=True)
    master["rank"] = pd.to_numeric(master["rank"], errors="coerce")
    master = master.sort_values(["rank","value","name"], ascending=[True, False, True], na_position="last")
    master["overall_rank"] = range(1, len(master)+1)
    cols = ["overall_rank","rank","name","team","pos","bye","value","source"]
    for c in cols:
        if c not in master.columns: master[c] = None
    return master[cols]
