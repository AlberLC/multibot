from __future__ import annotations  # todo0 remove in 3.11

import asyncio
import datetime
import functools
import io
import pathlib
import struct
from typing import Any, Callable

import flanautils
import telethon.events.common
import telethon.hints
import telethon.tl.functions.channels
import telethon.tl.types
from flanautils import Media, MediaType, OrderedSet, Source, return_if_first_empty, shift_args_if_called
from telethon import TelegramClient
from telethon.sessions import StringSession

from multibot import constants
from multibot.bots.multi_bot import MultiBot, find_message, inline, parse_arguments
from multibot.exceptions import LimitError
from multibot.models import Chat, Message, Platform, User


# ---------------------------------------------------------- #
# ----------------------- DECORATORS ----------------------- #
# ---------------------------------------------------------- #
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
    def __init__(self, api_id: int | str, api_hash: int | str, phone: int | str = None, bot_token: str = None, bot_session: str = None, user_session: str = None):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.bot_session = bot_session
        self.user_session = user_session

        if self.bot_session:
            bot_client = TelegramClient(StringSession(bot_session), self.api_id, self.api_hash)
        else:
            bot_client = TelegramClient('bot_session', self.api_id, self.api_hash)

        if self.user_session:
            self.user_client = TelegramClient(StringSession(user_session), self.api_id, self.api_hash)
        elif self.phone:
            self.user_client = TelegramClient('user_session', self.api_id, self.api_hash)
        else:
            self.user_client = None

        super().__init__(bot_token=bot_token,
                         bot_client=bot_client)

    # ----------------------------------------------------------- #
    # -------------------- PROTECTED METHODS -------------------- #
    # ----------------------------------------------------------- #
    async def _accept_button_event(self, event: constants.MESSAGE_EVENT | Message):
        match event:
            case Message():
                event = event.original_event

        await event.answer()

    # noinspection PyTypeChecker
    def _add_handlers(self):
        super()._add_handlers()
        self.bot_client.add_event_handler(self._on_button_press_raw, telethon.events.CallbackQuery)
        self.bot_client.add_event_handler(self._on_inline_query_raw, telethon.events.InlineQuery)
        self.bot_client.add_event_handler(self._on_new_message_raw, telethon.events.NewMessage)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _create_bot_message_from_telegram_bot_message(self, original_message: constants.TELEGRAM_MESSAGE, message: Message, contents: Any = None) -> Message | None:
        original_message._sender = await self.bot_client.get_entity(self.bot_id)
        original_message._chat = message.chat.original_object
        bot_message = await self._get_message(original_message)
        bot_message.contents = contents or []
        bot_message.save()
        return bot_message

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _create_chat_from_telegram_chat(self, telegram_chat: constants.TELEGRAM_CHAT) -> Chat | None:
        chat_name = await self._get_name_from_entity(telegram_chat)
        if isinstance(telegram_chat, constants.TELEGRAM_USER):
            users = [await self.get_user(self.owner_id), await self.get_user(self.bot_id)]
            group_id = None
            group_name = None
        else:
            users = [await self._create_user_from_telegram_user(participant, telegram_chat.id) for participant in await self.bot_client.get_participants(telegram_chat)]
            group_id = telegram_chat.id
            group_name = chat_name

        return Chat(
            platform=self.bot_platform.value,
            id=telegram_chat.id,
            name=chat_name,
            group_id=group_id,
            group_name=group_name,
            users=users,
            original_object=telegram_chat
        )

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _create_user_from_telegram_user(self, original_user: constants.TELEGRAM_USER, group_: int | str | Chat = None) -> User | None:
        group_id = self._get_group_id(group_)
        try:
            is_admin = (await self.bot_client.get_permissions(group_id, original_user)).is_admin
        except (AttributeError, TypeError, ValueError):
            is_admin = None

        return User(
            platform=self.bot_platform.value,
            id=original_user.id,
            name=(await self._get_name_from_entity(original_user)).strip(' @'),
            is_admin=is_admin,
            original_object=original_user
        )

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_author(self, original_message: constants.TELEGRAM_MESSAGE) -> User | None:
        return await self._create_user_from_telegram_user(original_message.sender, original_message.chat.id)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_last_button_pressed(self, event: constants.TELEGRAM_EVENT) -> str | None:
        try:
            return event.data.decode()
        except AttributeError:
            pass

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_chat(self, original_message: constants.TELEGRAM_MESSAGE) -> Chat | None:
        return await self._create_chat_from_telegram_chat(original_message.chat)

    async def _get_me(self, group_: int | str | Chat = None):
        return await self._create_user_from_telegram_user(await self.bot_client.get_me(), group_)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_mentions(self, original_message: constants.TELEGRAM_MESSAGE) -> list[User]:
        mentions = OrderedSet()
        try:
            entities = original_message.entities or ()
        except AttributeError:
            return list(mentions)

        text = await self._get_text(original_message)
        chat = await self._get_chat(original_message)

        for entity in entities:
            try:
                mentions.add(await self.get_user(text[entity.offset:entity.offset + entity.length], chat.group_id))
            except ValueError:
                pass

        words = text.lower().split()
        for user in chat.users:
            if user.name.lower() in words:
                mentions.add(user)

        return list(mentions - None)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_message_id(self, original_message: constants.TELEGRAM_MESSAGE) -> int | None:
        return original_message.id

    @return_if_first_empty('', exclude_self_types='TelegramBot', globals_=globals())
    async def _get_name_from_entity(self, entity: telethon.hints.EntityLike) -> str:
        if isinstance(entity, telethon.types.User):
            return f'@{entity.username}' if entity.username else entity.first_name
        elif isinstance(entity, (telethon.types.Channel, telethon.types.Chat)):
            return entity.title

        return ''

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_original_message(self, event: constants.TELEGRAM_EVENT) -> telethon.custom.Message:
        if isinstance(event, telethon.events.CallbackQuery.Event):
            return await event.get_message()
        else:
            return getattr(event, 'message', event)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_replied_message(self, original_message: constants.TELEGRAM_MESSAGE) -> Message | None:
        try:
            return await self._get_message(await original_message.get_reply_message())
        except AttributeError:
            pass

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_text(self, original_message: constants.TELEGRAM_MESSAGE) -> str:
        return original_message.text

    @staticmethod
    @return_if_first_empty
    async def _prepare_media_to_send(media: Media) -> str | io.BytesIO | None:
        if media.url:
            if not pathlib.Path(media.url).is_file() and media.source is Source.INSTAGRAM and (not (path_suffix := pathlib.Path(media.url).suffix) or len(path_suffix) > constants.MAX_FILE_EXTENSION_LENGHT):
                file = f'{media.url}.{media.type_.extension}'
            else:
                file = media.url
        elif media.bytes_:
            file = io.BytesIO(media.bytes_)
            file.name = f'bot_media.{media.type_.extension}'
        else:
            return

        return file

    # ---------------------------------------------- #
    #                    HANDLERS                    #
    # ---------------------------------------------- #
    @find_message
    async def _on_inline_query_raw(self, message: Message):
        await super()._on_new_message_raw(message)

    async def _on_ready(self):
        self.bot_platform = Platform.TELEGRAM
        me = await self.bot_client.get_me()
        self.bot_id = me.id
        self.bot_name = me.username
        if self.user_client:
            async with self.user_client:
                self.owner_id = (await self.user_client.get_me()).id
        await super()._on_ready()

    # -------------------------------------------------------- #
    # -------------------- PUBLIC METHODS -------------------- #
    # -------------------------------------------------------- #
    async def ban(self, user: int | str | User, chat: int | str | Chat | Message, seconds: int | datetime.timedelta = None):  # todo4 test en grupo de pruebas
        ...
        # if isinstance(user, User):
        #     user = user.original_object
        # if isinstance(chat, Chat):
        #     chat = chat.original_object
        # if isinstance(seconds, int):
        #     seconds = datetime.timedelta(seconds=seconds)
        #
        # rights = telethon.tl.types.ChatBannedRights(
        #     until_date=datetime.datetime.now(datetime.timezone.utc) + seconds if seconds else None,
        #     view_messages=True,
        #     send_messages=True,
        #     send_media=True,
        #     send_stickers=True,
        #     send_gifs=True,
        #     send_games=True,
        #     send_inline=True,
        #     embed_links=True,
        #     send_polls=True,
        #     change_info=True,
        #     invite_users=True,
        #     pin_messages=True
        # )
        #
        # await self.bot_client(telethon.tl.functions.channels.EditBannedRequest(chat, user, rights))

    @user_client
    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def clear(self, n_messages: int, chat: int | str | Chat | Message):
        if n_messages > constants.DELETE_MESSAGE_LIMIT:
            raise LimitError('El máximo es 100.')

        chat = await self.get_chat(chat)
        n_messages += 1

        async with self.user_client:
            owner_user = await self._create_user_from_telegram_user(await self.user_client.get_me(), chat.group_id)
            if owner_user not in chat.users:
                return

            user_chat = await self.user_client.get_entity(chat.id)
            messages_to_delete = await self.user_client.get_messages(user_chat, n_messages)
            await self.user_client.delete_messages(user_chat, messages_to_delete)
            for message_to_delete in messages_to_delete:
                message_to_delete.is_deleted = True
                message_to_delete.save()

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def delete_message(self, message_to_delete: int | str | Message, chat: int | str | Chat | Message = None):
        chat = await self.get_chat(chat)
        match message_to_delete:
            case int() | str():
                message_to_delete = Message.find_one({'platform': self.bot_platform.value, 'id': str(message_to_delete), 'chat': chat.object_id})
            case Message() if message_to_delete.original_object and message_to_delete.chat and message_to_delete.chat == chat:
                chat = None

        if chat and chat.original_object:
            await self.bot_client.delete_messages(chat.original_object, message_to_delete.id)
        elif message_to_delete.original_object:
            await message_to_delete.original_object.delete()
        else:
            raise ValueError('The original telegram object of the message or chat is needed')

        message_to_delete.is_deleted = True
        message_to_delete.save()

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def get_chat(self, chat: int | str | Chat | Message = None) -> Chat | None:
        match chat:
            case Chat():
                return chat
            case Message() as message:
                return message.chat

        return await self._create_chat_from_telegram_chat(await self.bot_client.get_entity(chat))

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def get_user(self, user: int | str | User, group_: int | str | Chat = None) -> User | None:
        if isinstance(user, User):
            return user

        try:
            with flanautils.suppress_stderr():
                return await self._create_user_from_telegram_user(await self.bot_client.get_entity(user), group_)
        except struct.error:
            pass

    @parse_arguments
    async def send(
        self,
        text='',
        media: Media = None,
        buttons: list[str | list[str]] = None,
        message: Message = None,
        silent: bool = False,
        send_as_file: bool = None,
        edit=False,
    ) -> Message | None:
        file = await self._prepare_media_to_send(media)
        if not text and not file:
            return

        if send_as_file is None:
            word_matches = flanautils.cartesian_product_string_matching(message.text, constants.KEYWORDS['send_as_file'], min_ratio=constants.TELEGRAM_SEND_AS_FILE_RATIO_MIN_RATIO)
            send_as_file_ratio = sum(max(matches.values()) for text_word, matches in word_matches.items())
            send_as_file = bool(send_as_file_ratio)

        buttons = buttons or []
        for i, row in enumerate(buttons):
            for j, column in enumerate(row):
                buttons[i][j] = telethon.Button.inline(buttons[i][j])

        kwargs = {
            'file': file,
            'force_document': send_as_file,
            'buttons': buttons or None,
            'parse_mode': 'html'
        }

        if message.is_inline:
            if media:
                if media.type_ is MediaType.IMAGE:
                    message.contents.append(message.original_event.builder.photo(file))
                else:
                    message.contents.append(message.original_event.builder.document(file, title=media.type_.name.title(), type=media.type_.name.lower()))
        elif edit:
            try:
                edited_message = await message.original_object.edit(text, **kwargs)
            except (
                    telethon.errors.rpcerrorlist.PeerIdInvalidError,
                    telethon.errors.rpcerrorlist.UserIsBlockedError,
                    telethon.errors.rpcerrorlist.MessageNotModifiedError
            ):
                pass
            else:
                message.original_object = edited_message
            if content := getattr(media, 'content', None):
                message.contents = [content]
            message.save()
            return message
        else:
            kwargs['silent'] = silent
            try:
                original_message = await self.bot_client.send_message(message.chat.original_object, text, **kwargs)
            except (telethon.errors.rpcerrorlist.PeerIdInvalidError, telethon.errors.rpcerrorlist.UserIsBlockedError):
                return
            if content := getattr(media, 'content', None):
                contents = [content]
            else:
                contents = []
            return await self._create_bot_message_from_telegram_bot_message(original_message, message, contents=contents)

    @inline
    async def send_inline_results(self, message: Message):
        try:
            await message.original_event.answer(message.contents)
        except telethon.errors.rpcerrorlist.QueryIdInvalidError:
            pass

    def start(self):
        async def start_():
            await self.bot_client.connect()

            if not self.bot_session:
                print('----- Bot client -----')
                if not self.bot_token:
                    self.bot_token = input('Enter a bot token: ').strip()
                await self.bot_client.sign_in(bot_token=self.bot_token)
                print('Done.')
            if not self.user_session and self.user_client:
                print('----- User client -----')
                async with self.user_client:
                    await self.user_client.sign_in(phone=self.phone)
                print('Done.')

            await self._on_ready()
            await self.bot_client.run_until_disconnected()

        try:
            asyncio.get_running_loop()
            return start_()
        except RuntimeError:
            asyncio.run(start_())

    async def unban(self, user: int | str | User, chat: int | str | Chat | Message):  # todo4 test en grupo de pruebas
        ...
        # if isinstance(user, User):
        #     user = user.original_object
        # if isinstance(chat, Chat):
        #     chat = chat.original_object
        #
        # rights = telethon.tl.types.ChatBannedRights(
        #     view_messages=False,
        #     send_messages=False,
        #     send_media=False,
        #     send_stickers=False,
        #     send_gifs=False,
        #     send_games=False,
        #     send_inline=False,
        #     embed_links=False,
        #     send_polls=False,
        #     change_info=False,
        #     invite_users=False,
        #     pin_messages=False
        # )
        #
        # await self.bot_client(telethon.tl.functions.channels.EditBannedRequest(chat, user, rights))
