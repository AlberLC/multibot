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
    keywords: tuple[tuple[str, ...], ...]
    priority: int | float
    min_score: float
    always: bool
    default: bool

    def __init__(
        self,
        callback: Callable,
        keywords: str | Iterable[str | Iterable[str]] = (),
        priority: int | float = 1,
        min_score: float = constants.PARSE_CALLBACKS_MIN_SCORE_DEFAULT,
        always=False,
        default=False
    ):
        self.callback = callback

        match keywords:
            case str(text):
                text = flanautils.remove_accents(text.strip().lower())
                self.keywords = (tuple(text.split()),)
            case [*_, [*_]]:
                def generator():
                    for element in keywords:
                        if isinstance(element, str):
                            text_ = flanautils.remove_accents(element.strip().lower())
                            keywords_group = tuple(text_.split())
                        else:
                            keywords_group = tuple(flanautils.remove_accents(keyword.strip().lower()) for keyword in element)
                        yield keywords_group

                self.keywords = tuple(generator())
            case [*_, str()]:
                keywords = (flanautils.remove_accents(keyword.strip().lower()) for keyword in keywords)
                self.keywords = (tuple(flanautils.flatten_iterator(keywords)),)
            case _:
                self.keywords = tuple(keywords)

        self.priority = priority
        self.min_score = min_score
        self.always = always
        self.default = default


@dataclass(eq=False)
class RegisteredButtonCallback(RegisteredCallbackBase):
    key: any
