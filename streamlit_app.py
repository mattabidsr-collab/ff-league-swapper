import streamlit as st
import pandas as pd

st.set_page_config(page_title="Fantasy Helper", layout="wide")

st.title("Fantasy Football Helper (Offline Mode)")

# === Uploads ===
st.sidebar.header("Upload your data")

roster_file = st.sidebar.file_uploader("Upload Roster CSV", type=["csv"])
weekly_file = st.sidebar.file_uploader("Upload Weekly Projections CSV", type=["csv"])
ros_file = st.sidebar.file_uploader("Upload ROS Projections CSV", type=["csv"])
dvp_file = st.sidebar.file_uploader("Upload DvP CSV (optional)", type=["csv"])

# Load dataframes
def load_csv(upload):
    return pd.read_csv(upload) if upload else pd.DataFrame()

roster_df = load_csv(roster_file)
weekly_df = load_csv(weekly_file)
ros_df = load_csv(ros_file)
dvp_df = load_csv(dvp_file)

tabs = st.tabs(["Draft Board", "Waiver Wire", "Lineup Optimizer", "Trade Evaluator"])

with tabs[0]:
    st.subheader("Draft Board")
    st.write("Upload master player list here in future.")
    if not weekly_df.empty:
        st.dataframe(weekly_df.head())

with tabs[1]:
    st.subheader("Waiver Wire")
    if not weekly_df.empty and not roster_df.empty:
        # Show best available by proj_points
        waiver = weekly_df[~weekly_df['player'].isin(roster_df['player'])]
        waiver = waiver.sort_values("proj_points", ascending=False)
        st.dataframe(waiver.head(20))
    else:
        st.info("Upload Weekly Projections + Roster to see waivers.")

with tabs[2]:
    st.subheader("Lineup Optimizer")
    if not weekly_df.empty and not roster_df.empty:
        merged = pd.merge(roster_df, weekly_df, on=["player","pos"], how="left")
        lineup = merged.sort_values("proj_points", ascending=False).head(9)
        st.dataframe(lineup)
    else:
        st.info("Upload Weekly Projections + Roster to optimize lineup.")

with tabs[3]:
    st.subheader("Trade Evaluator")
    if not ros_df.empty:
        st.dataframe(ros_df.head(20))
    else:
        st.info("Upload ROS Projections to evaluate trades.")
