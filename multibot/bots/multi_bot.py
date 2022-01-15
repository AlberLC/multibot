from __future__ import annotations  # todo0 remove in 3.11

import datetime
import functools
import random
from abc import abstractmethod
from typing import Any, Callable, Generic, Iterable, Type, TypeVar, overload

import discord
import flanautils
import telethon.events
import telethon.events.common
from flanautils import AmbiguityError, Media, NotFoundError, OrderedSet, RatioMatch, return_if_first_empty, shift_args_if_called

from multibot import constants
from multibot.exceptions import LimitError, SendError
from multibot.models import BotPlatform, Chat, Message, RegisteredCallback, User


# ---------------------------------------------------------- #
# ----------------------- DECORATORS ----------------------- #
# ---------------------------------------------------------- #
@shift_args_if_called
def find_message(func_: Callable = None, /, return_if_not_found=False) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self: MultiBot, *args, **kwargs):
            if not (message := flanautils.find((*args, *kwargs.values()), Message)):
                if event := flanautils.find((*args, *kwargs.values()), constants.MESSAGE_EVENT):
                    message = await self._get_message(event)
                elif return_if_not_found:
                    return
                else:
                    raise NotFoundError('No message object')

            return await func(self, message)

        return wrapper

    return decorator(func_) if func_ else decorator


@shift_args_if_called
def admin(func_: Callable = None, /, is_=True, send_negative=False) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        @find_message
        async def wrapper(self: MultiBot, message: Message, *args, **kwargs):
            message = message
            if is_ == message.author.is_admin or not message.chat.is_group:
                return await func(self, message, *args, **kwargs)
            if send_negative:
                await self.send_negative(message)

        return wrapper

    return decorator(func_) if func_ else decorator


def block(func: Callable) -> Callable:
    @functools.wraps(func)
    async def wrapper(*_args, **_kwargs):
        return

    return wrapper


@shift_args_if_called
def bot_mentioned(func_: Callable = None, /, is_=True) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        @find_message
        async def wrapper(self: MultiBot, message: Message, *args, **kwargs):
            if is_ == self.is_bot_mentioned(message):
                return await func(self, message, *args, **kwargs)

        return wrapper

    return decorator(func_) if func_ else decorator


@shift_args_if_called
def group(func_: Callable = None, /, is_=True) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        @find_message
        async def wrapper(self: MultiBot, message: Message, *args, **kwargs):
            if is_ == message.chat.is_group:
                return await func(self, message, *args, **kwargs)

        return wrapper

    return decorator(func_) if func_ else decorator


def ignore_self_message(func: Callable) -> Callable:
    @functools.wraps(func)
    @find_message
    async def wrapper(self: MultiBot, message: Message, *args, **kwargs):
        if message.author.id != self.bot_id:
            return await func(self, message, *args, **kwargs)

    return wrapper


@shift_args_if_called
def inline(func_: Callable = None, /, is_=True) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        @find_message
        async def wrapper(self: MultiBot, message: Message, *args, **kwargs):
            if message.is_inline is None or is_ == message.is_inline:
                return await func(self, message, *args, **kwargs)

        return wrapper

    return decorator(func_) if func_ else decorator


def out_of_service(func: Callable) -> Callable:
    @functools.wraps(func)
    @find_message
    async def wrapper(self: MultiBot, message: Message, *_args, **_kwargs):
        if self.is_bot_mentioned(message) or not message.chat.is_group:
            await self.send(random.choice(constants.OUT_OF_SERVICES_PHRASES), message)

    return wrapper


def parse_arguments(func: Callable) -> Callable:
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        bot: MultiBot | None = None
        text = ''
        media: Media | None = None
        buttons: list[str | list[str]] = []
        message: Message | None = None
        send_as_file: bool | None = None
        edit = False

        for arg in args:
            match arg:
                case MultiBot() as bot:
                    pass
                case str(text):
                    pass
                case bool(send_as_file_) if send_as_file is None:
                    send_as_file = send_as_file_
                case bool(edit):
                    pass
                case int() | float() as number:
                    text = str(number)
                case Media() as media:
                    pass
                case [str(), *_] as buttons:
                    buttons = [list(buttons)]
                case [[str(), *_], *_] as buttons:
                    buttons = list(buttons)
                    for i, buttons_row in enumerate(buttons):
                        buttons[i] = list(buttons_row)
                case Chat() as chat:
                    message = Message(chat=chat)
                case Message() as message:
                    pass

        send_as_file = send_as_file if (kw_value := kwargs.get('send_as_file')) is None else kw_value
        edit = edit if (kw_value := kwargs.get('edit')) is None else kw_value

        if edit is None:
            args = (bot, text, media, buttons, message)
            kwargs |= {'send_as_file': send_as_file}
        else:
            args = (bot, text, media, buttons, message)
            kwargs |= {'send_as_file': send_as_file, 'edit': edit}

        return await func(*args, **kwargs)

    return wrapper


@shift_args_if_called
def reply(func_: Callable = None, /, is_=True) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        @find_message
        async def wrapper(self: MultiBot, message: Message, *args, **kwargs):
            if is_ == bool(message.replied_message):
                return await func(self, message, *args, **kwargs)

        return wrapper

    return decorator(func_) if func_ else decorator


# ----------------------------------------------------------------------------------------------------- #
# --------------------------------------------- MULTI_BOT --------------------------------------------- #
# ----------------------------------------------------------------------------------------------------- #
T = TypeVar('T')


class MultiBot(Generic[T]):
    def __init__(self, bot_token: str, bot_client: T):
        self.bot_id: int | None = None
        self.bot_name: str | None = None
        self.owner_id: int | None = None
        self.bot_platform: BotPlatform | None = None
        self.bot_token: str = bot_token
        self.bot_client: T = bot_client
        self._registered_callbacks: list[RegisteredCallback] = []
        self._registered_button_callbacks: list[Callable] = []

        self._add_handlers()

    # ----------------------------------------------------------- #
    # -------------------- PROTECTED METHODS -------------------- #
    # ----------------------------------------------------------- #
    def _add_handlers(self):
        self.register(self._on_ban, constants.KEYWORDS['ban'])

        self.register(self._on_delete, constants.KEYWORDS['delete'])
        self.register(self._on_delete, (constants.KEYWORDS['delete'], constants.KEYWORDS['message']))

        self.register(self._on_unban, constants.KEYWORDS['unban'])

    # noinspection PyMethodMayBeStatic
    async def _create_empty_message(self) -> Message:
        return Message()

    @abstractmethod
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_author(self, original_message: constants.ORIGINAL_MESSAGE) -> User | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_button_text(self, original_message: constants.ORIGINAL_MESSAGE) -> str | None:
        pass

    @abstractmethod
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_chat(self, original_message: constants.ORIGINAL_MESSAGE) -> Chat | None:
        pass

    async def _get_me(self, group_id: int | str = None) -> User | None:
        pass

    @abstractmethod
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_mentions(self, original_message: constants.ORIGINAL_MESSAGE) -> list[User]:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_message(self, event: constants.MESSAGE_EVENT) -> Message:
        original_message = event if isinstance(event, constants.ORIGINAL_MESSAGE) else await self._get_original_message(event)

        message = await self._create_empty_message()
        message = message.from_dict({
            'id': await self._get_message_id(original_message),
            'author': await self._get_author(original_message),
            'text': await self._get_text(original_message),
            'button_text': await self._get_button_text(event),
            'mentions': await self._get_mentions(original_message),
            'chat': await self._get_chat(original_message),
            'replied_message': await self._get_replied_message(original_message),
            'is_inline': isinstance(event, telethon.events.InlineQuery.Event) if isinstance(event, constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) else None,
            'original_object': original_message,
            'original_event': event
        })
        message.resolve()
        message.save(pull_exclude=('author', 'button_text', 'chat', 'mentions', 'replied_message'), pull_database_priority=True)

        return message

    @abstractmethod
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_message_id(self, original_message: constants.ORIGINAL_MESSAGE) -> int | str | None:
        pass

    @abstractmethod
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_original_message(self, event: constants.MESSAGE_EVENT) -> constants.ORIGINAL_MESSAGE:
        pass

    @abstractmethod
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_replied_message(self, original_message: constants.ORIGINAL_MESSAGE) -> Message | None:
        pass

    @abstractmethod
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_text(self, original_message: constants.ORIGINAL_MESSAGE) -> str:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _manage_exceptions(self, exceptions: BaseException | Iterable[BaseException], message: Message):
        if not isinstance(exceptions, Iterable):
            exceptions = (exceptions,)

        for exception in exceptions:
            try:
                raise exception
            except ValueError:
                await self.delete_message(message)
            except LimitError as e:
                await self.delete_message(message)
                await self.send_error(str(e), message)
            except (SendError, NotFoundError) as e:
                await self.send_error(str(e), message)
            except AmbiguityError:
                if constants.RAISE_AMBIGUITY_ERROR:
                    await self.send_error(f'Hay varias acciones relacionadas con tu mensaje. ¿Puedes especificar un poco más?  {random.choice(constants.SAD_EMOJIS)}', message)

    def _parse_callbacks(
        self,
        text: str,
        ratio_reward_exponent: float = 7,
        keywords_lenght_penalty: float = 0.05,
        minimum_ratio_to_match: float = 21
    ) -> OrderedSet[RegisteredCallback]:
        text = text.lower()
        text = flanautils.remove_accents(text)
        text = flanautils.translate(text, {'?': ' ', '¿': ' ', '!': ' ', '¡': ' ', '_': ' ', 'auto': 'auto '})
        text = flanautils.translate(text, {'auto': 'automatico', 'matico': None, 'matic': None})
        original_text_words = OrderedSet(text.split())
        text_words = original_text_words - flanautils.CommonWords.words

        matched_callbacks: set[RatioMatch[RegisteredCallback]] = set()
        always_callbacks: set[RegisteredCallback] = set()
        default_callbacks: set[RegisteredCallback] = set()
        for registered_callback in self._registered_callbacks:
            if registered_callback.always:
                always_callbacks.add(registered_callback)
            elif registered_callback.default:
                default_callbacks.add(registered_callback)
            else:
                mached_keywords_groups = 0
                total_ratio = 0
                for keywords_group in registered_callback.keywords:
                    text_words += [original_text_word for original_text_word in original_text_words if original_text_word in keywords_group]
                    word_matches = flanautils.cartesian_product_string_matching(text_words, keywords_group, min_ratio=registered_callback.min_ratio)
                    ratio = sum((max(matches.values()) + 1) ** ratio_reward_exponent for text_word, matches in word_matches.items())
                    try:
                        ratio /= max(1., keywords_lenght_penalty * len(keywords_group))
                    except ZeroDivisionError:
                        continue
                    if ratio:
                        total_ratio += ratio
                        mached_keywords_groups += 1

                if mached_keywords_groups and mached_keywords_groups == len(registered_callback.keywords):
                    for matched_callback in matched_callbacks:
                        if matched_callback.element.callback == registered_callback.callback:
                            if total_ratio > matched_callback.ratio:
                                matched_callbacks.discard(matched_callback)
                                matched_callbacks.add(RatioMatch(registered_callback, total_ratio))
                            break
                    else:
                        matched_callbacks.add(RatioMatch(registered_callback, total_ratio))

        match sorted(matched_callbacks):
            case [single]:
                determined_callbacks = always_callbacks | {single.element}
            case [first, second, *_] if first.ratio >= minimum_ratio_to_match:
                if first.ratio == second.ratio:
                    raise AmbiguityError(f'\n{first.element.callback}\n{second.element.callback}')
                determined_callbacks = always_callbacks | {first.element}
            case _:
                determined_callbacks = always_callbacks | default_callbacks

        return OrderedSet(registered_callback for registered_callback in self._registered_callbacks if registered_callback in determined_callbacks)

    async def _update_punishment(self, func_: callable, message: Message, **kwargs):
        bot_user = await self._get_me(message.chat.group_id)
        users: OrderedSet[User] = OrderedSet(message.mentions)
        if message.replied_message:
            users.add(message.replied_message.author)

        match users:
            case []:
                await self.send_interrogation(message)
                return
            case [single] if single == bot_user:
                await self.send_negative(message)
                return

        users -= bot_user
        for user in users:
            await func_(user.id, message.chat.group_id, message=message, **kwargs)

        await flanautils.do_later(constants.COMMAND_MESSAGE_DURATION, message.original_object.delete)

    # ---------------------------------------------- #
    #                    HANDLERS                    #
    # ---------------------------------------------- #
    @bot_mentioned
    @group
    @admin(send_negative=True)
    async def _on_ban(self, message: Message):
        await self._update_punishment(self.ban, message, time=flanautils.words_to_time(message.text))

    @find_message
    async def _on_button_press_raw(self, message: Message):
        for registered_button_callback in self._registered_button_callbacks:
            await registered_button_callback(message)

    @inline(False)
    async def _on_delete(self, message: Message):
        if message.replied_message:
            if message.replied_message.author.id == self.bot_id:
                await self.delete_message(message.replied_message)
                await self.delete_message(message)
            elif self.is_bot_mentioned(message):
                await self.send_negative(message)
        elif message.author.is_admin and self.is_bot_mentioned(message) and (n_messages := flanautils.sum_numbers_in_text(message.text)):
            if n_messages <= 0:
                await self._manage_exceptions(ValueError(), message)
                return

            await self.clear(n_messages, message.chat)

    @ignore_self_message
    async def _on_new_message_raw(self, message: Message):
        try:
            registered_callbacks = self._parse_callbacks(message.text, constants.RATIO_REWARD_EXPONENT, constants.KEYWORDS_LENGHT_PENALTY, constants.MINIMUM_RATIO_TO_MATCH)
        except AmbiguityError as e:
            await self._manage_exceptions(e, message)
        else:
            for registered_callback in registered_callbacks:
                await registered_callback(message)

    async def _on_ready(self):
        print(f'{self.bot_name} activado en {self.bot_platform.name} (id: {self.bot_id})')

    @bot_mentioned
    @group
    @admin(send_negative=True)
    async def _on_unban(self, message: Message):
        await self._update_punishment(self.unban, message)

    # -------------------------------------------------------- #
    # -------------------- PUBLIC METHODS -------------------- #
    # -------------------------------------------------------- #
    async def ban(self, user: int | str | User, chat: int | str | Chat | Message, seconds: int | datetime.timedelta = None):
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def clear(self, n_messages: int, chat: int | str | Chat | Message):
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def delete_message(self, message_to_delete: int | str | Message, chat: int | str | Chat | Message = None):
        pass

    @overload
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_chat(self, chat_id: int) -> Chat | None:
        pass

    @overload
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_chat(self, chat_name: str) -> Chat | None:
        pass

    @overload
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_chat(self, chat: Chat) -> Chat | None:
        pass

    @overload
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_chat(self, message: Message) -> Chat | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_chat(self, chat: int | str | Chat | Message) -> Chat | None:
        pass

    @overload
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_user(self, user_id: int, group_id: int | str = None) -> User | None:
        pass

    @overload
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_user(self, user_name: str, group_id: int | str = None) -> User | None:
        pass

    @overload
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_user(self, user: User, group_id: int | str = None) -> User | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_user(self, user: int | str | User, group_id: int | str = None) -> User | None:
        pass

    @overload
    def register(self, func_: Callable = None, keywords=(), min_ratio=constants.PARSE_CALLBACKS_MIN_RATIO_DEFAULT, always=False, default=False):
        pass

    @overload
    def register(self, keywords=(), min_ratio=constants.PARSE_CALLBACKS_MIN_RATIO_DEFAULT, always=False, default=False):
        pass

    @shift_args_if_called(exclude_self_types='MultiBot', globals_=globals())
    def register(self, func_: Callable = None, keywords: str | Iterable[str | Iterable[str]] = (), min_ratio=constants.PARSE_CALLBACKS_MIN_RATIO_DEFAULT, always=False, default=False):
        def decorator(func):
            self._registered_callbacks.append(RegisteredCallback(func, keywords, min_ratio, always, default))
            return func

        return decorator(func_) if func_ else decorator

    @shift_args_if_called(exclude_self_types='MultiBot', globals_=globals())
    def register_button(self, func_: Callable = None):
        def decorator(func):
            self._registered_button_callbacks.append(func)
            return func

        return decorator(func_) if func_ else decorator

    @abstractmethod
    @parse_arguments
    async def send(self, text='', media: Media = None, buttons: list[str | list[str]] = None, message: Message = None, send_as_file: bool = None, edit=False, **_kwargs) -> Message | None:
        pass

    @parse_arguments
    async def edit(self, *args, **kwargs) -> Message:
        kwargs |= {'edit': True}
        return await self.send(*args, **kwargs)

    def is_bot_mentioned(self, message: Message) -> bool:
        return self.bot_id in (mention.id for mention in message.mentions)

    @parse_arguments
    async def send_error(self, *args, exceptions_to_ignore: Type[BaseException] | Iterable[Type[BaseException]] = (), **kwargs) -> constants.ORIGINAL_MESSAGE:
        bot_message = await self.send(*args, **kwargs)
        await flanautils.do_later(constants.ERROR_MESSAGE_DURATION, self.delete_message, bot_message, exceptions_to_ignore=exceptions_to_ignore or discord.errors.NotFound)
        return bot_message

    @inline
    async def send_inline_results(self, message: Message):
        pass

    async def send_interrogation(self, message: Message) -> constants.ORIGINAL_MESSAGE:
        return await self.send(random.choice(constants.INTERROGATION_PHRASES), message)

    async def send_negative(self, message: Message) -> constants.ORIGINAL_MESSAGE:
        return await self.send(random.choice(constants.NO_PHRASES), message)

    @abstractmethod
    async def start(self):
        pass

    async def typing_delay(self, message: Message):
        pass

    async def unban(self, user: int | str | User, chat: int | str | Chat, message: Message = None):
        pass
