import streamlit as st
import pandas as pd

from modules.loaders import load_league_rules_files, load_csv_or_default, standardize_players
from modules.models import LeagueRules, LeagueState
from modules.draft import best_available
from modules.lineup import optimize_lineup
from modules.waiver import waiver_candidates, bye_conflicts
from modules.trade import evaluate_trade
from modules.utils import load_league_state, save_league_state
from modules.cheatsheet_parser import parse_cheatsheet_pdf, merge_and_dedupe
st.set_page_config(page_title="FF Multi-League Helper", layout="wide")

st.set_page_config(page_title="FF Multi-League Helper", layout="wide")

# === Cheatsheet PDF -> Master CSV ===
st.header("Import Cheat Sheets (PDF) → Master Players CSV")
top_pdf = st.file_uploader("Upload Top 300 PPR PDF", type=["pdf"], key="pdf_top300")
beg_pdf = st.file_uploader("Upload Beginner's PPR PDF", type=["pdf"], key="pdf_beg")

if st.button("Parse & Combine PDFs"):
    if not top_pdf or not beg_pdf:
        st.warning("Please upload both PDFs first.")
    else:
        import tempfile, os, traceback
        tpath = os.path.join(tempfile.gettempdir(), "top300.pdf")
        with open(tpath, "wb") as f:
            f.write(top_pdf.getbuffer())
        try:
            top_df = parse_cheatsheet_pdf(tpath, assume_has_value=True)
        except Exception as e:
            st.error(f"Failed to parse Top 300 PDF: {e}")
            st.code(traceback.format_exc())
            st.stop()

        bpath = os.path.join(tempfile.gettempdir(), "beg.pdf")
        with open(bpath, "wb") as f:
            f.write(beg_pdf.getbuffer())
        try:
            beg_df = parse_cheatsheet_pdf(bpath, assume_has_value=False)
        except Exception as e:
            st.error(f"Failed to parse Beginner PDF: {e}")
            st.code(traceback.format_exc())
            st.stop()

        master = merge_and_dedupe(top_df, beg_df)
        st.success(f"Parsed Top300: {len(top_df)} rows, Beginner: {len(beg_df)} rows. Combined: {len(master)} rows.")
        st.dataframe(master.head(50), use_container_width=True, hide_index=True)
        st.download_button("Download master_players.csv", master.to_csv(index=False), "master_players.csv", "text/csv")

# --- Sidebar: League selection & data uploads ---
st.sidebar.title("Settings & Data")
leagues = load_league_rules_files()
if not leagues:
    st.sidebar.error("No league rule files found in ./leagues. Add JSONs then restart.")
    st.stop()

league_key = st.sidebar.selectbox("Select League", list(leagues.keys()), format_func=lambda k: leagues[k].league_name)
rules = leagues[league_key]

# Load & persist session league state
if "league_states" not in st.session_state:
    st.session_state.league_states = {}

if league_key not in st.session_state.league_states:
    # try to restore from temp file
    persisted = load_league_state(league_key)
    st.session_state.league_states[league_key] = LeagueState(**persisted) if persisted else LeagueState()

lst: LeagueState = st.session_state.league_states[league_key]

st.sidebar.subheader("Upload Your Data")
roster_file = st.sidebar.file_uploader("Roster CSV (or use data/roster_template.csv)", type=["csv"], key=f"roster_{league_key}")
proj_file = st.sidebar.file_uploader("Weekly Projections CSV", type=["csv"], key=f"proj_{league_key}")
ros_file = st.sidebar.file_uploader("ROS Projections CSV", type=["csv"], key=f"ros_{league_key}")
dvp_file = st.sidebar.file_uploader("Defense vs Position CSV (optional)", type=["csv"], key=f"dvp_{league_key}")

rules_upload = st.sidebar.file_uploader("League Rules JSON (optional: overrides selection)", type=["json"], key=f"rules_{league_key}")
if rules_upload is not None:
    try:
        import json
        rules_dict = json.loads(rules_upload.getvalue().decode("utf-8"))
        from modules.models import parse_league_rules
        rules = parse_league_rules(rules_dict)
        st.sidebar.success("League rules loaded from uploaded JSON for this session.")
    except Exception as e:
        st.sidebar.error(f"Failed to parse league rules JSON: {e}")

week = st.sidebar.number_input("Week (for Waiver/Lineup)", min_value=1, max_value=18, value=1, step=1)

# Save uploaded files to temp if provided (so switching pages/leagues doesn't lose them)
import os, tempfile
tmpdir = tempfile.gettempdir()
def stash_upload(upload, name_hint):
    if not upload: return ""
    p = os.path.join(tmpdir, f"ff_{league_key}_{name_hint}.csv")
    with open(p, "wb") as f:
        f.write(upload.getbuffer())
    return p

if roster_file: lst.roster_csv_path = stash_upload(roster_file, "roster")
proj_path = stash_upload(proj_file, "proj")
ros_path = stash_upload(ros_file, "ros")
dvp_path = stash_upload(dvp_file, "dvp")

# Persist state
save_league_state(league_key, {"drafted": lst.drafted, "roster_csv_path": lst.roster_csv_path})

# Load dataframes (with fallbacks to /data samples)
roster_df = load_csv_or_default(lst.roster_csv_path, "roster_template.csv")
proj_df = load_csv_or_default(proj_path, "projections_week1.csv")
ros_df = load_csv_or_default(ros_path, "ros.csv")
dvp_df = load_csv_or_default(dvp_path, "dvp_template.csv")

proj_df = standardize_players(proj_df)
ros_df = standardize_players(ros_df)

# --- Header ---
left, right = st.columns([3,2])
with left:
    st.title("Fantasy Football Multi-League Helper")
    st.caption(f"League: **{rules.league_name}** · Teams: {rules.num_teams} · PPR: {rules.scoring.ppr}")
with right:
    st.write("")
    st.write("")
    st.metric("Players drafted (this session)", len(lst.drafted))

# === Cheatsheet PDF -> Master CSV ===
st.header("Import Cheat Sheets (PDF) → Master Players CSV")
top_pdf = st.file_uploader("Upload Top 300 PPR PDF", type=["pdf"], key="pdf_top300")
beg_pdf = st.file_uploader("Upload Beginner's PPR PDF", type=["pdf"], key="pdf_beg")

if st.button("Parse & Combine PDFs"):
    if not top_pdf or not beg_pdf:
        st.warning("Please upload both PDFs first.")
    else:
        import tempfile, os
        tpath = os.path.join(tempfile.gettempdir(), "top300.pdf")
        with open(tpath, "wb") as f:
            f.write(top_pdf.getbuffer())
        top_df = parse_cheatsheet_pdf(tpath, assume_has_value=True)

        bpath = os.path.join(tempfile.gettempdir(), "beg.pdf")
        with open(bpath, "wb") as f:
            f.write(beg_pdf.getbuffer())
        beg_df = parse_cheatsheet_pdf(bpath, assume_has_value=False)

        master = merge_and_dedupe(top_df, beg_df)
        st.success(f"Parsed Top300: {len(top_df)} rows, Beginner: {len(beg_df)} rows. Combined: {len(master)} rows.")
        st.dataframe(master.head(50), use_container_width=True, hide_index=True)
        st.download_button("Download master_players.csv", master.to_csv(index=False), "master_players.csv", "text/csv")
# --- Tabs ---
tab_draft, tab_waiver, tab_lineup, tab_trade, tab_settings = st.tabs(
    ["Draft Board", "Waiver Wire", "Lineup Optimizer", "Trade Evaluator", "Settings & Data"]
)

with tab_draft:
    st.subheader("Manual Draft Helper")
    st.write("Use the controls to mark players as drafted. 'Best Available' updates live and excludes drafted players.")
    col1, col2 = st.columns([1,2])
    with col1:
        position = st.selectbox("Filter Position", ["ALL","QB","RB","WR","TE","DST","K"])
        reset = st.button("Reset Drafted List")
        if reset:
            lst.drafted = []
            save_league_state(league_key, {"drafted": lst.drafted, "roster_csv_path": lst.roster_csv_path})
            st.success("Drafted list reset for this league.")
        # Pick a player to mark drafted
        pool = best_available(proj_df, lst.drafted, position_filter=position)
        take = st.selectbox("Mark drafted", [""] + pool["player"].tolist())
        if take:
            if take not in lst.drafted:
                lst.drafted.append(take)
                save_league_state(league_key, {"drafted": lst.drafted, "roster_csv_path": lst.roster_csv_path})
                st.toast(f"Drafted: {take}")
    with col2:
        st.write("**Best Available** (Top 50)")
        st.dataframe(pool, use_container_width=True, hide_index=True)

with tab_waiver:
    st.subheader("Waiver Wire")
    st.write("Shows potential pickups not on your roster, factoring projection and (optional) matchup strength (higher DvP = easier).")
    bye_col, cand_col = st.columns([1,2])
    with bye_col:
        st.caption("Bye weeks on your roster")
        st.dataframe(bye_conflicts(roster_df), use_container_width=True, hide_index=True)
    with cand_col:
        dvp_use = dvp_df if not dvp_df.empty else None
        cands = waiver_candidates(proj_df, roster_df, dvp_df=dvp_use, week=int(week))
        st.dataframe(cands, use_container_width=True, hide_index=True)

with tab_lineup:
    st.subheader("Lineup Optimizer")
    if proj_df.empty or roster_df.empty:
        st.warning("Upload roster and projections to optimize.")
    else:
        lineup = optimize_lineup(roster_df, proj_df, rules)
        st.dataframe(lineup, use_container_width=True, hide_index=True)

with tab_trade:
    st.subheader("Trade Evaluator")
    all_players = sorted(ros_df["player"].dropna().unique().tolist())
    a = st.multiselect("Team A receives", all_players, key=f"a_{league_key}")
    b = st.multiselect("Team B receives", all_players, key=f"b_{league_key}")
    if st.button("Evaluate Trade"):
        if not len(a) and not len(b):
            st.info("Add some players to evaluate.")
        else:
            res = evaluate_trade(a, b, ros_df, rules)
            st.write("**Result**")
            st.json(res)

with tab_settings:
    st.subheader("League Rules (read-only)")
    st.json({
        "league_name": rules.league_name,
        "num_teams": rules.num_teams,
        "roster_slots": rules.roster_slots,
        "flex_eligible": rules.flex_eligible,
        "scoring": {"ppr": rules.scoring.ppr, "pass_td": rules.scoring.pass_td, "rush_td": rules.scoring.rush_td}
    })
    st.markdown("""
    **Tips**
    - Replace the JSON files in `./leagues` with your real ESPN rules (or upload in the sidebar to override).
    - Use any projections source (FantasyPros CSVs work great). Name columns similar to the samples or map them before upload.
    - For persistence across sessions, the app saves minimal state in a temp folder; you can extend this in `modules/utils.py`.
    """)
