from __future__ import annotations  # todo0 remove in 3.11

import datetime
from dataclasses import dataclass, field
from typing import AbstractSet, Iterable

from multibot import constants
from multibot.models.chat import Chat
from multibot.models.database import db
from multibot.models.enums import Platform
from multibot.models.event_component import EventComponent
from multibot.models.user import User


@dataclass(eq=False)
class Message(EventComponent):
    collection = db.message
    _unique_keys = ('platform', 'id', 'author')
    _nullable_unique_keys = ('platform', 'id', 'author')

    platform: Platform = None
    id: int = None
    author: User = None
    text: str = None
    buttons: list[list[str]] = None
    last_button_pressed: str = None
    mentions: list[User] = field(default_factory=list)
    chat: Chat = None
    replied_message: Message = None
    last_update: datetime.datetime = None
    is_inline: bool = None
    contents: list = field(default_factory=list)
    is_deleted: bool = False
    original_object: constants.ORIGINAL_MESSAGE = None
    original_event: constants.MESSAGE_EVENT = None

    def save(self, pickle_types: tuple | list = (AbstractSet,), pull_overwrite_fields: Iterable[str] = (), references=True):
        self.last_update = datetime.datetime.now(datetime.timezone.utc)
        super().save(pickle_types, pull_overwrite_fields, references)
