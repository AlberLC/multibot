from __future__ import annotations  # todo0 remove in 3.11

from typing import Any, TypeVar

from flanautils import DCMongoBase, FlanaBase

T = TypeVar('T', bound='EventComponent')


class EventComponent(DCMongoBase, FlanaBase):
    def _json_repr(self) -> Any:
        return {k: v for k, v in super()._json_repr().items() if k not in ('original_object', 'original_event')}

    def _mongo_repr(self) -> Any:
        return {k: v for k, v in super()._mongo_repr().items() if k not in ('original_object', 'original_event')}
