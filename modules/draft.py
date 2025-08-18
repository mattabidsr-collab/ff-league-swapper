import pandas as pd

def best_available(proj_df: pd.DataFrame, drafted: list[str], position_filter: str|None=None) -> pd.DataFrame:
    df = proj_df.copy()
    df = df[~df["player"].isin(set(drafted))]
    if position_filter and position_filter != "ALL":
        df = df[df["pos"] == position_filter]
    # prefer ECR if present; else proj_points
    if "ecr" in df.columns and df["ecr"].notna().any():
        df = df.sort_values("ecr")
    else:
        df = df.sort_values("proj_points", ascending=False)
    return df[["player","team","pos","opp","week","proj_points","ecr","adp","bye_week"]].head(50)
