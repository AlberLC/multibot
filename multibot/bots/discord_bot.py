from __future__ import annotations  # todo0 remove when it's by default

__all__ = ['DiscordBot']

import asyncio
import datetime
import io
import pathlib
import random
import traceback
from typing import Any, Iterable, Sequence

import discord
import flanautils
import pymongo
from discord.ext.commands import Bot
from flanautils import Media, MediaType, NotFoundError, OrderedSet, return_if_first_empty

from multibot import constants
from multibot.bots.multi_bot import MultiBot, parse_arguments
from multibot.exceptions import LimitError, SendError, UserDisconnectedError
from multibot.models import Button, ButtonsInfo, Chat, Message, Mute, Platform, Role, User


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
        self.client.add_listener(self._on_ready, 'on_ready')
        self.client.add_listener(self._on_new_message_raw, 'on_message')

    async def _ban(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        user = await self.get_user(user, group_)
        await user.original_object.ban(delete_message_days=0)

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _create_chat_from_discord_chat(self, original_chat: constants.DISCORD_CHAT) -> Chat | None:
        try:
            chat_name = original_chat.name
            group_id = original_chat.guild.id
            group_name = original_chat.guild.name
        except AttributeError:
            try:
                chat_name = original_chat.recipient.name
            except AttributeError:
                original_chat = await self.client.fetch_channel(original_chat.id)
                # noinspection PyUnresolvedReferences
                chat_name = original_chat.recipient.name
            group_id = None
            group_name = None

        return self.Chat(
            platform=self.platform,
            id=original_chat.id,
            name=chat_name,
            group_id=group_id,
            group_name=group_name,
            original_object=original_chat
        )

    @return_if_first_empty
    async def _create_user_from_discord_user(self, original_user: constants.DISCORD_USER) -> User | None:
        try:
            is_admin = original_user.guild_permissions.administrator
        except AttributeError:
            is_admin = None
        try:
            # noinspection PyTypeChecker
            current_roles = await self.get_current_roles(original_user)
            for current_role in current_roles:
                current_role.pull_from_database()
            current_roles = OrderedSet(current_roles)
        except AttributeError:
            current_roles = OrderedSet()

        if database_user_data := self.User.collection.find_one({'platform': self.platform.value, 'id': original_user.id}):
            database_roles = OrderedSet(Role.find({'_id': {'$in': database_user_data['roles']}}))
        else:
            database_roles = OrderedSet()

        return self.User(
            platform=self.platform,
            id=original_user.id,
            name=f'{original_user.name}#{original_user.discriminator}',
            is_admin=is_admin,
            is_bot=original_user.bot,
            roles=list(current_roles | database_roles),
            original_object=original_user
        )

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_author(self, original_message: constants.DISCORD_MESSAGE) -> User | None:
        return await self._create_user_from_discord_user(original_message.author)

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_button_pressed_text(self, event: constants.DISCORD_EVENT) -> str | None:
        try:
            button_id = event.data['custom_id']
        except AttributeError:
            pass
        else:
            original_message = await self._get_original_message(event)
            for row in original_message.components:
                for button in row.children:
                    if button.custom_id == button_id:
                        return button.label

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_button_presser_user(self, event: constants.DISCORD_EVENT) -> User | None:
        try:
            return await self._create_user_from_discord_user(event.user)
        except AttributeError:
            pass

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_chat(self, original_message: constants.DISCORD_MESSAGE) -> Chat | None:
        # noinspection PyTypeChecker
        return await self._create_chat_from_discord_chat(original_message.channel)

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_discord_group(self, group_: int | str | Chat | Message) -> constants.DISCORD_GROUP | None:
        match group_:
            case int(group_id):
                return self.client.get_guild(group_id) or await self.client.fetch_guild(group_id)
            case str(group_name):
                group_id = self.get_group_id(group_name)
                return self.client.get_guild(group_id) or await self.client.fetch_guild(group_id)
            case self.Chat() as chat:
                return chat.original_object.guild
            case self.Message() as message:
                return message.chat.original_object.guild

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_mentions(self, original_message: constants.DISCORD_MESSAGE) -> list[User]:
        mentions = OrderedSet([await self._create_user_from_discord_user(user) for user in original_message.mentions])

        chat = await self._get_chat(original_message)
        text = await self._get_text(original_message)
        text = flanautils.remove_symbols(text, ignore=('#',), replace_with=' ')
        words = text.lower().split()

        if chat.is_group:
            for member in chat.original_object.guild.members:
                user_name = f'{member.name}#{member.discriminator}'.lower()
                short_user_name = member.name.lower()
                if user_name in words or short_user_name in words:
                    mentions.add(await self._create_user_from_discord_user(member))
        else:
            user_name = f'{chat.original_object.recipient.name}#{chat.original_object.recipient.discriminator}'.lower()
            short_user_name = chat.original_object.recipient.name.lower()
            if user_name in words or short_user_name in words:
                mentions.add(await self._create_user_from_discord_user(chat.original_object.recipient))

            bot_name = f'{chat.original_object.me.name}#{chat.original_object.me.discriminator}'.lower()
            short_bot_name = chat.original_object.me.name.lower()
            if bot_name in words or short_bot_name in words:
                mentions.add(await self._create_user_from_discord_user(chat.original_object.me))

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
            replied_original_message = original_message.reference.resolved
        except AttributeError:
            return

        if not isinstance(replied_original_message, discord.DeletedReferencedMessage):
            return await self._get_message(replied_original_message)

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def _get_text(self, original_message: constants.DISCORD_MESSAGE) -> str:
        return original_message.content

    async def _mute(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        user = await self.get_user(user, group_)
        try:
            await user.original_object.edit(mute=True)
        except discord.errors.HTTPException:
            raise UserDisconnectedError(user.name)

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

        file_name = f"{media.title or 'bot_media'}.{media.extension}"

        if media.url:
            if pathlib.Path(media.url).is_file():
                if (path_suffix := pathlib.Path(media.url).suffix) and len(path_suffix) <= constants.MAX_FILE_EXTENSION_LENGHT:
                    return discord.File(media.url)
                else:
                    return discord.File(media.url, filename=file_name)
            elif not media.bytes_:
                media.bytes_ = await flanautils.get_request(media.url)

        if bytes_ := media.bytes_:
            if media.type_ is MediaType.GIF:
                bytes_ = await flanautils.to_gif(bytes_)
            if len(bytes_) > constants.DISCORD_MEDIA_MAX_BYTES:
                raise LimitError
            return discord.File(fp=io.BytesIO(bytes_), filename=file_name)

    async def _unban(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        user = await self.get_user(user)
        discord_group = await self._get_discord_group(group_)
        await discord_group.unban(user)

    async def _unmute(self, user: int | str | User, group_: int | str | Chat | Message, message: Message = None):
        user = await self.get_user(user, group_)
        try:
            await user.original_object.edit(mute=False)
        except discord.errors.HTTPException:
            raise UserDisconnectedError(user.name)

    # ---------------------------------------------- #
    #                    HANDLERS                    #
    # ---------------------------------------------- #
    async def _on_ready(self):
        self.platform = Platform.DISCORD
        self.id = self.client.user.id
        self.name = self.client.user.name
        self.owner_id = (await self.client.application_info()).owner.id
        await super()._on_ready()

    # -------------------------------------------------------- #
    # -------------------- PUBLIC METHODS -------------------- #
    # -------------------------------------------------------- #
    async def accept_button_event(self, event: constants.DISCORD_EVENT | Message):
        match event:
            case self.Message():
                event = event.original_event

        try:
            await event.response.defer()
        except AttributeError:
            pass

    async def add_role(self, user: int | str | User, group_: int | str | Chat | Message, role: int | str | Role):
        user = await self.get_user(user, group_)
        role = await self.find_role(role, group_)

        try:
            await user.original_object.add_roles(role.original_object)
        except (AttributeError, discord.errors.NotFound):
            raise NotFoundError('role not found')

        if role not in user.roles:
            user.roles.append(role)
            user.save(('roles',))

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def clear(self, n_messages: int, chat: int | str | Chat | Message):
        if n_messages > 100:
            raise LimitError('El máximo es 100.')

        chat = await self.get_chat(chat)
        n_messages += 1

        while n_messages > 0:
            if n_messages > 100:
                n_messages_chunk = 100
                n_messages -= 100
            else:
                n_messages_chunk = n_messages
                n_messages = 0

            try:
                await chat.original_object.purge(limit=n_messages_chunk)
            except discord.errors.HTTPException:
                raise LimitError(f'Solo puedo eliminar mensajes con menos de 14 días {random.choice(constants.SAD_EMOJIS)}')

            database_messages_to_delete_generator = self.Message.find({'platform': self.platform.value, 'chat': chat.object_id}, sort_keys=(('date', pymongo.DESCENDING),), limit=n_messages_chunk, lazy=True)
            for database_message_to_delete in database_messages_to_delete_generator:
                database_message_to_delete.is_deleted = True
                database_message_to_delete.save()

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def delete_message(
        self,
        message_to_delete: int | str | Message,
        chat: int | str | Chat | Message = None,
        raise_not_found=False
    ):
        if isinstance(message_to_delete, self.Message) and message_to_delete.original_object:
            original_message = message_to_delete.original_object
        else:
            chat = await self.get_chat(chat)
            chat.pull_from_database()
            if not isinstance(message_to_delete, Message):
                message_to_delete = self.Message.find_one({'platform': self.platform.value, 'id': int(message_to_delete), 'chat': chat.object_id})
            original_message = await chat.original_object.fetch_message(message_to_delete.id)

        try:
            await original_message.delete()
        except discord.errors.NotFound:
            if raise_not_found:
                raise NotFoundError(traceback.format_exc().splitlines()[-1])
        except discord.errors.Forbidden:
            return

        message_to_delete.is_deleted = True
        message_to_delete.save()

    # noinspection PyTypeChecker
    def distribute_buttons(self, texts: Sequence[str], vertically=False) -> list[list[str]]:
        texts = [f'{text[:constants.DISCORD_BUTTON_MAX_CHARACTERS - 3]}...' if len(text) > constants.DISCORD_BUTTON_MAX_CHARACTERS else text for text in texts]

        if len(texts) <= constants.DISCORD_BUTTONS_MAX and vertically:
            return flanautils.chunks(texts, 1)
        return flanautils.chunks(texts, constants.DISCORD_BUTTONS_MAX)

    async def find_audit_entries(
        self,
        group_: int | str | Chat | Message,
        limit: int = None,
        actions=None,
        before: datetime.datetime = None,
        after: datetime.datetime = None,
        newer_first=True
    ) -> list[discord.AuditLogEntry]:
        discord_group = await self._get_discord_group(group_)
        if actions is not None:
            actions = list(actions)

        audit_entries = []
        async for entry in discord_group.audit_logs(before=before, after=after, oldest_first=not newer_first):
            if limit is not None and len(audit_entries) == limit:
                break
            if actions is None or entry.action in actions:
                audit_entries.append(entry)

        return audit_entries

    async def find_users_by_roles(self, roles: Iterable[int | str | Role], group_: int | str | Chat | Message) -> list[User]:
        match roles:
            case [*_, int()] as role_ids:
                role_ids = set(role_ids)
            case [*_, str()] as role_names:
                role_ids = {(await self.find_role(role_name, group_)).id for role_name in role_names}
            case [*_, Role()]:
                role_ids = {role.id for role in roles}
            case []:
                role_ids = set()
            case _:
                raise TypeError('bad arguments')
        role_ids.add((await self.find_role('@everyone', group_)).id)

        users = []
        discord_group = await self._get_discord_group(group_)
        for original_user in discord_group.members:
            for original_role in original_user.roles:
                if original_role.id not in role_ids:
                    break
            else:
                if len(original_user.roles) == len(role_ids):
                    users.append(await self._create_user_from_discord_user(original_user))

        return users

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def get_chat(self, chat: int | str | User | Chat | Message) -> Chat | None:
        match chat:
            case int(chat_id):
                pass
            case str(chat_name):
                chat_id = self.Chat.find_one({'platform': self.platform.value, 'name': chat_name}).id
            case self.User() as user:
                return await self._create_chat_from_discord_chat(await user.original_object.create_dm())
            case self.Chat():
                return chat
            case self.Message() as message:
                return message.chat
            case _:
                raise TypeError('bad arguments')

        # noinspection PyTypeChecker
        return await self._create_chat_from_discord_chat(self.client.get_channel(chat_id) or await self.client.fetch_channel(chat_id))

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def get_current_roles(self, user: int | str | User | constants.DISCORD_USER, group_: int | str | Chat | Message = None) -> list[Role]:
        if isinstance(user, User) and not group_:
            original_user = user.original_object
        elif isinstance(user, (int, str, User)):
            original_user = (await self.get_user(user, group_)).original_object
        elif isinstance(user, constants.DISCORD_USER):
            original_user = user
        else:
            raise TypeError('bad arguments')

        try:
            # noinspection PyTypeChecker
            return [Role(self.platform, discord_role.id, original_user.guild.id, discord_role.name, discord_role.permissions.administrator, discord_role) for discord_role in original_user.roles]
        except AttributeError:
            return []

    async def get_me(self, group_: int | str | Chat | Message = None) -> User | None:
        # noinspection PyTypeChecker
        user = await self._create_user_from_discord_user(self.client.user)
        if group_ is None:
            return user
        else:
            return await self.get_user(user, group_)

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def get_message(self, chat: int | str | User | Chat | Message, message: int | str | Message) -> Message | None:
        match message:
            case int(message_id):
                pass
            case str(message_id):
                message_id = int(message_id)
            case self.Message():
                return message
            case _:
                raise TypeError('bad arguments')

        chat = await self.get_chat(chat)
        return await self._get_message(await chat.original_object.fetch_message(message_id))

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def get_group_roles(self, group_: int | str | Chat | Message) -> list[Role]:
        if not (discord_group := await self._get_discord_group(group_)):
            return []

        # noinspection PyTypeChecker
        return [Role(self.platform, discord_role.id, discord_group.id, discord_role.name, discord_role.permissions.administrator, discord_role) for discord_role in discord_group.roles]

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def get_user(self, user: int | str | User, group_: int | str | Chat | Message = None) -> User | None:
        user_id = self.get_user_id(user)

        if group_ is None:
            original_user = self.client.get_user(user_id) or await self.client.fetch_user(user_id)
        else:
            discord_group = await self._get_discord_group(group_)
            original_user = discord_group.get_member(user_id)

        return await self._create_user_from_discord_user(original_user)

    @return_if_first_empty(exclude_self_types='DiscordBot', globals_=globals())
    async def get_users(self, group_: int | str | Chat | Message) -> list[User]:
        discord_group = await self._get_discord_group(group_)
        return [await self._create_user_from_discord_user(member) for member in discord_group.members]

    async def has_role(self, user: int | str | User, group_: int | str | Chat | Message, role: int | str | Role) -> bool:
        user = await self.get_user(user, group_)
        if not (user_roles := getattr(user.original_object, 'roles', None)):
            return False

        role = await self.find_role(role)
        return role.original_object in user_roles

    async def is_deaf(self, user: int | str | User, group_: int | str | Chat | Message) -> bool:
        user = await self.get_user(user, group_)
        try:
            return user.original_object.voice.deaf
        except AttributeError:
            raise UserDisconnectedError(user.name)

    async def is_muted(self, user: int | str | User, group_: int | str | Chat | Message) -> bool:
        user = await self.get_user(user, group_)
        try:
            return user.original_object.voice.mute
        except AttributeError:
            group_id = self.get_group_id(group_)
            return group_id in {mute.group_id for mute in Mute.find({
                'platform': self.platform.value,
                'user_id': user.id,
                'group_id': group_id,
                'is_active': True
            })}

    async def is_self_deaf(self, user: int | str | User, group_: int | str | Chat | Message) -> bool:
        user = await self.get_user(user, group_)
        try:
            return user.original_object.voice.self_deaf
        except AttributeError:
            raise UserDisconnectedError(user.name)

    async def is_self_muted(self, user: int | str | User, group_: int | str | Chat | Message) -> bool:
        user = await self.get_user(user, group_)
        try:
            return user.original_object.voice.self_mute
        except AttributeError:
            raise UserDisconnectedError(user.name)

    async def remove_role(self, user: int | str | User, group_: int | str | Chat | Message, role: int | str | Role):
        user = await self.get_user(user, group_)
        role = await self.find_role(role, group_)

        try:
            await user.original_object.remove_roles(role.original_object)
        except (AttributeError, discord.errors.NotFound):
            raise NotFoundError('role not found')

        try:
            user.roles.remove(role)
        except ValueError:
            pass
        else:
            user.save(('roles',))

    @parse_arguments
    async def send(
        self,
        text: str = None,
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
        async def file_too_large():
            if random.randint(0, 10):
                error_message = 'El archivo pesa más de 8 MB.'
            else:
                error_message = 'El archivo pesa mas que tu madre'
            await self._manage_exceptions(SendError(error_message), chat)

        text = self._parse_html_to_discord_markdown(text)
        try:
            file = await self._prepare_media_to_send(media)
        except LimitError:
            await file_too_large()
            return
        view = None

        if buttons:
            view = discord.ui.View(timeout=None)
            for i, row in enumerate(buttons):
                for button in row:
                    discord_button = discord.ui.Button(label=button.text, row=i)
                    discord_button.callback = self._on_button_press_raw
                    view.add_item(discord_button)

        if edit:
            kwargs = {}
            if text is not None:
                kwargs['content'] = text
            if file:
                kwargs['attachments'] = [file]
            if buttons is not None:
                kwargs['view'] = view
                message.buttons_info.buttons = buttons
            if buttons_key is not None:
                message.buttons_info.key = buttons_key

            try:
                message.original_object = await message.original_object.edit(**kwargs)
            except discord.errors.NotFound:
                return

            if data is None:
                if media is not None:
                    message.data['media'] = media.content
            else:
                if media is None:
                    message.data = data
                else:
                    message.data = {'media': media.content} | data

            message.update_last_edit()
            message.save()

            return message

        match reply_to:
            case int(message_id):
                reply_to = await chat.original_object.fetch_message(message_id)
            case str(message_id):
                reply_to = await chat.original_object.fetch_message(int(message_id))
            case self.Message() as message_to_reply:
                reply_to = message_to_reply.original_object

        try:
            bot_message = await self._get_message(await chat.original_object.send(text, file=file, view=view, reference=reply_to))
        except discord.errors.HTTPException as e:
            if 'too large' in str(e).lower():
                await file_too_large()
                return
            raise

        bot_message.buttons_info = ButtonsInfo(buttons=buttons, key=buttons_key)
        if media:
            bot_message.data['media'] = media.content
        if data:
            bot_message.data |= data

        bot_message.save()

        return bot_message

    def start(self):
        async def start_():
            await self.client.start(self.token)

        try:
            asyncio.get_running_loop()
            return start_()
        except RuntimeError:
            asyncio.run(start_())

    async def typing_delay(self, message: Message):
        async with message.chat.original_object.typing():
            await asyncio.sleep(random.randint(1, 3))
