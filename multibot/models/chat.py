__all__ = ['Chat']

from dataclasses import dataclass

from multibot import constants
from multibot.models.enums import Platform
from multibot.models.event_component import EventComponent


@dataclass(eq=False)
class Chat(EventComponent):
    collection_name = 'chat'
    unique_keys = ('platform', 'id')

    platform: Platform = None
    id: int = None
    name: str = None
    group_id: int = None
    group_name: str = None
    original_object: constants.ORIGINAL_CHAT = None

    @property
    def is_group(self) -> bool:
        return self.group_id is not None

    @property
    def is_private(self) -> bool:
        return not self.is_group
