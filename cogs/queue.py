import discord
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
from discord_slash.utils.manage_commands import create_option

import config
from cogs.shared.add import add
from includes import msg, general
from models.queue_models import Queue as QueueEnum
from schemas import member_schema, queue_schema
import cogs.admin
from cogs.admin import check_admin


class Queue(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Queue Cog: Loaded")

    @cog_ext.cog_slash(
        name="add",
        description="Adds you to a queue",
        options=[
            create_option(
                name="queue",
                description="Choose a queue to add to",
                option_type=3,
                required=True,
                choices=config.queues(True)
            )
        ],
        guild_ids=config.variables['guild_ids']
    )
    async def _add(self, ctx: SlashContext, queue: str):
        user = ctx.author
        if not await general.correct_channel(ctx, user):
            return
        if await (check_admin(ctx) < 1 and config.variables['needs_access'] == 1):
            await msg.lacks_permission(ctx)
            return
        queue_enum = QueueEnum(queue)
        await add(ctx, self.bot, queue_enum)

    @cog_ext.cog_slash(
        name="del",
        description="Removes you from queue",
        options=[
            create_option(
                name="queue",
                description="Choose a queue to be removed from",
                option_type=3,
                required=True,
                choices=config.queues(False)
            )
        ],
        guild_ids=config.variables['guild_ids']
    )
    async def _del(self, ctx: SlashContext, queue: str):
        user = ctx.author
        if not await general.correct_channel(ctx, user):
            return
        queue_schema.remove_from_queue(user, queue)

        if queue != "all":
            await msg.removed_from_single_queue(ctx, self.bot, queue, queue_schema.get_queue_count(QueueEnum(queue)))
        else:
            await msg.removed_from_all_queues(ctx, self.bot, queue_schema.get_all_queue_counts())

    @cog_ext.cog_slash(
        name="status",
        description="Show the queue status",
        guild_ids=config.variables['guild_ids']
    )
    async def _status(self, ctx: SlashContext):
        user = ctx.author
        if not await general.correct_channel(ctx, user):
            return
        queues = [QueueEnum.QUICKPLAY.value]
        embed = discord.Embed(color=msg.success_color)
        for q in queues:
            is_live = queue_schema.queue_is_ingame(q)
            players = []
            for player in queue_schema.get_queue_players(q):
                games_played = member_schema.get_profile_by_id(player['userId'])['gamesPlayed']
                players.append(f"{config.variables['rank']} **`{games_played}`** **`{player['username'][:14]}`**")
            embed.add_field(
                name=f"{config.variables['live'] if is_live else ''}**{q.upper()}** **`[{queue_schema.get_queue_count(QueueEnum(q))}/10]`**",
                value="**`OPEN`**" if len(players) < 1 else '\n'.join(players))

        await ctx.send(embed=embed)


def setup(cog):
    cog.add_cog(Queue(cog))
