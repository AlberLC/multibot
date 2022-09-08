from __future__ import annotations  # todo0 remove in 3.11

__all__ = ['PunishmentBase', 'Ban', 'Mute']

import datetime
from dataclasses import dataclass, field
from typing import Any, Callable

import flanautils
from flanautils import DCMongoBase, FlanaBase

from multibot import constants
from multibot.exceptions import BadRoleError, UserDisconnectedError
from multibot.models.database import db
from multibot.models.enums import Platform
from multibot.models.message import Message


@dataclass(eq=False)
class PunishmentBase(DCMongoBase, FlanaBase):
    _unique_keys = ('platform', 'user_id', 'group_id')

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

    async def apply(self, punishment_method: Callable, unpunishment_method: Callable, message: Message = None):
        try:
            await punishment_method(self.user_id, self.group_id, message)
        except (BadRoleError, UserDisconnectedError) as e:
            if message and message.chat.original_object:
                await self._manage_exceptions(e, message)
            else:
                raise e
        else:
            self.save(pull_exclude_fields=('until',))
            if self.time is not None and datetime.timedelta() <= self.time <= constants.TIME_THRESHOLD_TO_MANUAL_UNPUNISH:
                await flanautils.do_later(self.time, self.check_olds, unpunishment_method, self.platform)

    @classmethod
    async def check_olds(cls, unpunishment_method: Callable, platform: Platform):
        punishments = cls.find({'platform': platform.value})

        for punishment in punishments:
            if punishment.until and punishment.until <= datetime.datetime.now(datetime.timezone.utc):
                await punishment.remove(unpunishment_method)

    async def remove(self, unpunishment_method: Callable, message: Message = None, delete=True):
        try:
            await unpunishment_method(self.user_id, self.group_id, message)
        except UserDisconnectedError as e:
            if message and message.chat.original_object:
                await self._manage_exceptions(e, message)
            else:
                raise e
        else:
            if delete:
                try:
                    self.__class__.find_one({
                        'platform': self.platform.value,
                        'user_id': self.user_id,
                        'group_id': self.group_id
                    }).delete()
                except AttributeError:
                    pass


@dataclass(eq=False)
class Ban(PunishmentBase):
    collection = db.ban


@dataclass(eq=False)
class Mute(PunishmentBase):
    collection = db.mute
