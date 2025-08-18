from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class Scoring:
    ppr: float = 1.0
    pass_td: int = 4
    rush_td: int = 6

@dataclass
class LeagueRules:
    league_name: str
    num_teams: int
    scoring: Scoring
    roster_slots: Dict[str, int]
    flex_eligible: List[str] = field(default_factory=lambda: ["RB","WR","TE"])

@dataclass
class LeagueState:
    drafted: List[str] = field(default_factory=list)  # player names marked drafted
    roster_csv_path: str = ""  # saved path of last uploaded roster

# Helper to parse dict -> LeagueRules
def parse_league_rules(d: dict) -> LeagueRules:
    sc = d.get("scoring", {}) or {}
    scoring = Scoring(
        ppr=float(sc.get("ppr", 1.0)),
        pass_td=int(sc.get("pass_td", 4)),
        rush_td=int(sc.get("rush_td", 6)),
    )
    return LeagueRules(
        league_name=d.get("league_name", "My League"),
        num_teams=int(d.get("num_teams", 10)),
        scoring=scoring,
        roster_slots=d.get("roster_slots", {"QB":1,"RB":2,"WR":2,"TE":1,"FLEX":1,"DST":1,"K":1,"BENCH":6}),
        flex_eligible=d.get("flex_eligible", ["RB","WR","TE"]),
    )
