__all__ = ['MessagesFormat', 'Platform']

from enum import auto

from flanautils import FlanaEnum


class MessagesFormat(FlanaEnum):
    SIMPLE = auto()
    NORMAL = auto()
    COMPLETE = auto()


class Platform(FlanaEnum):
    DISCORD = auto()
    TELEGRAM = auto()
    TWITCH = auto()

    @property
    def name(self):
        return super().name.title()
