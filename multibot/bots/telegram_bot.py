from __future__ import annotations  # todo0 remove in 3.11

__all__ = ['user_client', 'TelegramBot']

import asyncio
import functools
import io
import pathlib
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
from multibot.models import Button, ButtonsInfo, Chat, Message, Platform, User


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
    # noinspection PyTypeChecker
    def _add_handlers(self):
        super()._add_handlers()
        self.client.add_event_handler(self._on_button_press_raw, telethon.events.CallbackQuery)
        self.client.add_event_handler(self._on_inline_query_raw, telethon.events.InlineQuery)
        self.client.add_event_handler(self._on_new_message_raw, telethon.events.NewMessage)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _create_bot_message_from_telegram_bot_message(self, original_message: constants.TELEGRAM_MESSAGE, media: Media, chat: Chat, buttons: list[list[Button]] = None, buttons_key: Any = None, contents: dict = None) -> Message | None:
        original_message._sender = await self.client.get_entity(self.id)
        original_message._chat = chat.original_object
        bot_message = await self._get_message(original_message)
        bot_message.buttons_info = ButtonsInfo(buttons=buttons, key=buttons_key)
        if media and media.bytes_ and len(media.bytes_) <= constants.PYMONGO_MEDIA_MAX_BYTES:
            media = media.content
        else:
            media = None
        bot_message.contents = {'media': media}
        if contents is not None:
            bot_message.contents |= contents
        bot_message.save()

        return bot_message

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _create_chat_from_telegram_chat(self, original_chat: constants.TELEGRAM_CHAT) -> Chat | None:
        chat_name = self._get_name_from_entity(original_chat)
        if isinstance(original_chat, constants.TELEGRAM_USER):
            group_id = None
            group_name = None
        else:
            group_id = original_chat.id
            group_name = chat_name

        return Chat(
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

        return User(
            platform=self.platform,
            id=original_user.id,
            name=self._get_name_from_entity(original_user),
            is_admin=is_admin,
            is_bot=original_user.bot,
            original_object=original_user
        )

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_author(self, original_message: constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) -> User | None:
        return await self._create_user_from_telegram_user(original_message.sender, original_message.chat.id)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_button_pressed_text(self, event: constants.TELEGRAM_EVENT) -> str | None:
        try:
            return event.data.decode()
        except AttributeError:
            pass

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_button_presser_user(self, event: constants.TELEGRAM_EVENT) -> User | None:
        return await self._create_user_from_telegram_user(event.sender, event.chat.id)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_chat(self, original_message: constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) -> Chat | None:
        return await self._create_chat_from_telegram_chat(original_message.chat)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_mentions(self, original_message: constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) -> list[User]:
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

        text = flanautils.remove_symbols(text, replace_with=' ')
        words = text.lower().split()

        for participant in await self.client.get_participants(chat.original_object):
            user_name = self._get_name_from_entity(participant).lower()
            if user_name in words:
                mentions.add(await self._create_user_from_telegram_user(participant, chat))
        if chat.is_private:
            if self.name.lower() in words:
                mentions.add(await self.get_me())

        return list(mentions - None)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_message_id(self, original_message: constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) -> int | None:
        return original_message.id

    @return_if_first_empty('', exclude_self_types='TelegramBot', globals_=globals())
    def _get_name_from_entity(self, entity: telethon.hints.EntityLike) -> str:
        if isinstance(entity, telethon.types.User):
            return entity.username or entity.first_name
        elif isinstance(entity, (telethon.types.Channel, telethon.types.Chat)):
            return entity.title

        return ''

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_original_message(self, event: constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) -> constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE:
        if isinstance(event, telethon.events.CallbackQuery.Event):
            return await event.get_message()
        else:
            return getattr(event, 'message', event)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_replied_message(self, original_message: constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) -> Message | None:
        try:
            return await self._get_message(await original_message.get_reply_message())
        except AttributeError:
            pass

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def _get_text(self, original_message: constants.TELEGRAM_EVENT | constants.TELEGRAM_MESSAGE) -> str:
        return original_message.text

    @staticmethod
    @return_if_first_empty
    def _prepare_media_to_send(media: Media, prefer_bytes=False) -> str | io.BytesIO | None:
        def url_file() -> str | None:
            if not media.url:
                return

            if not pathlib.Path(media.url).is_file() and media.source is Source.INSTAGRAM and (not (path_suffix := pathlib.Path(media.url).suffix) or len(path_suffix) > constants.MAX_FILE_EXTENSION_LENGHT):
                return f'{media.url}.{media.type_.extension}'
            else:
                return media.url

        def bytes_file() -> io.BytesIO | None:
            if not media.bytes_:
                return

            file_ = io.BytesIO(media.bytes_)
            file_.name = f'bot_media.{media.type_.extension}'
            return file_

        if prefer_bytes:
            file = bytes_file() or url_file()
        else:
            file = url_file() or bytes_file()

        return file

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
            async with self.user_client:
                self.owner_id = (await self.user_client.get_me()).id
        await super()._on_ready()

    # -------------------------------------------------------- #
    # -------------------- PUBLIC METHODS -------------------- #
    # -------------------------------------------------------- #
    async def accept_button_event(self, event: constants.TELEGRAM_EVENT | Message):
        match event:
            case Message():
                event = event.original_event

        try:
            await event.answer()
        except AttributeError:
            pass

    # async def ban(self, user: int | str | User, chat: int | str | Chat | Message, seconds: int | datetime.timedelta = None):  # todo4 test en grupo de pruebas
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
                message_to_delete = Message.find_one({'platform': self.platform.value, 'id': str(message_to_delete), 'chat': chat.object_id})
            case Message() if message_to_delete.original_object and message_to_delete.chat and message_to_delete.chat == chat:
                chat = None

        if chat and chat.original_object:
            await self.client.delete_messages(chat.original_object, message_to_delete.id)
        elif message_to_delete.original_object:
            await message_to_delete.original_object.delete()
        else:
            raise ValueError('The original telegram object of the message or chat is needed')

        message_to_delete.is_deleted = True
        message_to_delete.save()

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def get_chat(self, chat: int | str | User | Chat | Message) -> Chat | None:
        match chat:
            case User() as user:
                if user.original_object:
                    return await self._create_chat_from_telegram_chat(user.original_object)
                chat_id = user.id
            case Chat():
                return chat
            case Message() as message:
                return message.chat
            case _ as chat_id:
                pass

        return await self._create_chat_from_telegram_chat(await self.client.get_entity(chat_id))

    async def get_me(self, group_: int | str | Chat = None):
        return await self._create_user_from_telegram_user(await self.client.get_me(), group_)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def get_message(self, chat: int | str | User | Chat | Message, message: int | str | Message) -> Message | None:
        match message:
            case int(message_id):
                pass
            case str(message_id):
                pass
            case Message():
                return message
            case _:
                raise TypeError('bad arguments')

        chat = await self.get_chat(chat)
        return await self._get_message(await self.client.get_messages(chat.original_object, ids=message_id))

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def get_user(self, user: int | str | User, group_: int | str | Chat | Message = None) -> User | None:
        group_id = self.get_group_id(group_)

        with flanautils.suppress_stderr():
            return await self._create_user_from_telegram_user(await self.client.get_entity(user), group_id)

    @return_if_first_empty(exclude_self_types='TelegramBot', globals_=globals())
    async def get_users(self, group_: int | str | Chat | Message) -> list[User]:
        chat = await self.get_chat(group_)
        return [await self._create_user_from_telegram_user(participant, chat.id) for participant in await self.client.get_participants(chat.original_object)]

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
        contents: dict = None,
        silent: bool = False,
        send_as_file: bool = None,
        edit=False,
    ) -> Message | None:
        file = self._prepare_media_to_send(media)
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
            'parse_mode': 'html'
        }

        if message:
            if send_as_file is None:
                word_matches = flanautils.cartesian_product_string_matching(message.text, constants.KEYWORDS['send_as_file'], min_ratio=constants.TELEGRAM_SEND_AS_FILE_RATIO_MIN_RATIO)
                send_as_file_ratio = sum(max(matches.values()) for text_word, matches in word_matches.items())
                kwargs['force_document'] = bool(send_as_file_ratio)

            if message.is_inline:
                if media:
                    if 'inline_media' not in message.contents:
                        message.contents['inline_media'] = []
                    message.contents['inline_media'].append(media)
                return
            elif edit:
                if buttons is not None:
                    kwargs['buttons'] = telegram_buttons
                    message.buttons_info.buttons = buttons
                if buttons_key is not None:
                    message.buttons_info.key = buttons_key

                try:
                    message.original_object = await message.original_object.edit(text, **kwargs)
                except (
                        telethon.errors.rpcerrorlist.PeerIdInvalidError,
                        telethon.errors.rpcerrorlist.UserIsBlockedError,
                        telethon.errors.rpcerrorlist.MessageNotModifiedError
                ):
                    return
                else:
                    last_contents = message.contents
                    if media_content := getattr(media, 'content', None):
                        del last_contents['media']
                    message.contents = {'media': media_content}
                    if contents is None:
                        message.contents |= last_contents
                    else:
                        message.contents |= contents
                    message.update_last_edit()
                    message.save()

                    return message

        match reply_to:
            case str():
                reply_to = int(reply_to)
            case Message() as message_to_reply:
                reply_to = message_to_reply.original_object

        try:
            original_message = await self.client.send_message(chat.original_object, text, buttons=telegram_buttons, reply_to=reply_to, silent=silent, **kwargs)
        except telethon.errors.rpcerrorlist.WebpageCurlFailedError:
            if media.bytes_:
                kwargs['file'] = self._prepare_media_to_send(media, prefer_bytes=True)
                original_message = await self.client.send_message(chat.original_object, text, buttons=telegram_buttons, reply_to=reply_to, silent=silent, **kwargs)
            else:
                raise
        except (telethon.errors.rpcerrorlist.PeerIdInvalidError, telethon.errors.rpcerrorlist.UserIsBlockedError):
            return

        return await self._create_bot_message_from_telegram_bot_message(original_message, media, chat, buttons, buttons_key, contents)

    @inline
    async def send_inline_results(self, message: Message):
        def create_result(media: Media, prefer_bytes=False) -> telethon.types.InputBotInlineResultPhoto | telethon.types.InputBotInlineResultDocument:
            file = self._prepare_media_to_send(media, prefer_bytes)
            if media.type_ is MediaType.IMAGE:
                return message.original_event.builder.photo(file)
            else:
                return message.original_event.builder.document(file, title=media.type_.name.title(), type=media.type_.name.lower())

        try:
            try:
                await message.original_event.answer([create_result(media) for media in message.contents['inline_media']])
            except telethon.errors.rpcerrorlist.WebpageCurlFailedError:
                await message.original_event.answer([create_result(media, prefer_bytes=True) for media in message.contents['inline_media']])
        except (KeyError, telethon.errors.rpcerrorlist.QueryIdInvalidError):
            pass

    def start(self):
        async def start_():
            await self.client.connect()

            if not self.bot_session:
                print('----- Bot client -----')
                if not self.token:
                    self.token = input('Enter a bot token: ').strip()
                await self.client.sign_in(bot_token=self.token)
                print('Done.')
            if not self.user_session and self.user_client:
                print('----- User client -----')
                async with self.user_client:
                    await self.user_client.sign_in(phone=self.phone)
                print('Done.')

            await self._on_ready()
            await self.client.run_until_disconnected()

        try:
            asyncio.get_running_loop()
            return start_()
        except RuntimeError:
            asyncio.run(start_())

    # async def unban(self, user: int | str | User, chat: int | str | Chat | Message):  # todo4 test en grupo de pruebas
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
