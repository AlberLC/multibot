from __future__ import annotations  # todo0 remove when it's by default

__all__ = ['Penalty', 'Ban', 'Mute']

import datetime
from dataclasses import dataclass, field
from typing import Any

from flanautils import DCMongoBase, FlanaBase

from multibot.models.enums import Platform


@dataclass(eq=False)
class Penalty(DCMongoBase, FlanaBase):
    unique_keys = ('platform', 'user_id', 'group_id')

    platform: Platform = None
    user_id: int = None
    group_id: int = None
    time: int | datetime.timedelta = None
    until: datetime.datetime = None
    is_active: bool = True
    last_update: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))

    def __post_init__(self):
        super().__post_init__()
        self.platform = Platform(self.platform)
        if isinstance(self.time, int):
            self.time = datetime.timedelta(seconds=self.time)
        if self.time:
            self.until = datetime.datetime.now(datetime.timezone.utc) + self.time

    def _mongo_repr(self) -> Any:
        return {
            'platform': self.platform.value,
            'user_id': self.user_id,
            'group_id': self.group_id,
            'until': self.until,
            'is_active': self.is_active,
            'last_update': self.last_update
        }


@dataclass(eq=False)
class Ban(Penalty):
    collection_name = 'ban'


@dataclass(eq=False)
class Mute(Penalty):
    collection_name = 'mute'
