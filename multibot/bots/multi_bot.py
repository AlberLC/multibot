from __future__ import annotations  # todo0 remove when it's by default

__all__ = [
    'find_message',
    'admin',
    'block',
    'bot_mentioned',
    'group',
    'ignore_self_message',
    'inline',
    'out_of_service',
    'owner',
    'parse_arguments',
    'reply',
    'MultiBot'
]

import asyncio
import contextlib
import datetime
import functools
import random
import traceback
from abc import ABC
from collections import defaultdict
from collections.abc import Callable, Coroutine, Iterable, Iterator, Sequence
from typing import Any, Generic, Literal, TypeVar, overload

import flanautils
import pymongo
from flanautils import AmbiguityError, Media, NotFoundError, OrderedSet, ScoreMatch, return_if_first_empty, shift_args_if_called

from multibot import constants
from multibot.exceptions import BadRoleError, LimitError, SendError, UserDisconnectedError
from multibot.models import Ban, Button, ButtonsInfo, Chat, Message, Mute, Penalty, Platform, RegisteredCallback, Role, User


# ---------------------------------------------------- #
# -------------------- DECORATORS -------------------- #
# ---------------------------------------------------- #
@shift_args_if_called
def find_message(func_: Callable = None, /, return_if_not_found=False) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self: MultiBot, *args, **kwargs):
            def take_arg(type_: type, args_, kwargs_):
                object_ = None
                new_args = []
                for arg in args_:
                    if isinstance(arg, type_):
                        object_ = arg
                    else:
                        new_args.append(arg)
                new_kwargs = {}
                for k, v in kwargs_.items():
                    if isinstance(v, type_):
                        object_ = v
                    else:
                        new_kwargs[k] = v
                return object_, new_args, new_kwargs

            message, args, kwargs = take_arg(Message, args, kwargs)
            if not message:
                event, args, kwargs = take_arg(constants.MESSAGE_EVENT, args, kwargs)
                if event:
                    message = await self._get_message(event)
                elif return_if_not_found:
                    return
                else:
                    raise NotFoundError('No message object')

            return await func(self, message, *args, **kwargs)

        return wrapper

    return decorator(func_) if func_ else decorator


@shift_args_if_called
def admin(func_: Callable = None, /, is_=True, send_negative=False) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        @find_message
        async def wrapper(self: MultiBot, message: Message, *args, **kwargs):
            if is_ is message.author.is_admin or message.chat.is_private:
                return await func(self, message, *args, **kwargs)
            await self.accept_button_event(message)
            if send_negative:
                await self.send_negative(message)

        return wrapper

    return decorator(func_) if func_ else decorator


def block(func: Callable) -> Callable:
    @functools.wraps(func)
    @find_message
    async def wrapper(self: MultiBot, message: Message):
        await self.accept_button_event(message)
        return

    return wrapper


@shift_args_if_called
def bot_mentioned(func_: Callable = None, /, is_=True) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        @find_message
        async def wrapper(self: MultiBot, message: Message, *args, **kwargs):
            if is_ is self.is_bot_mentioned(message):
                return await func(self, message, *args, **kwargs)
            await self.accept_button_event(message)

        return wrapper

    return decorator(func_) if func_ else decorator


@shift_args_if_called
def group(func_: Callable = None, /, is_=True) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        @find_message
        async def wrapper(self: MultiBot, message: Message, *args, **kwargs):
            if is_ is message.chat.is_group:
                return await func(self, message, *args, **kwargs)
            await self.accept_button_event(message)

        return wrapper

    return decorator(func_) if func_ else decorator


def ignore_self_message(func: Callable) -> Callable:
    @functools.wraps(func)
    @find_message
    async def wrapper(self: MultiBot, message: Message, *args, **kwargs):
        if message.author.id != self.id:
            return await func(self, message, *args, **kwargs)
        await self.accept_button_event(message)

    return wrapper


@shift_args_if_called
def inline(func_: Callable = None, /, is_=True) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        @find_message
        async def wrapper(self: MultiBot, message: Message, *args, **kwargs):
            if message.is_inline is None or is_ is message.is_inline:
                return await func(self, message, *args, **kwargs)
            await self.accept_button_event(message)

        return wrapper

    return decorator(func_) if func_ else decorator


def out_of_service(func: Callable) -> Callable:
    @functools.wraps(func)
    @find_message
    async def wrapper(self: MultiBot, message: Message):
        if message.chat.is_private or self.is_bot_mentioned(message):
            await self.send(random.choice(constants.OUT_OF_SERVICES_PHRASES), message)
        await self.accept_button_event(message)

    return wrapper


@shift_args_if_called
def owner(func_: Callable = None, /, is_=True, send_negative=False) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        @find_message
        async def wrapper(self: MultiBot, message: Message, *args, **kwargs):
            if is_ is (message.author.id == self.owner_id):
                return await func(self, message, *args, **kwargs)
            await self.accept_button_event(message)
            if send_negative:
                await self.send_negative(message)

        return wrapper

    return decorator(func_) if func_ else decorator


def parse_arguments(func: Callable) -> Callable:
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        def parse_buttons(buttons_) -> list[list[Button]] | None:
            match buttons_:
                case [*_, str()] as buttons_:
                    buttons_ = [[Button(button_text, False) for button_text in buttons_]]
                case [*_, (str(), bool())] as buttons_:
                    buttons_ = [[Button(button_text, is_checked) for button_text, is_checked in buttons_]]
                case [*_, Button()] as buttons_:
                    buttons_ = [list(buttons_)]
                case [*_, [*_, str()]] as buttons_:
                    buttons_ = list(buttons_)
                    for i, buttons_row in enumerate(buttons_):
                        buttons_[i] = [Button(button_text, False) for button_text in buttons_row]
                case [*_, [*_, (str(), bool())]] as buttons_:
                    buttons_ = list(buttons_)
                    for i, buttons_row in enumerate(buttons_):
                        buttons_[i] = [Button(button_text, is_checked) for button_text, is_checked in buttons_row]
                case [*_, [*_, Button()]] as buttons_:
                    buttons_ = list(buttons_)
                    for i, buttons_row in enumerate(buttons_):
                        buttons_[i] = list(buttons_row)
                case [] as buttons_:
                    pass
                case _:
                    return
            return buttons_

        self: MultiBot | None = None
        text: str | None = None
        media: Media | None = None
        buttons: list[str | tuple[str, bool] | Button | list[str | tuple[str, bool] | Button]] | None = None
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
                case self.User() as user:
                    chat = user
                case self.Chat() as chat:
                    pass
                case self.Message() as message:
                    pass
                case _:
                    buttons = parse_buttons(arg)

        message = kwargs.get('message', message)
        chat = await self.get_chat(kwargs.get('chat', chat))
        if 'buttons' in kwargs:
            buttons = parse_buttons(kwargs['buttons'])
        reply_to = kwargs.get('reply_to')
        edit = kwargs.get('edit')

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

        for arg_name in ('self', 'text', 'media', 'message'):
            if arg_name not in kwargs:
                kwargs[arg_name] = locals()[arg_name]
        kwargs['buttons'] = buttons
        kwargs['chat'] = chat

        return await func(**kwargs)

    return wrapper


@shift_args_if_called
def reply(func_: Callable = None, /, is_=True) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        @find_message
        async def wrapper(self: MultiBot, message: Message, *args, **kwargs):
            if is_ is bool(message.replied_message):
                return await func(self, message, *args, **kwargs)
            await self.accept_button_event(message)

        return wrapper

    return decorator(func_) if func_ else decorator


# ----------------------------------------------------------------------------------------------------- #
# --------------------------------------------- MULTI_BOT --------------------------------------------- #
# ----------------------------------------------------------------------------------------------------- #
T = TypeVar('T')


class MultiBot(Generic[T], ABC):
    Chat = Chat
    Message = Message
    User = User

    def __init__(self, token: str, client: T):
        self.platform: Platform | None = None
        self.id: int | None = None
        self.name: str | None = None
        self.owner_id: int | None = None
        self._owner_chat: Chat | None = None
        self.token: str = token
        self.client: T = client
        self._registered_callbacks: list[RegisteredCallback] = []
        self._registered_button_callbacks: dict[Any, list[Callable]] = defaultdict(list)
        # noinspection PyPep8Naming
        MessageType = self.Message
        self._message_cache: dict[tuple[int, int], MessageType] = {}

    # -------------------------------------------------------- #
    # ------------------- PROTECTED METHODS ------------------ #
    # -------------------------------------------------------- #
    def _add_handlers(self):
        pass

    async def _ban(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        pass

    async def _check_penalties(self, penalty_class: type[Penalty], unpenalize_method: Callable):
        penalties = penalty_class.find({'platform': self.platform.value}, lazy=True)

        for penalty in penalties:
            if penalty.until and penalty.until <= datetime.datetime.now(datetime.timezone.utc):
                try:
                    await self._remove_penalty(penalty, unpenalize_method)
                except UserDisconnectedError:
                    pass

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

        return users - bot_user

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_author(self, original_message: constants.ORIGINAL_MESSAGE) -> User | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_button_pressed_text(self, event: constants.MESSAGE_EVENT) -> str | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_button_presser_user(self, event: constants.MESSAGE_EVENT) -> User | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_chat(self, original_message: constants.ORIGINAL_MESSAGE) -> Chat | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_mentions(self, original_message: constants.ORIGINAL_MESSAGE) -> list[User]:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_message(
        self,
        event: constants.MESSAGE_EVENT,
        pull_overwrite_fields: Iterable[str] = ('_id', 'date')
    ) -> Message:
        original_message = await self._get_original_message(event)

        message_id = await self._get_message_id(original_message)
        chat = await self._get_chat(original_message)
        try:
            cached_message = self._message_cache[message_id, chat.id]
        except KeyError:
            message = self.Message(
                platform=self.platform,
                id=message_id,
                author=await self._get_author(original_message),
                text=await self._get_text(original_message),
                mentions=await self._get_mentions(original_message),
                chat=chat,
                replied_message=await self._get_replied_message(original_message),
                is_inline=isinstance(event, constants.TELEGRAM_INLINE_EVENT) if isinstance(event, constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) else None,
                original_object=original_message,
                original_event=event
            )
            message.resolve()
            message.save(pull_overwrite_fields=pull_overwrite_fields, pull_lazy=False)
            return message

        if cached_message.buttons_info:
            cached_message.buttons_info.pressed_text = await self._get_button_pressed_text(event)
            cached_message.buttons_info.presser_user = await self._get_button_presser_user(event)
        cached_message.original_object = original_message
        cached_message.original_event = event
        return cached_message

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_message_id(self, original_message: constants.ORIGINAL_MESSAGE) -> int | str | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_original_message(self, event: constants.MESSAGE_EVENT) -> constants.ORIGINAL_MESSAGE:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_replied_message(self, original_message: constants.ORIGINAL_MESSAGE) -> Message | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_text(self, original_message: constants.ORIGINAL_MESSAGE) -> str:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _manage_exceptions(
        self,
        exceptions: Exception | Iterable[Exception],
        context: Chat | Message,
        reraise=False,
        print_traceback=False
    ):
        if not isinstance(exceptions, Iterable):
            exceptions = (exceptions,)

        for exception in exceptions:
            # noinspection PyBroadException
            try:
                raise exception
            except LimitError as e:
                await self.delete_message(context)
                await self.send_error(str(e), context)
            except (SendError, NotFoundError) as e:
                await self.send_error(str(e), context)
            except UserDisconnectedError as e:
                await self.send_error(f'{e} no está conectado.', context)
            except AmbiguityError:
                if constants.RAISE_AMBIGUITY_ERROR:
                    await self.send_error(f'Hay varias acciones relacionadas con tu mensaje. ¿Puedes especificar un poco más? {random.choice(constants.SAD_EMOJIS)}', context)
            except Exception:
                if constants.SEND_EXCEPTION_MESSAGE_LINES:
                    traceback_message = '\n'.join(traceback.format_exc().splitlines()[-constants.SEND_EXCEPTION_MESSAGE_LINES:])
                    await self.send(f'{random.choice(constants.EXCEPTION_PHRASES)}\n\n...\n{traceback_message}', context)
                if print_traceback:
                    print(traceback.format_exc())
                if reraise:
                    raise

    async def _mute(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        pass

    @staticmethod
    def _parse_callbacks(
        text: str,
        registered_callbacks: list[RegisteredCallback],
        score_reward_exponent: float = constants.PARSER_SCORE_REWARD_EXPONENT,
        keywords_lenght_penalty: float = constants.PARSER_KEYWORDS_LENGHT_PENALTY,
        minimum_score_to_match: float = constants.PARSER_MIN_SCORE_TO_MATCH
    ) -> OrderedSet[RegisteredCallback]:
        text = flanautils.remove_accents(text.lower())

        original_words = OrderedSet()
        for word in text.split():
            if len(word) <= constants.PARSER_MAX_WORD_LENGTH:
                original_words.add(word)
        important_words = original_words - flanautils.CommonWords.get()

        matched_callbacks: set[tuple[int, ScoreMatch[RegisteredCallback]]] = set()
        always_callbacks: set[RegisteredCallback] = set()
        default_callbacks: set[RegisteredCallback] = set()
        for registered_callback in registered_callbacks:
            if registered_callback.always:
                always_callbacks.add(registered_callback)
            elif registered_callback.default:
                default_callbacks.add(registered_callback)
            else:
                mached_keywords_groups = 0
                total_score = 0
                for keywords_group in registered_callback.keywords:
                    important_words |= {original_word for original_word in original_words if flanautils.cartesian_product_string_matching(original_word, keywords_group, min_score=registered_callback.min_score)}
                    word_matches = flanautils.cartesian_product_string_matching(important_words, keywords_group, min_score=registered_callback.min_score)
                    score = sum((max(matches.values()) + 1) ** score_reward_exponent for matches in word_matches.values())
                    try:
                        score /= max(1., keywords_lenght_penalty * len(keywords_group))
                    except ZeroDivisionError:
                        continue
                    if score:
                        total_score += score
                        mached_keywords_groups += 1

                if mached_keywords_groups and mached_keywords_groups == len(registered_callback.keywords):
                    for priority, matched_callback in matched_callbacks:  # If the callback has been matched before but with less score it is overwritten, otherwise it is added
                        if matched_callback.element.callback == registered_callback.callback:
                            if total_score > matched_callback.score:
                                matched_callbacks.discard((priority, matched_callback))
                                matched_callbacks.add((registered_callback.priority, ScoreMatch(registered_callback, total_score)))
                            break
                    else:
                        matched_callbacks.add((registered_callback.priority, ScoreMatch(registered_callback, total_score)))

        sorted_matched_callbacks = sorted(matched_callbacks, key=lambda e: e[1])
        sorted_matched_callbacks = sorted(sorted_matched_callbacks, key=lambda e: e[0], reverse=True)
        match sorted_matched_callbacks:
            case [(_priority, single)]:
                determined_callbacks = always_callbacks | {single.element}
            case [(first_priority, first), (second_priority, second), *_] if first.score >= minimum_score_to_match:
                if first_priority == second_priority and first.score == second.score:
                    raise AmbiguityError(f'\n{first.element.callback}\n{second.element.callback}')
                determined_callbacks = always_callbacks | {first.element}
            case _:
                determined_callbacks = always_callbacks | default_callbacks

        return OrderedSet(registered_callback for registered_callback in registered_callbacks if registered_callback in determined_callbacks)

    async def _remove_penalty(self, penalty: Penalty, unpenalize_method: Callable, message: Message = None, delete=True):
        try:
            await unpenalize_method(penalty.user_id, penalty.group_id)
        except (BadRoleError, UserDisconnectedError) as e:
            if message and message.chat.original_object:
                await self._manage_exceptions(e, message)
            else:
                raise e
        else:
            if delete:
                penalty.pull_from_database()
                penalty.delete()

    async def _start_async(self):
        pass

    def _start_sync(self):
        asyncio.run(self._start_async())

    async def _unban(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        pass

    async def _unmute(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        pass

    async def _unpenalize_later(self, penalty: Penalty, unpenalize_method: Callable, message: Message = None):
        if penalty.time and penalty.time <= constants.TIME_THRESHOLD_TO_MANUAL_UNPUNISH:
            flanautils.do_later(penalty.time, self._remove_penalty, penalty, unpenalize_method, message)

    def _update_message_attributes(
        self,
        message: Message,
        media: Media = None,
        buttons: list[str | tuple[str, bool] | Button | list[str | tuple[str, bool] | Button]] | None = None,
        chat: int | str | User | Chat | Message | None = None,
        buttons_key: Any = None,
        data: dict = None,
        update_last_edit=False
    ):
        if media is not None:
            if len(bytes(media)) <= constants.PYMONGO_MEDIA_MAX_BYTES:
                message.medias = [media]
            else:
                empty_media = Media.from_dict({k: v for k, v in media.to_dict().items() if k not in ('bytes_', 'song_info')})
                if media.song_info:
                    empty_song_info = Media.from_dict({k: v for k, v in media.song_info.to_dict().items() if k != 'bytes_'})
                    empty_media.song_info = empty_song_info
                message.medias = [empty_media]
        try:
            if buttons is not None:
                self._message_cache[message.id, chat.id].buttons_info.buttons = buttons
            if buttons_key is not None:
                self._message_cache[message.id, chat.id].buttons_info.key = buttons_key
        except (AttributeError, KeyError):
            message.buttons_info = ButtonsInfo(buttons=buttons, key=buttons_key)
        if data is not None:
            message.data = data
        if message.buttons_info or message.data is not None:
            self._message_cache[message.id, chat.id] = message

        if update_last_edit:
            message.update_last_edit()
        message.save()

        return message

    # ---------------------------------------------- #
    #                    HANDLERS                    #
    # ---------------------------------------------- #
    @find_message
    async def _on_button_press_raw(self, message: Message):
        if not message.buttons_info:
            return

        for callback in self._registered_button_callbacks[message.buttons_info.key]:
            try:
                await callback(message)
            except Exception as e:
                await self._manage_exceptions(e, message, reraise=True)

    @ignore_self_message
    async def _on_new_message_raw(self, message: Message):
        try:
            registered_callbacks = self._parse_callbacks(message.text, self._registered_callbacks)
        except AmbiguityError as e:
            await self._manage_exceptions(e, message, reraise=True)
        else:
            for registered_callback in registered_callbacks:
                try:
                    await registered_callback(message)
                except Exception as e:
                    await self._manage_exceptions(e, message, reraise=True)

    async def _on_ready(self):
        constants.load_environment()
        flanautils.init_database()
        print(f'{self.name} activado en {self.platform.name} (id: {self.id})')
        flanautils.do_every(constants.CHECK_OLD_CACHE_MESSAGES_EVERY_SECONDS, self.check_old_cache_messages)
        flanautils.do_every(constants.CHECK_OLD_DATABASE_MESSAGES_EVERY_SECONDS, self.check_old_database_messages)
        flanautils.do_every(constants.CHECK_PENALTIES_EVERY_SECONDS, self.check_bans)
        flanautils.do_every(constants.CHECK_PENALTIES_EVERY_SECONDS, self.check_mutes)

    # -------------------------------------------------------- #
    # -------------------- PUBLIC METHODS -------------------- #
    # -------------------------------------------------------- #
    async def accept_button_event(self, event: constants.MESSAGE_EVENT | Message):
        pass

    async def add_role(self, user: int | str | User, group_: int | str | Chat | Message, role: int | str | Role):
        pass

    async def ban(self, user: int | str | User, group_: int | str | Chat | Message, time: int | datetime.timedelta = None, message: Message = None):
        # noinspection PyTypeChecker
        ban = Ban(self.platform, self.get_user_id(user), self.get_group_id(group_), time)
        await self._ban(ban.user_id, ban.group_id, message)
        ban.save(pull_exclude_fields=('until',))
        await self._unpenalize_later(ban, self._unban, message)

    async def check_bans(self):
        await self._check_penalties(Ban, self._unban)

    async def check_mutes(self):
        await self._check_penalties(Mute, self._unmute)

    def check_old_cache_messages(self):
        keys_to_delete = []
        for k, v in self._message_cache.items():
            if datetime.datetime.now(datetime.timezone.utc) < v.date + constants.BUTTONS_INFOS_EXPIRATION_TIME:
                break

            keys_to_delete.append(k)

        for key in keys_to_delete:
            del self._message_cache[key]

    def check_old_database_messages(self):
        before_date = datetime.datetime.now(datetime.timezone.utc) - constants.DATABASE_MESSAGE_EXPIRATION_TIME
        self.Message.delete_many_raw({'platform': self.platform.value, 'date': {'$lte': before_date}})

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def clear(self, n_messages: int, chat: int | str | Chat | Message):
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def delete_message(
        self,
        message_to_delete: int | str | Message,
        chat: int | str | Chat | Message = None,
        raise_not_found=False
    ):
        pass

    def distribute_buttons(self, texts: Sequence[str], vertically=False) -> list[list[str]]:
        pass

    @parse_arguments
    async def edit(self, *args, **kwargs) -> Message:
        return await self.send(*args, **kwargs | {'edit': True})

    async def filter_mention_ids(self, text: str | Iterable[str], message: Message, delete_names=False) -> list[str]:
        if isinstance(text, str):
            words = text.split()
        else:
            words = text

        ids = []
        if delete_names:
            for user in message.mentions:
                ids.append(user.name.lower())
                ids.append(user.name.split('#')[0].lower())
                ids.append(str(user.id))
        else:
            for user in message.mentions:
                ids.append(str(user.id))
        for role in await self.get_group_roles(message):
            ids.append(str(role.id))

        return [word for word in words if flanautils.remove_symbols(word).strip() not in ids]

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def find_role(self, role: int | str | Role, group_: int | str | Chat | Message) -> Role | None:
        if isinstance(role, Role):
            return role

        roles = await self.get_group_roles(group_)

        match role:
            case int(role_id):
                return flanautils.find(roles, condition=lambda role_: role_.id == role_id)
            case str(role_name):
                return flanautils.find(roles, condition=lambda role_: role_.name == role_name)

    async def find_users_by_roles(self, roles: Iterable[int | str | Role], group_: int | str | Chat | Message) -> list[User]:
        return []

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_chat(self, chat: int | str | User | Chat | Message) -> Chat | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_current_roles(self, user: int | str | User | constants.ORIGINAL_USER, group_: int | str | Chat | Message = None) -> list[Role]:
        return []

    def get_formatted_last_database_messages(self, n_messages: int, name_limit=10, platform_limit=10, chat_limit=10, text_limit=40, timezone=None, simple=False) -> str:
        if simple:
            title = f"       {'Usuario'[:name_limit]:<{name_limit}}  {'Texto'[:text_limit]:<{text_limit}}  {'Fecha':<12}"

            def generator_():
                for i, message in enumerate(self.get_last_database_messages(n_messages, lazy=True), start=1):
                    name = message.author.name.split('#')[0]
                    text = repr(message.text).replace('`', '').strip("'")
                    date = message.date.astimezone(timezone).strftime('%d  %H:%M')
                    yield f"{i:>4}.  {name[:name_limit]:<{name_limit}}  {text[:text_limit]:<{text_limit}}  {date}"
        else:
            title = f"       {'Usuario'[:name_limit]:<{name_limit}}  {'Plataforma'[:platform_limit]:<{platform_limit}}  {'Chat'[:chat_limit]:<{chat_limit}}  {'Texto'[:text_limit]:<{text_limit}}  {'Fecha':<20}"

            def generator_():
                for i, message in enumerate(self.get_last_database_messages(n_messages, lazy=True), start=1):
                    name = message.author.name.split('#')[0]
                    platform = Platform(message.platform).name
                    chat = message.chat.name
                    text = repr(message.text).replace('`', '').strip("'")
                    date = message.date.astimezone(timezone).strftime('%d/%m/%Y  %H:%M:%S')
                    yield f"{i:>4}.  {name[:name_limit]:<{name_limit}}  {platform[:platform_limit]:<{platform_limit}}  {chat[:chat_limit]:<{chat_limit}}  {text[:text_limit]:<{text_limit}}  {date}"

        joined_text = '\n'.join(generator_())
        return f"­<code><code><code>{title}\n\n{joined_text}</code></code></code>"

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    def get_group_id(self, group_: int | str | Chat | Message) -> int | None:
        match group_:
            case int(group_id):
                return group_id
            case str(group_name):
                try:
                    return self.Chat.find_one({'platform': self.platform.value, 'group_name': group_name}).group_id
                except AttributeError:
                    return
            case self.Chat() as chat:
                return chat.group_id
            case self.Message() as message:
                return message.chat.group_id

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    def get_group_name(self, group_: int | str | Chat | Message) -> str | None:
        match group_:
            case int(group_id):
                try:
                    return self.Chat.find_one({'platform': self.platform.value, 'group_id': group_id}).group_name
                except AttributeError:
                    return
            case str(group_name):
                return group_name
            case self.Chat() as chat:
                return chat.group_name
            case self.Message() as message:
                return message.chat.group_name

    @overload
    def get_last_database_messages(self, n_messages: int, lazy: Literal[False] = False) -> list[Message]:
        pass

    @overload
    def get_last_database_messages(self, n_messages: int, lazy: Literal[True] = False) -> Iterator[Message]:
        pass

    def get_last_database_messages(self, n_messages: int, lazy=False) -> Iterator[Message] | list[Message]:
        return self.Message.find(sort_keys=(('date', pymongo.DESCENDING),), limit=n_messages, lazy=lazy)

    async def get_me(self, group_: int | str | Chat | Message = None) -> User | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_message(self, message: int | str | Message, chat: int | str | User | Chat | Message) -> Message | None:
        pass

    @return_if_first_empty([], exclude_self_types='MultiBot', globals_=globals())
    async def get_group_roles(self, group_: int | str | Chat | Message) -> list[Role]:
        return []

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_user(self, user: int | str | User, group_: int | str | Chat | Message = None) -> User | None:
        pass

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
                    return self.User.find_one({'platform': self.platform.value, 'name': user_name}).id
                except AttributeError:
                    return
            case self.User():
                return user.id

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    def get_user_name(self, user: int | str | User) -> str | None:
        match user:
            case int(user_id):
                try:
                    return self.User.find_one({'platform': self.platform.value, 'id': user_id}).name
                except AttributeError:
                    return
            case str(user_name):
                return user_name
            case self.User():
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

    async def make_mention(self, user: int | str | User, group_: int | str | Chat | Message = None) -> str:
        pass

    async def mute(self, user: int | str | User, group_: int | str | Chat | Message, time: int | datetime.timedelta = None, message: Message = None):
        # noinspection PyTypeChecker
        mute = Mute(self.platform, self.get_user_id(user), self.get_group_id(group_), time)
        await self._mute(mute.user_id, mute.group_id, message)
        mute.save(pull_exclude_fields=('until',))
        await self._unpenalize_later(mute, self._unmute, message)

    @property
    async def owner_chat(self) -> Chat:
        if not self._owner_chat:
            self._owner_chat = await self.get_chat(self.owner_id) or await self.get_chat(await self.get_user(self.owner_id))
        return self._owner_chat

    @overload
    def register(self, func_: Callable = None, keywords: str | Iterable[str | Iterable[str]] = (), priority: int | float = 1, min_score=constants.PARSER_MIN_SCORE_DEFAULT, always=False, default=False):
        pass

    @overload
    def register(self, keywords: str | Iterable[str | Iterable[str]] = (), priority: int | float = 1, min_score=constants.PARSER_MIN_SCORE_DEFAULT, always=False, default=False):
        pass

    @shift_args_if_called(exclude_self_types='MultiBot', globals_=globals())
    def register(self, func_: Callable = None, keywords: str | Iterable[str | Iterable[str]] = (), priority: int | float = 1, min_score=constants.PARSER_MIN_SCORE_DEFAULT, always=False, default=False):
        def decorator(func: Callable):
            self._registered_callbacks.append(RegisteredCallback(func, keywords, priority, min_score, always, default))
            return func

        return decorator(func_) if func_ else decorator

    @overload
    def register_button(self, func_: Callable = None, key: Any = None):
        pass

    @overload
    def register_button(self, key: Any = None):
        pass

    @shift_args_if_called(exclude_self_types='MultiBot', globals_=globals())
    def register_button(self, func_: Callable = None, key: Any = None):
        def decorator(func: Callable):
            self._registered_button_callbacks[key].append(func)
            return func

        return decorator(func_) if func_ else decorator

    async def remove_role(self, user: int | str | User, group_: int | str | Chat | Message, role: int | str | Role):
        pass

    @parse_arguments
    async def send(
        self,
        text='',
        media: Media = None,
        buttons: list[str | tuple[str, bool] | Button | list[str | tuple[str, bool] | Button]] | None = None,
        chat: int | str | User | Chat | Message | None = None,
        message: Message = None,
        *,
        buttons_key: Any = None,
        reply_to: int | str | Message = None,
        data: dict = None,
        silent: bool = False,
        send_as_file: bool = None,
        edit=False
    ) -> Message | None:
        pass

    @parse_arguments
    async def send_error(self, *args, **kwargs) -> constants.ORIGINAL_MESSAGE:
        bot_message = await self.send(*args, **kwargs)
        flanautils.do_later(constants.ERROR_MESSAGE_DURATION, self.delete_message, bot_message)
        return bot_message

    @inline
    async def send_inline_results(self, message: Message):
        pass

    async def send_interrogation(self, chat: int | str | User | Chat | Message) -> constants.ORIGINAL_MESSAGE:
        chat = await self.get_chat(chat)
        return await self.send(random.choice(constants.INTERROGATION_PHRASES), chat)

    async def send_negative(self, chat: int | str | User | Chat | Message) -> constants.ORIGINAL_MESSAGE:
        chat = await self.get_chat(chat)
        return await self.send(random.choice(constants.NO_PHRASES), chat)

    def start(self) -> Coroutine | None:
        self._add_handlers()
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            self._start_sync()
        else:
            return self._start_async()

    async def typing(self, chat: int | str | User | Chat | Message) -> contextlib.AbstractAsyncContextManager:
        pass

    async def unban(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        # noinspection PyTypeChecker
        ban = Ban(self.platform, self.get_user_id(user), self.get_group_id(group_))
        await self._remove_penalty(ban, self._unban, message)

    async def unmute(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        # noinspection PyTypeChecker
        mute = Mute(self.platform, self.get_user_id(user), self.get_group_id(group_))
        await self._remove_penalty(mute, self._unmute, message)
