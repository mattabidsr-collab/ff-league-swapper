import pandas as pd
from .models import LeagueRules

def fill_slots(start_df: pd.DataFrame, slots: dict) -> pd.DataFrame:
    """Return start_df rows assigned to slots with a 'slot' column."""
    rows = []
    used = set()
    # Fill fixed positions first
    for pos, cnt in slots.items():
        if pos in ("FLEX", "BENCH"):
            continue
        pool = start_df[start_df["pos"] == pos].sort_values("proj_points", ascending=False)
        for _ in range(cnt):
            pick = pool[~pool["player"].isin(used)].head(1)
            if not pick.empty:
                r = pick.iloc[0].to_dict()
                r["slot"] = pos
                rows.append(r)
                used.add(r["player"])
    # Fill FLEX
    flex_cnt = int(slots.get("FLEX", 0))
    if flex_cnt:
        flex_pool = start_df[start_df["pos"].isin(["RB","WR","TE"])].sort_values("proj_points", ascending=False)
        for _ in range(flex_cnt):
            pick = flex_pool[~flex_pool["player"].isin(used)].head(1)
            if not pick.empty:
                r = pick.iloc[0].to_dict()
                r["slot"] = "FLEX"
                rows.append(r)
                used.add(r["player"])
    return pd.DataFrame(rows)

def optimize_lineup(roster_df: pd.DataFrame, projections_df: pd.DataFrame, rules: LeagueRules) -> pd.DataFrame:
    # Consider only roster players
    on_team = set(roster_df[roster_df.get("on_team", True) == True]["player"])
    merged = projections_df[projections_df["player"].isin(on_team)].copy()
    merged = merged.sort_values("proj_points", ascending=False)
    picks = fill_slots(merged, rules.roster_slots)
    return picks
