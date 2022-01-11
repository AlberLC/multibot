from __future__ import annotations  # todo0 remove in 3.11

import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import AbstractSet, Iterable

from multibot import constants
from multibot.models.chat import Chat
from multibot.models.database import db
from multibot.models.event_component import EventComponent
from multibot.models.user import User


@dataclass(eq=False)
class Message(EventComponent):
    collection = db.message
    _unique_keys = ('id', 'author')
    _nullable_unique_keys = ('id', 'author')

    id: int | str = None
    author: User = None
    text: str = None
    button_text: str = None
    mentions: Iterable[User] = field(default_factory=list)
    chat: Chat = None
    replied_message: Message = None
    last_update: datetime.datetime = None
    is_inline: bool = None
    contents: list = field(default_factory=list)
    is_deleted: bool = False
    original_object: constants.ORIGINAL_MESSAGE = None
    original_event: constants.MESSAGE_EVENT = None

    def save(self, pickle_types: tuple | list = (Enum, AbstractSet), pull_exclude: Iterable[str] = (), pull_database_priority=False, references=True):
        self.last_update = datetime.datetime.now()
        super().save(pickle_types, pull_exclude, pull_database_priority, references)
