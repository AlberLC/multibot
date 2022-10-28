from multibot.models.bot_action import *
from multibot.models.buttons import *
from multibot.models.chat import *
from multibot.models.enums import *
from multibot.models.event_component import *
from multibot.models.message import *
from multibot.models.penalties import *
from multibot.models.registered_callback import *
from multibot.models.role import *
from multibot.models.user import *

try:
    from models import *  # To use new classes if there are any in the current project
except ModuleNotFoundError:
    pass
