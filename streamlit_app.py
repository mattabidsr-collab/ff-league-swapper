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
    
        # ---------- Smart Scoring Controls ----------
    st.markdown("### Draft Scoring Weights")
    c1, c2, c3 = st.columns(3)
    with c1:
        w_proj = st.slider("Weight: Projections/Rank", 0.0, 2.0, 1.0, 0.05)
        w_need = st.slider("Weight: Roster Need", 0.0, 2.0, 0.8, 0.05)
    with c2:
        w_scar = st.slider("Weight: Positional Scarcity", 0.0, 2.0, 0.6, 0.05)
        w_tier = st.slider("Weight: Tier", 0.0, 2.0, 0.6, 0.05)
    with c3:
        w_bye  = st.slider("Penalty: Bye Cluster", 0.0, 2.0, 0.3, 0.05)
        w_stack= st.slider("Bonus: Stacking", 0.0, 2.0, 0.4, 0.05)

    # ------------- Helpers -------------
    def _pos_list():
        return ["QB","RB","WR","TE","DST","K","FLEX"]

    # current drafted players (by you) — we know their pos/team/bye from all_df
    drafted_df = all_df[all_df["player"].astype(str).isin(st.session_state.drafted_set)].copy()

    # roster needs from RULES
    slots = {p: int(RULES.roster_slots.get(p, 0)) for p in _pos_list()}
    flex_elig = set(RULES.flex_eligible)

    # count how many you’ve drafted at each slot and flex-eligible pool
    drafted_counts = drafted_df["pos"].value_counts().to_dict()

    # bye clusters on your current roster (including drafted so far)
    my_bye = drafted_df.groupby(["pos","bye"]).size().reset_index(name="count") if "bye" in drafted_df.columns else pd.DataFrame(columns=["pos","bye","count"])

    # baseline “projection” source
    # prefer proj_points; else invert rank; else neutral
    import numpy as np
    base = all_df.copy()
    if "proj_points" in base.columns and base["proj_points"].notna().any():
        base["proj_norm"] = (base["proj_points"] - base["proj_points"].min()) / (base["proj_points"].max() - base["proj_points"].min() + 1e-9)
    elif "rank" in base.columns and base["rank"].notna().any():
        # smaller rank is better → convert to 0..1 (1 = best)
        mx = base["rank"].max()
        base["proj_norm"] = 1.0 - (base["rank"] / (mx + 1e-9))
    else:
        base["proj_norm"] = 0.5  # flat if you provided neither

    # auto-tier if no `tier`
    if "tier" not in base.columns:
        if "rank" in base.columns and base["rank"].notna().any():
            # simple breakpoints: 1-12, 13-36, 37-72, 73-120, 121+
            bins = [0, 12, 36, 72, 120, 9999]
            labels = [1,2,3,4,5]
            base["tier"] = pd.cut(base["rank"].fillna(9999), bins=bins, labels=labels).astype("Int64")
        else:
            base["tier"] = pd.Series([3]*len(base), dtype="Int64")

    # scarcity per position: how many remain and the drop-off nearby
    def scarcity_score(df: pd.DataFrame):
        scores = []
        for pos, group in df.groupby("pos"):
            g = group.sort_values(["proj_norm"], ascending=False).reset_index(drop=True)
            total = len(g)
            # remaining (exclude already drafted)
            remaining = g[~g["player"].astype(str).isin(st.session_state.drafted_set)]
            rem = len(remaining)
            # positional scarcity = fewer remaining → higher scarcity
            sc_base = 1.0 - (rem / (total + 1e-9))
            # drop-off: difference between this player’s proj and the Nth after
            idx_map = {p:i for i,p in enumerate(g["player"])}
            for _, row in g.iterrows():
                i = idx_map[row["player"]]
                j = min(i+5, len(g)-1)  # look 5 picks ahead in same position
                drop = float(row["proj_norm"] - g.iloc[j]["proj_norm"]) if len(g) > 1 else 0.0
                scores.append((row["player"], max(0.0, sc_base*0.5 + drop*0.5)))
        return dict(scores)

    scar_map = scarcity_score(base)

    # roster-need score:
    # If you still need starters at that pos → big boost.
    # If starters filled but FLEX exists and pos is flex-eligible → smaller boost.
    def need_score(pos: str):
        cur = drafted_counts.get(pos, 0)
        need = slots.get(pos, 0)
        if cur < need:
            # need ratio: how far from filling
            return 1.0 if need == 0 else (1.0 - (cur / max(1, need)))
        # FLEX consideration
        if pos in flex_elig and slots.get("FLEX", 0) > 0:
            # count how many flex-eligible drafted vs total flex slots
            drafted_flex = drafted_df[drafted_df["pos"].isin(flex_elig)].shape[0]
            flex_need_left = max(0, slots["FLEX"] - drafted_flex)
            return 0.5 if flex_need_left > 0 else 0.0
        return 0.0

    # bye-week penalty: more players on same pos+bye → bigger penalty
    def bye_penalty(pos: str, bye):
        if bye is None or pd.isna(bye) or my_bye.empty:
            return 0.0
        hit = my_bye[(my_bye["pos"]==pos) & (my_bye["bye"]==bye)]
        if hit.empty: return 0.0
        # 1 player already on that bye at that pos → small penalty; 2+ → bigger
        c = int(hit["count"].iloc[0])
        return min(1.0, 0.3*c)

    # stacking bonus: QB with your WR/TE, or WR/TE with your QB, same team
    my_qb_teams = set(drafted_df.loc[drafted_df["pos"]=="QB","team"]) if "team" in drafted_df.columns else set()
    my_passcatcher_teams = set(drafted_df.loc[drafted_df["pos"].isin(["WR","TE"]),"team"]) if "team" in drafted_df.columns else set()
    def stack_bonus(pos: str, team: str):
        if team is None or pd.isna(team): return 0.0
        team = str(team)
        if pos=="QB" and team in my_passcatcher_teams: return 1.0
        if pos in ["WR","TE"] and team in my_qb_teams: return 0.7
        return 0.0

    # league-scoring nudge (tiny bias)
    def scoring_bias(pos: str):
        bias = 0.0
        # More PPR → bump WR/RB/TE a hair
        if RULES.ppr >= 1.0 and pos in ["WR","RB","TE"]:
            bias += 0.05
        # 6-pt pass TD → bump QB a hair
        if RULES.pass_td >= 6 and pos=="QB":
            bias += 0.05
        return bias

    # Build candidate pool (exclude drafted, filter by pos_choice)
    drafted_names = st.session_state.drafted_set
    pool = base[~base["player"].astype(str).isin(drafted_names)].copy()
    if pos_choice != "ALL":
        pool = pool[pool["pos"].astype(str) == pos_choice]

    # Final score = weighted sum
    def row_score(r):
        pos = str(r.get("pos",""))
        team = r.get("team", None)
        bye  = r.get("bye", None)
        proj = float(r.get("proj_norm", 0.5))
        need = need_score(pos)
        scar = scar_map.get(r["player"], 0.0)
        tier = r.get("tier", pd.NA)
        tier_bonus = 0.0 if pd.isna(tier) else (1.0 - (int(tier)-1)/5.0)  # tier 1→1.0, tier 5→0.2
        bye_pen = bye_penalty(pos, bye)
        stack_b = stack_bonus(pos, team)
        score = (
            w_proj*proj +
            w_need*need +
            w_scar*scar +
            w_tier*tier_bonus +
            w_stack*stack_b -
            w_bye*bye_pen +
            scoring_bias(pos)
        )
        return float(score)

    pool["draft_score"] = pool.apply(row_score, axis=1)

    # Show Best Available by draft_score
    st.markdown("**Best Available (Smart Score)**")
    show_cols = ["player","pos","team","draft_score"]
    if "proj_points" in pool.columns: show_cols.insert(3, "proj_points")
    elif "rank" in pool.columns: show_cols.insert(3, "rank")
    if "bye" in pool.columns: show_cols.append("bye")

    st.dataframe(
        pool.sort_values("draft_score", ascending=False).head(50)[show_cols],
        use_container_width=True, hide_index=True
    )

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
            st.rerun()

    with c2:
        manual_name = st.text_input("Manual add (exact player name)")
        if st.button("Add manual"):
            if manual_name.strip():
                st.session_state.drafted_set.add(manual_name.strip())
                st.rerun()

    # Remove drafted
    drafted_df = all_df[all_df["player"].astype(str).isin(st.session_state.drafted_set)].copy()
    st.markdown("### Drafted so far")
    st.dataframe(
        drafted_df[["player","pos","team"]].sort_values(["pos","player"]),
        use_container_width=True, hide_index=True, height=260
    )

    rem = st.multiselect(
        "Remove drafted entries",
        options=drafted_df["player"].astype(str).tolist(),
        key="rem_drafted"
    )

    col_a, col_b, col_c = st.columns([1,1,1])
    with col_a:
        if st.button("Remove selected"):
            st.session_state.drafted_set.difference_update(rem)
            st.rerun()
    with col_b:
        if st.button("Reset drafted list"):
            st.session_state.drafted_set = set()
            st.rerun()
    with col_c:
        # Export drafted list
        if not drafted_df.empty:
            st.download_button(
                label="Download drafted.csv",
                data=drafted_df[["player","pos","team"]].to_csv(index=False),
                file_name="drafted.csv",
                mime="text/csv"
            )

    # Also let user export Best Available
    if not pool.empty:
        st.download_button(
            label="Download best_available.csv",
            data=pool[["player","pos","team"] + ([sort_by] if sort_by else [])].to_csv(index=False),
            file_name="best_available.csv",
            mime="text/csv"
        )



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
