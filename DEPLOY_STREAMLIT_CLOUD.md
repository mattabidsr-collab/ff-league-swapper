# Deploying to Streamlit Cloud

1. Create a new **GitHub** repo (public or private).
2. Upload the contents of this folder (including `streamlit_app.py`, `modules/`, `leagues/`, `data/`, and `requirements.txt`). Keep the folder structure intact.
3. Go to **share.streamlit.io** (Streamlit Community Cloud) and click **New app**.
4. Select your repo and branch, set **Main file path** to `streamlit_app.py`, then click **Deploy**.
5. Once it builds, the app will open at your unique Streamlit Cloud URL.
6. Inside the app, use the **left sidebar** to select your league and upload **roster**, **weekly projections**, and **ROS projections** CSVs (and optional DvP).

Notes:
- The draft 'taken' list is session-scoped. For durable saves across sessions, wire a simple JSON save in `modules/utils.py` to a remote store (S3/Drive/Sheets) or use Streamlit's Community Cloud secrets + API.
- You can change league rules by editing JSONs in `/leagues` or uploading a rules file from the sidebar while the app runs.
