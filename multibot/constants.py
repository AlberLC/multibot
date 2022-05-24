import datetime

import discord.ext.commands
import telethon.events.common
import twitchio

DISCORD_CHAT = discord.abc.Messageable | discord.ext.commands.Context | discord.channel.DMChannel | discord.channel.GroupChannel | discord.Member | discord.channel.TextChannel | discord.abc.User
DISCORD_MESSAGE = discord.Message
DISCORD_USER = discord.User | discord.Member | discord.ClientUser
DISCORD_EVENT = DISCORD_MESSAGE | discord.Interaction
DISCORD_ROLE = discord.Role

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

ROLE = DISCORD_ROLE

CHECK_MESSAGE_EVERY_SECONDS = datetime.timedelta(days=1).total_seconds()
CHECK_MUTES_EVERY_SECONDS = datetime.timedelta(hours=1).total_seconds()
COMMAND_MESSAGE_DURATION = 5
DISCORD_COMMAND_PREFIX = '/'
DISCORD_MEDIA_MAX_BYTES = 8000000
ERROR_MESSAGE_DURATION = 10
KEYWORDS_LENGHT_PENALTY = 0.001
MAX_FILE_EXTENSION_LENGHT = 5
MESSAGE_EXPIRATION_TIME = datetime.timedelta(weeks=1)
MINIMUM_RATIO_TO_MATCH = 3
PARSE_CALLBACKS_MIN_RATIO_DEFAULT = 0.93
RAISE_AMBIGUITY_ERROR = False
RATIO_REWARD_EXPONENT = 2
DELETE_MESSAGE_LIMIT = 100
TELEGRAM_SEND_AS_FILE_RATIO_MIN_RATIO = 0.85
TIME_THRESHOLD_TO_MANUAL_UNMUTE = datetime.timedelta(days=3)

SAD_EMOJIS = '😥😪😓😔😕☹🙁😞😢😭😩😰'

INTERROGATION_PHRASES = ('?', 'que?', 'que dise', 'no entiendo', 'no entender', 'mi no entender', 'ein?', '🤔', '🤨',
                         '🧐', '🙄', '🙃')

KEYWORDS = {
    'activate': ('activa', 'activar', 'activate', 'deja', 'dejale', 'devuelve', 'devuelvele', 'enable', 'encender',
                 'enciende', 'habilita', 'habilitar'),
    'ban': ('ban', 'banea', 'banealo'),
    'bye': ('adieu', 'adio', 'adiooooo', 'adios', 'agur', 'buenas', 'bye', 'cama', 'chao', 'farewell', 'goodbye',
            'hasta', 'luego', 'noches', 'pronto', 'taluego', 'taluegorl', 'tenga', 'vemos', 'vista', 'voy'),
    'change': ('alter', 'alternar', 'alternate', 'cambiar', 'change', 'default', 'defecto', 'edit', 'editar',
               'exchange', 'modificar', 'modify', 'permutar', 'predeterminado', 'shift', 'swap', 'switch', 'turn',
               'vary'),
    'config': ('ajustar', 'ajuste', 'ajustes', 'automatico', 'automatic', 'config', 'configs', 'configuracion',
               'configuration', 'default', 'defecto', 'setting', 'settings'),
    'date': ('ayer', 'de', 'domingo', 'fin', 'finde', 'friday', 'hoy', 'jueves', 'lunes', 'martes', 'mañana',
             'miercoles', 'monday', 'pasado', 'sabado', 'saturday', 'semana', 'sunday', 'thursday', 'today', 'tomorrow',
             'tuesday', 'viernes', 'wednesday', 'week', 'weekend', 'yesterday'),
    'deactivate': ('apaga', 'apagar', 'deactivate', 'deactivate', 'desactivar', 'deshabilita', 'deshabilitar',
                   'disable', 'forbids', 'prohibe', 'quita', 'remove', 'return'),
    'delete': ('borra', 'borrado', 'borres', 'clear', 'delete', 'elimina', 'limpia', 'remove'),
    'hello': ('alo', 'aloh', 'buenas', 'dias', 'hello', 'hey', 'hi', 'hola', 'holaaaaaa', 'ola', 'saludos', 'tardes'),
    'help': ('ayuda', 'help'),
    'message': ('mensaje', 'message', 'original'),
    'mute': ('calla', 'calle', 'cierra', 'close', 'mute', 'mutea', 'mutealo', 'noise', 'ruido', 'shut', 'silence',
             'silencia'),
    'negate': ('no', 'ocurra', 'ocurre'),
    'permission': ('permiso', 'permission'),
    'reset': ('recover', 'recovery', 'recupera', 'reinicia', 'reset', 'resetea', 'restart'),
    'send_as_file': ('arhivo', 'calidad', 'compress', 'compression', 'comprimir', 'file', 'quality'),
    'show': ('actual', 'enseña', 'estado', 'how', 'muestra', 'show', 'como'),
    'sound': ('hablar', 'hable', 'micro', 'microfono', 'microphone', 'sonido', 'sound', 'talk', 'volumen'),
    'thanks': ('gracia', 'gracias', 'grasia', 'grasias', 'grax', 'thank', 'thanks', 'ty'),
    'unban': ('desbanea', 'unban'),
    'unmute': ('desilencia', 'desmutea', 'desmutealo', 'unmute'),
}

NO_PHRASES = ('NO', 'no', 'no.', 'nope', 'hin', 'ahora mismo', 'va a ser que no', 'claro que si', 'claro que si guapi',
              'no me da la gana', 'y si no?', 'paso', 'pasando', 'ahora despues', 'ahora en un rato', 'tiene pinta')

OUT_OF_SERVICES_PHRASES = ('Estoy fuera de servicio.', 'Estoy fuera de servicio.', 'No estoy disponible :(',
                           'Que estoy fuera de servicioooo', 'ahora mismo no puedo', 'dehame', 'estoy indispuesto',
                           'estoy malito, me están arreglando', 'https://www.youtube.com/watch?v=4KfpmQBqNZY',
                           'no estoy bien', 'no funciono', 'no me encuentro muy bien..', *SAD_EMOJIS)
