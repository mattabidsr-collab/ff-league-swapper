import json, glob, os
from dataclasses import dataclass

@dataclass
class LeagueRules:
    league_name: str
    num_teams: int
    ppr: float
    pass_td: float
    rush_td: float
    roster_slots: dict
    flex_eligible: list

def load_league_rules_files(path="./leagues"):
    """
    Load all league rules JSON files from the given folder.
    Returns a dict {filename_stem: LeagueRules}.
    """
    leagues = {}
    for fp in glob.glob(os.path.join(path, "*.json")):
        with open(fp, "r") as f:
            obj = json.load(f)
        rules = LeagueRules(
            league_name=obj["league_name"],
            num_teams=int(obj["num_teams"]),
            ppr=float(obj["scoring"]["ppr"]),
            pass_td=float(obj["scoring"]["pass_td"]),
            rush_td=float(obj["scoring"]["rush_td"]),
            roster_slots=obj["roster_slots"],
            flex_eligible=obj.get("flex_eligible", ["RB","WR","TE"]),
        )
        leagues[os.path.splitext(os.path.basename(fp))[0]] = rules
    return leagues
