from datetime import datetime

import discord
import timeago
import uuid
from discord.ext import commands
from discord_slash import cog_ext
from discord_slash.context import SlashContext
from discord_slash.utils.manage_commands import create_option, create_choice

import config
from includes import general, msg
from schemas import member_schema, general_schema

import cogs.admin
from cogs.admin import check_admin, check_admin_member


class Profile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print("Profile Cog: Loaded")

    @cog_ext.cog_slash(
        name="profile",
        description="Show player profile",
        options=[
            create_option(
                name="member",
                description="Choose a member",
                required=False,
                option_type=6,
            )
        ],
        guild_ids=config.variables['guild_ids']
    )
    async def profile(self, ctx: SlashContext, member: discord.Member = None):
        user = ctx.author
        if not await general.correct_channel(ctx, user):
            return
        if member is None:
            member_schema.check_profile(user)
            profile = member_schema.get_profile(user)
            profile_stats = member_schema.get_player_stats(user.id)
            region_emojis = {
                "NA":":flag_us: ",
                "EU":":flag_eu: ",
                "AUS":":flag_au: ",
                "Not Set":""
            }
            embed = discord.Embed()
            embed.set_author(icon_url=user.avatar_url, name=user.name)
            embed.set_thumbnail(url=user.avatar_url)

            access_level = await check_admin(ctx)
            if access_level == 1:
                embed.add_field(name="Role", value="**`Gamer`**")
            elif access_level == 2:
                embed.add_field(name="Role", value="**`Admin`**")
            elif access_level == 3:
                embed.add_field(name="Role", value="**`Super Admin`**")
            else:
                embed.add_field(name="Role", value="**`No Access`**")

            embed.add_field(name="Total Games", value=f"**`{profile['gamesPlayed']}`**",
                            inline=True)
            embed.add_field(name="Region", value=f"{region_emojis[profile['region']]}**`{profile['region']}`**")
            if profile['lastPlayed'] != "Never":
                now = datetime.now()
                last_played = timeago.format(profile['lastPlayed'], now)
            else:
                last_played = "Never"
            embed.add_field(name="Last Played", value=f"**`{last_played}`**", inline=True)
            embed.add_field(name="Position", value=f"**`{profile['position']}`**", inline=True)
            if not profile['hideRank']:
                embed.add_field(name="W/L/T*", value=f"**`{profile_stats[0]}/{profile_stats[1]}/{profile_stats[2]}`**")
            else:
                embed.add_field(name="W/L/T*", value=f"**`Hidden`**")
        else:
            member_schema.check_profile(member)
            profile = member_schema.get_profile(member)
            profile_stats = member_schema.get_player_stats(member.id)
            region_emojis = {
                "NA":":flag_us: ",
                "EU":":flag_eu: ",
                "AUS":":flag_au: ",
                "Not Set":""
            }
            embed = discord.Embed()
            embed.set_author(icon_url=member.avatar_url, name=member.name)
            embed.set_thumbnail(url=member.avatar_url)

            access_level = await check_admin_member(ctx, member)
            if access_level == 1:
                embed.add_field(name="Role", value="**`Gamer`**")
            elif access_level == 2:
                embed.add_field(name="Role", value="**`Admin`**")
            elif access_level == 3:
                embed.add_field(name="Role", value="**`Super Admin`**")
            else:
                embed.add_field(name="Role", value="**`No Access`**")

            embed.add_field(name="Total Games", value=f"**`{profile['gamesPlayed']}`**",
                            inline=True)
            embed.add_field(name="Region", value=f"{region_emojis[profile['region']]}**`{profile['region']}`**")
            if profile['lastPlayed'] != "Never":
                now = datetime.now()
                last_played = timeago.format(profile['lastPlayed'], now)
            else:
                last_played = "Never"
            embed.add_field(name="Last Played", value=f"**`{last_played}`**", inline=True)
            embed.add_field(name="Position", value=f"**`{profile['position']}`**", inline=True)
            if not profile['hideRank']:
                embed.add_field(name="W/L/T*", value=f"**`{profile_stats[0]}/{profile_stats[1]}/{profile_stats[2]}`**")
            else:
                embed.add_field(name="W/L/T*", value=f"**`Hidden`**")

        await ctx.send(embed=embed, hidden=True)

    @cog_ext.cog_slash(
        name="setup",
        description="Setup your profile",
        guild_ids=config.variables['guild_ids']
    )
    async def _setup(self, ctx:SlashContext):
        if await general.correct_channel(ctx, ctx.author) == False:
            return
        if general_schema.check_setup_exists(ctx.author):
            return await ctx.send("Setup already in progress. Check your DM's", hidden=True)
        unique_id = str(uuid.uuid4())
        general_schema.add_profile_setup(ctx.author, str(unique_id), 1)
        await msg.profile_setup(ctx.author, unique_id)
        embed = discord.Embed(description="Setup has been sent. **Check your DM's**", color=msg.success_color)
        await ctx.send(embed=embed, hidden=True)


def setup(bot):
    bot.add_cog(Profile(bot))
