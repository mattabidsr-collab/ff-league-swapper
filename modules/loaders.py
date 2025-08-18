import json, os
import pandas as pd
from .models import parse_league_rules, LeagueRules

DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DEFAULT_LEAGUE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "leagues")

def load_league_rules_files() -> dict:
    """Return mapping {filename: LeagueRules} for all JSON in leagues/"""
    leagues = {}
    for fn in os.listdir(DEFAULT_LEAGUE_DIR):
        if fn.endswith(".json"):
            p = os.path.join(DEFAULT_LEAGUE_DIR, fn)
            with open(p, "r") as f:
                d = json.load(f)
            leagues[fn] = parse_league_rules(d)
    return leagues

def load_csv_or_default(path: str, default_name: str) -> pd.DataFrame:
    """Try to read CSV at path; if missing, fallback to data/default_name."""
    if path and os.path.exists(path):
        return pd.read_csv(path)
    fallback = os.path.join(DEFAULT_DATA_DIR, default_name)
    if os.path.exists(fallback):
        return pd.read_csv(fallback)
    return pd.DataFrame()

def standardize_players(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names used downstream."""
    rename_map = {
        "Player": "player",
        "Team": "team",
        "Pos": "pos",
        "Opp": "opp",
        "Week": "week",
        "Proj": "proj_points",
        "ECR": "ecr",
        "ADP": "adp",
        "Bye": "bye_week"
    }
    cols = {c: rename_map.get(c, c) for c in df.columns}
    df = df.rename(columns=cols)
    # enforce needed cols if present
    for col in ["player","team","pos","proj_points"]:
        if col not in df.columns:
            df[col] = None
    return df

def replacement_levels(ros_df: pd.DataFrame, rules: LeagueRules) -> dict:
    """
    Compute naive replacement level per position:
    rank = startable_count per pos * num_teams.
    Use ecr or ros_points ranking as available.
    """
    start_counts = {}
    for pos, cnt in rules.roster_slots.items():
        if pos == "FLEX" or pos == "BENCH":
            continue
        start_counts[pos] = cnt * rules.num_teams
    # FLEX complicates replacement; ignore for baseline (conservative)
    rep = {}
    for pos, cap in start_counts.items():
        pool = ros_df[ros_df["pos"] == pos].copy()
        if pool.empty:
            rep[pos] = 0.0
            continue
        if "ecr" in pool.columns and pool["ecr"].notna().any():
            pool = pool.sort_values("ecr")
        else:
            pool = pool.sort_values("ros_points", ascending=False)
        if len(pool) >= cap:
            rep[pos] = float(pool.iloc[cap-1]["ros_points"])
        else:
            rep[pos] = float(pool.iloc[-1]["ros_points"])
    return rep
