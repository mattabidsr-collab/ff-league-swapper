import streamlit as st
import pandas as pd
from modules.rules import load_league_rules_files, LeagueRules

st.set_page_config(page_title="Fantasy Helper (Offline)", layout="wide")
st.title("Fantasy Football Helper — Offline Mode")

# === Load league rules & choose league ===
leagues = load_league_rules_files("./leagues")
if not leagues:
    st.error("No league rule files found in /leagues. Add your 3 JSONs and restart.")
    st.stop()

league_key = st.sidebar.selectbox(
    "Select League",
    list(leagues.keys()),
    format_func=lambda k: leagues[k].league_name
)
RULES: LeagueRules = leagues[league_key]
st.sidebar.caption(
    f"{RULES.league_name} • {RULES.num_teams} teams • {RULES.ppr} PPR • PassTD {RULES.pass_td}"
)

# === CSV Uploads ===
st.sidebar.header("Upload your CSVs")
roster_file = st.sidebar.file_uploader("Roster CSV", type=["csv"])
weekly_file = st.sidebar.file_uploader("Weekly Projections CSV", type=["csv"])
ros_file    = st.sidebar.file_uploader("ROS Projections CSV", type=["csv"])
dvp_file    = st.sidebar.file_uploader("DvP CSV (optional)", type=["csv"])

def load_csv(upload):
    try:
        return pd.read_csv(upload) if upload else pd.DataFrame()
    except Exception as e:
        st.warning(f"Could not read CSV: {e}")
        return pd.DataFrame()

roster_df = load_csv(roster_file)
weekly_df = load_csv(weekly_file)
ros_df    = load_csv(ros_file)
dvp_df    = load_csv(dvp_file)

tab_draft, tab_waiver, tab_lineup, tab_trade = st.tabs(
    ["Draft Board", "Waiver Wire", "Lineup Optimizer", "Trade Evaluator"]
)

# ---------- Draft Board ----------
with tab_draft:
    st.subheader("Draft Board")
    if weekly_df.empty:
        st.info("Upload Weekly Projections to populate Best Available.")
    else:
        for c in ["player","pos","team","proj_points"]:
            if c not in weekly_df.columns: weekly_df[c] = pd.NA
        best = weekly_df.sort_values("proj_points", ascending=False, na_position="last").head(50)
        st.dataframe(best, use_container_width=True, hide_index=True)

# ---------- Waiver Wire ----------
with tab_waiver:
    st.subheader("Waiver Wire")
    if weekly_df.empty or roster_df.empty:
        st.info("Upload Weekly Projections + Roster to see waiver suggestions.")
    else:
        if "player" not in roster_df.columns:
            st.warning("Roster CSV must have a 'player' column.")
        else:
            pool = weekly_df[~weekly_df["player"].isin(roster_df["player"])].copy()
            # (Optional) show your bye clusters to help target waivers
            if "bye_week" in roster_df.columns:
                bye_clusters = roster_df.groupby(["pos","bye_week"]).size().reset_index(name="count")
                st.caption("Your bye clusters:")
                st.dataframe(bye_clusters.sort_values("count", ascending=False), hide_index=True, use_container_width=True)
            if "proj_points" in pool.columns:
                pool = pool.sort_values("proj_points", ascending=False, na_position="last")
            st.dataframe(pool.head(50), use_container_width=True, hide_index=True)

# ---------- Lineup Optimizer (rules-aware) ----------
with tab_lineup:
    st.subheader("Lineup Optimizer")
    if weekly_df.empty or roster_df.empty:
        st.info("Upload Weekly Projections + Roster to optimize lineup.")
    else:
        for c in ["player","pos"]:
            if c not in weekly_df.columns or c not in roster_df.columns:
                st.warning("Both CSVs must include 'player' and 'pos' columns.")
                st.stop()
        df = pd.merge(roster_df, weekly_df, on=["player","pos"], how="left")

        starters = []
        slots = RULES.roster_slots.copy()

        # Fill fixed slots first
        for pos in ["QB","RB","WR","TE","DST","K"]:
            need = int(slots.get(pos, 0))
            if need > 0:
                choice = df[df["pos"]==pos].sort_values("proj_points", ascending=False, na_position="last").head(need)
                starters.append(choice)

        # FLEX last
        flex_need = int(slots.get("FLEX", 0))
        if flex_need > 0:
            taken = pd.concat(starters)["player"] if starters else pd.Series([], dtype=str)
            flex_pool = df[~df["player"].isin(taken) & df["pos"].isin(RULES.flex_eligible)]
            flex_pick = flex_pool.sort_values("proj_points", ascending=False, na_position="last").head(flex_need)
            starters.append(flex_pick)

        lineup = pd.concat(starters) if starters else df.head(0)
        st.dataframe(lineup, use_container_width=True, hide_index=True)

# ---------- Trade Evaluator (uses ROS CSV) ----------
with tab_trade:
    st.subheader("Trade Evaluator")
    if ros_df.empty:
        st.info("Upload ROS Projections to evaluate trades.")
    else:
        st.dataframe(ros_df.head(20), use_container_width=True, hide_index=True)
