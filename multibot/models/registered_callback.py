__all__ = ['RegisteredCallback']

from collections.abc import Callable, Iterable

import flanautils
from flanautils import FlanaBase

from multibot import constants


class RegisteredCallback(FlanaBase):
    callback: Callable
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
        min_score: float = constants.PARSER_MIN_SCORE_DEFAULT,
        always=False,
        default=False
    ):
        self.callback = callback

        if not keywords:
            keywords = ()
        elif isinstance(keywords, str):
            text = flanautils.remove_accents(keywords.strip().lower())
            self.keywords = (tuple(text.split()),)
        elif isinstance(keywords, Iterable) and any(not isinstance(keyword, str) and isinstance(keyword, Iterable) for keyword in keywords):
            def generator():
                for element in keywords:
                    if isinstance(element, str):
                        text_ = flanautils.remove_accents(element.strip().lower())
                        keywords_group = tuple(text_.split())
                    else:
                        keywords_group = tuple(flanautils.remove_accents(keyword.strip().lower()) for keyword in element)
                    yield keywords_group

            self.keywords = tuple(generator())
        elif isinstance(keywords, Iterable) and any(isinstance(keyword, str) for keyword in keywords):
            keywords = (flanautils.remove_accents(keyword.strip().lower()).split() for keyword in keywords)
            self.keywords = (tuple(flanautils.flatten(keywords, lazy=True)),)
        else:
            raise TypeError('bad arguments')

        self.priority = priority
        self.min_score = min_score
        self.always = always
        self.default = default

    def __call__(self, *args, **kwargs):
        return self.callback(*args, **kwargs)

    def __eq__(self, other):
        if isinstance(other, RegisteredCallback):
            return self.callback == other.callback
        else:
            return self.callback == other

    def __hash__(self):
        return hash(self.callback)
