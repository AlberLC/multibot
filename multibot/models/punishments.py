from __future__ import annotations  # todo0 remove in 3.11

__all__ = ['PunishmentBase', 'Ban', 'Mute']

import datetime
import itertools
from dataclasses import dataclass
from typing import Any, Callable, Iterator

import flanautils
from flanautils import DCMongoBase, FlanaBase

from multibot import constants
from multibot.exceptions import BadRoleError, UserDisconnectedError
from multibot.models.database import db
from multibot.models.enums import Platform
from multibot.models.message import Message


@dataclass(eq=False)
class PunishmentBase(DCMongoBase, FlanaBase):
    _unique_keys = ('platform', 'user_id', 'group_id', 'until', 'is_active')
    _nullable_unique_keys = ('until',)

    platform: Platform = None
    user_id: int = None
    group_id: int = None
    time: int | datetime.timedelta = None
    until: datetime.datetime = None
    is_active: bool = True

    def __post_init__(self):
        super().__post_init__()
        self.platform = Platform(self.platform)
        if isinstance(self.time, int):
            self.time = datetime.timedelta(seconds=self.time)
        if self.time:
            self.until = datetime.datetime.now(datetime.timezone.utc) + self.time

    @classmethod
    def _get_grouped_punishments(cls, platform: Platform) -> tuple[tuple[tuple[int, int], list[PunishmentBase]], ...]:
        sorted_punishments = cls.find({'platform': platform.value}, sort_keys=('user_id', 'group_id', 'until'))
        group_iterator: Iterator[
            tuple[
                tuple[int, int],
                Iterator[cls]
            ]
        ] = itertools.groupby(sorted_punishments, key=lambda punishment: (punishment.user_id, punishment.group_id))
        return tuple(((user_id, group_id), list(group_)) for (user_id, group_id), group_ in group_iterator)

    def _mongo_repr(self) -> Any:
        return {
            'platform': self.platform.value,
            'user_id': self.user_id,
            'group_id': self.group_id,
            'until': self.until,
            'is_active': self.is_active
        }

    @classmethod
    async def check_olds(cls, unpunishment_method: Callable, platform: Platform):
        punishment_groups = cls._get_grouped_punishments(platform)

        now = datetime.datetime.now(datetime.timezone.utc)
        for (_, _), sorted_punishments in punishment_groups:
            if (last_punishment := sorted_punishments[-1]).until and last_punishment.until <= now:
                await last_punishment.unpunish(unpunishment_method)
                for punishment in sorted_punishments:
                    punishment.delete()

    async def punish(self, punishment_method: Callable, unpunishment_method: Callable, message: Message = None):
        try:
            await punishment_method(self.user_id, self.group_id, message)
        except (BadRoleError, UserDisconnectedError) as e:
            if message and message.chat.original_object:
                await self._manage_exceptions(e, message)
            else:
                raise e
        else:
            self.save()
            if datetime.timedelta() < self.time <= constants.TIME_THRESHOLD_TO_MANUAL_UNPUNISH:
                await flanautils.do_later(self.time, self.check_olds, unpunishment_method, self.platform)

    async def unpunish(self, unpunishment_method: Callable, message: Message = None):
        try:
            await unpunishment_method(self.user_id, self.group_id, message)
        except UserDisconnectedError as e:
            if message and message.chat.original_object:
                await self._manage_exceptions(e, message)
            else:
                raise e
        else:
            try:
                self.__class__.find_one({
                    'platform': self.platform.value,
                    'user_id': self.user_id,
                    'group_id': self.group_id,
                    'until': None
                }).delete()
            except AttributeError:
                pass


@dataclass(eq=False)
class Ban(PunishmentBase):
    collection = db.ban


@dataclass(eq=False)
class Mute(PunishmentBase):
    collection = db.mute
