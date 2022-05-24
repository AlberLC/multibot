MultiBot
========

|license| |project_version| |python_version|

Platform agnostic high-level bot infrastructure. Develop one bot and you will have three: one for Discord, another one for Telegram and another one for Twitch. All bots use the same objects and logic.

For now there are adapters for three platforms but more may be added in the future.

|

Installation
------------

Python 3.10 or higher is required.

.. code-block::

    pip install multibot

|

Quick start
-----------

Discord
~~~~~~~

You will need create an discord application at https://discord.com/developers/applications and generate a **BOT_TOKEN** for your bot.


You will have to select the **bot** and **applications.commands** scopes and the **Administrator** permission. And as for the Discord Intents (in the Bot/Build-A-Bot panel) you must activate **PRESENCE INTENT**, **SERVER MEMBERS INTENT** and **MESSAGE CONTENT INTENT**.

.. code-block:: python

    import os

    from multibot import DiscordBot, Message

    discord_bot = DiscordBot(os.environ['DISCORD_BOT_TOKEN'])


    @discord_bot.register('hello')
    async def function_name_1(message: Message):
        await discord_bot.send('Hi!', message)


    discord_bot.start()

|

Telegram
~~~~~~~~

You will need your own **API_ID** and **API_HASH**. To get them see `Native Telegram app & MTProto configuration`_.

.. code-block:: python

    import os

    from multibot import Message, TelegramBot

    telegram_bot = TelegramBot(
        api_id=os.environ['TELEGRAM_API_ID'],
        api_hash=os.environ['TELEGRAM_API_HASH'],
        bot_token=os.environ['TELEGRAM_BOT_TOKEN']
    )


    @telegram_bot.register('hello')
    async def function_name_1(message: Message):
        await telegram_bot.send('Hi!', message)


    telegram_bot.start()

The session will be saved locally using SQLite.

|

You can save the session data in a string (string session). This serves to facilitate the use of sessions when hosting the application in cloud services with ephemeral file systems:

.. code-block:: python

    from telethon.sessions import StringSession

    ...
    string_session = StringSession.save(telegram_bot.bot_client.session)

|

If you have a string session you can provide it instead of the bot token:

.. code-block:: python

    telegram_bot = TelegramBot(
        api_id=os.environ['TELEGRAM_API_ID'],
        api_hash=os.environ['TELEGRAM_API_HASH'],
        bot_session=os.environ['TELEGRAM_BOT_SESSION']  # <----- instead of bot_token
    )

|

Adding an user bot
..................

You can add a user bot to your telegram bot to extend certain functionalities such as accessing the message history (useful if you have not been registering the messages in a database or similar), accessing the user's contacts to make whitelists, etc.

.. code-block:: python

    telegram_bot = TelegramBot(
        api_id=os.environ['TELEGRAM_API_ID'],
        api_hash=os.environ['TELEGRAM_API_HASH'],
        bot_session=os.environ['TELEGRAM_BOT_SESSION'],
        phone='+00123456789'
    )

|

Or provide an user string session instead of phone:

.. code-block:: python

    telegram_bot = TelegramBot(
        api_id=os.environ['TELEGRAM_API_ID'],
        api_hash=os.environ['TELEGRAM_API_HASH'],
        bot_session=os.environ['TELEGRAM_BOT_SESSION'],
        user_session=os.environ['TELEGRAM_USER_SESSION'],
    )

|

Twitch
~~~~~~

You will need your own **BOT_TOKEN** which you can generate on: https://twitchapps.com/tmi/. For more information see https://dev.twitch.tv/docs/irc.

.. code-block:: python

    import os

    from multibot import Message, TwitchBot

    twitch_bot = TwitchBot(
        bot_token=os.environ['TWITCH_ACCESS_TOKEN'],
        initial_channels=['channel_name'],  # Optional. You can later make the bot join a chat with join() method
        owner_name='owner_name'  # Optional. So the bot knows who to respect. Although keep in mind that the streamer cannot be punished
    )


    @twitch_bot.register('hello')
    async def function_name_1(message: Message):
        await twitch_bot.send('Hi!', message)


    twitch_bot.start()

|

Run multiple bots
-----------------

.. code-block:: python

    import asyncio
    import os

    from multibot import DiscordBot, TelegramBot, TwitchBot


    async def main():
        discord_bot = DiscordBot(os.environ['DISCORD_BOT_TOKEN'])

        telegram_bot = TelegramBot(
            api_id=os.environ['TELEGRAM_API_ID'],
            api_hash=os.environ['TELEGRAM_API_HASH'],
            bot_token=os.environ['TELEGRAM_BOT_TOKEN']
        )

        # If you run a TwitchBot in an asyncio loop you must create it inside the loop like below.
        # Other bots like DiscordBot or TelegramBot don't have this need and can be created at the module level.
        twitch_bot = TwitchBot(
            bot_token=os.environ['TWITCH_ACCESS_TOKEN'],
            initial_channels=['channel_name'],
            owner_name='owner_name'
        )

        await asyncio.gather(
            discord_bot.start(),
            telegram_bot.start(),
            twitch_bot.start()
        )


    asyncio.run(main())

|

Extended tutorial
-----------------

How the bot works
~~~~~~~~~~~~~~~~~

The bot works by registering functions that will be executed later when the user provides an input message that meets the requirements specified in the arguments of :code:`Multibot.register()`.

Each function you have registered in the bot will receive a :code:`Message` object that contains all the necessary information related to the context of said message.

|multiBot_class_diagram|

|

Ways to design your bot
~~~~~~~~~~~~~~~~~~~~~~~

For the examples we are going to use the TelegramBot. But remember that all bots work the same since they use the same objects and logic. "They speak the same language".

A) Simple form
..............

.. code-block:: python

    import os
    import random

    import flanautils
    from multibot import Message, TelegramBot

    bot = TelegramBot(
        api_id=os.environ['TELEGRAM_API_ID'],
        api_hash=os.environ['TELEGRAM_API_HASH'],
        bot_token=os.environ['TELEGRAM_BOT_TOKEN']
    )

    @bot.register('hello')
    async def function_name_1(message: Message):
        """
        This function will be executed when someone types something like "hello".

        Functions names are irrelevant.
        """

        await bot.send('Hi!', message)  # response in same chat of received message context


    @bot.register('multibot', min_ratio=1)
    async def function_name_2(message: Message):
        """
        This function will be executed when someone types exactly "multibot".

        min_ratio=0.93 by default.
        """

        await bot.delete_message(message)  # deletes the received message
        bot_message = await bot.send('Message deleted.', message)  # keep the response message

        await flanautils.do_later(10, bot.delete_message, bot_message)  # delete the response message after 10 seconds


    @bot.register(('house', 'home'))
    # @bot.register(['house', 'home'])  <-- same
    # @bot.register('house home')       <-- same
    async def function_name_3(message: Message):
        """This function will be executed when someone types "house" or/and "home"."""

        await bot.clear(5, message)  # delete last 5 message (only works if a user_bot is activated in current chat)


    @bot.register((('hello', 'hi'), ('world',)))  # <-- note that is Iterable[Iterable[str]]
    # @bot.register([('hello', 'hi'), ('world',)])  <-- same
    # @bot.register(['hello hi', ['world']])        <-- same
    # @bot.register(['hello hi', 'world'])          !!! NOT same, this is "or" logic (like previous case)
    async def function_name_4(message: Message):
        """This function will be executed when someone types ("hello" or/and "hi") and "world"."""

        message.chat = await bot.get_chat('@user_name')  # get chat object from id or user_name and insert it to message context
        await bot.send('I <3 to kill you.', message)


    @bot.register('troll')
    async def function_name_5(message: Message):
        """This function will be executed when someone types "troll" but returns if he isn't an admin."""

        if not message.author.is_admin:
            return

        await bot.ban('@user_name', message)


    @bot.register(always=True)
    async def function_name_6(message: Message):
        """This function will be executed always but returns if bot isn't mentioned."""

        if not bot.is_bot_mentioned(message):
            return

        await bot.send('shut up.', message)


    @bot.register(default=True)
    async def function_name_7(message: Message):
        """
        This function will be executed if no other function is determined by provided keywords.

        always=True functions don't affect to determine if default=True functions are called.
        """

        phrases = ["I don't understand u mate", '?', '???????']
        await bot.send(random.choice(phrases), message)


    bot.start()

|

B) Extensible form
..................

.. code-block:: python

    import os
    import random

    import flanautils
    from multibot import Message, TelegramBot, admin, bot_mentioned


    class MyBot(TelegramBot):
        def __init__(self):
            super().__init__(api_id=os.environ['TELEGRAM_API_ID'],
                             api_hash=os.environ['TELEGRAM_API_HASH'],
                             bot_token=os.environ['TELEGRAM_BOT_TOKEN'])

        def _add_handlers(self):
            super()._add_handlers()
            self.register(self.function_name_1, 'hello')
            self.register(self.function_name_2, 'multibot', min_ratio=1)
            self.register(self.function_name_3, ('house', 'home'))
            self.register(self.function_name_4, (('hello', 'hi'), ('world',)))  # <-- note that is Iterable[Iterable[str]]
            self.register(self.function_name_5, 'troll')
            self.register(self.function_name_6, always=True)
            self.register(self.function_name_7, default=True)

        async def function_name_1(self, message: Message):
            """
            This function will be executed when someone types something like "hello".

            Functions names are irrelevant.
            """

            await self.send('Hi!', message)  # response in same chat of received message context

        async def function_name_2(self, message: Message):
            """
            This function will be executed when someone types exactly "multibot".

            min_ratio=0.93 by default.
            """

            await self.delete_message(message)  # deletes the received message
            bot_message = await self.send('Message deleted.', message)  # keep the response message

            await flanautils.do_later(10, self.delete_message, bot_message)  # delete the response message after 10 seconds

        async def function_name_3(self, message: Message):
            """This function will be executed when someone types "house" or/and "home"."""

            await self.clear(5, message)  # delete last 5 message (only works if a user_bot is activated in current chat)

        async def function_name_4(self, message: Message):
            """This function will be executed when someone types ("hello" or/and "hi") and "world"."""

            message.chat = await self.get_chat('@user_name')  # get chat object from id or user_name and insert it to message context
            await self.send('I <3 to kill you.', message)

        @admin
        async def function_name_5(self, message: Message):
            """This function will be executed when someone types "troll" but returns if he isn't an admin."""

            await self.ban('@user_name', message)

        @bot_mentioned
        async def function_name_6(self, message: Message):
            """This function will be executed always but returns if bot isn't mentioned."""

            await self.send('shut up.', message)

        async def function_name_7(self, message: Message):
            """
            This function will be executed if no other function is determined by provided keywords.

            always=True functions don't affect to determine if default=True functions are called.
            """

            phrases = ["I don't understand u mate", '?', '???????']
            await self.send(random.choice(phrases), message)


    MyBot().start()

|

Annex
-----

Native Telegram app & MTProto configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

TelegramBot connects directly to Telegram servers using its own protocol (MTProto), so you are not limited by the http bots api. Anything you can do with the official mobile app, desktop or web is possible with this bot.

MTProto also allows the creation of user bots, bots that automate tasks with your own human account for which you would need to create a new session as when you open a session for the first time on a new device. Keep in mind that you will be asked for the security code that Telegram sends you by private chat when someone wants to log in with your account.

For both a normal bot and a user bot (bot using your "human" account) you will need the **API_ID** and **API_HASH**. To get them you will have to go to https://my.telegram.org, log in and create an app.

    **WARNING!**
        The **my.telegram.org** security code is **NOT** like a session code, do not give it to anyone, it is only to enter this website. If you have doubts: the code that :code:`MultiBot.TelegramBot` may ask you for is **NOT** the same. :code:`MultiBot.TelegramBot` would only need a different code in case of a new session when you run it for the first time.

|my.telegram.org_app|


.. |license| image:: https://img.shields.io/github/license/AlberLC/multibot?style=flat
    :target: https://github.com/AlberLC/multibot/blob/main/LICENSE
    :alt: License

.. |project_version| image:: https://img.shields.io/pypi/v/multibot
    :target: https://pypi.org/project/multibot/
    :alt: PyPI

.. |python_version| image:: https://img.shields.io/pypi/pyversions/multibot
    :target: https://www.python.org/downloads/
    :alt: PyPI - Python Version

.. |multiBot_class_diagram| image:: https://user-images.githubusercontent.com/37489786/170136350-fb04ecb1-02c7-4f1e-923a-b51b88980f91.png
    :alt: multiBot_class_diagram

.. |my.telegram.org_app| image:: https://user-images.githubusercontent.com/37489786/149607226-36b0e3d6-6e21-4852-a08f-16ce52d3a7dc.png
    :target: https://my.telegram.org/
    :alt: my.telegram.org