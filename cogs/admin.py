import discord
from discord.ext import commands
from discord_slash import cog_ext
from discord_slash.context import SlashContext
from discord_slash.model import SlashCommandPermissionType
from discord_slash.utils.manage_commands import create_option, create_choice
from discord_slash.utils.manage_commands import create_permission

import config
from includes import general, msg
from includes.general import admin_channel
from schemas import ingame_schema, member_schema
from services import game_service


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Cog Admin: Loaded")

    @cog_ext.cog_slash(
        name="warn",
        description="Warn a player",
        options=[
            create_option(
                name="member",
                description="Choose a member",
                required=True,
                option_type=6
            ),
            create_option(
                name="message",
                description="Message to member",
                required=True,
                option_type=3
            )
        ],
        guild_ids=config.variables['guild_ids']
    )
    async def _warn(self, ctx: SlashContext, member: discord.Member, message: str):
        if not await general.admin_channel(ctx, ctx.author):
            return
        if await check_admin(ctx) < 2:
            await msg.lacks_permission(ctx)
            return
        # get warnings
        warnings = member_schema.get_number_of_warnings(member)
        if warnings == 2:
            # ban player
            member_schema.ban_player(ctx.author, member)
            member_schema.remove_warnings(member)
            body = f"""
                You have been **banned**.

                **Admin:** **`{ctx.author.name}`**
                **Message:** `{message}`
            """
            embed = discord.Embed(title="Banned", description=body, color=msg.accent_color)
            try:
                await member.send(embed=embed)
            except Exception as e:
                print(e)

            body = f"""
                **{member.name}** has been banned for too many warnings.

                **Admin:** **`{ctx.author.name}`**
                **Last warning message:** `{message}`
            """
            embed = discord.Embed(title="Banned", description=body, color=msg.error_color)
            embed.set_author(name=member.name, icon_url=member.avatar_url)
            await ctx.send(embed=embed, hidden=True)
        else:
            # warn player
            member_schema.warn_player(ctx.author, member)
            warnings = member_schema.get_number_of_warnings(member)
            body = f"""
                You have been **warned**.

                **Admin:** **`{ctx.author.name}`**
                **Message:** `{message}`
            """
            embed = discord.Embed(title="Warned", description=body, color=0xffb300)
            try:
                await member.send(embed=embed)
            except Exception as e:
                print(e)
            body = f"""
                **Total Warnings**: **`{warnings}/3`**
                **Admin**: **`{ctx.author.name}`**
                **Message:** **`{message}`**
            """
            embed = discord.Embed(title="Warning", description=body, color=0xffb300)
            embed.set_author(name=member.name, icon_url=member.avatar_url)
            await ctx.send(embed=embed, hidden=True)

    @cog_ext.cog_slash(
        name="banplayer",
        description="Bans player: only admins can do this",
        options=[
            create_option(
                name="member",
                description="Choose a member",
                required=True,
                option_type=6
            ),
            create_option(
                name="message",
                description="Message to member",
                required=True,
                option_type=3
            )
        ],
        guild_ids=config.variables['guild_ids']
    )
    async def _banplayer(self, ctx: SlashContext, member: discord.Member, message: str):
        if not await general.admin_channel(ctx, ctx.author):
            return
        if await check_admin(ctx) < 3:
            await msg.lacks_permission(ctx)
            return
        if member_schema.is_banned(member):
            await ctx.send(f"**{member.name}** is already banned.", hidden=True)
        else:
            member_schema.ban_player(ctx.author, member)
            body = f"""
                You have been **banned**.

                **Admin:** **`{ctx.author.name}`**
                **Message:** `{message}`
            """
            embed = discord.Embed(title="Banned", description=body, color=msg.accent_color)
            try:
                await member.send(embed=embed)
            except Exception as e:
                print(e)

            body = f"""
                **{member.name}** has been banned for too many warnings.

                **Admin:** **`{ctx.author.name}`**
                **Message:** `{message}`
            """
            embed = discord.Embed(title="Banned", description=body, color=msg.error_color)
            embed.set_author(name=member.name, icon_url=member.avatar_url)
            await ctx.send(embed=embed, hidden=True)

    @cog_ext.cog_slash(
        name="revokeban",
        description="Unbans player: only admins can do this",
        options=[
            create_option(
                name="member",
                description="Choose a member",
                required=True,
                option_type=6
            )
        ],
        guild_ids=config.variables['guild_ids']
    )
    async def _revokeban(self, ctx: SlashContext, member: discord.Member):
        if not await general.admin_channel(ctx, ctx.author):
            return
        if await check_admin(ctx) < 3:
            await msg.lacks_permission(ctx)
            return
        if member_schema.is_banned(member):
            member_schema.unban_player(member)
            body = f"""
                Your ban has been **revoked**.

                **Revoke by:** **`{ctx.author.name}`**
            """
            embed = discord.Embed(title="Ban Revoked", description=body, color=msg.success_color)
            try:
                await member.send(embed=embed)
            except Exception as e:
                print(e)
            warnings = member_schema.get_number_of_warnings(member)

            body = f"""
                **{member.name}**'s ban has been **revoked**.

                **Admin:** **`{ctx.author.name}`**
            """
            embed = discord.Embed(title="Ban Revoked", description=body, color=msg.success_color)
            embed.set_author(name=member.name, icon_url=member.avatar_url)
            await ctx.send(embed=embed, hidden=True)
        else:
            await ctx.send(f"**{member.name}** is not banned", hidden=True)

    @cog_ext.cog_slash(
        name="cancel",
        description="Cancel game",
        options=[
            create_option(
                name="member",
                description="Select a player from game",
                required=True,
                option_type=6
            )
        ],
        guild_ids=config.variables['guild_ids']
    )
    async def _cancel(self, ctx: SlashContext, member: discord.Member):
        if not await general.correct_channel(ctx, ctx.author):
            return
        if await check_admin(ctx) < 2:
            await msg.lacks_permission(ctx)
            return
        if ingame_schema.is_ingame(member):
            ingame_schema.cancel_game(member)
            try:
                return await msg.cancel_game_message(ctx, ctx.author)
            except Exception as e:
                print(e)
        else:
            await ctx.send(f"{member.name} isn't ingame.", hidden=True)

    @cog_ext.cog_slash(
        name="shutdown",
        description="Shuts down the bot (Admin only)",
        guild_ids=config.variables['guild_ids']
    )
    async def _shutdown(self, ctx: SlashContext):
        user = ctx.author
        if not await general.correct_channel(ctx, user):
            return
        if await check_admin(ctx) < 3:
            await msg.lacks_permission(ctx)
            return
        embed = discord.Embed(description="Okay, **goodnight!** :heartpulse:")
        await ctx.send(embed=embed, hidden=True)

    @cog_ext.cog_slash(
        name="remove",
        description="Remove player from queue",
        options=[
            create_option(
                name="member",
                description="Type member name",
                required=True,
                option_type=3
            )
        ],
        guild_ids=config.variables['guild_ids'],
    )
    async def _remove(self, ctx: SlashContext, member: str):
        user = ctx.author
        if not await general.correct_channel(ctx, user):
            return
        if await check_admin(ctx) < 2:
            await msg.lacks_permission(ctx)
            return
        if ingame_schema.raw_member_inqueue(member):
            ingame_schema.remove_raw_member_from_queue(member)
            await msg.force_remove_from_queue(ctx, user, member)
        else:
            await ctx.send(f"{member} isn't in queue", hidden=True)

    @cog_ext.cog_slash(
        name="history",
        description="Show game history",
        guild_ids=config.variables['guild_ids'],
    )
    async def _history(self, ctx: SlashContext):
        if not await admin_channel(ctx, ctx.author):
            return
        if await check_admin(ctx) < 1:
            await msg.lacks_permission(ctx)
            return
        history = game_service.get_history()
        await msg.show_history(ctx, history)

    @cog_ext.cog_slash(
        name="removewarnings",
        description="Removes user warnings",
        options=[
            create_option(
                name="member",
                description="Select a member",
                required=True,
                option_type=6
            ),
            create_option(
                name="amount",
                description="Type amount",
                required=True,
                option_type=4,
                choices=[
                    create_choice(
                        name="1",
                        value=1
                    ),
                    create_choice(
                        name="2",
                        value=2
                    )
                ]
            ),
        ],
        guild_ids=config.variables['guild_ids']
    )
    async def _removewarnings(self, ctx: SlashContext, member: discord.Member, amount: int):
        if not await admin_channel(ctx, ctx.author):
            return
        if await check_admin(ctx) < 2:
            await msg.lacks_permission(ctx)
            return
        warnings = member_schema.get_number_of_warnings(member)
        if warnings < 1:
            return await ctx.send(f"**{member.name}** has no warnings or is banned.", hidden=True)
        updated_warnings = member_schema.remove_single_warnings(member, warnings, amount)

        body = f"""
            Your warning(s) has been **removed**.

            **Admin:** **`{ctx.author.name}`**
            **Warnings Removed:** **`{amount}`**
            **Remaining Warnings:** `{updated_warnings}`
        """
        embed = discord.Embed(title="Warning(s) Removed", description=body, color=msg.success_color)
        try:
            await member.send(embed=embed)
        except Exception as e:
            print(e)

        body = f"""
            Warning(s) removed from **{member.name}**.

            **Admin:** **`{ctx.author.name}`**
            **Warnings Removed:** **`{amount}`**
            **Remaining Warnings:** `{updated_warnings}`
        """
        embed = discord.Embed(title="Removed Warning(s)", description=body, color=msg.success_color)
        embed.set_author(name=member.name, icon_url=member.avatar_url)

        await ctx.send(embed=embed, hidden=True)

    @cog_ext.cog_slash(
        name="moderation",
        description="Shows banned players and warnings",
        options=[
            create_option(
                name="category",
                description="View either banned or warnings",
                required=True,
                option_type=3,
                choices=[
                    create_choice(
                        name="banned",
                        value="banned"
                    ),
                    create_choice(
                        name="warned",
                        value="warned"
                    )
                ]
            )
        ],
        guild_ids=config.variables['guild_ids']
    )
    async def _moderation(self, ctx: SlashContext, category: str):
        if not await admin_channel(ctx, ctx.author):
            return
        if await check_admin(ctx) < 3:
            await msg.lacks_permission(ctx)
            return
        if category == "banned":
            banned_list = member_schema.get_all_banned()
            if banned_list.count() < 1:
                embed = discord.Embed(title="Banned", description="No one is **banned**.", color=msg.success_color)
                await ctx.send(embed=embed, hidden=True)
            else:
                body = ""
                for player in banned_list:
                    body = body + f"**Player Name**: **`{player['username']}`**\n**Player ID**: **`{player['userId']}`**\n**By**: **`{player['by']}`**\n\n"
                embed = discord.Embed(title="Banned", description=body, color=msg.error_color)
                await ctx.send(embed=embed, hidden=True)
        else:
            warning_list = member_schema.get_all_warned()
            if warning_list.count() < 1:
                embed = discord.Embed(title="Warned", description="No one has been **warned**.",
                                      color=msg.success_color)
                await ctx.send(embed=embed, hidden=True)
            else:
                body = ""
                for player in warning_list:
                    body = body + f"**Player Name**: **`{player['username']}`**\n**Player ID**: **`{player['userId']}`**\n**By**: **`{player['by']}`**\n\n"
                embed = discord.Embed(title="Warned", description=body, color=msg.error_color)
                await ctx.send(embed=embed, hidden=True)


async def check_admin(ctx: SlashContext) -> int:
    # check if user has admin role
    user = ctx.author
    permissions = 0
    role = discord.utils.get(ctx.guild.roles, id=config.variables['bittah_access_role'])
    if role in user.roles:
        permissions = 1

    role = discord.utils.get(ctx.guild.roles, id=config.variables['bittah_admin_role'])
    if role in user.roles:
        permissions = 2

    role = discord.utils.get(ctx.guild.roles, id=config.variables['bittah_sa_role'])
    if role in user.roles:
        permissions = 3

    return permissions


async def check_admin_member(member: discord.Member) -> int:
    # check if member has admin role
    permissions = 0
    role = discord.utils.get(ctx.guild.roles, id=config.variables['bittah_access_role'])
    if role in member.roles:
        permissions = 1

    role = discord.utils.get(ctx.guild.roles, id=config.variables['bittah_admin_role'])
    if role in member.roles:
        permissions = 2

    role = discord.utils.get(ctx.guild.roles, id=config.variables['bittah_sa_role'])
    if role in member.roles:
        permissions = 3

    return permissions


def setup(bot):
    bot.add_cog(Admin(bot))
