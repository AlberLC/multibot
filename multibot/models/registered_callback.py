__all__ = ['RegisteredCallbackBase', 'RegisteredCallback', 'RegisteredButtonCallback']

from dataclasses import dataclass
from typing import Callable, Iterable

import flanautils
from flanautils import FlanaBase

from multibot import constants


@dataclass
class RegisteredCallbackBase(FlanaBase):
    callback: Callable

    def __call__(self, *args, **kwargs):
        return self.callback(*args, **kwargs)

    def __eq__(self, other):
        if isinstance(other, RegisteredCallback):
            return self.callback == other.callback
        else:
            return self.callback == other

    def __hash__(self):
        return hash(self.callback)


@dataclass(eq=False)
class RegisteredCallback(RegisteredCallbackBase):
    keywords: str | Iterable[str | Iterable[str]]
    min_ratio: float
    always: bool
    default: bool

    def __init__(
        self,
        callback: Callable,
        keywords: str | Iterable[str | Iterable[str]] = (),
        min_ratio: float = constants.PARSE_CALLBACKS_MIN_RATIO_DEFAULT,
        always=False,
        default=False
    ):
        self.callback = callback
        match keywords:
            case str(keyword):
                self.keywords = (tuple(keyword.strip().split()),)
            case [*_, [*_]]:
                self.keywords = tuple(tuple(keywords_group.strip().split()) if isinstance(keywords_group, str) else tuple(keywords_group) for keywords_group in keywords)
            case [*_, str()]:
                self.keywords = (tuple(flanautils.flatten_iterator(keyword.strip().split() for keyword in keywords)),)
            case _:
                self.keywords = tuple(keywords)
        self.min_ratio = min_ratio
        self.always = always
        self.default = default


@dataclass(eq=False)
class RegisteredButtonCallback(RegisteredCallbackBase):
    key: any
