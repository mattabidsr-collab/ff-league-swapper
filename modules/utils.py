import os, json, tempfile

APP_STATE_DIR = os.path.join(tempfile.gettempdir(), "ff_helper_state")
os.makedirs(APP_STATE_DIR, exist_ok=True)

def state_path(league_key: str) -> str:
    return os.path.join(APP_STATE_DIR, f"{league_key}.json")

def save_league_state(league_key: str, state: dict):
    try:
        with open(state_path(league_key), "w") as f:
            json.dump(state, f)
    except Exception:
        pass

def load_league_state(league_key: str) -> dict:
    try:
        with open(state_path(league_key), "r") as f:
            return json.load(f)
    except Exception:
        return {}
