from enum import auto

from flanautils import FlanaEnum


class Action(FlanaEnum):
    AUTO_WEATHER_CHART = auto()
    MESSAGE_DELETED = auto()


class Platform(FlanaEnum):
    DISCORD = auto()
    TELEGRAM = auto()
    TWITCH = auto()

    @property
    def name(self):
        return super().name.title()
