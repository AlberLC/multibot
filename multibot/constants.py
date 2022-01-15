import datetime

import discord.ext.commands
import telethon.events.common
import twitchio

DISCORD_CHAT = discord.abc.Messageable | discord.ext.commands.Context | discord.channel.DMChannel | discord.channel.GroupChannel | discord.Member | discord.channel.TextChannel | discord.abc.User
DISCORD_MESSAGE = discord.Message
DISCORD_USER = discord.User | discord.Member
DISCORD_EVENT = DISCORD_MESSAGE

TELEGRAM_CHAT = telethon.types.Channel | telethon.types.Chat
TELEGRAM_MESSAGE = telethon.custom.Message
TELEGRAM_USER = telethon.types.User
TELEGRAM_EVENT = telethon.events.common.EventCommon | telethon.events.common.EventBuilder

TWITCH_CHAT = twitchio.Channel
TWITCH_MESSAGE = twitchio.Message
TWITCH_USER = twitchio.Chatter | twitchio.User
TWITCH_EVENT = TWITCH_MESSAGE

ORIGINAL_CHAT = DISCORD_CHAT | TELEGRAM_CHAT | TWITCH_CHAT
ORIGINAL_MESSAGE = DISCORD_MESSAGE | TELEGRAM_MESSAGE | TWITCH_MESSAGE
ORIGINAL_USER = DISCORD_USER | TELEGRAM_USER | TWITCH_USER
MESSAGE_EVENT = DISCORD_EVENT | TELEGRAM_EVENT | TWITCH_EVENT | TELEGRAM_MESSAGE

RAISE_AMBIGUITY_ERROR = False
COMMAND_MESSAGE_DURATION = 5
DISCORD_COMMAND_PREFIX = '/'
DISCORD_MEDIA_MAX_BYTES = 8000000
ERROR_MESSAGE_DURATION = 10
KEYWORDS_LENGHT_PENALTY = 0.001
MAX_FILE_EXTENSION_LENGHT = 5
MESSAGE_EXPIRATION_TIME = datetime.timedelta(weeks=1)
MINIMUM_RATIO_TO_MATCH = 3
PARSE_CALLBACKS_MIN_RATIO_DEFAULT = 0.8
RATIO_REWARD_EXPONENT = 2
TELEGRAM_DELETE_MESSAGE_LIMIT = 100

SAD_EMOJIS = '😥😪😓😔😕☹🙁😞😢😭😩😰'

INTERROGATION_PHRASES = ('?', 'que?', 'que dise', 'no entiendo', 'no entender', 'mi no entender', 'ein?', '🤔', '🤨',
                         '🧐', '🙄', '🙃')

KEYWORDS = {
    'ban': ('ban', 'banea', 'banealo'),
    'delete': ('borra', 'borrado', 'borres', 'clear', 'delete', 'elimina', 'limpia', 'remove'),
    'message': ('mensaje', 'message', 'original'),
    'send_as_file': ('arhivo', 'calidad', 'compress', 'compression', 'comprimir', 'file', 'quality'),
    'unban': ('desbanea', 'unban'),
}

NO_PHRASES = ('NO', 'no', 'no.', 'nope', 'hin', 'ahora mismo', 'va a ser que no', 'claro que si', 'claro que si guapi',
              'no me da la gana', 'y si no?', 'paso', 'pasando', 'ahora despues', 'ahora en un rato', 'tiene pinta')

OUT_OF_SERVICES_PHRASES = ('Estoy fuera de servicio.', 'Estoy fuera de servicio.', 'No estoy disponible :(',
                           'Que estoy fuera de servicioooo', 'ahora mismo no puedo', 'dehame', 'estoy indispuesto',
                           'estoy malito, me están arreglando', 'https://www.youtube.com/watch?v=4KfpmQBqNZY',
                           'no estoy bien', 'no funciono', 'no me encuentro muy bien..', *SAD_EMOJIS)
