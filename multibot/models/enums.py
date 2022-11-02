__all__ = ['Platform']

from enum import auto

from flanautils import FlanaEnum


class Platform(FlanaEnum):
    DISCORD = auto()
    TELEGRAM = auto()
    TWITCH = auto()

    @property
    def name(self):
        return super().name.title()
