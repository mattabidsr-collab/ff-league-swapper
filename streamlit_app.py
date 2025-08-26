import streamlit as st
import pandas as pd

# === CSV Uploads ===
st.sidebar.header("Upload your CSVs")
roster_file = st.sidebar.file_uploader("Roster CSV", type=["csv"])
weekly_file = st.sidebar.file_uploader("Weekly Projections CSV", type=["csv"])
ros_file = st.sidebar.file_uploader("ROS Projections CSV", type=["csv"])
dvp_file = st.sidebar.file_uploader("DvP CSV (optional)", type=["csv"])

def load_csv(upload): return pd.read_csv(upload) if upload else pd.DataFrame()
roster_df, weekly_df, ros_df, dvp_df = map(load_csv, [roster_file, weekly_file, ros_file, dvp_file])

tab_draft, tab_waiver, tab_lineup, tab_trade = st.tabs(["Draft Board", "Waiver Wire", "Lineup Optimizer", "Trade Evaluator"])

with tab_draft:
    st.subheader("Draft Board")
    if weekly_df.empty: st.info("Upload Weekly Projections or Master CSV with proj_points to populate Best Available.")
    else: st.dataframe(weekly_df.sort_values("proj_points", ascending=False).head(50))

with tab_waiver:
    st.subheader("Waiver Wire")
    if not weekly_df.empty and not roster_df.empty:
        pool = weekly_df[~weekly_df["player"].isin(roster_df.get("player", []))].copy()
        if "proj_points" in pool.columns: pool = pool.sort_values("proj_points", ascending=False)
        st.dataframe(pool.head(50))
    else: st.info("Upload Weekly Projections + Roster to see waiver suggestions.")

with tab_lineup:
    st.subheader("Lineup Optimizer")
    if not weekly_df.empty and not roster_df.empty and "proj_points" in weekly_df.columns:
        merged = pd.merge(roster_df, weekly_df, on=["player","pos"], how="left")
        st.dataframe(merged.sort_values("proj_points", ascending=False).head(9))
    else: st.info("Upload Weekly Projections + Roster to optimize lineup.")

with tab_trade:
    st.subheader("Trade Evaluator")
    if not ros_df.empty: st.dataframe(ros_df.head(20))
    else: st.info("Upload ROS Projections to evaluate trades.")
