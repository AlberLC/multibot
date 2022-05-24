from __future__ import annotations  # todo0 remove in 3.11

import asyncio
import datetime
import functools
import re
from collections import defaultdict
from typing import Iterable, Iterator

import flanautils
import pymongo
import twitchio
from flanautils import Media, OrderedSet, return_if_first_empty

from multibot.bots.multi_bot import MultiBot, parse_arguments
from multibot.models import Chat, Message, Platform, User


# --------------------------------------------------------------------------------------------------- #
# ------------------------------------------- DISCORD_BOT ------------------------------------------- #
# --------------------------------------------------------------------------------------------------- #
class TwitchBot(MultiBot[twitchio.Client]):
    def __init__(self, bot_token: str, initial_channels: Iterable[str] = None, owner_name: str = None):
        super().__init__(bot_token=bot_token,
                         bot_client=twitchio.Client(token=bot_token, initial_channels=initial_channels))
        self.owner_name = owner_name

    # ----------------------------------------------------------- #
    # -------------------- PROTECTED METHODS -------------------- #
    # ----------------------------------------------------------- #
    # noinspection PyProtectedMember
    def _add_handlers(self):
        super()._add_handlers()
        self.bot_client._events = defaultdict(list)
        self.bot_client._events['event_ready'].append(self._on_ready)
        self.bot_client._events['event_message'].append(self._on_new_message_raw)

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _create_chat_from_twitch_chat(self, twitch_chat: twitchio.Channel) -> Chat | None:
        channel_name = twitch_chat.name
        try:
            channel_id = int(flanautils.find(twitch_chat.chatters, condition=lambda user: user.name == channel_name).id)
        except AttributeError:
            channel_id = int(next(iter(await self.bot_client.fetch_users([channel_name])), None).id)

        return Chat(
            platform=self.bot_platform.value,
            id=channel_id,
            name=channel_name,
            group_id=channel_id,
            group_name=channel_name,
            users=list(OrderedSet([await self._create_user_from_twitch_user(chatter) for chatter in twitch_chat.chatters])),
            original_object=twitch_chat
        )

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _create_user_from_twitch_user(self, twitch_user: twitchio.Chatter | twitchio.User, is_admin: bool = None) -> User | None:
        if (id := twitch_user.id) is None:
            id = next(iter(await self.bot_client.fetch_users([twitch_user.name])), None).id

        return User(
            platform=self.bot_platform.value,
            id=int(id),
            name=twitch_user.name,
            is_admin=getattr(twitch_user, 'is_mod', None) if is_admin is None else is_admin,
            original_object=twitch_user
        )

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _get_author(self, original_message: twitchio.Message) -> User | None:
        if original_message.echo:
            return await self._get_me(original_message.channel.name)
        return await self._create_user_from_twitch_user(original_message.author)

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _get_chat(self, original_message: twitchio.Message) -> Chat | None:
        return await self._create_chat_from_twitch_chat(original_message.channel)

    async def _get_me(self, group_: int | str | Chat = None) -> User | None:
        return await self.get_user(self.bot_id, group_)

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _get_mentions(self, original_message: twitchio.Message) -> list[User]:
        mentions = OrderedSet([user for mention in re.findall(r'@[\d\w]+', original_message.content) if (user := await self.get_user(mention[1:], original_message.channel.name))])

        text = await self._get_text(original_message)
        chat = await self._get_chat(original_message)

        words = text.lower().split()
        for user in chat.users:
            if user.name.lower() in words:
                mentions.add(user)

        return list(mentions)

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _get_message_id(self, original_message: twitchio.Message) -> str:
        return original_message.id

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _get_original_message(self, event: twitchio.Message) -> twitchio.Message:
        return event

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _get_replied_message(self, original_message: twitchio.Message) -> Message | None:
        try:
            return Message.find_one({'platform': self.bot_platform.value, 'id': original_message.tags['reply-parent-msg-id']})
        except KeyError:
            pass

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def _get_text(self, original_message: twitchio.Message) -> str:
        return re.sub(r'@[\d\w]+', '', original_message.content).strip()

    # ---------------------------------------------- #
    #                    HANDLERS                    #
    # ---------------------------------------------- #
    async def _on_ready(self):
        self.bot_platform = Platform.TWITCH
        self.bot_id = (await self.get_user(self.bot_client.nick)).id
        self.bot_name = self.bot_client.nick
        self.owner_id = user.id if (user := await self.get_user(self.owner_name)) else None
        await super()._on_ready()

    # -------------------------------------------------------- #
    # -------------------- PUBLIC METHODS -------------------- #
    # -------------------------------------------------------- #
    async def ban(self, user: int | str | User, chat: int | str | Chat | Message, seconds: int | datetime.timedelta = None):
        user_name = (await self.get_user(user)).name
        chat = await self.get_chat(chat)
        if isinstance(seconds, datetime.timedelta):
            seconds = seconds.total_seconds()

        if seconds:
            await self.send(f'/timeout {user_name} {seconds}', Message(chat=chat))
        else:
            await self.send(f'/ban {user_name}', Message(chat=chat))

    clear_user_messages = functools.partialmethod(ban, seconds=1)

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def clear(self, n_messages: int, chat: int | str | Chat | Message):
        chat = await self.get_chat(chat)

        owner_user = User.find_one({'platform': self.bot_platform.value, 'name': self.owner_name})
        messages_to_delete: Iterator[Message] = Message.find({
            'platform': self.bot_platform.value,
            'author': {'$ne': owner_user.object_id},
            'chat': chat.object_id,
            'is_deleted': False,
            'last_update': {'$gt': datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)}
        }, sort_keys=(('last_update', pymongo.DESCENDING),), lazy=True)

        deleted_message_count = 0
        while deleted_message_count < n_messages:
            try:
                message_to_delete = next(messages_to_delete)
            except StopIteration:
                break

            if not message_to_delete.author.is_admin:
                await self.delete_message(message_to_delete, chat)
                deleted_message_count += 1

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def delete_message(self, message_to_delete: int | str | Message, chat: int | str | Chat | Message = None):
        chat = await self.get_chat(chat)
        match message_to_delete:
            case int() | str():
                message_to_delete = Message.find_one({'platform': self.bot_platform.value, 'id': str(message_to_delete), 'chat': chat.object_id})
            case Message() if message_to_delete.original_object and message_to_delete.chat and message_to_delete.chat == chat:
                chat = None

        if chat and chat.original_object:
            message = Message(chat=chat)
        elif message_to_delete.original_object:
            message = message_to_delete
        else:
            raise ValueError('The original twitch object of the message or chat is needed')

        await self.send(f'/delete {message_to_delete.id}', message)
        message_to_delete.is_deleted = True
        message_to_delete.save()

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def get_chat(self, chat: int | str | Chat | Message = None) -> Chat | None:
        match chat:
            case int():
                group_name = self._get_group_name(chat)
            case str(group_name):
                pass
            case Chat():
                return chat
            case Message() as message:
                return message.chat
            case _:
                raise TypeError('bad arguments')

        return await self._create_chat_from_twitch_chat(self.bot_client.get_channel(group_name) or await self.bot_client.fetch_channel(group_name))

    @return_if_first_empty(exclude_self_types='TwitchBot', globals_=globals())
    async def get_user(self, user: int | str | User, group_: int | str | Chat = None) -> User | None:
        if isinstance(user, User):
            return user

        twitch_user: twitchio.User | twitchio.Chatter
        if not (twitch_user := next(iter(await self.bot_client.fetch_users([user])), None)):
            return

        group_name = self._get_group_name(group_)

        if group_name:
            if twitch_user.name == group_name:
                is_admin = True
            else:
                chat = await self.get_chat(group_)
                twitch_user = chat.original_object.get_chatter(twitch_user.name)
                is_admin = twitch_user.is_mod if twitch_user else None
        else:
            is_admin = None
        return await self._create_user_from_twitch_user(twitch_user, is_admin=is_admin)

    async def join(self, chat_name: str | Iterable[str]):
        await self.bot_client.join_channels((chat_name,) if isinstance(chat_name, str) else chat_name)

    @parse_arguments
    async def send(
        self,
        text='',
        media: Media = None,
        buttons: list[str | list[str]] = None,
        message: Message = None,
        silent: bool = False,
        send_as_file: bool = None,
        edit=False
    ):
        await message.chat.original_object.send(text)

    def start(self):
        async def start_():
            await asyncio.create_task(self.bot_client.connect())
            # noinspection PyProtectedMember
            await self.bot_client._connection._keep_alive()

        try:
            asyncio.get_running_loop()
            return start_()
        except RuntimeError:
            self.bot_client.run()

    async def unban(self, user: int | str | User, chat: int | str | Chat | Message):
        user_name = (await self.get_user(user)).name
        chat = await self.get_chat(chat)
        await self.send(f'/unban {user_name}', Message(chat=chat))
