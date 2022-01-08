from dataclasses import dataclass

from multibot import constants
from multibot.models.database import db
from multibot.models.event_component import EventComponent


@dataclass(eq=False)
class User(EventComponent):
    collection = db.user
    _unique_keys = 'id'

    id: int = None
    name: str = None
    is_admin: bool = None
    original_object: constants.ORIGINAL_USER = None
