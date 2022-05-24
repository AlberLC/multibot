from dataclasses import dataclass

from multibot import constants
from multibot.models.database import db
from multibot.models.enums import Platform
from multibot.models.event_component import EventComponent


@dataclass(eq=False)
class Role(EventComponent):
    collection = db.role
    _unique_keys = ('platform', 'id', 'name', 'is_admin')

    platform: Platform = None
    id: int = None
    name: str = None
    is_admin: bool = None
    original_object: constants.ROLE = None
