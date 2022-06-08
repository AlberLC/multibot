from __future__ import annotations  # todo0 remove in 3.11

__all__ = [
    'find_message',
    'admin',
    'block',
    'bot_mentioned',
    'group',
    'ignore_self_message',
    'inline',
    'out_of_service',
    'parse_arguments',
    'reply',
    'MultiBot'
]

import datetime
import functools
import random
from abc import ABC, abstractmethod
from typing import Any, Callable, Generic, Iterable, Type, TypeVar, overload

import discord
import flanautils
import telethon.events
import telethon.events.common
from flanautils import AmbiguityError, Media, NotFoundError, OrderedSet, RatioMatch, return_if_first_empty, shift_args_if_called

from multibot import constants
from multibot.exceptions import LimitError, SendError
from multibot.models import Ban, BotAction, Chat, Message, Mute, Platform, RegisteredCallback, Role, User


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
                if event := flanautils.find(args, constants.MESSAGE_EVENT):
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
        if message.author.id != self.id:
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
        self: MultiBot | None = None
        text = ''
        media: Media | None = None
        buttons: list[str | list[str]] | None = None
        chat: int | str | User | Chat | Message | None = None
        message: Message | None = None

        for arg in args:
            match arg:
                case MultiBot() as self:
                    pass
                case str(text):
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
                case User() as user:
                    chat = user
                case Chat() as chat:
                    pass
                case Message() as message:
                    pass

        chat = await self.get_chat(kwargs.get('chat', chat))
        reply_to = kwargs.get('reply_to', None)
        edit = kwargs.get('edit', None)

        if reply_to is not None:
            if chat:
                raise TypeError('chat and reply_to parameters can not be setted at the same time')
            if edit is not None:
                raise TypeError('reply_to and edit parameters can not be setted at the same time')

        if not chat:
            if isinstance(reply_to, Message) and reply_to.chat:
                chat = reply_to.chat
            elif message:
                chat = message.chat

        if not message and isinstance(reply_to, Message):
            message = reply_to

        for arg_name in ('self', 'text', 'media', 'buttons', 'message'):
            if arg_name not in kwargs:
                kwargs[arg_name] = locals()[arg_name]
        kwargs['chat'] = chat

        return await func(**kwargs)

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
    client: T

    def __init__(self, bot_token: str, bot_client: T):
        self.Chat = Chat
        self.Message = Message
        self.User = User

        self.platform: Platform | None = None
        self.id: int | None = None
        self.name: str | None = None
        self.owner_id: int | None = None
        self.token: str = bot_token
        self.client: T = bot_client
        self._registered_callbacks: list[RegisteredCallback] = []
        self._registered_button_callbacks: list[RegisteredCallback] = []

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

        self.register(self._on_users, constants.KEYWORDS['user'])

        self.register_button(self._on_users_button_press, always=True)

    async def _ban(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        pass

    @staticmethod
    async def _check_messages():
        before_date = datetime.datetime.now(datetime.timezone.utc) - constants.MESSAGE_EXPIRATION_TIME
        Message.collection.delete_many({'last_update': {'$lte': before_date}})
        BotAction.collection.delete_many({'date': {'$lte': before_date}})

    async def _find_users_to_punish(self, message: Message) -> OrderedSet[User]:
        bot_user = await self.get_me(message.chat.group_id)
        users: OrderedSet[User] = OrderedSet(message.mentions)
        if message.replied_message:
            users.add(message.replied_message.author)

        match users:
            case []:
                await self.send_interrogation(message)
                return OrderedSet()
            case [single] if single == bot_user:
                await self.send_negative(message)
                return OrderedSet()

        await flanautils.do_later(constants.COMMAND_MESSAGE_DURATION, self.delete_message, message)
        return users - bot_user

    @abstractmethod
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_author(self, original_message: constants.ORIGINAL_MESSAGE) -> User | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_button_pressed_text(self, event: constants.MESSAGE_EVENT) -> str | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_button_pressed_user(self, event: constants.MESSAGE_EVENT) -> User | None:
        pass

    @abstractmethod
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_chat(self, original_message: constants.ORIGINAL_MESSAGE) -> Chat | None:
        pass

    @abstractmethod
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_mentions(self, original_message: constants.ORIGINAL_MESSAGE) -> list[User]:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_message(self, event: constants.MESSAGE_EVENT) -> Message:
        original_message = event if isinstance(event, constants.ORIGINAL_MESSAGE) else await self._get_original_message(event)

        message = Message(
            platform=self.platform,
            id=await self._get_message_id(original_message),
            author=await self._get_author(original_message),
            text=await self._get_text(original_message),
            button_pressed_text=await self._get_button_pressed_text(event),
            button_pressed_user=await self._get_button_pressed_user(event),
            mentions=await self._get_mentions(original_message),
            chat=await self._get_chat(original_message),
            replied_message=await self._get_replied_message(original_message),
            is_inline=isinstance(event, telethon.events.InlineQuery.Event) if isinstance(event, constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) else None,
            original_object=original_message,
            original_event=event
        )
        message.save(pull_overwrite_fields=('_id', 'config'))

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
    async def _manage_exceptions(self, exceptions: BaseException | Iterable[BaseException], context: Chat | Message):
        if not isinstance(exceptions, Iterable):
            exceptions = (exceptions,)

        for exception in exceptions:
            try:
                raise exception
            except ValueError:
                await self.delete_message(context)
            except LimitError as e:
                await self.delete_message(context)
                await self.send_error(str(e), context)
            except (SendError, NotFoundError) as e:
                await self.send_error(str(e), context)
            except AmbiguityError:
                if constants.RAISE_AMBIGUITY_ERROR:
                    await self.send_error(f'Hay varias acciones relacionadas con tu mensaje. ¿Puedes especificar un poco más?  {random.choice(constants.SAD_EMOJIS)}', context)

    async def _mute(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        pass

    @staticmethod
    def _parse_callbacks(
        text: str,
        registered_callbacks: list[RegisteredCallback],
        ratio_reward_exponent: float = constants.RATIO_REWARD_EXPONENT,
        keywords_lenght_penalty: float = constants.KEYWORDS_LENGHT_PENALTY,
        minimum_ratio_to_match: float = constants.MINIMUM_RATIO_TO_MATCH
    ) -> OrderedSet[RegisteredCallback]:
        text = text.lower()
        # text = flanautils.remove_accents(text)
        text = flanautils.translate(text, {'?': ' ', '¿': ' ', '!': ' ', '¡': ' '})
        # text = flanautils.translate(text, {'auto': 'automatico', 'matico': None, 'matic': None})
        original_text_words = OrderedSet(text.split())
        text_words = original_text_words - flanautils.CommonWords.all_words

        matched_callbacks: set[RatioMatch[RegisteredCallback]] = set()
        always_callbacks: set[RegisteredCallback] = set()
        default_callbacks: set[RegisteredCallback] = set()
        for registered_callback in registered_callbacks:
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
                    for matched_callback in matched_callbacks:  # If the callback has been matched before but with less score it is overwritten, otherwise it is added
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

        return OrderedSet(registered_callback for registered_callback in registered_callbacks if registered_callback in determined_callbacks)

    async def _unban(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        pass

    async def _unmute(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        pass

    # ---------------------------------------------- #
    #                    HANDLERS                    #
    # ---------------------------------------------- #
    @bot_mentioned
    @group
    @admin(send_negative=True)
    async def _on_ban(self, message: Message):
        for user in await self._find_users_to_punish(message):
            await self.ban(user, message, flanautils.words_to_time(message.text), message)

    @find_message
    async def _on_button_press_raw(self, message: Message):
        try:
            registered_callbacks = self._parse_callbacks(message.button_pressed_text, self._registered_button_callbacks)
        except AmbiguityError as e:
            await self._manage_exceptions(e, message)
        else:
            for registered_callback in registered_callbacks:
                await registered_callback(message)

    @inline(False)
    async def _on_delete(self, message: Message):
        if message.replied_message:
            if message.replied_message.author.id == self.id:
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
        for user in await self._find_users_to_punish(message):
            await self.mute(user, message, flanautils.words_to_time(message.text), message)

    @ignore_self_message
    async def _on_new_message_raw(self, message: Message):
        try:
            registered_callbacks = self._parse_callbacks(message.text, self._registered_callbacks)
        except AmbiguityError as e:
            await self._manage_exceptions(e, message)
        else:
            for registered_callback in registered_callbacks:
                await registered_callback(message)

    async def _on_ready(self):
        print(f'{self.name} activado en {self.platform.name} (id: {self.id})')
        await flanautils.do_every(constants.CHECK_MESSAGE_EVERY_SECONDS, self._check_messages)
        await flanautils.do_every(constants.CHECK_MUTES_EVERY_SECONDS, Mute.check_olds, self._unmute, self.platform)
        await flanautils.do_every(constants.CHECK_MUTES_EVERY_SECONDS, Ban.check_olds, self._unban, self.platform)

    @bot_mentioned
    @group
    @admin(send_negative=True)
    async def _on_unban(self, message: Message):
        for user in await self._find_users_to_punish(message):
            await self.unban(user, message, message)

    @group
    @bot_mentioned
    @admin(send_negative=True)
    async def _on_unmute(self, message: Message):
        for user in await self._find_users_to_punish(message):
            await self.unmute(user, message, message)

    @group
    @bot_mentioned
    async def _on_users(self, message: Message):
        role_names = [role.name for role in await self.get_roles(message.chat.group_id)]
        role_names.remove('@everyone')

        user_names = [f'<@{user.id}>' for user in await self.find_users_by_roles([], message)]
        joined_user_names = ', '.join(user_names)
        await self.send(
            f"<b>{len(user_names)} usuario{'' if len(user_names) == 1 else 's'}:<b>\n"
            f"{joined_user_names}\n\n"
            f"<b>Filtrar usuarios por roles:<b>",
            flanautils.chunks([f'❌  {role_name}' for role_name in role_names], 5),
            message
        )

    async def _on_users_button_press(self, message: Message):
        await self._accept_button_event(message)

        try:
            button_role_name = message.button_pressed_text.split()[1]
        except IndexError:
            return
        if not (role_names := [role.name for role in await self.get_roles(message.chat)]) or button_role_name not in role_names:
            return

        new_buttons = []
        selected_role_names = []
        for row in message.original_object.components:
            new_row = []
            for button in row.children:
                emoji, role_name = button.label.split(maxsplit=1)
                if role_name == button_role_name:
                    if emoji == '✔':
                        new_emoji = '❌'
                    else:
                        new_emoji = '✔'
                        selected_role_names.append(role_name)
                    new_row.append(f'{new_emoji}  {role_name}')
                else:
                    if emoji == '✔':
                        selected_role_names.append(role_name)
                    new_row.append(button.label)
            new_buttons.append(new_row)

        await self.edit(new_buttons, message)
        user_names = [f'<@{user.id}>' for user in await self.find_users_by_roles(selected_role_names, message)]
        joined_user_names = ', '.join(user_names)
        await self.edit(
            f"<b>{len(user_names)} usuario{'' if len(user_names) == 1 else 's'}:<b>\n"
            f"{joined_user_names}\n\n"
            f"<b>Filtrar usuarios por roles:<b>",
            message
        )

    # -------------------------------------------------------- #
    # -------------------- PUBLIC METHODS -------------------- #
    # -------------------------------------------------------- #
    async def ban(self, user: int | str | User, group_: int | str | Chat | Message, time: int | datetime.timedelta = None, message: Message = None):
        # noinspection PyTypeChecker
        ban = Ban(self.platform, self.get_user_id(user), self.get_group_id(group_), time)
        await ban.punish(self._ban, self._unban, message)

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

    async def find_users_by_roles(self, roles: Iterable[int | str | Role], group_: int | str | Chat | Message) -> list[User]:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_chat(self, chat: int | str | User | Chat | Message) -> Chat | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    def get_group_id(self, group_: int | str | Chat | Message) -> int | None:
        match group_:
            case int(group_id):
                return group_id
            case str(group_name):
                try:
                    return Chat.find_one({'platform': self.platform.value, 'group_name': group_name}).group_id
                except AttributeError:
                    return
            case Chat() as chat:
                return chat.group_id
            case Message() as message:
                return message.chat.group_id

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    def get_group_name(self, group_: int | str | Chat | Message) -> str | None:
        match group_:
            case int(group_id):
                try:
                    return Chat.find_one({'platform': self.platform.value, 'group_id': group_id}).group_name
                except AttributeError:
                    return
            case str(group_name):
                return group_name
            case Chat() as chat:
                return chat.group_name
            case Message() as message:
                return message.chat.group_name

    async def get_me(self, group_: int | str | Chat | Message = None) -> User | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_role(self, role: int | str | Role, group_: int | str | Chat | Message) -> Role | None:
        if isinstance(role, Role):
            return role

        roles = await self.get_roles(group_)

        match role:
            case int(role_id):
                return flanautils.find(roles, condition=lambda role_: role_.id == role_id)
            case str(role_name):
                return flanautils.find(roles, condition=lambda role_: role_.name == role_name)

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_roles(self, group_: int | str | Chat | Message) -> list[Role]:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_user(self, user: int | str | User, group_: int | str | Chat | Message = None) -> User | None:
        pass

    @abstractmethod
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_users(self, group_: int | str | Chat | Message) -> list[User]:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    def get_user_id(self, user: int | str | User) -> int | None:
        match user:
            case int(user_id):
                return user_id
            case str(user_name):
                try:
                    return User.find_one({'platform': self.platform.value, 'name': user_name}).id
                except AttributeError:
                    return
            case User():
                return user.id

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    def get_user_name(self, user: int | str | User) -> str | None:
        match user:
            case int(user_id):
                try:
                    return User.find_one({'platform': self.platform.value, 'id': user_id}).name
                except AttributeError:
                    return
            case str(user_name):
                return user_name
            case User():
                return user.name

    def is_bot_mentioned(self, message: Message) -> bool:
        return self.id in (mention.id for mention in message.mentions)

    async def is_deaf(self, user: int | str | User, group_: int | str | Chat | Message) -> bool:
        pass

    async def is_muted(self, user: int | str | User, group_: int | str | Chat | Message) -> bool:
        pass

    async def is_self_deaf(self, user: int | str | User, group_: int | str | Chat | Message) -> bool:
        pass

    async def is_self_muted(self, user: int | str | User, group_: int | str | Chat | Message) -> bool:
        pass

    async def mute(self, user: int | str | User, group_: int | str | Chat | Message, time: int | datetime.timedelta, message: Message = None):
        # noinspection PyTypeChecker
        mute = Mute(self.platform, self.get_user_id(user), self.get_group_id(group_), time)
        await mute.punish(self._mute, self._unmute, message)

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

    @overload
    def register_button(self, func_: Callable = None, keywords=(), min_ratio=constants.PARSE_BUTTON_CALLBACKS_MIN_RATIO_DEFAULT, always=False, default=False):
        pass

    @overload
    def register_button(self, keywords=(), min_ratio=constants.PARSE_BUTTON_CALLBACKS_MIN_RATIO_DEFAULT, always=False, default=False):
        pass

    @shift_args_if_called(exclude_self_types='MultiBot', globals_=globals())
    def register_button(self, func_: Callable = None, keywords: str | Iterable[str | Iterable[str]] = (), min_ratio=constants.PARSE_BUTTON_CALLBACKS_MIN_RATIO_DEFAULT, always=False, default=False):
        def decorator(func):
            self._registered_button_callbacks.append(RegisteredCallback(func, keywords, min_ratio, always, default))
            return func

        return decorator(func_) if func_ else decorator

    @abstractmethod
    @parse_arguments
    async def send(self, text='', media: Media = None, buttons: list[str | list[str]] | None = None, chat: int | str | User | Chat | Message | None = None, message: Message = None, *, reply_to: int | str | Message = None, silent: bool = False, send_as_file: bool = None, edit=False) -> Message | None:
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

    async def unban(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        # noinspection PyTypeChecker
        ban = Ban(self.platform, self.get_user_id(user), self.get_group_id(group_))
        await ban.unpunish(self._unban, message)

    async def unmute(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        # noinspection PyTypeChecker
        mute = Mute(self.platform, self.get_user_id(user), self.get_group_id(group_))
        await mute.unpunish(self._unmute, message)
