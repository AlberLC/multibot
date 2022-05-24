from __future__ import annotations  # todo0 remove in 3.11

import datetime
import functools
import itertools
import random
from abc import ABC, abstractmethod
from typing import Any, Callable, Generic, Iterable, Iterator, Type, TypeVar, overload

import discord
import flanautils
import telethon.events
import telethon.events.common
from flanautils import AmbiguityError, Media, NotFoundError, OrderedSet, RatioMatch, return_if_first_empty, shift_args_if_called

from multibot import constants
from multibot.exceptions import LimitError, SendError, UserDisconnectedError
from multibot.models import Chat, Message, Mute, Platform, RegisteredCallback, Role, User


# ---------------------------------------------------------- #
# ----------------------- DECORATORS ----------------------- #
# ---------------------------------------------------------- #
@shift_args_if_called
def find_message(func_: Callable = None, /, return_if_not_found=False) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self: MultiBot, *args, **kwargs):
            args = (*args, *kwargs.values())
            if not (message := flanautils.find(args, Message)):
                if discord_interaction := flanautils.find(args, discord.Interaction):
                    message = await self._get_message(discord_interaction)
                    message.last_button_pressed = flanautils.find(args, str)
                elif event := flanautils.find(args, constants.MESSAGE_EVENT):
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
            if is_ == message.author.is_admin or message.chat.is_private:
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
        if self.is_bot_mentioned(message) or message.chat.is_private:
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
        silent: bool | None = None
        send_as_file: bool | None = None
        edit = False

        for arg in args:
            match arg:
                case MultiBot() as bot:
                    pass
                case str(text):
                    pass
                case bool(silent):
                    pass
                case bool(send_as_file):
                    pass
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

        buttons = buttons or message.buttons or []

        silent = silent if (kw_value := kwargs.get('silent')) is None else kw_value
        send_as_file = send_as_file if (kw_value := kwargs.get('send_as_file')) is None else kw_value
        edit = edit if (kw_value := kwargs.get('edit')) is None else kw_value

        if edit is None:
            args = (bot, text, media, buttons, message)
            kwargs |= {'silent': silent, 'send_as_file': send_as_file}
        else:
            args = (bot, text, media, buttons, message)
            kwargs |= {'silent': silent, 'send_as_file': send_as_file, 'edit': edit}

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


class MultiBot(Generic[T], ABC):
    def __init__(self, bot_token: str, bot_client: T):
        self.Chat = Chat
        self.Message = Message
        self.User = User

        self.bot_platform: Platform | None = None
        self.bot_id: int | None = None
        self.bot_name: str | None = None
        self.owner_id: int | None = None
        self.bot_token: str = bot_token
        self.bot_client: T = bot_client
        self._registered_callbacks: list[RegisteredCallback] = []
        self._registered_button_callbacks: list[Callable] = []

        self._add_handlers()

    # ----------------------------------------------------------- #
    # -------------------- PROTECTED METHODS -------------------- #
    # ----------------------------------------------------------- #
    async def _accept_button_event(self, event: constants.MESSAGE_EVENT | Message):
        pass

    def _add_handlers(self):
        self.register(self._on_ban, constants.KEYWORDS['ban'])

        self.register(self._on_delete, constants.KEYWORDS['delete'])
        self.register(self._on_delete, (constants.KEYWORDS['delete'], constants.KEYWORDS['message']))

        self.register(self._on_mute, constants.KEYWORDS['mute'])
        self.register(self._on_mute, (('haz', 'se'), constants.KEYWORDS['mute']))
        self.register(self._on_mute, (constants.KEYWORDS['deactivate'], constants.KEYWORDS['unmute']))
        self.register(self._on_mute, (constants.KEYWORDS['deactivate'], constants.KEYWORDS['sound']))

        self.register(self._on_unban, constants.KEYWORDS['unban'])

        self.register(self._on_unmute, constants.KEYWORDS['unmute'])
        self.register(self._on_unmute, (constants.KEYWORDS['deactivate'], constants.KEYWORDS['mute']))
        self.register(self._on_unmute, (constants.KEYWORDS['activate'], constants.KEYWORDS['sound']))

    @staticmethod
    async def _check_messages():
        Message.collection.delete_many({'last_update': {'$lte': datetime.datetime.now(datetime.timezone.utc) - constants.MESSAGE_EXPIRATION_TIME}})

    async def _check_mutes(self):
        mute_groups = self._get_grouped_punishments(Mute)

        now = datetime.datetime.now(datetime.timezone.utc)
        for (user_id, group_id), sorted_mutes in mute_groups:
            if (last_mute := sorted_mutes[-1]).until and last_mute.until <= now:
                await self.unmute(user_id, group_id)
                for mute in sorted_mutes:
                    mute.delete()

    @abstractmethod
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_author(self, original_message: constants.ORIGINAL_MESSAGE) -> User | None:
        pass

    @abstractmethod
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_chat(self, original_message: constants.ORIGINAL_MESSAGE) -> Chat | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    def _get_group_id(self, group_: int | str | Chat) -> int | None:
        match group_:
            case int():
                return group_
            case str():
                try:
                    return Chat.find_one({'platform': self.bot_platform.value, 'group_name': group_}).group_id
                except AttributeError:
                    pass
            case Chat():
                return group_.group_id

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    def _get_group_name(self, group_: int | str | Chat) -> str | None:
        match group_:
            case int():
                try:
                    return Chat.find_one({'platform': self.bot_platform.value, 'group_id': group_}).group_name
                except AttributeError:
                    pass
            case str():
                return group_
            case Chat():
                return group_.group_name

    def _get_grouped_punishments(self, MuteClass: Type[Mute]) -> tuple[tuple[tuple[int, int], list[Mute]]]:
        sorted_punishments = MuteClass.find({'platform': self.bot_platform.value}, sort_keys=('user_id', 'group_id', 'until'))
        group_iterator: Iterator[
            tuple[
                tuple[int, int],
                Iterator[MuteClass]
            ]
        ] = itertools.groupby(sorted_punishments, key=lambda punishment: (punishment.user_id, punishment.group_id))
        return tuple(((user_id, group_id), list(group_)) for (user_id, group_id), group_ in group_iterator)

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_last_button_pressed(self, original_message: constants.ORIGINAL_MESSAGE) -> str | None:
        pass

    async def _get_me(self, group_: int | str | Chat = None) -> User | None:
        pass

    @abstractmethod
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_mentions(self, original_message: constants.ORIGINAL_MESSAGE) -> list[User]:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_message(self, event: constants.MESSAGE_EVENT) -> Message:
        original_message = event if isinstance(event, constants.ORIGINAL_MESSAGE) else await self._get_original_message(event)

        message = Message(
            platform=self.bot_platform,
            id=await self._get_message_id(original_message),
            author=await self._get_author(original_message),
            text=await self._get_text(original_message),
            last_button_pressed=await self._get_last_button_pressed(event),
            mentions=await self._get_mentions(original_message),
            chat=await self._get_chat(original_message),
            replied_message=await self._get_replied_message(original_message),
            is_inline=isinstance(event, telethon.events.InlineQuery.Event) if isinstance(event, constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) else None,
            original_object=original_message,
            original_event=event
        )
        message.resolve()
        message.save(pull_overwrite_fields='config')

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

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_roles_from_group_id(self, group_id: int) -> list[Role]:
        pass

    @abstractmethod
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_text(self, original_message: constants.ORIGINAL_MESSAGE) -> str:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    def _get_user_id(self, user: int | str | User) -> int | None:
        match user:
            case int():
                return user
            case str():
                try:
                    return User.find_one({'platform': self.bot_platform.value, 'name': user}).id
                except AttributeError:
                    pass
            case User():
                return user.id

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

    async def _mute(self, user: int | str | User, group_: int | str | Chat):
        pass

    def _parse_callbacks(
        self,
        text: str,
        ratio_reward_exponent: float = constants.RATIO_REWARD_EXPONENT,
        keywords_lenght_penalty: float = constants.KEYWORDS_LENGHT_PENALTY,
        minimum_ratio_to_match: float = constants.MINIMUM_RATIO_TO_MATCH
    ) -> OrderedSet[RegisteredCallback]:
        text = text.lower()
        text = flanautils.remove_accents(text)
        text = flanautils.translate(text, {'?': ' ', '¿': ' ', '!': ' ', '¡': ' ', '_': ' ', 'auto': 'auto '})
        text = flanautils.translate(text, {'auto': 'automatico', 'matico': None, 'matic': None})
        original_text_words = OrderedSet(text.split())
        text_words = original_text_words - flanautils.CommonWords.all_words

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

    async def _unmute(self, user: int | str | User, group_: int | str | Chat):
        pass

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

            try:
                await self.clear(n_messages, message.chat)
            except LimitError as e:
                await self._manage_exceptions(e, message)

    @group
    @bot_mentioned
    @admin(send_negative=True)
    async def _on_mute(self, message: Message):
        await self._update_punishment(self.mute, message, time=flanautils.words_to_time(message.text))

    @ignore_self_message
    async def _on_new_message_raw(self, message: Message):
        try:
            registered_callbacks = self._parse_callbacks(message.text)
        except AmbiguityError as e:
            await self._manage_exceptions(e, message)
        else:
            for registered_callback in registered_callbacks:
                await registered_callback(message)

    async def _on_ready(self):
        print(f'{self.bot_name} activado en {self.bot_platform.name} (id: {self.bot_id})')
        await flanautils.do_every(constants.CHECK_MESSAGE_EVERY_SECONDS, self._check_messages)
        await flanautils.do_every(constants.CHECK_MUTES_EVERY_SECONDS, self._check_mutes)

    @bot_mentioned
    @group
    @admin(send_negative=True)
    async def _on_unban(self, message: Message):
        await self._update_punishment(self.unban, message)

    @group
    @bot_mentioned
    @admin(send_negative=True)
    async def _on_unmute(self, message: Message):
        await self._update_punishment(self.unmute, message)

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

    @parse_arguments
    async def edit(self, *args, **kwargs) -> Message:
        kwargs |= {'edit': True}
        return await self.send(*args, **kwargs)

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_chat(self, chat: int | str | Chat | Message) -> Chat | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_role(self, role: int | str | Role, group_: int | str | Chat | Message = None, chat: int | str | Chat | Message = None) -> Role | None:
        if isinstance(role, Role):
            return role

        match group_:
            case int():
                roles = await self._get_roles_from_group_id(group_)
            case str():
                group_id = Chat.find_one({'platform': self.bot_platform.value, 'group_name': group_}).group_id
                roles = await self._get_roles_from_group_id(group_id)
            case Chat():
                roles = group_.roles
            case Message():
                roles = group_.chat.roles
            case _:
                match chat:
                    case int() | str() | Chat() | Message():
                        roles = (await self.get_chat(chat)).roles
                    case _:
                        raise TypeError('bad arguments')

        match role:
            case int():
                return flanautils.find(roles, condition=lambda role_: role_.id == role)
            case str():
                return flanautils.find(roles, condition=lambda role_: role_.name == role)

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_user(self, user: int | str | User, group_: int | str | Chat = None) -> User | None:
        pass

    def is_bot_mentioned(self, message: Message) -> bool:
        return self.bot_id in (mention.id for mention in message.mentions)

    async def is_deaf(self, user: int | str | User, group_: int | str | Chat) -> bool:
        pass

    async def is_muted(self, user: int | str | User, group_: int | str | Chat) -> bool:
        pass

    async def is_self_deaf(self, user: int | str | User, group_: int | str | Chat) -> bool:
        pass

    async def is_self_muted(self, user: int | str | User, group_: int | str | Chat) -> bool:
        pass

    async def mute(self, user: int | str | User, group_: int | str | Chat, time: int | datetime.timedelta, message: Message = None):
        user_id = self._get_user_id(user)
        group_id = self._get_group_id(group_)
        if isinstance(time, int):
            time = datetime.timedelta(seconds=time)

        try:
            await self._mute(user_id, group_id)
        except UserDisconnectedError as e:
            if message and message.chat.original_object:
                await self._manage_exceptions(e, message)
            else:
                raise e
        else:
            if time:
                until = datetime.datetime.now(datetime.timezone.utc) + time
                if datetime.timedelta() < time <= constants.TIME_THRESHOLD_TO_MANUAL_UNMUTE:
                    await flanautils.do_later(time, self._check_mutes)
            else:
                until = None
            # noinspection PyTypeChecker
            Mute(self.bot_platform, user_id, group_id, until=until).save()

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
    async def send(self, text='', media: Media = None, buttons: list[str | list[str]] = None, message: Message = None, silent: bool = False, send_as_file: bool = None, edit=False, **_kwargs) -> Message | None:
        pass

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

    async def unban(self, user: int | str | User, chat: int | str | Chat | Message):
        pass

    async def unmute(self, user: int | str | User, group_: int | str | Chat, message: Message = None):
        try:
            await self._unmute(user, group_)
        except UserDisconnectedError as e:
            if message and message.chat.original_object:
                await self._manage_exceptions(e, message)
            else:
                raise e
        else:
            user_id = self._get_user_id(user)
            group_id = self._get_group_id(group_)
            try:
                Mute.find_one({'platform': self.bot_platform.value, 'user_id': user_id, 'group_id': group_id, 'until': None}).delete()
            except AttributeError:
                pass
