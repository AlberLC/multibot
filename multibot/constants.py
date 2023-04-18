import datetime
import os

import discord.ext.commands
import flanautils
import telethon.events.common
import twitchio

DISCORD_USER = discord.User | discord.Member | discord.ClientUser
DISCORD_CHAT = discord.abc.Messageable | discord.ext.commands.Context | discord.channel.DMChannel | discord.channel.GroupChannel | discord.Member | discord.channel.TextChannel | discord.abc.User
DISCORD_GROUP = discord.Guild
DISCORD_ROLE = discord.Role
DISCORD_MESSAGE = discord.Message
DISCORD_BUTTON_EVENT = discord.Interaction
DISCORD_NEW_MESSAGE_EVENT = DISCORD_MESSAGE
DISCORD_EVENT = DISCORD_BUTTON_EVENT | DISCORD_NEW_MESSAGE_EVENT

TELEGRAM_USER = telethon.types.User
TELEGRAM_CHAT = TELEGRAM_USER | telethon.types.Channel | telethon.types.Chat
TELEGRAM_GROUP = TELEGRAM_CHAT
TELEGRAM_MESSAGE = telethon.custom.Message
TELEGRAM_BUTTON_EVENT = telethon.events.CallbackQuery.Event
TELEGRAM_INLINE_EVENT = telethon.events.InlineQuery.Event
TELEGRAM_NEW_MESSAGE_EVENT = telethon.events.NewMessage.Event
TELEGRAM_EVENT = TELEGRAM_BUTTON_EVENT | TELEGRAM_INLINE_EVENT | TELEGRAM_NEW_MESSAGE_EVENT

TWITCH_USER = twitchio.Chatter | twitchio.User
TWITCH_CHAT = twitchio.Channel | twitchio.ChannelInfo
TWITCH_GROUP = TWITCH_CHAT
TWITCH_MESSAGE = twitchio.Message
TWITCH_NEW_MESSAGE_EVENT = TWITCH_MESSAGE
TWITCH_EVENT = TWITCH_NEW_MESSAGE_EVENT

ORIGINAL_USER = DISCORD_USER | TELEGRAM_USER | TWITCH_USER
ORIGINAL_CHAT = DISCORD_CHAT | TELEGRAM_CHAT | TWITCH_CHAT
ORIGINAL_GROUP = DISCORD_GROUP | TELEGRAM_GROUP | TWITCH_GROUP
ROLE = DISCORD_ROLE
ORIGINAL_MESSAGE = DISCORD_MESSAGE | TELEGRAM_MESSAGE | TWITCH_MESSAGE | TELEGRAM_INLINE_EVENT
MESSAGE_EVENT = DISCORD_EVENT | TELEGRAM_EVENT | TWITCH_EVENT | TELEGRAM_MESSAGE

BUTTONS_INFOS_EXPIRATION_TIME = datetime.timedelta(weeks=1)
CHECK_OLD_CACHE_MESSAGES_EVERY_SECONDS = datetime.timedelta(days=1).total_seconds()
CHECK_OLD_DATABASE_MESSAGES_EVERY_SECONDS = datetime.timedelta(days=1).total_seconds()
CHECK_PENALTIES_EVERY_SECONDS = datetime.timedelta(hours=1).total_seconds()
COMMAND_MESSAGE_DURATION = 5
DATABASE_MESSAGE_EXPIRATION_TIME = datetime.timedelta(weeks=flanautils.WEEKS_IN_A_MONTH)
DELETE_MESSAGE_LIMIT = 100
DISCORD_BUTTON_MAX_CHARACTERS = 80
DISCORD_BUTTONS_MAX = 5
DISCORD_COMMAND_PREFIX = flanautils.random_string()
DISCORD_MEDIA_MAX_BYTES = 25000000
ERROR_MESSAGE_DURATION = 10
MAX_FILE_EXTENSION_LENGHT = 5
PARSER_KEYWORDS_LENGHT_PENALTY = 0.001
PARSER_MAX_WORD_LENGTH = 25
PARSER_MIN_SCORE_DEFAULT = 0.93
PARSER_MIN_SCORE_TO_MATCH = 3
PARSER_SCORE_REWARD_EXPONENT = 2
PYMONGO_MEDIA_MAX_BYTES = 15000000
RAISE_AMBIGUITY_ERROR = False
SEND_EXCEPTION_MESSAGE_LINES = 0
TELEGRAM_BUTTONS_MAX_PER_LINE = 8
TELEGRAM_SEND_AS_FILE_MIN_SCORE = 0.85
TIME_THRESHOLD_TO_MANUAL_UNPUNISH = datetime.timedelta(days=3)

SAD_EMOJIS = '😥😪😓😔😕☹🙁😞😢😭😩😰'

EXCEPTION_PHRASES = ('A ver como lo digo...', 'Anda mira que error más bonito.', 'Ayudaaa',
                     'Bueeeno... esto es incómodo...',
                     'Con que querías que hiciera eso... pues esto es lo que he hecho:', 'Feliz Navidad:',
                     'Flanagan, ayuda!', 'Ha pasado esto:', 'Han pasado cosas.', 'He hecho pum',
                     'Iba a hacer eso peeero he hecho esto:', 'La cagué', 'La he cagao', 'Me fui a la puta',
                     'Me hice caca', 'Me rompí', 'No funciono', 'No me siento muy bien...', 'Pues me he roto',
                     'Pues no ha salido muy bien la cosa', 'Todo iba bien hasta que dejó de ir bien', 'Toma error',
                     'me rompido')

GIF_DOMAINS = ('Gfycat', 'Gifbin', 'Giphy', 'Imgur', 'ReactionGifs', 'Tenor')

INTERROGATION_PHRASES = ('?', 'que?', 'que dise', 'no entiendo', 'no entender', 'mi no entender', 'ein?', '🤔', '🤨',
                         '🧐', '🙄', '🙃')

KEYWORDS = {
    'activate': ('abre', 'activa', 'activar', 'activate', 'add', 'añade', 'añadir', 'dale', 'deja', 'dejale',
                 'devuelve', 'devuelvele', 'enable', 'encender', 'enciende', 'habilita', 'habilitar', 'open',
                 'permite', 'return'),
    'all': ('all', 'complete', 'completo', 'entero', 'full', 'toda', 'todas', 'todo', 'todos'),
    'audio': ('audio', 'music', 'musica', 'sonido', 'sound'),
    'audit': ('audit', 'auditoria', 'desconectado', 'disconnect', 'log', 'move', 'mover', 'movido', 'registro'),
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
    'deactivate': ('apaga', 'apagar', 'cancel', 'cancela', 'cierra', 'close', 'deactivate', 'deactivate', 'desactivar',
                   'deshabilita', 'deshabilitar', 'disable', 'forbids', 'prohibe', 'quita', 'remove'),
    'delete': ('borra', 'borrado', 'borres', 'clear', 'delete', 'elimina', 'limpia', 'remove'),
    'hello': ('alo', 'aloh', 'buenas', 'dias', 'hello', 'hey', 'hi', 'hola', 'holaaaaaa', 'ola', 'saludos', 'tardes'),
    'help': ('ayuda', 'help'),
    'last': ('last', 'ultima', 'ultimas', 'ultimo', 'ultimos'),
    'message': ('comentario', 'comment', 'mensaje', 'mensajes', 'message', 'messages', 'original'),
    'mute': ('calla', 'calle', 'mute', 'mutea', 'mutealo', 'noise', 'ruido', 'shut', 'silence', 'silencia'),
    'negate': ('no', 'ocurra', 'ocurre'),
    'permission': ('permiso', 'permission'),
    'reset': ('recover', 'recovery', 'recupera', 'reinicia', 'reset', 'resetea', 'restart'),
    'role': ('rol', 'role', 'roles'),
    'send_as_file': ('arhivo', 'calidad', 'compresion', 'compress', 'compression', 'comprimir', 'file', 'quality'),
    'show': ('actual', 'enseña', 'estado', 'how', 'muestra', 'show', 'como'),
    'simple': ('sencillo', 'simple'),
    'sound': ('hablar', 'hable', 'micro', 'microfono', 'microphone', 'sonido', 'sound', 'talk', 'volumen'),
    'stop': ('acabar', 'caducar', 'detener', 'end', 'expirar', 'expire', 'finalizar', 'finish', 'parar', 'stop',
             'suspend', 'suspender', 'terminar', 'terminate'),
    'thanks': ('gracia', 'gracias', 'grasia', 'grasias', 'grax', 'thank', 'thanks', 'ty'),
    'unban': ('desbanea', 'unban'),
    'unmute': ('desilencia', 'desmutea', 'desmutealo', 'unmute'),
    'user': ('member', 'miembro', 'participant', 'participante', 'user', 'usuario')
}

NO_PHRASES = ('NO', 'no', 'no.', 'nope', 'hin', 'ahora mismo', 'va a ser que no', 'claro que si', 'claro que si guapi',
              'no me da la gana', 'y si no?', 'paso', 'pasando', 'ahora despues', 'ahora en un rato', 'tiene pinta')

OUT_OF_SERVICES_PHRASES = ('Estoy fuera de servicio.', 'Estoy fuera de servicio.', 'No estoy disponible :(',
                           'Que estoy fuera de servicioooo', 'ahora mismo no puedo', 'dehame', 'estoy indispuesto',
                           'estoy malito, me están arreglando', 'https://www.youtube.com/watch?v=4KfpmQBqNZY',
                           'no estoy bien', 'no funciono', 'no me encuentro muy bien..', *SAD_EMOJIS)


def load_environment():
    global SEND_EXCEPTION_MESSAGE_LINES

    SEND_EXCEPTION_MESSAGE_LINES = int(os.environ.get('SEND_EXCEPTION_MESSAGE_LINES', 0))
