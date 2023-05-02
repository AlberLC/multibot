from __future__ import annotations  # todo0 remove when it's by default

__all__ = ['user_client', 'TelegramBot']

import asyncio
import contextlib
import functools
import io
import pathlib
import struct
from collections.abc import Coroutine
from typing import Any, Callable, Sequence

import flanautils
import pymongo
import telethon
import telethon.hints
import telethon.tl.types
from flanautils import Media, MediaType, OrderedSet, ResponseError, Source, return_if_first_empty, shift_args_if_called
from telethon import TelegramClient
from telethon.sessions import StringSession

from multibot import constants
from multibot.bots.multi_bot import MultiBot, find_message, inline, parse_arguments
from multibot.exceptions import LimitError
from multibot.models import Button, Chat, Message, Platform, User


# ---------------------------------------------------- #
# ----------------- CONTEXT MANAGERS ----------------- #
# ---------------------------------------------------- #
@contextlib.asynccontextmanager
async def use_user_client(self: TelegramBot):
    if await self.client.is_bot():
        await self.user_client.connect()

    yield self.user_client

    if await self.client.is_bot():
        await self.user_client.disconnect()


# ---------------------------------------------------- #
# -------------------- DECORATORS -------------------- #
# ---------------------------------------------------- #
@shift_args_if_called
def user_client(func_: Callable = None, /, is_=True) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self: TelegramBot, *args, **kwargs):
            if is_ == bool(self.user_client):
                return await func(self, *args, **kwargs)

        return wrapper

    return decorator(func_) if func_ else decorator


# ---------------------------------------------------------------------------------------------------- #
# ------------------------------------------- TELEGRAM_BOT ------------------------------------------- #
# ---------------------------------------------------------------------------------------------------- #
class TelegramBot(MultiBot[TelegramClient]):
    def __init__(self, api_id: int | str, api_hash: int | str, bot_token: str = None, bot_session: str = None, phone: int | str = None, user_session: str = None):
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_session = bot_session
        self.phone = phone
        self.user_session = user_session

        if self.bot_session:
            client = TelegramClient(StringSession(bot_session), self.api_id, self.api_hash)
        elif bot_token:
            client = TelegramClient('bot_session', self.api_id, self.api_hash)
        else:
            client = None

        if self.user_session:
            self.user_client = TelegramClient(StringSession(user_session), self.api_id, self.api_hash)
        elif self.phone:
            self.user_client = TelegramClient('user_session', self.api_id, self.api_hash)
        else:
            self.user_client = None

        super().__init__(token=bot_token,
                         client=client)

    # -------------------------------------------------------- #
    # ------------------- PROTECTED METHODS ------------------ #
    # -------------------------------------------------------- #
    # noinspection PyTypeChecker
    def _add_handlers(self):
        super()._add_handlers()
        self.client.add_event_handler(self._on_button_press_raw, telethon.events.CallbackQuery)
        self.client.add_event_handler(self._on_inline_query_raw, telethon.events.InlineQuery)
        self.client.add_event_handler(self._on_new_message_raw, telethon.events.NewMessage)

    async def _ban(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        user = await self.get_user(user, group_)
        chat = await self.get_chat(group_)

        await self.client.edit_permissions(chat.original_object, user.original_object, view_messages=False)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _create_chat_from_telegram_chat(self, original_chat: constants.TELEGRAM_CHAT) -> Chat | None:
        chat_name = self._get_entity_name(original_chat)
        if isinstance(original_chat, constants.TELEGRAM_USER):
            group_id = None
            group_name = None
        else:
            group_id = original_chat.id
            group_name = chat_name

        return self.Chat(
            platform=self.platform,
            id=original_chat.id,
            name=chat_name,
            group_id=group_id,
            group_name=group_name,
            original_object=original_chat
        )

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _create_user_from_telegram_user(self, original_user: constants.TELEGRAM_USER, group_: int | str | Chat | Message = None) -> User | None:
        group_id = self.get_group_id(group_)
        try:
            is_admin = (await self.client.get_permissions(group_id, original_user)).is_admin
        except (AttributeError, TypeError, ValueError):
            is_admin = None

        return self.User(
            platform=self.platform,
            id=original_user.id,
            name=self._get_entity_name(original_user),
            is_admin=is_admin,
            is_bot=original_user.bot,
            original_object=original_user
        )

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_author(self, original_message: constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) -> User | None:
        return await self._create_user_from_telegram_user(await original_message.get_sender(), original_message.chat_id)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_button_pressed_text(self, event: constants.TELEGRAM_EVENT) -> str | None:
        try:
            return event.data.decode()
        except AttributeError:
            pass

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_button_presser_user(self, event: constants.TELEGRAM_EVENT) -> User | None:
        return await self._get_author(event)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_chat(self, original_message: constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) -> Chat | None:
        return await self._create_chat_from_telegram_chat(await original_message.get_chat())

    @return_if_first_empty('', exclude_self_types='TelegramBot', globals_=globals())
    def _get_entity_name(self, entity: telethon.hints.EntityLike) -> str:
        if isinstance(entity, constants.TELEGRAM_USER):
            return entity.username or entity.first_name
        elif isinstance(entity, constants.TELEGRAM_CHAT):
            return entity.title

        return ''

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_mentions(self, original_message: constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) -> list[User]:
        if isinstance(original_message, constants.TELEGRAM_INLINE_EVENT):
            return []

        mentions = OrderedSet()

        if replied_message := await self._get_replied_message(original_message):
            mentions.add(replied_message.author)

        text = await self._get_text(original_message)
        chat = await self._get_chat(original_message)

        for entity in original_message.entities or ():
            if not isinstance(entity, telethon.tl.types.MessageEntityMention):
                continue

            try:
                mentions.add(await self.get_user(text[entity.offset:entity.offset + entity.length], chat.group_id))
            except ValueError:
                if getattr(entity, 'user_id', None):
                    # noinspection PyUnresolvedReferences
                    mentions.add(await self.get_user(entity.user_id, chat.group_id))

        text = flanautils.remove_symbols(text, replace_with=' ')
        words = text.lower().split()

        for participant in await self.client.get_participants(chat.original_object):
            user_name = self._get_entity_name(participant).lower()
            if user_name in words:
                mentions.add(await self._create_user_from_telegram_user(participant, chat))
        if chat.is_private:
            if self.name.lower() in words:
                mentions.add(await self.get_me())

        return list(mentions - None)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_message_id(self, original_message: constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) -> int | None:
        return original_message.id

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_original_message(self, event: constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) -> constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE:
        if isinstance(event, constants.TELEGRAM_NEW_MESSAGE_EVENT):
            return event.message
        elif isinstance(event, constants.TELEGRAM_BUTTON_EVENT):
            return await event.get_message()
        else:
            return event

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_replied_message(self, original_message: constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) -> Message | None:
        try:
            return await self._get_message(await original_message.get_reply_message())
        except (AttributeError, telethon.errors.rpcerrorlist.BotMethodInvalidError):
            pass

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_text(self, original_message: constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) -> str:
        return original_message.text

    @staticmethod
    @return_if_first_empty
    async def _prepare_media_to_send(media: Media, prefer_bytes=False, is_inline=False) -> str | io.BytesIO | None:
        def url_file() -> str | None:
            if not media.url:
                return

            if not pathlib.Path(media.url).is_file() and media.source is Source.INSTAGRAM and (not (path_suffix := pathlib.Path(media.url).suffix) or len(path_suffix) > constants.MAX_FILE_EXTENSION_LENGHT):
                return f'{media.url}.{media.extension}'
            else:
                return media.url

        async def bytes_file() -> io.BytesIO | None:
            if not media.bytes_:
                try:
                    media.bytes_ = await flanautils.get_request(media.url)
                except ResponseError:
                    return

            bytes_ = media.bytes_
            file_stem = media.title or 'bot_media'
            if media.title or is_inline:
                try:
                    bytes_ = await flanautils.edit_metadata(bytes_, {'title': file_stem}, overwrite=False)
                except FileNotFoundError:
                    pass
            file_ = io.BytesIO(bytes_)
            file_.name = f"{file_stem}{f'.{media.extension}' if media.extension else ''}"
            return file_

        if prefer_bytes:
            file = await bytes_file() or url_file()
        else:
            file = url_file() or await bytes_file()

        return file

    async def _start_async(self):
        await self.sign_in()
        await self._on_ready()
        await self.client.run_until_disconnected()

    async def _unban(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        user = await self.get_user(user, group_)
        chat = await self.get_chat(group_)

        await self.client.edit_permissions(chat.original_object, user.original_object)

    # ---------------------------------------------- #
    #                    HANDLERS                    #
    # ---------------------------------------------- #
    @find_message
    async def _on_inline_query_raw(self, message: Message):
        await super()._on_new_message_raw(message)

    async def _on_ready(self):
        self.platform = Platform.TELEGRAM
        me = await self.client.get_me()
        self.id = me.id
        self.name = me.username
        if self.user_client:
            async with use_user_client(self):
                self.owner_id = (await self.user_client.get_me()).id
        await super()._on_ready()

    # -------------------------------------------------------- #
    # -------------------- PUBLIC METHODS -------------------- #
    # -------------------------------------------------------- #
    async def accept_button_event(self, event: constants.TELEGRAM_EVENT | Message):
        match event:
            case self.Message():
                event = event.original_event

        try:
            await event.answer()
        except AttributeError:
            pass

    @user_client
    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def clear(self, n_messages: int, chat: int | str | Chat | Message):
        if n_messages > constants.DELETE_MESSAGE_LIMIT:
            raise LimitError('El máximo es 100.')

        n_messages = int(n_messages)
        chat = await self.get_chat(chat)

        async with use_user_client(self):
            user_client_user = await self._create_user_from_telegram_user(await self.user_client.get_me(), chat.group_id)
            if await self.client.is_bot() and user_client_user not in await self.get_users(chat):
                return

            if chat.is_group:
                original_chat = await self.user_client.get_entity(chat.original_object)
            else:
                original_chat = await self.user_client.get_input_entity(self.name)

            message_ids = [message.id async for message in self.user_client.iter_messages(original_chat, n_messages)]
            await self.user_client.delete_messages(original_chat, message_ids)
            deleted_messages_generator = self.Message.find({'platform': self.platform.value, 'chat': chat.object_id}, sort_keys=(('date', pymongo.DESCENDING),), limit=n_messages, lazy=True)
            for deleted_message in deleted_messages_generator:
                deleted_message.is_deleted = True
                deleted_message.save()

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def delete_message(
        self,
        message_to_delete: int | str | Message,
        chat: int | str | Chat | Message = None,
        raise_not_found=False
    ):
        if isinstance(message_to_delete, self.Message) and message_to_delete.original_object:
            await message_to_delete.original_object.delete()
        else:
            chat = await self.get_chat(chat)
            chat.pull_from_database()
            if not isinstance(message_to_delete, Message):
                message_to_delete = self.Message.find_one({'platform': self.platform.value, 'id': int(message_to_delete), 'chat': chat.object_id})
            await self.client.delete_messages(chat.original_object, message_to_delete.id)

        message_to_delete.is_deleted = True
        message_to_delete.save(('is_deleted',))

    # noinspection PyTypeChecker
    def distribute_buttons(self, texts: Sequence[str], vertically=False) -> list[list[str]]:
        if vertically:
            return flanautils.chunks(texts, 1)
        else:
            return flanautils.chunks(texts, constants.TELEGRAM_BUTTONS_MAX_PER_LINE)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def get_chat(self, chat: int | str | User | Chat | Message) -> Chat | None:
        match chat:
            case self.User() as user:
                if user.original_object:
                    return await self._create_chat_from_telegram_chat(user.original_object)
                chat_id_or_name = user.id
            case self.Chat():
                return chat
            case self.Message() as message:
                return message.chat
            case _ as chat_id_or_name:
                pass

        try:
            return await self._create_chat_from_telegram_chat(await self.client.get_entity(chat_id_or_name))
        except (ValueError, telethon.errors.rpcerrorlist.UsernameInvalidError):
            pass

    async def get_me(self, group_: int | str | Chat = None):
        return await self._create_user_from_telegram_user(await self.client.get_me(), group_)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def get_message(self, message: int | str | Message, chat: int | str | User | Chat | Message) -> Message | None:
        if not (chat := await self.get_chat(chat)):
            return

        match message:
            case int(message_id):
                pass
            case str(message_id):
                pass
            case self.Message():
                return message
            case _:
                raise TypeError('bad arguments')

        try:
            with flanautils.suppress_low_level_stderr():
                return await self._get_message(await self.client.get_messages(chat.original_object, ids=message_id))
        except (TypeError, struct.error):
            pass

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def get_user(self, user: int | str | User, group_: int | str | Chat | Message = None) -> User | None:
        match user:
            case self.User() if user.original_object:
                original_user = user.original_object
            case _:
                match user:
                    case self.User():
                        user_id_or_name = user.id
                    case user_id_or_name:
                        pass
                try:
                    original_user = await self.client.get_entity(user_id_or_name)
                except (ValueError, telethon.errors.rpcerrorlist.UsernameInvalidError):
                    return

        return await self._create_user_from_telegram_user(original_user, group_)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def get_users(self, group_: int | str | Chat | Message) -> list[User]:
        chat = await self.get_chat(group_)
        return [await self._create_user_from_telegram_user(participant, chat.id) for participant in await self.client.get_participants(chat.original_object)]

    async def make_mention(self, user: int | str | User, group_: int | str | Chat | Message = None) -> str:
        if isinstance(user, int):
            id = user
            text = str(id)
            prefix = ''
        else:
            if isinstance(user, str):
                user = await self.get_user(user, group_)
            id = user.id
            text = user.name
            prefix = '@' if user.original_object.username else ''

        return f'<a href="tg://user?id={id}">{prefix}{text}</a>'

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
        file = await self._prepare_media_to_send(media)
        telegram_buttons = None

        if buttons:
            telegram_buttons = []
            for row in buttons:
                telegram_buttons_row = []
                for button in row:
                    telegram_buttons_row.append(telethon.Button.inline(button.text))
                telegram_buttons.append(telegram_buttons_row)

        kwargs = {
            'file': file,
            'parse_mode': 'html',
            'supports_streaming': True
        }

        if message:
            if send_as_file is None:
                word_matches = flanautils.cartesian_product_string_matching(message.text, constants.KEYWORDS['send_as_file'], min_score=constants.TELEGRAM_SEND_AS_FILE_MIN_SCORE)
                send_as_file_score = sum(max(matches.values()) for text_word, matches in word_matches.items())
                kwargs['force_document'] = bool(send_as_file_score)
            else:
                kwargs['force_document'] = send_as_file

            if message.is_inline:
                if media:
                    if 'inline_medias' not in message.data:
                        message.data['inline_medias'] = []
                    message.data['inline_medias'].append(media)
                return
            elif edit:
                if buttons is not None:
                    kwargs['buttons'] = telegram_buttons

                try:
                    message.original_object = await message.original_object.edit(text, **kwargs)
                except (
                        telethon.errors.rpcerrorlist.PeerIdInvalidError,
                        telethon.errors.rpcerrorlist.MessageIdInvalidError,
                        telethon.errors.rpcerrorlist.MessageNotModifiedError,
                        telethon.errors.rpcerrorlist.UserIsBlockedError
                ):
                    return

                return self._update_message_attributes(message, media, buttons, chat, buttons_key, data, update_last_edit=True)

        match reply_to:
            case str():
                reply_to = int(reply_to)
            case self.Message() as message_to_reply:
                reply_to = message_to_reply.original_object

        with flanautils.suppress_stderr():
            attempts = 2
            for attempt in range(attempts - 1, -1, -1):
                try:
                    original_message = await self.client.send_message(chat.original_object, text, buttons=telegram_buttons, reply_to=reply_to, silent=silent, **kwargs)
                except telethon.errors.VideoContentTypeInvalidError:
                    if attempt:
                        try:
                            del kwargs['supports_streaming']
                        except KeyError:
                            pass
                    else:
                        raise
                except telethon.errors.WebpageCurlFailedError:
                    if bytes_ := await self._prepare_media_to_send(media, prefer_bytes=True):
                        kwargs['file'] = bytes_
                    else:
                        raise
                except ValueError as e:
                    if 'parse' in str(e).lower() and attempt:
                        try:
                            del kwargs['parse_mode']
                        except KeyError:
                            pass
                    else:
                        raise
                except telethon.errors.rpcerrorlist.MediaEmptyError:
                    if (bytes_ := await self._prepare_media_to_send(media, prefer_bytes=True)) and isinstance(bytes_, bytes):
                        kwargs['file'] = bytes_
                    else:
                        return
                except (telethon.errors.rpcerrorlist.PeerIdInvalidError, telethon.errors.rpcerrorlist.UserIsBlockedError):
                    return
                else:
                    break

        original_message._sender = await self.client.get_me()
        original_message._chat = chat.original_object
        bot_message = await self._get_message(original_message)

        return self._update_message_attributes(bot_message, media, buttons, chat, buttons_key, data)

    @inline
    async def send_inline_results(self, message: Message):
        async def create_result(media: Media, prefer_bytes=False) -> telethon.types.InputBotInlineResultPhoto | telethon.types.InputBotInlineResultDocument:
            file = await self._prepare_media_to_send(media, prefer_bytes, is_inline=True)
            match media.type_:
                case MediaType.IMAGE:
                    return message.original_event.builder.photo(file)
                case _:
                    return message.original_event.builder.document(file, title=media.type_.name.title(), type=media.type_.name.lower())

        with flanautils.suppress_stderr():
            try:
                try:
                    await message.original_event.answer([await create_result(media) for media in message.data['inline_medias']])
                except telethon.errors.rpcerrorlist.WebpageCurlFailedError:
                    await message.original_event.answer([await create_result(media, prefer_bytes=True) for media in message.data['inline_medias']])
            except (AttributeError, KeyError, telethon.errors.rpcerrorlist.QueryIdInvalidError):
                pass

    async def sign_in(self):
        if not self.bot_session and self.client:
            print('----- Bot client -----')
            await self.client.connect()
            await self.client.sign_in(bot_token=self.token)
            print('Done.')

        if not self.user_session and self.user_client:
            print('----- User client -----')
            await self.user_client.connect()
            if not await self.user_client.is_user_authorized():
                await self.user_client.sign_in(self.phone)
                code = input('Enter the login code: ')
                await self.user_client.sign_in(self.phone, code)
            print('Done.')

        if not self.client:
            self.client = self.user_client

        await self.client.connect()

    @property
    def string_sessions(self) -> dict[str, str] | Coroutine:
        async def string_session_() -> dict[str, str]:
            await self.sign_in()
            return {
                'bot_session': StringSession.save(self.client.session) if self.client else None,
                'user_session': StringSession.save(self.user_client.session) if self.user_client else None
            }

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(string_session_())
        else:
            return string_session_()

    async def typing(self, chat: int | str | User | Chat | Message) -> contextlib.AbstractAsyncContextManager:
        chat = await self.get_chat(chat)
        return self.client.action(chat.original_object, 'typing')
