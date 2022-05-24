import datetime
from dataclasses import dataclass

from flanautils import DCMongoBase, FlanaBase

from multibot.models.database import db
from multibot.models.enums import Platform


@dataclass(eq=False)
class Mute(DCMongoBase, FlanaBase):
    collection = db.mute
    _unique_keys = ('platform', 'user_id', 'group_id', 'until', 'is_active')
    _nullable_unique_keys = ('until',)

    platform: Platform = None
    user_id: int = None
    group_id: int = None
    until: datetime.datetime = None
    is_active: bool = True

    def __post_init__(self):
        super().__post_init__()
        self.platform = Platform(self.platform)
