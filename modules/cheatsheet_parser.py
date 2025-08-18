import pdfplumber
import pandas as pd
import re

CLEAN_TEAM = {
    "JAX":"JAC", "JAX.":"JAC", "WSH":"WAS", "LA":"LAR", "LAC":"LAC", "LV":"LV", "SF":"SF", "TB":"TB",
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
    """
    Generic parser for ESPN-style cheat sheet PDFs.
    Tries to extract columns: rank, name, team, pos, bye, value (optional).
    """
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            try:
                table = page.extract_table()
                if not table:
                    tables = page.extract_tables()
                else:
                    tables = [table]
            except Exception:
                tables = []
            for tbl in tables or []:
                # skip tiny tables
                if not tbl or len(tbl) < 3: 
                    continue
                # Some pages have header rows; we won't rely on them, just extract tokens.
                for r in tbl:
                    cells = [_clean_cell(c) for c in r]
                    line = " | ".join(cells)
                    # Heuristic: line must contain a position
                    mpos = POS_RE.search(line)
                    if not mpos:
                        continue
                    # rank likely first numeric token
                    rank = None
                    for c in cells:
                        if c.isdigit():
                            rank = int(c)
                            break
                    # name + team tokens
                    name = None
                    team = None
                    bye = None
                    value = None
                    # try to find team and bye
                    mt = TEAM_RE.findall(line)
                    if mt:
                        # choose last 2-3 letter token that is an NFL team
                        for cand in mt:
                            cand2 = _normalize_team(cand)
                            if cand2 in CLEAN_TEAM.values() or cand2 in ["LAC","LAR","LV","NE","NO","SF","TB","KC","GB","NYG","NYJ"]:
                                team = cand2
                    mb = BYE_RE.search(line)
                    if mb:
                        try:
                            bye = int(mb.group(1))
                        except:
                            bye = None
                    # position
                    pos = mpos.group(1).replace("D/ST","DST")
                    # name heuristics: look for part before team token
                    # Often the first non-numeric cell with spaces is the name
                    for c in cells:
                        if not c or c.isdigit(): 
                            continue
                        if POS_RE.search(c): 
                            continue
                        # avoid "Bye 10" strings
                        if "Bye" in c or "BYE" in c:
                            continue
                        if len(c.split())>=2:
                            name = c
                            break
                    # value if present and flag set
                    if assume_has_value:
                        # last numeric-ish token in row could be value
                        for c in reversed(cells):
                            try:
                                if c and c.replace('.','',1).isdigit():
                                    valf = float(c)
                                    if valf>0 and valf<1000:
                                        value = valf
                                        break
                            except:
                                pass
                    if name and pos and team:
                        rows.append({
                            "rank": rank,
                            "name": name,
                            "team": team,
                            "pos": pos,
                            "bye": bye,
                            "value": value
                        })
    df = pd.DataFrame(rows).drop_duplicates(subset=["name","team","pos"])
    # Some sheets list DST as team names; normalize name for DST rows to include team
    dst_mask = df["pos"]=="DST"
    df.loc[dst_mask & df["name"].isna(), "name"] = df.loc[dst_mask, "team"] + " DST"
    return df

def merge_and_dedupe(top_df: pd.DataFrame, beg_df: pd.DataFrame) -> pd.DataFrame:
    """
    Auto-resolve duplicates preferring Top300 (rank/value) over Beginner.
    Keep one row per (name,pos). Fill missing fields from the other.
    """
    # standardize keys
    for d in (top_df, beg_df):
        if "rank" not in d.columns: d["rank"] = None
        if "value" not in d.columns: d["value"] = None
        if "bye" not in d.columns: d["bye"] = None
    top_df["source"] = "Top300"
    beg_df["source"] = "Beginner"

    # sort so Top300 comes first for same player/pos
    both = pd.concat([top_df, beg_df], ignore_index=True)
    both = both.sort_values(["name","pos","source"], ascending=[True, True, True])  # Top300 before Beginner alphabetically
    # now group and prefer first non-null rank/value from Top300
    def combine(g):
        row = g.iloc[0].copy()
        # fill blanks from any others in group
        for col in ["rank","team","bye","value"]:
            if pd.isna(row.get(col)) or row.get(col) in ("", None):
                for _, r in g.iterrows():
                    if pd.notna(r.get(col)) and r.get(col) not in ("", None):
                        row[col] = r.get(col)
                        break
        row["source"] = ",".join(sorted(set(g["source"])))
        return row

    master = both.groupby(["name","pos"], as_index=False).apply(combine).reset_index(drop=True)
    # Re-rank if many missing ranks: sort by existing rank then by value desc, then name
    master["rank"] = pd.to_numeric(master["rank"], errors="coerce")
    master = master.sort_values(["rank","value","name"], ascending=[True, False, True], na_position="last")
    # add ecr-like overall rank
    master["overall_rank"] = range(1, len(master)+1)
    # Final column order
    cols = ["overall_rank","rank","name","team","pos","bye","value","source"]
    for c in cols:
        if c not in master.columns:
            master[c] = None
    return master[cols]
