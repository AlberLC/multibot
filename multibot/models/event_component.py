__all__ = ['EventComponent']

from typing import Any

from flanautils import DCMongoBase, FlanaBase


class EventComponent(DCMongoBase, FlanaBase):
    def __getstate__(self):
        return self._mongo_repr()

    def _json_repr(self) -> Any:
        return {k: v for k, v in super()._json_repr().items() if k not in ('original_object', 'original_event')}

    def _mongo_repr(self) -> Any:
        return {k: v for k, v in super()._mongo_repr().items() if k not in ('original_object', 'original_event')}
