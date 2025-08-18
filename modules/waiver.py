import pandas as pd

def bye_conflicts(roster_df: pd.DataFrame) -> pd.DataFrame:
    """Simple bye matrix for your roster."""
    cols = ["player","team","pos","bye_week"]
    df = roster_df.copy()
    if not set(cols).issubset(df.columns):
        for c in cols:
            if c not in df.columns: df[c] = None
    return df[cols].sort_values(["bye_week","pos","player"])

def waiver_candidates(proj_df: pd.DataFrame, roster_df: pd.DataFrame, dvp_df: pd.DataFrame|None=None, week:int|None=None) -> pd.DataFrame:
    on_team = set(roster_df[roster_df.get("on_team", True) == True]["player"])
    df = proj_df[~proj_df["player"].isin(on_team)].copy()
    if week is not None and "week" in df.columns:
        df = df[df["week"] == week]
    if dvp_df is not None and not dvp_df.empty:
        df = df.merge(dvp_df, how="left", left_on=["opp","pos"], right_on=["team","pos"], suffixes=("","_dvp"))
        df["matchup_score"] = df["dvp"].fillna(df["dvp"].median() if "dvp" in dvp_df.columns else 0)
    else:
        df["matchup_score"] = 0
    # Rank by projection then matchup_score
    df = df.sort_values(["proj_points","matchup_score"], ascending=[False, False])
    keep_cols = ["player","team","pos","opp","week","proj_points","bye_week","matchup_score","ecr","adp"]
    return df[[c for c in keep_cols if c in df.columns]].head(50)
