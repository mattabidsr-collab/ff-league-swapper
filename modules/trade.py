import pandas as pd
from .loaders import replacement_levels
from .models import LeagueRules

def vorp_scores(ros_df: pd.DataFrame, rules: LeagueRules) -> pd.DataFrame:
    reps = replacement_levels(ros_df, rules)
    df = ros_df.copy()
    df["rep"] = df["pos"].map(reps).fillna(0.0)
    df["vorp"] = df["ros_points"] - df["rep"]
    return df

def evaluate_trade(side_a: list[str], side_b: list[str], ros_df: pd.DataFrame, rules: LeagueRules) -> dict:
    df = vorp_scores(ros_df, rules)
    m = df.set_index("player")
    a_score = float(m.loc[side_a]["vorp"].sum()) if side_a else 0.0
    b_score = float(m.loc[side_b]["vorp"].sum()) if side_b else 0.0
    diff = a_score - b_score
    verdict = "Fair"
    if diff > 10: verdict = "Advantage A"
    if diff < -10: verdict = "Advantage B"
    return {
        "A_vorp": round(a_score, 1),
        "B_vorp": round(b_score, 1),
        "difference": round(diff, 1),
        "verdict": verdict
    }
