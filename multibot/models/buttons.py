__all__ = ['Button', 'ButtonsInfo']

from dataclasses import dataclass, field
from typing import Any

from flanautils import FlanaBase

from multibot.models.user import User


@dataclass(eq=False)
class Button(FlanaBase):
    text: str = None
    is_checked: bool = False

    def _dict_repr(self) -> Any:
        return bytes(self)


@dataclass(eq=False)
class ButtonsInfo(FlanaBase):
    pressed_text: str = None
    presser_user: User = None
    buttons: list[list[Button]] = field(default_factory=lambda: [[]])
    key: Any = None

    def __getitem__(self, item) -> Button | None:
        if not item:
            return
        if not isinstance(item, str):
            raise TypeError('index has to be a string')

        for row in self.buttons:
            for button in row:
                if button.text == item:
                    return button

    def _dict_repr(self) -> Any:
        return bytes(self)

    def checked_buttons(self) -> list[Button]:
        return [button for row in self.buttons for button in row if button.is_checked]

    def find_button(self, text: str) -> Button:
        return self[text]

    @property
    def pressed_button(self) -> Button | None:
        return self[self.pressed_text]
