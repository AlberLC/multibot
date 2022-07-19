__all__ = ['User']

from dataclasses import dataclass, field

from multibot import constants
from multibot.models.database import db
from multibot.models.enums import Platform
from multibot.models.event_component import EventComponent
from multibot.models.role import Role


@dataclass(eq=False)
class User(EventComponent):
    collection = db.user
    _unique_keys = ('platform', 'id')

    platform: Platform = None
    id: int = None
    name: str = None
    is_admin: bool = None
    is_bot: bool = None
    roles: list[Role] = field(default_factory=list)
    original_object: constants.ORIGINAL_USER = None

    def group_roles(self, group_id: int) -> list[Role]:
        return [role for role in self.roles if role.group_id == group_id]
