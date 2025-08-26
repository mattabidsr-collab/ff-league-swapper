import streamlit as st
import pandas as pd
from modules.cheatsheet_parser import parse_cheatsheet_pdf, merge_and_dedupe

st.set_page_config(page_title="Fantasy Helper (Offline)", layout="wide")
st.title("Fantasy Football Helper — Offline Mode")

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
        with open(tpath, "wb") as f: f.write(top_pdf.getbuffer())
        try: top_df = parse_cheatsheet_pdf(tpath, assume_has_value=True)
        except Exception as e:
            st.error(f"Failed to parse Top 300 PDF: {e}"); st.code(traceback.format_exc()); st.stop()
        bpath = os.path.join(tempfile.gettempdir(), "beg.pdf")
        with open(bpath, "wb") as f: f.write(beg_pdf.getbuffer())
        try: beg_df = parse_cheatsheet_pdf(bpath, assume_has_value=False)
        except Exception as e:
            st.error(f"Failed to parse Beginner PDF: {e}"); st.code(traceback.format_exc()); st.stop()
        st.caption(f"Top300 rows: {len(top_df)} | cols: {list(top_df.columns)}")
        st.caption(f"Beginner rows: {len(beg_df)} | cols: {list(beg_df.columns)}")

        if top_df.empty and beg_df.empty:
            st.error("Couldn’t extract any rows from either PDF. The table layout may not be recognized. "
                     "Try re-uploading, or export the cheat sheet to CSV if available.")
            st.stop()

        if top_df.empty or beg_df.empty:
            st.warning("Only one PDF parsed successfully — combining with what’s available.")  
            
        master = merge_and_dedupe(top_df, beg_df)
        st.success(f"Parsed Top300: {len(top_df)} rows, Beginner: {len(beg_df)} rows. Combined: {len(master)} rows.")
        st.dataframe(master.head(50), use_container_width=True, hide_index=True)
        st.download_button("Download master_players.csv", master.to_csv(index=False), "master_players.csv", "text/csv")

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
