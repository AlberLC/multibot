from dataclasses import dataclass, field

from multibot import constants
from multibot.models.database import db
from multibot.models.event_component import EventComponent
from multibot.models.user import User


@dataclass(eq=False)
class Chat(EventComponent):
    collection = db.chat
    _unique_keys = 'id'

    id: int | str = None
    name: str = None
    is_group: bool = None
    users: list[User] = field(default_factory=list)
    group_id: int | str = None
    config: dict[str, bool] = field(default_factory=lambda: {'auto_clear': False})
    original_object: constants.ORIGINAL_CHAT = None
