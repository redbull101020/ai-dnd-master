from dataclasses import dataclass


@dataclass
class CampaignState:
    id: str
    ruleset_id: str
    ruleset_version: str
