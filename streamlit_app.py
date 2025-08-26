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

    # --- Upload full player pool (All Players) ---
    all_players_file = st.file_uploader("Upload ALL PLAYERS CSV (ECR/master)", type=["csv"], key="all_players_csv")

    # Optional: load/save drafted list to/from CSV
    col_imp, col_exp = st.columns([1,1])
    with col_imp:
        drafted_import = st.file_uploader("Import drafted list (CSV)", type=["csv"], key="drafted_import_csv")
    with col_exp:
        pass

    # Initialize session state for drafted set
    if "drafted_set" not in st.session_state:
        st.session_state.drafted_set = set()

    # Load dataframes
    def _read_csv(upload):
        import pandas as pd
        return pd.read_csv(upload) if upload else pd.DataFrame()

    all_df = _read_csv(all_players_file)

    # If weekly projections were uploaded, you can still use them for sorting;
    # but 'all_df' is the driver for Best Available.
    # Normalize column names
    def _normalize(df):
        if df.empty:
            return df
        cols = {c.lower(): c for c in df.columns}
        # unify to canonical
        out = df.copy()
        # map 'name'->'player' if needed
        if "player" not in cols and "name" in cols:
            out["player"] = out[cols["name"]]
        if "pos" not in cols and "position" in cols:
            out["pos"] = out[cols["position"]]
        # Keep common helpers if present
        for need in ["team","bye","proj_points","rank"]:
            if need not in out.columns and need in cols:
                out[need] = out[cols[need]]
        # Ensure required exist
        for req in ["player","pos"]:
            if req not in out.columns:
                out[req] = pd.NA
        # Drop rows without a player name
        out = out.dropna(subset=["player"]).copy()
        # Build a nice display key
        out["key"] = out.apply(lambda r: f"{r.get('player','')} ({r.get('pos','')}, {r.get('team','')})", axis=1)
        return out

    all_df = _normalize(all_df)

    # Handle drafted import
    if drafted_import is not None:
        imp_df = _read_csv(drafted_import)
        if not imp_df.empty:
            name_col = "player" if "player" in imp_df.columns else ("name" if "name" in imp_df.columns else None)
            if name_col:
                st.session_state.drafted_set.update(imp_df[name_col].dropna().astype(str).tolist())
                st.success(f"Imported {len(imp_df)} drafted players.")

    if all_df.empty:
        st.info("Upload your ALL PLAYERS CSV to enable Best Available and drafting.")
        st.stop()

    # Position filter
    pos_options = ["ALL"] + sorted([p for p in all_df["pos"].dropna().astype(str).unique()])
    pos_choice = st.selectbox("Filter by position", pos_options, index=0)

    # Choose sort: use proj_points if present else rank
    sort_by = "proj_points" if "proj_points" in all_df.columns else ("rank" if "rank" in all_df.columns else None)

    # Build Best Available by excluding drafted
    drafted_names = st.session_state.drafted_set
    pool = all_df[~all_df["player"].astype(str).isin(drafted_names)].copy()
    if pos_choice != "ALL":
        pool = pool[pool["pos"].astype(str) == pos_choice]

    if sort_by and sort_by in pool.columns:
        pool = pool.sort_values(sort_by, ascending=False if sort_by=="proj_points" else True, na_position="last")

    st.markdown("**Best Available**")
    st.dataframe(
        pool[["player","pos","team"] + ([sort_by] if sort_by else []) + ([ "bye" ] if "bye" in pool.columns else [])].head(50),
        use_container_width=True, hide_index=True
    )

    # --- Draft controls ---
    st.markdown("### Mark players as drafted")
    c1, c2 = st.columns([2,1])

    # Quick pick: search & add
    with c1:
        # Use multiselect over remaining pool
        add_multi = st.multiselect(
            "Pick drafted players to add",
            options=pool["key"].tolist(),
            max_selections=10
        )
        if st.button("Add selected to drafted"):
            to_add = pool[pool["key"].isin(add_multi)]["player"].astype(str).tolist()
            st.session_state.drafted_set.update(to_add)
            st.experimental_rerun()

    with c2:
        manual_name = st.text_input("Manual add (exact player name)")
        if st.button("Add manual"):
            if manual_name.strip():
                st.session_state.drafted_set.add(manual_name.strip())
                st.experimental_rerun()

    # Remove drafted
    drafted_df = all_df[all_df["player"].astype(str).isin(st.session_state.drafted_set)].copy()
    st.markdown("### Drafted so far")
    st.dataframe(
        drafted_df[["player","pos","team"]].sort_values(["pos","player"]),
        use_container_width=True, hide_index=True, height=260
    )

    rem = st.multiselect("Remove drafted entries", options=drafted_df["player"].astype(str).tolist(), key="rem_drafted")
    col_a, col_b, col_c = st.columns([1,1,1])
    with col_a:
        if st.button("Remove selected"):
            st.session_state.drafted_set.difference_update(rem)
            st.experimental_rerun()
    with col_b:
        if st.button("Reset drafted list"):
            st.session_state.drafted_set = set()
            st.experimental_rerun()
    with col_c:
        # Export drafted list
        if not drafted_df.empty:
            st.download_button(
                "Download drafted.csv",
                drafted_df[["player","pos","team"]].to_csv(index=False),
                file_name="drafted.csv",


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
