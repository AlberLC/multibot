from __future__ import annotations  # todo0 remove in 3.11

import asyncio
import datetime
import io
import random
from typing import Iterable

import discord
import flanautils
from discord.ext.commands import Bot
from flanautils import Media, MediaType, OrderedSet, Source, return_if_first_empty

from multibot import constants
from multibot.bots.multi_bot import MultiBot, parse_arguments
from multibot.exceptions import LimitError, SendError
from multibot.models import BotPlatform, Chat, Message, User


# --------------------------------------------------------------------------------------------------- #
# ------------------------------------------- DISCORD_BOT ------------------------------------------- #
# --------------------------------------------------------------------------------------------------- #
class DiscordBot(MultiBot[Bot]):
    def __init__(self, bot_token: str):
        super().__init__(bot_token=bot_token,
                         bot_client=Bot(command_prefix=constants.DISCORD_COMMAND_PREFIX, intents=discord.Intents.all()))

    # ----------------------------------------------------------- #
    # -------------------- PROTECTED METHODS -------------------- #
    # ----------------------------------------------------------- #
    def _add_handlers(self):
        super()._add_handlers()
        self.bot_client.add_listener(self._on_ready, 'on_ready')
        self.bot_client.add_listener(self._on_new_message_raw, 'on_message')

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _create_chat_from_discord_chat(self, discord_chat: constants.DISCORD_CHAT) -> Chat | None:
        try:
            users = [self._create_user_from_discord_user(member) for member in discord_chat.guild.members]
            chat_name = discord_chat.name
            group_id = discord_chat.guild.id
        except AttributeError:
            users = [await self.get_user(self.owner_id), await self.get_user(self.bot_id)]
            chat_name = discord_chat.recipient.name
            group_id = None

        return Chat(
            id=discord_chat.channel.id,
            name=chat_name,
            is_group=discord_chat.channel.type is not discord.ChannelType.private,
            users=users,
            group_id=group_id,
            original_object=discord_chat.channel
        )

    @staticmethod
    @return_if_first_empty
    def _create_user_from_discord_user(discord_user: constants.DISCORD_USER) -> User | None:
        try:
            is_admin = discord_user.guild_permissions.administrator
        except AttributeError:
            is_admin = None

        return User(
            id=discord_user.id,
            name=discord_user.name,
            is_admin=is_admin,
            original_object=discord_user
        )

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_author(self, original_message: constants.DISCORD_EVENT) -> User | None:
        return self._create_user_from_discord_user(original_message.author)

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_chat(self, original_message: constants.DISCORD_EVENT) -> Chat | None:
        # noinspection PyTypeChecker
        return await self._create_chat_from_discord_chat(original_message.channel)

    async def _get_me(self, group_id: int = None) -> User | None:
        if group_id is None:
            discord_user = self.bot_client.user
        else:
            discord_user = self.bot_client.get_guild(group_id).get_member(self.bot_client.user.id)
        return self._create_user_from_discord_user(discord_user)

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_mentions(self, original_message: constants.DISCORD_EVENT) -> list[User]:
        return list(OrderedSet(self._create_user_from_discord_user(user) for user in original_message.mentions) - None)

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_message_id(self, original_message: constants.DISCORD_EVENT) -> int:
        return original_message.id

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_original_message(self, original_message: constants.DISCORD_EVENT) -> discord.Message:
        return original_message

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_replied_message(self, original_message: constants.DISCORD_EVENT) -> Message | None:
        try:
            replied_discord_message = original_message.reference.resolved
        except AttributeError:
            return

        if not isinstance(replied_discord_message, discord.DeletedReferencedMessage):
            return await self._get_message(replied_discord_message)

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_text(self, original_message: constants.DISCORD_EVENT) -> str:
        return original_message.content

    @staticmethod
    def _find_role_by_id(role_id: int, roles: Iterable[discord.Role]) -> discord.Role | None:
        for role in roles:
            if role.id == role_id:
                return role

    @staticmethod
    def _find_role_by_name(role_name: str, roles: Iterable[discord.Role]) -> discord.Role | None:
        for role in roles:
            if role.name.lower() == role_name.lower():
                return role

    @staticmethod
    @return_if_first_empty
    async def _prepare_media_to_send(media: Media) -> discord.File | None:
        if not media:
            return
        if media.url:
            if media.source is Source.LOCAL:
                with open(media.url, 'b') as file:
                    bytes_ = file.read()
            else:
                bytes_ = await flanautils.get_request(media.url)
        elif media.bytes_:
            bytes_ = media.bytes_
        else:
            return

        if len(bytes_) > constants.DISCORD_MEDIA_MAX_BYTES:
            if random.randint(0, 10):
                error_message = 'El archivo pesa más de 8 MB.'
            else:
                error_message = 'El archivo pesa mas que tu madre'
            raise SendError(error_message)

        if media.type_ is MediaType.GIF:
            bytes_ = await flanautils.mp4_to_gif(bytes_)

        return discord.File(fp=io.BytesIO(bytes_), filename=f'bot_media.{media.type_.extension}')

    # ---------------------------------------------- #
    #                    HANDLERS                    #
    # ---------------------------------------------- #
    async def _on_ready(self):
        self.bot_id = self.bot_client.user.id
        self.bot_name = self.bot_client.user.name
        self.owner_id = (await self.bot_client.application_info()).owner.id
        self.bot_platform = BotPlatform.DISCORD
        await super()._on_ready()

    # -------------------------------------------------------- #
    # -------------------- PUBLIC METHODS -------------------- #
    # -------------------------------------------------------- #
    async def ban(self, user: int | str | User, chat: int | str | Chat | Message, seconds: int | datetime.timedelta = None):  # todo2
        pass

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def clear(self, n_messages: int, chat: int | str | Chat | Message):  # todo2 test
        chat = await self.get_chat(chat)
        n_messages += 1

        try:
            messages = await chat.original_object.history(limit=n_messages).flatten()
        except discord.ClientException:
            await self._manage_exceptions(LimitError('El máximo es 99.'), Message(chat=chat))
        else:
            await chat.original_object.delete_messages(messages)

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def delete_message(self, message_to_delete: int | str | Message, chat: int | str | Chat | Message = None):  # todo2 test
        chat = await self.get_chat(chat)
        match message_to_delete:
            case int() | str():
                message_to_delete = Message.find_one({'id': str(message_to_delete), 'chat': chat.object_id})
            case Message() if message_to_delete.original_object and message_to_delete.chat and message_to_delete.chat == chat:
                chat = None

        if chat and chat.original_object:
            await (await chat.original_object.fetch_message(message_to_delete.id)).delete()
        elif message_to_delete.original_object:
            await message_to_delete.original_object.delete()
        else:
            raise ValueError('The original discord object of the message or chat is needed')

        message_to_delete.is_deleted = True
        message_to_delete.save()

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def get_user(self, user: int | str | User, group_id: int | str = None) -> User | None:
        if isinstance(user, User):
            return user

        if group_id is None:
            discord_user = self.bot_client.get_user(user)
        else:
            discord_user = self.bot_client.get_guild(int(group_id)).get_member(user)

        return self._create_user_from_discord_user(discord_user)

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def get_chat(self, chat: int | str | Chat | Message = None) -> Chat | None:
        match chat:
            case Chat():
                return chat
            case Message() as message:
                return message.chat

        # noinspection PyTypeChecker
        return await self._create_chat_from_discord_chat(self.bot_client.get_channel(int(chat)) or await self.bot_client.fetch_channel(int(chat)))

    @parse_arguments
    async def send(
        self,
        text='',
        media: Media = None,
        buttons: list[str | list[str]] = None,
        message: Message = None,
        send_as_file: bool = None,
        edit=False
    ) -> Message:
        if edit:
            await message.original_object.edit(text, file=await self._prepare_media_to_send(media))
            return message
        else:
            return await self._get_message(
                await message.chat.original_object.send(text, file=await self._prepare_media_to_send(media))
            )

    def start(self):
        async def start_():
            await self.bot_client.start(self.bot_token)

        try:
            asyncio.get_running_loop()
            return start_()
        except RuntimeError:
            asyncio.run(start_())

    async def typing_delay(self, message: Message):
        async with message.chat.original_object.typing():
            await asyncio.sleep(random.randint(1, 3))

    def user_has_role(self, user: User, role: int | discord.Role):
        if not (user_roles := getattr(user.original_object, 'roles', None)):
            return

        if isinstance(role, int):
            role = self._find_role_by_id(role, user.original_object.guild.roles)

        return role in user_roles

    async def unban(self, user: int | str | User, chat: int | str | Chat, message: Message = None):  # todo2
        pass
