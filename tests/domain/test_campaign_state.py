from dataclasses import fields

from dnd_engine.domain.state.campaign import CampaignState


CANONICAL_FIELDS = (
    "id",
    "ruleset_id",
    "ruleset_version",
)

FORBIDDEN_OR_FUTURE_FIELDS = (
    "creatures",
    "characters",
    "npcs",
    "world",
    "world_state",
    "world_time",
    "game_time",
    "combat",
    "combat_state",
    "quests",
    "inventory",
    "equipment",
    "events",
    "event_log",
    "state_store",
    "event_store",
    "schema_version",
    "metadata",
    "session_state",
    "lifecycle",
    "status",
    "current_session_id",
)


def campaign_state() -> CampaignState:
    return CampaignState(
        id="campaign_001",
        ruleset_id="dnd_5e",
        ruleset_version="5.1",
    )


def test_campaign_state_accepts_canonical_fields() -> None:
    campaign = campaign_state()

    assert campaign.id == "campaign_001"
    assert campaign.ruleset_id == "dnd_5e"
    assert campaign.ruleset_version == "5.1"


def test_campaign_state_has_only_canonical_fields() -> None:
    assert tuple(field.name for field in fields(CampaignState)) == CANONICAL_FIELDS


def test_campaign_state_is_mutable() -> None:
    campaign = campaign_state()

    campaign.ruleset_version = "5.2.2"

    assert campaign.ruleset_version == "5.2.2"


def test_campaign_and_ruleset_identities_are_separate() -> None:
    campaign = campaign_state()

    assert campaign.id == "campaign_001"
    assert campaign.ruleset_id == "dnd_5e"
    assert campaign.id != campaign.ruleset_id


def test_ruleset_id_and_version_are_separate() -> None:
    campaign = campaign_state()

    assert campaign.ruleset_id == "dnd_5e"
    assert campaign.ruleset_version == "5.1"
    assert campaign.ruleset_id != campaign.ruleset_version


def test_campaign_state_does_not_include_cross_domain_or_future_fields() -> None:
    canonical_fields = {field.name for field in fields(CampaignState)}

    assert canonical_fields.isdisjoint(FORBIDDEN_OR_FUTURE_FIELDS)
