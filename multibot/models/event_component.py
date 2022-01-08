from __future__ import annotations  # todo0 remove in 3.11

from typing import Any, TypeVar

from flanautils import FlanaBase, MongoBase

T = TypeVar('T', bound='EventComponent')


class EventComponent(MongoBase, FlanaBase):
    def _dict_repr(self) -> Any:
        return {k: v for k, v in super()._dict_repr().items() if k not in ('original_object', 'original_event')}

    def _json_repr(self) -> Any:
        return {k: v for k, v in super()._json_repr().items() if k not in ('original_object', 'original_event')}

    @classmethod
    def from_event_component(cls, event_component: EventComponent) -> T:
        return cls(**super(EventComponent, event_component)._dict_repr())
