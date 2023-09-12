from os import getenv
from typing import List

from dotenv import load_dotenv

load_dotenv()


def getenv_int(key) -> int:
    value = getenv(key)
    return None if value is None else int(value)


def getenv_list_int(key) -> List[int]:
    value = getenv(key)
    if value is None:
        return []
    return [int(value.strip()) for value in value.split(",")]


variables = {
    "version": "1.0.0",
    "environment": getenv("BITTAH_ENVIRONMENT", "DEV"),
    "mongo_connection_string": getenv("BITTAH_MONGO_CONNECTION_STRING", "localhost:27017"),
    "mongo_database_name": getenv("BITTAH_MONGO_DATABASE_NAME", "Bittah"),
    "token": getenv("BITTAH_DISCORD_TOKEN"),
    "main_guild": getenv("BITTAH_DISCORD_MAIN_GUILD"),
    "main_guild_id": getenv_int("BITTAH_DISCORD_MAIN_GUILD_ID"),
    "channel": getenv("BITTAH_DISCORD_CHANNEL"),
    "channelid": getenv_int("BITTAH_DISCORD_CHANNEL_ID"),
    "guild_ids": getenv_list_int("BITTAH_DISCORD_GUILD_IDS"),
    "admin_channel": getenv("BITTAH_DISCORD_ADMIN_CHANNEL"),
    "twitch_client_id": getenv("TWITCH_CLIENT_ID"),
    "twitch_client_secret": getenv("TWITCH_CLIENT_SECRET"),
    "twitch_game_id": getenv_int("TWITCH_GAME_ID"),
    "bittah_access_role": getenv_int("BITTAH_ACCESS_ROLE_ID"),
    "bittah_admin_role": getenv_int("BITTAH_ADMIN_ROLE_ID"),
    "bittah_sa_role": getenv_int("BITTAH_SUPERADMIN_ROLE_ID"),
    "auto_remove": getenv_int("QUEUE_EXPIRE_MINUTES"),
    "expire_message": getenv_int("QUEUE_EXPIRE_MESSAGES"),
    "num_offense_needed": getenv_int("NUM_OFFENSE_NEEDED"),
    "num_chase_needed": getenv_int("NUM_CHASE_NEEDED"),
    "num_home_needed": getenv_int("NUM_HOME_NEEDED"),
    "rating_tolerance": getenv_int("RATING_TOLERANCE"),
    "needs_access": getenv_int("QUEUE_ROLE_ACCESS"),
    "avail": ":green_square:",
    "taken": ":red_square:",
    "live": ":green_circle:",
    "notlive": ":red_circle:",
    "gold": ":first_place:",
    "silver": ":second_place:",
    "bronze": ":third_place:",
    "b_medal": ":medal:",
    "rank": ":heavy_minus_sign:",
    "rank_red": ":crown:"
}

map_imgs = {
    "exhumed": "https://i.imgur.com/MQGW6eJ.jpg",
    "elite": "https://i.imgur.com/9Xib6tF.jpg",
    "brynhildr": "https://i.imgur.com/9CAybAC.jpg",
    "minora": "https://i.imgur.com/YMetT8z.jpg",
    "ingonyama": "https://i.imgur.com/MRbwf5u.jpg",
    "twilightgrove": "https://i.imgur.com/GTzvA8t.jpg",
    "kryosis": "https://i.imgur.com/HJuawtp.jpg",
    "nightflare": "https://i.imgur.com/8wMHNjK.jpg",
    "outpost": "https://i.imgur.com/Nkc04Di.jpg",
    "forlorn": "https://i.imgur.com/igFANQB.png",
    "relay": "https://i.imgur.com/jQnPNBh.png",
    "sunward": "https://i.imgur.com/aIr4rjt.png",
    "yolandi": "https://i.imgur.com/WwkEDgj.png",
}


def queues(default: bool):
    if default is True:
        return [{"name": "Quickplay", "value": "quickplay"}]

    return [{"name": "All Queues", "value": "all"},
            {"name": "Quickplay", "value": "quickplay"}]
