import datetime
from dataclasses import dataclass, field

from flanautils import DCMongoBase, FlanaBase

from multibot.models.chat import Chat
from multibot.models.database import db
from multibot.models.enums import Action
from multibot.models.message import Message
from multibot.models.user import User


@dataclass(eq=False)
class BotAction(DCMongoBase, FlanaBase):
    collection = db.bot_action
    _unique_keys = 'message'
    _nullable_unique_keys = 'message'

    action: Action = None
    message: Message = None
    author: User = None
    chat: Chat = None
    affected_objects: list = field(default_factory=list)
    date: datetime.datetime = field(default_factory=datetime.datetime.now)

    def __post_init__(self):
        super().__post_init__()
        self.author = self.author or getattr(self.message, 'author', None)
        self.chat = self.chat or getattr(self.message, 'chat', None)
