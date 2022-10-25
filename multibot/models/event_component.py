from __future__ import annotations  # todo0 remove when it's by default

__all__ = ['EventComponent']

from typing import Any, TypeVar

from flanautils import DCMongoBase, FlanaBase

T = TypeVar('T', bound='EventComponent')


class EventComponent(DCMongoBase, FlanaBase):
    def __getstate__(self):
        return self._mongo_repr()

    def _json_repr(self) -> Any:
        return {k: v for k, v in super()._json_repr().items() if k not in ('original_object', 'original_event')}

    def _mongo_repr(self) -> Any:
        return {k: v for k, v in super()._mongo_repr().items() if k not in ('original_object', 'original_event')}
