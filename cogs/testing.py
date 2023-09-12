from discord.ext import commands
from discord_slash import cog_ext
from discord_slash.context import SlashContext
from discord_slash.utils.manage_commands import create_option, create_choice

import config
from includes import msg
from schemas import testing_schema, ingame_schema
from services import game_service


class Testing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Cog Testing: Loaded")


def setup(bot):
    bot.add_cog(Testing(bot))
