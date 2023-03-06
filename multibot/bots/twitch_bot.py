from __future__ import annotations  # todo0 remove when it's by default

__all__ = ['TwitchBot']

import re
from collections import defaultdict
from typing import Any, Iterable, Iterator

import flanautils
import pymongo
import twitchio
import twitchio.ext.commands
from flanautils import Media, OrderedSet, return_if_first_empty

from multibot import constants
from multibot.bots.multi_bot import MultiBot, parse_arguments
from multibot.models import Button, Chat, Message, Platform, User


# --------------------------------------------------------------------------------------------------- #
# ------------------------------------------- DISCORD_BOT ------------------------------------------- #
# --------------------------------------------------------------------------------------------------- #
class TwitchBot(MultiBot[twitchio.Client]):
    def __init__(self, token: str, initial_channels: Iterable[str] = None, owner_name: str = None):
        super().__init__(token=token,
                         client=twitchio.ext.commands.Bot(token=token, prefix='/', initial_channels=initial_channels))
        self.owner_name = owner_name

    # -------------------------------------------------------- #
    # ------------------- PROTECTED METHODS ------------------ #
    # -------------------------------------------------------- #
    # noinspection PyProtectedMember
    def _add_handlers(self):
        super()._add_handlers()
        self.client._events = defaultdict(list)
        self.client._events['event_ready'].append(self._on_ready)
        self.client._events['event_message'].append(self._on_new_message_raw)

    async def _ban(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        user_name = self.get_user_name(user)
        chat = await self.get_chat(group_)
        await self.send(f'/ban {user_name}', self.Message(chat=chat) or message)

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _create_chat_from_twitch_chat(self, original_chat: constants.TWITCH_CHAT) -> Chat | None:
        channel_name = original_chat.name
        try:
            channel_id = int(flanautils.find(original_chat.chatters, condition=lambda user: user.name == channel_name).id)
        except (AttributeError, TypeError):
            channel_id = int(next(iter(await self.client.fetch_users([channel_name])), None).id)

        return self.Chat(
            platform=self.platform,
            id=channel_id,
            name=channel_name,
            group_id=channel_id,
            group_name=channel_name,
            original_object=original_chat
        )

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _create_user_from_twitch_user(self, original_user: constants.TWITCH_USER, is_admin: bool = None) -> User | None:
        if (id := original_user.id) is None:
            id = next(iter(await self.client.fetch_users([original_user.name])), None).id

        return self.User(
            platform=self.platform,
            id=int(id),
            name=original_user.display_name,
            is_admin=getattr(original_user, 'is_mod', None) if is_admin is None else is_admin,
            original_object=original_user
        )

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _get_author(self, original_message: constants.TWITCH_MESSAGE) -> User | None:
        if original_message.echo:
            return await self.get_me(original_message.channel.name)
        return await self._create_user_from_twitch_user(original_message.author)

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _get_chat(self, original_message: constants.TWITCH_MESSAGE) -> Chat | None:
        return await self._create_chat_from_twitch_chat(original_message.channel)

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _get_mentions(self, original_message: constants.TWITCH_MESSAGE) -> list[User]:
        text = await self._get_text(original_message)
        chat = await self._get_chat(original_message)
        mentions = OrderedSet([user for mention in re.findall(r'@\w+', text) if (user := await self.get_user(mention[1:], chat))])

        if chat.original_object.chatters:
            text = flanautils.remove_symbols(text, replace_with=' ')
            words = text.lower().split()

            for chatter in chat.original_object.chatters:
                if chatter.name.lower() in words:
                    mentions.add(await self._create_user_from_twitch_user(chatter))

        return list(mentions)

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _get_message_id(self, original_message: constants.TWITCH_MESSAGE) -> str:
        return original_message.id

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _get_original_message(self, event: constants.TWITCH_MESSAGE) -> constants.TWITCH_MESSAGE:
        return event

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _get_replied_message(self, original_message: constants.TWITCH_MESSAGE) -> Message | None:
        try:
            return self.Message.find_one({'platform': self.platform.value, 'id': original_message.tags['reply-parent-msg-id']})
        except KeyError:
            pass

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _get_text(self, original_message: constants.TWITCH_MESSAGE) -> str:
        return original_message.content

    async def _start_async(self):
        await self.client.start()

    def _start_sync(self):
        self.client.run()

    async def _unban(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        user_name = self.get_user_name(user)
        chat = await self.get_chat(group_)
        await self.send(f'/unban {user_name}', self.Message(chat=chat) or message)

    # ---------------------------------------------- #
    #                    HANDLERS                    #
    # ---------------------------------------------- #
    async def _on_ready(self):
        self.platform = Platform.TWITCH
        self.id = (await self.client.fetch_users([self.client.nick]))[0].id
        self.name = self.client.nick
        if self.owner_name:
            self.owner_id = (await self.client.fetch_users([self.owner_name]))[0].id
        await super()._on_ready()

    # -------------------------------------------------------- #
    # -------------------- PUBLIC METHODS -------------------- #
    # -------------------------------------------------------- #
    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def clear(self, n_messages: int, chat: int | str | Chat | Message):
        n_messages = int(n_messages)
        chat = await self.get_chat(chat)

        messages_to_delete: Iterator[Message] = self.Message.find(
            {
                'platform': self.platform.value,
                'chat': chat.object_id,
                'is_deleted': False
            },
            sort_keys=(('date', pymongo.DESCENDING),),
            limit=n_messages,
            lazy=True
        )

        for message_to_delete in messages_to_delete:
            if not message_to_delete.author.is_admin:
                await self.delete_message(message_to_delete, chat)

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def delete_message(
        self,
        message_to_delete: int | str | Message,
        chat: int | str | Chat | Message = None,
        raise_not_found=False
    ):
        if isinstance(message_to_delete, self.Message) and message_to_delete.chat.original_object:
            chat = message_to_delete.chat
        else:
            chat = await self.get_chat(chat)
            chat.pull_from_database()
            if not isinstance(message_to_delete, Message):
                message_to_delete = self.Message.find_one({'platform': self.platform.value, 'id': int(message_to_delete), 'chat': chat.object_id})

        await self.send(f'/delete {message_to_delete.id}', chat)
        message_to_delete.is_deleted = True
        message_to_delete.save(('is_deleted',))

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def get_chat(self, chat: int | str | User | Chat | Message = None) -> Chat | None:
        match chat:
            case int(group_id):
                group_name = self.get_group_name(group_id)
                if not group_name:
                    # noinspection PyTypeChecker
                    return await self._create_chat_from_twitch_chat(await self.client.fetch_channel(group_id))
            case str(group_name):
                pass
            case self.User() as user:
                group_name = user.name.lower()
            case self.Chat():
                return chat
            case self.Message() as message:
                return message.chat
            case _:
                raise TypeError('bad arguments')

        return await self._create_chat_from_twitch_chat(self.client.get_channel(group_name) or await self.client.fetch_channel(group_name))

    async def get_me(self, group_: int | str | Chat = None) -> User | None:
        return await self.get_user(self.id, group_)

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def get_user(self, user: int | str | User, group_: int | str | Chat | Message = None) -> User | None:
        group_name = self.get_group_name(group_)
        match user:
            case self.User() if user.group_name == group_name:
                return user
            case _ as user_id_or_name:
                pass

        original_user: constants.TWITCH_USER
        if not (original_user := next(iter(await self.client.fetch_users([user_id_or_name])), None)):
            return

        if group_name:
            if original_user.name == group_name:
                is_admin = True
            else:
                chat = await self.get_chat(group_)
                original_user = chat.original_object.get_chatter(original_user.name)
                is_admin = None
        else:
            is_admin = None
        return await self._create_user_from_twitch_user(original_user, is_admin=is_admin)

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def get_users(self, group_: int | str | Chat | Message) -> list[User]:
        chat = await self.get_chat(group_)
        return list(OrderedSet([await self._create_user_from_twitch_user(chatter) for chatter in chat.original_object.chatters]))

    async def join(self, chat_name: str | Iterable[str]):
        await self.client.join_channels((chat_name,) if isinstance(chat_name, str) else chat_name)

    async def leave(self, chat_name: str | Iterable[str]):
        await self.client.part_channels((chat_name,) if isinstance(chat_name, str) else chat_name)

    async def make_mention(self, user: int | str | User, group_: int | str | Chat | Message = None) -> str:
        if isinstance(user, str):
            name = user
        else:
            if isinstance(user, int):
                user = await self.get_user(user, group_)
            name = user.name

        return f'@{name}'

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
        reply_to: str | Message = None,
        data: dict = None,
        silent: bool = False,
        send_as_file: bool = None,
        edit=False
    ):
        match reply_to:
            case str(message_id):
                # noinspection PyProtectedMember
                await message.chat.original_object._ws.reply(message_id, f"PRIVMSG #{message.author.name.lower()} :{text}\r\n")
            case self.Message() as message_to_reply:
                # noinspection PyUnresolvedReferences
                context = await self.client.get_context(message_to_reply.original_object)
                await context.reply(text)
            case _:
                await chat.original_object.send(text)
