from __future__ import annotations  # todo0 remove in 3.11

__all__ = ['Message']

import datetime
from dataclasses import dataclass, field

from multibot import constants
from multibot.models.buttons import ButtonsInfo
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
    id: int | str = None
    author: User = None
    text: str = None
    mentions: list[User] = field(default_factory=list)
    buttons_info: ButtonsInfo = None
    chat: Chat = None
    replied_message: Message = None
    date: datetime.datetime = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc))
    last_edit: datetime.datetime = None
    is_inline: bool = None
    contents: dict = field(default_factory=dict)
    is_deleted: bool = False
    original_object: constants.ORIGINAL_MESSAGE = None
    original_event: constants.MESSAGE_EVENT = None

    def update_last_edit(self):
        self.last_edit = datetime.datetime.now(datetime.timezone.utc)
