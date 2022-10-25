__all__ = ['Role']

from dataclasses import dataclass

from multibot import constants
from multibot.models.enums import Platform
from multibot.models.event_component import EventComponent


@dataclass(eq=False)
class Role(EventComponent):
    collection_name = 'role'
    unique_keys = ('platform', 'id', 'name', 'is_admin')

    platform: Platform = None
    id: int = None
    group_id: int = None
    name: str = None
    is_admin: bool = None
    original_object: constants.ROLE = None
