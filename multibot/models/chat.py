from dataclasses import dataclass, field

from multibot import constants
from multibot.models.database import db
from multibot.models.enums import Platform
from multibot.models.event_component import EventComponent
from multibot.models.role import Role
from multibot.models.user import User


@dataclass(eq=False)
class Chat(EventComponent):
    collection = db.chat
    _unique_keys = ('platform', 'id')

    platform: Platform = None
    id: int = None
    name: str = None
    group_id: int = None
    group_name: str = None
    users: list[User] = field(default_factory=list)
    roles: list[Role] = field(default_factory=list)
    config: dict[str, bool] = field(default_factory=dict)
    original_object: constants.ORIGINAL_CHAT = None

    @property
    def is_group(self) -> bool:
        return self.group_id is not None

    @property
    def is_private(self) -> bool:
        return not self.is_group
