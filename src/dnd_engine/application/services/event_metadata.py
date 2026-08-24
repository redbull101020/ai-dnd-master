from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol


@dataclass(frozen=True)
class EventMetadata:
    event_id: str
    timestamp: datetime

    def __post_init__(self) -> None:
        if type(self.event_id) is not str:
            raise TypeError("event_id must be a str")
        if type(self.timestamp) is not datetime:
            raise TypeError("timestamp must be a datetime")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        if self.timestamp.utcoffset() != timedelta(0):
            raise ValueError("timestamp must be UTC")


class EventMetadataProvider(Protocol):
    def next_metadata(self, campaign_id: str) -> EventMetadata:
        ...
