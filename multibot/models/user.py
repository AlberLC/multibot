__all__ = ['User']

from dataclasses import dataclass

from multibot import constants
from multibot.models.database import db
from multibot.models.enums import Platform
from multibot.models.event_component import EventComponent


@dataclass(eq=False)
class User(EventComponent):
    collection = db.user
    _unique_keys = ('platform', 'id')

    platform: Platform = None
    id: int = None
    name: str = None
    is_admin: bool = None
    is_bot: bool = None
    original_object: constants.ORIGINAL_USER = None
