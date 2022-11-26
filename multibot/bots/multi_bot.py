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
    'parse_arguments',
    'reply',
    'MultiBot'
]

import datetime
import functools
import random
import traceback
from abc import ABC, abstractmethod
from typing import Any, Callable, Generic, Iterable, Sequence, Type, TypeVar, overload

import discord
import flanautils
import telethon.events
import telethon.events.common
from flanautils import AmbiguityError, Media, NotFoundError, OrderedSet, ScoreMatch, return_if_first_empty, shift_args_if_called

from multibot import constants
from multibot.exceptions import BadRoleError, LimitError, SendError, UserDisconnectedError
from multibot.models import Ban, Button, Chat, Message, Mute, Penalty, Platform, RegisteredButtonCallback, RegisteredCallback, Role, User


# ---------------------------------------------------------- #
# ----------------------- DECORATORS ----------------------- #
# ---------------------------------------------------------- #
@shift_args_if_called
def find_message(func_: Callable = None, /, return_if_not_found=False) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self: MultiBot, *args, **kwargs):
            def take_arg(type_: Type, args_, kwargs_):
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
            message = message
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
    client: T
    Chat = Chat
    Message = Message
    User = User

    def __init__(self, bot_token: str, bot_client: T):
        self.platform: Platform | None = None
        self.id: int | None = None
        self.name: str | None = None
        self.owner_id: int | None = None
        self.token: str = bot_token
        self.client: T = bot_client
        self._registered_callbacks: list[RegisteredCallback] = []
        self._registered_button_callbacks: list[RegisteredButtonCallback] = []

        self._add_handlers()

    # ----------------------------------------------------------- #
    # -------------------- PROTECTED METHODS -------------------- #
    # ----------------------------------------------------------- #
    def _add_handlers(self):
        pass

    async def _ban(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        pass

    async def _check_penalties(self, penalty_class: Type[Penalty], unpenalize_method: Callable):
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

    @abstractmethod
    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_author(self, original_message: constants.ORIGINAL_MESSAGE) -> User | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_button_pressed_text(self, event: constants.MESSAGE_EVENT) -> str | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def _get_button_presser_user(self, event: constants.MESSAGE_EVENT) -> User | None:
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
    async def _get_message(
        self,
        event: constants.MESSAGE_EVENT,
        pull_overwrite_fields: Iterable[str] = ('_id',)
    ) -> Message:
        original_message = event if isinstance(event, constants.ORIGINAL_MESSAGE) else await self._get_original_message(event)

        message = self.Message(
            platform=self.platform,
            id=await self._get_message_id(original_message),
            author=await self._get_author(original_message),
            text=await self._get_text(original_message),
            mentions=await self._get_mentions(original_message),
            chat=await self._get_chat(original_message),
            replied_message=await self._get_replied_message(original_message),
            is_inline=isinstance(event, telethon.events.InlineQuery.Event) if isinstance(event, constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) else None,
            original_object=original_message,
            original_event=event
        )
        message.resolve()
        message.pull_from_database()
        if message.buttons_info:
            message.buttons_info.pressed_text = await self._get_button_pressed_text(event)
            message.buttons_info.presser_user = await self._get_button_presser_user(event)
        message.save(pull_overwrite_fields=pull_overwrite_fields)

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
            except UserDisconnectedError as e:
                await self.send_error(f'{e} no está conectado.', context)
            except AmbiguityError:
                if constants.RAISE_AMBIGUITY_ERROR:
                    await self.send_error(f'Hay varias acciones relacionadas con tu mensaje. ¿Puedes especificar un poco más? {random.choice(constants.SAD_EMOJIS)}', context)
            except Exception:
                if constants.SEND_EXCEPTION_MESSAGE_LINES:
                    traceback_message = '\n'.join(traceback.format_exc().splitlines()[-constants.SEND_EXCEPTION_MESSAGE_LINES:])
                    await self.send(f'{random.choice(constants.EXCEPTION_PHRASES)}\n\n...\n{traceback_message}', context)
                raise

    async def _mute(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        pass

    @staticmethod
    def _parse_callbacks(
        text: str,
        registered_callbacks: list[RegisteredCallback],
        score_reward_exponent: float = constants.SCORE_REWARD_EXPONENT,
        keywords_lenght_penalty: float = constants.KEYWORDS_LENGHT_PENALTY,
        minimum_score_to_match: float = constants.MINIMUM_SCORE_TO_MATCH
    ) -> OrderedSet[RegisteredCallback]:
        text = flanautils.remove_accents(text.lower())

        original_words = OrderedSet()
        for word in text.split():
            if len(word) <= constants.MAX_WORD_LENGTH:
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
                    important_words |= {original_text_word for original_text_word in original_words if flanautils.cartesian_product_string_matching(original_text_word, keywords_group, min_score=registered_callback.min_score)}
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

    async def _unban(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        pass

    async def _unmute(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        pass

    async def _unpenalize_later(self, penalty: Penalty, unpenalize_method: Callable, message: Message = None):
        if penalty.time and datetime.timedelta() <= penalty.time <= constants.TIME_THRESHOLD_TO_MANUAL_UNPUNISH:
            await flanautils.do_later(penalty.time, self._remove_penalty, penalty, unpenalize_method, message)

    # ---------------------------------------------- #
    #                    HANDLERS                    #
    # ---------------------------------------------- #
    @find_message
    async def _on_button_press_raw(self, message: Message):
        if getattr(message.buttons_info, 'key', None) is None:
            return

        for registered_callback in self._registered_button_callbacks:
            if registered_callback.key == message.buttons_info.key:
                try:
                    await registered_callback(message)
                except Exception as e:
                    await self._manage_exceptions(e, message)

    @ignore_self_message
    async def _on_new_message_raw(self, message: Message):
        try:
            registered_callbacks = self._parse_callbacks(message.text, self._registered_callbacks)
        except AmbiguityError as e:
            await self._manage_exceptions(e, message)
        else:
            for registered_callback in registered_callbacks:
                try:
                    await registered_callback(message)
                except Exception as e:
                    await self._manage_exceptions(e, message)

    async def _on_ready(self):
        flanautils.init_db()
        print(f'{self.name} activado en {self.platform.name} (id: {self.id})')
        await flanautils.do_every(constants.CLEAR_OLD_DATABASE_ITEMS_EVERY_SECONDS, self.clear_old_database_items)
        await flanautils.do_every(constants.CHECK_MUTES_EVERY_SECONDS, self.check_bans)
        await flanautils.do_every(constants.CHECK_MUTES_EVERY_SECONDS, self.check_mutes)

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

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def clear(self, n_messages: int, chat: int | str | Chat | Message):
        pass

    @classmethod
    async def clear_old_database_items(cls):
        before_date = datetime.datetime.now(datetime.timezone.utc) - constants.MESSAGE_EXPIRATION_TIME
        cls.Message.collection.delete_many({'date': {'$lte': before_date}})

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
        pass

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

    async def get_me(self, group_: int | str | Chat | Message = None) -> User | None:
        pass

    @return_if_first_empty(exclude_self_types='MultiBot', globals_=globals())
    async def get_message(self, chat: int | str | User | Chat | Message, message: int | str | Message) -> Message | None:
        pass

    @return_if_first_empty([], exclude_self_types='MultiBot', globals_=globals())
    async def get_group_roles(self, group_: int | str | Chat | Message) -> list[Role]:
        return []

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

    async def mute(self, user: int | str | User, group_: int | str | Chat | Message, time: int | datetime.timedelta = None, message: Message = None):
        # noinspection PyTypeChecker
        mute = Mute(self.platform, self.get_user_id(user), self.get_group_id(group_), time)
        try:
            await self._mute(mute.user_id, mute.group_id)
        except UserDisconnectedError as e:
            if message and message.chat.original_object:
                await self._manage_exceptions(e, message)
            else:
                raise e
        else:
            mute.save(pull_exclude_fields=('until',))
            await self._unpenalize_later(mute, self._unmute, message)

    @overload
    def register(self, func_: Callable = None, keywords=(), priority: int | float = 1, min_score=constants.PARSE_CALLBACKS_MIN_SCORE_DEFAULT, always=False, default=False):
        pass

    @overload
    def register(self, keywords=(), priority: int | float = 1, min_score=constants.PARSE_CALLBACKS_MIN_SCORE_DEFAULT, always=False, default=False):
        pass

    @shift_args_if_called(exclude_self_types='MultiBot', globals_=globals())
    def register(self, func_: Callable = None, keywords: str | Iterable[str | Iterable[str]] = (), priority: int | float = 1, min_score=constants.PARSE_CALLBACKS_MIN_SCORE_DEFAULT, always=False, default=False):
        def decorator(func):
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
        def decorator(func):
            self._registered_button_callbacks.append(RegisteredButtonCallback(func, key))
            return func

        return decorator(func_) if func_ else decorator

    async def remove_role(self, user: int | str | User, group_: int | str | Chat | Message, role: int | str | Role):
        pass

    @abstractmethod
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
    async def send_error(self, *args, exceptions_to_capture: Type[BaseException] | Iterable[Type[BaseException]] = (), **kwargs) -> constants.ORIGINAL_MESSAGE:
        bot_message = await self.send(*args, **kwargs)
        await flanautils.do_later(constants.ERROR_MESSAGE_DURATION, self.delete_message, bot_message, exceptions_to_capture=exceptions_to_capture or discord.errors.NotFound)
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
        await self._remove_penalty(ban, self._unban, message)

    async def unmute(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        # noinspection PyTypeChecker
        mute = Mute(self.platform, self.get_user_id(user), self.get_group_id(group_))
        await self._remove_penalty(mute, self._unmute, message)
