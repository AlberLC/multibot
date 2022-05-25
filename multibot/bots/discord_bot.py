from __future__ import annotations  # todo0 remove in 3.11

import asyncio
import datetime
import functools
import io
import random
from typing import Iterable

import discord
import flanautils
from discord.ext.commands import Bot
from discord.ui import Button, View
from flanautils import Media, MediaType, NotFoundError, OrderedSet, Source, return_if_first_empty

from multibot import constants
from multibot.bots.multi_bot import MultiBot, parse_arguments
from multibot.exceptions import LimitError, SendError, UserDisconnectedError
from multibot.models import Chat, Message, Mute, Platform, Role, User


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
    async def _accept_button_event(self, event: constants.MESSAGE_EVENT | Message):
        match event:
            case Message():
                event = event.original_event

        await event.response.defer()

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
            group_name = discord_chat.guild.name
            roles = self._create_roles_from_discord_roles(discord_chat.guild.roles)
        except AttributeError:
            users = [await self.get_user(self.owner_id), await self.get_user(self.bot_id)]
            try:
                chat_name = discord_chat.recipient.name
            except AttributeError:
                discord_chat = await self.bot_client.fetch_channel(discord_chat.id)
                chat_name = discord_chat.recipient.name
            group_id = None
            group_name = None
            roles = []

        return Chat(
            platform=self.bot_platform.value,
            id=discord_chat.id,
            name=chat_name,
            group_id=group_id,
            group_name=group_name,
            users=users,
            roles=roles,
            original_object=discord_chat
        )

    @return_if_first_empty
    def _create_user_from_discord_user(self, discord_user: constants.DISCORD_USER) -> User | None:
        try:
            is_admin = discord_user.guild_permissions.administrator
        except AttributeError:
            is_admin = None

        return User(
            platform=self.bot_platform.value,
            id=discord_user.id,
            name=f'{discord_user.name}#{discord_user.discriminator}',
            is_admin=is_admin,
            original_object=discord_user
        )

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    def _create_roles_from_discord_roles(self, discord_roles: list[constants.DISCORD_ROLE]) -> list[Role]:
        # noinspection PyTypeChecker
        return [Role(self.bot_platform.value, discord_role.id, discord_role.name, discord_role.permissions.administrator, discord_role) for discord_role in discord_roles]

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_author(self, original_message: constants.DISCORD_MESSAGE) -> User | None:
        return self._create_user_from_discord_user(original_message.author)

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_chat(self, original_message: constants.DISCORD_MESSAGE) -> Chat | None:
        # noinspection PyTypeChecker
        return await self._create_chat_from_discord_chat(original_message.channel)

    async def _get_me(self, group_: int | str | Chat = None) -> User | None:
        # noinspection PyTypeChecker
        user = self._create_user_from_discord_user(self.bot_client.user)
        if group_ is None:
            return user
        else:
            return await self.get_user(user, group_)

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_mentions(self, original_message: constants.DISCORD_MESSAGE) -> list[User]:
        mentions = OrderedSet(self._create_user_from_discord_user(user) for user in original_message.mentions)

        text = await self._get_text(original_message)
        chat = await self._get_chat(original_message)

        words = text.lower().split()
        for user in chat.users:
            if user.name.split('#')[0].lower() in words:
                mentions.add(user)

        return list(mentions - None)

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_message_id(self, original_message: constants.DISCORD_MESSAGE) -> int:
        return original_message.id

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_original_message(self, event: constants.DISCORD_EVENT) -> discord.Message:
        if isinstance(event, discord.Interaction):
            return event.message
        else:
            return event

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_replied_message(self, original_message: constants.DISCORD_MESSAGE) -> Message | None:
        try:
            replied_discord_message = original_message.reference.resolved
        except AttributeError:
            return

        if not isinstance(replied_discord_message, discord.DeletedReferencedMessage):
            return await self._get_message(replied_discord_message)

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_roles_from_group_id(self, group_id: int) -> list[Role]:
        guild = self.bot_client.get_guild(group_id) or await self.bot_client.fetch_guild(group_id)
        return self._create_roles_from_discord_roles(guild.roles)

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_text(self, original_message: constants.DISCORD_MESSAGE) -> str:
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

    async def _mute(self, user: int | str | User, group_: int | str | Chat):
        user = await self.get_user(user, group_)
        try:
            await user.original_object.edit(mute=True)
        except discord.errors.HTTPException:
            raise UserDisconnectedError

    @staticmethod
    def _parse_html_to_discord_markdown(text: str | None) -> str | None:
        if not text:
            return text

        return flanautils.replace(text, {
            '<b>': '**',
            '</b>': '**',
            '<i>': '*',
            '</i>': '*',
            '<u>': '__',
            '</u>': '__',
            '<del>': '~~',
            '</del>': '~~',
            '<code>': '`',
            '</code>': '`'
        })

    @staticmethod
    @return_if_first_empty
    async def _prepare_media_to_send(media: Media) -> discord.File | None:
        if not media:
            return
        if media.url:
            if media.source is Source.LOCAL:
                with open(media.url, 'rb') as file:
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

    async def _unmute(self, user: int | str | User, group_: int | str | Chat):
        user = await self.get_user(user, group_)
        try:
            await user.original_object.edit(mute=False)
        except discord.errors.HTTPException:
            raise UserDisconnectedError

    # ---------------------------------------------- #
    #                    HANDLERS                    #
    # ---------------------------------------------- #
    async def _on_ready(self):
        self.bot_platform = Platform.DISCORD
        self.bot_id = self.bot_client.user.id
        self.bot_name = self.bot_client.user.name
        self.owner_id = (await self.bot_client.application_info()).owner.id
        await super()._on_ready()

    # -------------------------------------------------------- #
    # -------------------- PUBLIC METHODS -------------------- #
    # -------------------------------------------------------- #
    async def add_role(self, user: int | str | User, group_: int | str | Chat, role: int | str | Role):
        user = await self.get_user(user, group_)
        try:
            await user.original_object.add_roles((await self.get_role(role, group_)).original_object)
        except AttributeError:
            raise NotFoundError('role not found')

    async def ban(self, user: int | str | User, chat: int | str | Chat | Message, seconds: int | datetime.timedelta = None):  # todo2
        pass

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def clear(self, n_messages: int, chat: int | str | Chat | Message):  # todo2 test
        if n_messages > 100:
            raise LimitError('El máximo es 100.')

        chat = await self.get_chat(chat)
        n_messages += 1
        messages = [message async for message in chat.original_object.history(limit=n_messages)]

        for chunk in flanautils.chunks(messages, 100, lazy=True):
            try:
                await chat.original_object.delete_messages(chunk)
            except discord.errors.HTTPException:
                raise LimitError(f'Solo puedo eliminar mensajes con menos de 14 días  {random.choice(constants.SAD_EMOJIS)}')

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def delete_message(self, message_to_delete: int | str | Message, chat: int | str | Chat | Message = None):  # todo2 test
        chat = await self.get_chat(chat)
        match message_to_delete:
            case int() | str():
                message_to_delete = Message.find_one({'platform': self.bot_platform.value, 'id': str(message_to_delete), 'chat': chat.object_id})
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
    async def get_chat(self, chat: int | str | Chat | Message = None) -> Chat | None:
        match chat:
            case int(chat_id):
                pass
            case str():
                chat_id = Chat.find_one({'platform': self.bot_platform.value, 'name': chat}).id
            case Chat():
                return chat
            case Message() as message:
                return message.chat
            case _:
                raise TypeError('bad arguments')

        # noinspection PyTypeChecker
        return await self._create_chat_from_discord_chat(self.bot_client.get_channel(chat_id) or await self.bot_client.fetch_channel(chat_id))

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def get_user(self, user: int | str | User, group_: int | str | Chat = None) -> User | None:
        user_id = self._get_user_id(user)
        group_id = self._get_group_id(group_)
        if group_id is None:
            discord_user = self.bot_client.get_user(user_id) or await self.bot_client.fetch_user(user_id)
        else:
            guild = self.bot_client.get_guild(group_id) or await self.bot_client.fetch_guild(group_id)
            discord_user = guild.get_member(user_id)

        return self._create_user_from_discord_user(discord_user)

    async def has_role(self, user: int | str | User, group_: int | str | Chat, role: int | str | discord.Role):
        user = await self.get_user(user, group_)
        if not (user_roles := getattr(user.original_object, 'roles', None)):
            return

        match role:
            case int():
                role = self._find_role_by_id(role, user.original_object.guild.roles)
            case str():
                role = self._find_role_by_name(role, user.original_object.guild.roles)

        return role in user_roles

    async def is_deaf(self, user: int | str | User, group_: int | str | Chat) -> bool:
        user = await self.get_user(user, group_)
        try:
            return user.original_object.voice.deaf
        except AttributeError:
            raise UserDisconnectedError

    async def is_muted(self, user: int | str | User, group_: int | str | Chat) -> bool:
        user = await self.get_user(user, group_)
        try:
            return user.original_object.voice.mute
        except AttributeError:
            group_id = self._get_group_id(group_)
            return group_id in {mute.group_id for mute in Mute.find({
                'platform': self.bot_platform.value,
                'user_id': user.id,
                'group_id': group_id,
                'is_active': True
            })}

    async def is_self_deaf(self, user: int | str | User, group_: int | str | Chat) -> bool:
        user = await self.get_user(user, group_)
        try:
            return user.original_object.voice.self_deaf
        except AttributeError:
            raise UserDisconnectedError

    async def is_self_muted(self, user: int | str | User, group_: int | str | Chat) -> bool:
        user = await self.get_user(user, group_)
        try:
            return user.original_object.voice.self_mute
        except AttributeError:
            raise UserDisconnectedError

    async def remove_role(self, user: int | str | User, group_: int | str | Chat, role: int | str | Role):
        user = await self.get_user(user, group_)
        try:
            await user.original_object.remove_roles((await self.get_role(role, group_)).original_object)
        except AttributeError:
            raise NotFoundError('role not found')

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
    ) -> Message:
        def create_view():
            nonlocal buttons
            buttons = buttons or []
            view_ = View(timeout=None)
            for i, row in enumerate(buttons):
                for j, column in enumerate(row):
                    discord_button = Button(label=buttons[i][j], row=i)
                    discord_button.callback = functools.partial(self._on_button_press_raw, discord_button.label)
                    view_.add_item(discord_button)

            return view_

        text = self._parse_html_to_discord_markdown(text)
        file = await self._prepare_media_to_send(media)

        if edit:
            kwargs = {}
            if file:
                kwargs['attachments'] = [file]
            if buttons:
                kwargs['view'] = create_view()
            message.original_object = await message.original_object.edit(content=text, **kwargs)
            return message
        else:
            view = create_view() if buttons else None
            bot_message = await self._get_message(await message.chat.original_object.send(text, file=file, view=view))
            bot_message.buttons = buttons
            if content := getattr(media, 'content', None):
                bot_message.contents = [content]
            bot_message.save()
            return bot_message

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

    async def unban(self, user: int | str | User, chat: int | str | Chat | Message):  # todo2
        pass
