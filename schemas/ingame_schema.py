import datetime
from itertools import combinations
import random
from typing import List, Tuple

import pymongo
from discord import User
from pymongo import ASCENDING
from trueskill import Rating, rate

import config
from includes import custom_ids
from includes import mongo
from models.game import GameStatus, EmptyGame
from models.queue_models import Queue

# Define constants
NUM_OFFENSE_NEEDED = config.variables['num_offense_needed']
NUM_CHASE_NEEDED = config.variables['num_chase_needed']
NUM_HOME_NEEDED = config.variables['num_home_needed']
RATING_TOLERANCE = config.variables['rating_tolerance']
TEAM_SIZE = NUM_OFFENSE_NEEDED + NUM_CHASE_NEEDED + NUM_HOME_NEEDED


class Player:
    def __init__(self, user_id=0, username="", r=Rating(), position=""):
        self.rating = r
        self.username = username
        self.user_id = user_id
        self.position = position

    def __repr__(self):
        return f"Player(user_id={self.user_id}, username='{self.username}')"

    def __eq__(self, other):
        if not isinstance(other, Player):
            return False
        return self.__repr__() == other.__repr__()

    def __hash__(self):
        return hash(self.__repr__())


def create_game(queue: Queue, game_id, maps):
    data = {
        "gameId": game_id,
        "queue": queue.value,
        "status": 2,
        "maps": maps,
        "started": datetime.datetime.now(),
        "reshuffles": 0
    }

    mongo.db['GameData'].insert_one(data)


def generate_teams(queue: Queue, game_id):
    players = []
    for player in mongo.db['Queue'].find({"queue": queue.value}).limit(10):
        mongo.db['Queue'].delete_many({"userId": player['userId']})
        player_profile = mongo.db['Profiles'].find_one({"userId": player['userId']})
        player_rank = mongo.db['Ranks'].find_one({"userId": player['userId']})

        players.append(Player(player_rank['userId'], player_rank['username'],
                              Rating(player_rank['rank'], player_rank['confidence']), player_profile['position']))

    reshuffle_count = get_game(game_id)["reshuffles"]
    set_teams_for_game(game_id, players, reshuffle_count)


def form_team_by_preferences(team_comb):
    team = []
    positions_filled = {'offense': 0, 'chase': 0, 'home': 0}

    for player in sorted(team_comb, key=lambda p: p.rating.mu, reverse=True):
        if (player.position != 'flexible' and positions_filled[player.position]
                < config.variables[f'num_{player.position}_needed']):
            team.append(player)
            positions_filled[player.position] += 1
        elif player.position == 'flexible':
            least_filled_position = min(positions_filled, key=positions_filled.get)
            team.append(player)
            positions_filled[least_filled_position] += 1

    return team


def calculate_match_balance(team1, team2):
    avg_rating_team1 = sum(player.rating.mu for player in team1) / len(team1)
    avg_rating_team2 = sum(player.rating.mu for player in team2) / len(team2)
    return abs(avg_rating_team1 - avg_rating_team2)


def generate_match_combinations(players: List[Player],
                                reshuffle_count: int = 0) -> Tuple[Tuple[Player, ...], Tuple[Player, ...]]:
    players.sort(key=lambda player: player.rating.mu, reverse=True)
    all_matches = []

    for team1_comb in combinations(players, TEAM_SIZE):
        team1 = form_team_by_preferences(team1_comb)
        remaining_players = set(players) - set(team1)
        team2 = form_team_by_preferences(remaining_players)

        match = (tuple(team1), tuple(team2))
        all_matches.append(match)

    all_matches.sort(key=lambda test_match: calculate_match_balance(*test_match))
    reshuffle_count = min(reshuffle_count, len(all_matches) - 1)
    return all_matches[reshuffle_count]


def set_teams_for_game(game_id, players, reshuffles):
    best_match = generate_match_combinations(players, reshuffles)

    if reshuffles > 0:
        mongo.db["GameData"].update_one({"gameId": game_id}, {"$set": {"reshuffles": reshuffles}})

    team1 = best_match[0]
    team2 = best_match[1]
    team1_captain = random.choice(team1)
    team2_captain = random.choice(team2)

    for player in team1:
        data = {
            "userId": player.user_id,
            "username": player.username,
            "team": 1,
            "isCaptain": player.user_id == team1_captain.user_id,
            "gameId": game_id
        }
        mongo.db['Ingame'].insert_one(data)

    for player in team2:
        data = {
            "userId": player.user_id,
            "username": player.username,
            "team": 2,
            "isCaptain": player.user_id == team2_captain.user_id,
            "gameId": game_id
        }
        mongo.db['Ingame'].insert_one(data)


def update_game_status(game_id, status):
    status_query = {
        "gameId": game_id
    }
    data = {
        "$set": {
            "status": status
        }
    }
    mongo.db['GameData'].update_one(status_query, data)


def get_captains(game_id):
    return list(mongo.db['Ingame'].find({"gameId": game_id, "isCaptain": True}).sort("team"))


def get_team(game_id, team: int):
    return mongo.db['Ingame'].find({"gameId": game_id, "team": team})


def get_all_ingame_players(game_id):
    return mongo.db['Ingame'].find({"gameId": game_id})


def is_games(queue):
    if queue is None:
        data = {
            "$or": [
                {
                    "status": 1
                },
                {
                    "status": 2
                }
            ]
        }
        if mongo.db['GameData'].count_documents(data) > 0:
            return True
        else:
            return False
    else:
        data = {
            "queue": queue,
            "$or": [
                {
                    "status": 1
                },
                {
                    "status": 2
                }
            ]
        }
        if mongo.db['GameData'].count_documents(data) > 0:
            return True
        else:
            return False


def get_games(queue: Queue):
    if queue is None:
        data = {
            "$or": [
                {
                    "status": 1
                },
                {
                    "status": 2
                }
            ]
        }
        return mongo.db['GameData'].find(data)
    else:
        data = {
            "queue": queue.value,
            "$or": [
                {
                    "status": 1
                },
                {
                    "status": 2
                }
            ]
        }
        return mongo.db['GameData'].find(data)


def get_game_id_from_user(user):
    return mongo.db['Ingame'].find_one({"userId": user.id})['gameId']


def is_ingame(user):
    result = mongo.db['Ingame'].find_one({"userId": user.id})

    if result:
        return True
    else:
        return False


def is_captain(user):
    if mongo.db['Ingame'].find_one({"userId": user.id, "isCaptain": True}):
        return True
    else:
        return False


def new_is_captain(game_id, user):
    if mongo.db['Ingame'].find_one({"gameId": game_id, "userId": user.id, "isCaptain": True}):
        return True
    else:
        return False


def update_rankings(winner_ids: List[int], loser_ids: List[int], tie: bool):
    winning_team_ranks = {}
    for rank in mongo.db["Ranks"].find({"userId": {"$in": [user_id for user_id in winner_ids]}}):
        winning_team_ranks[rank["userId"]] = Rating(rank["rank"], rank["confidence"])

    losing_team_ranks = {}
    for rank in mongo.db["Ranks"].find({"userId": {"$in": [user_id for user_id in loser_ids]}}):
        losing_team_ranks[rank["userId"]] = Rating(rank["rank"], rank["confidence"])

    game_outcome = [0, 0] if tie else [0, 1]

    new_winning_team_ranks, new_losing_team_ranks = rate([winning_team_ranks, losing_team_ranks], ranks=game_outcome)
    updated_ranks = {**new_winning_team_ranks, **new_losing_team_ranks}
    for user_id in updated_ranks.keys():
        true_skill = updated_ranks[user_id]
        data = {
            "$set": {
                "rank": true_skill.mu,
                "confidence": true_skill.sigma
            }
        }
        mongo.db['Ranks'].update_one({"userId": user_id}, data)


def finish_game(game_id):
    mongo.db['Ingame'].delete_many({"gameId": game_id})
    mongo.db['GameData'].update_one({"gameId": game_id}, {
        "$set": {
            "status": GameStatus.FINISHED.value,
            "ended": datetime.datetime.now()
        }
    })


def swap_players(user: User, target: User, game_id):
    user_data = mongo.db["Ingame"].find_one({"userId": user.id, "gameId": game_id})
    target_data = mongo.db["Ingame"].find_one({"userId": target.id, "gameId": game_id})

    mongo.db["Ingame"].update_one({"_id": user_data["_id"]}, {
        "$set": {
            "userId": target.id,
            "username": target.name
        }
    })

    mongo.db["Ingame"].update_one({"_id": target_data["_id"]}, {
        "$set": {
            "userId": user.id,
            "username": user.name
        }
    })


def sub_player(user, member):
    mongo.db['Ingame'].update_one({"userId": member.id}, {"$set": {"userId": user.id, "username": user.name}})
    mongo.db['Queue'].delete_many({"userId": user.id})


def check_if_comp_game_by_user(user):
    ingame = mongo.db['Ingame'].find_one({"userId": user.id})
    if mongo.db['DraftState'].find_one({"gameId": ingame['gameId']}):
        return True
    else:
        return False


def get_game(game_id):
    return mongo.db['GameData'].find_one({"gameId": game_id})


def query(start_date: datetime.date, end_date: datetime.date):
    start_normalized = datetime.datetime(datetime.MINYEAR, 1, 1) if start_date is None else datetime.datetime(
        start_date.year, start_date.month, start_date.day)
    end_normalized = datetime.datetime(datetime.MAXYEAR, 1, 1) if end_date is None else datetime.datetime(
        end_date.year, end_date.month, end_date.day, 23, 59, 59)
    return mongo.db['GameData'].find({
        "ended": {
            "$gte": start_normalized,
            "$lte": end_normalized
        },
        "status": GameStatus.FINISHED.value
    })


def update_maps(game_id, maps):
    mongo.db['GameData'].update_one({"gameId": game_id}, {
        "$set": {
            "maps": maps
        }
    })


def get_games_last_24_hours():
    data = {
        "started": {
            "$lt": datetime.datetime.now(),
            "$gt": datetime.datetime.today() - datetime.timedelta(days=1)
        }
    }
    return mongo.db['GameData'].find(data).sort("started", ASCENDING)


def new_map(game_id, maps, button_id):
    game = mongo.db['GameData'].find_one({"gameId": game_id})
    new_maps = []  # Initialize new_maps to an empty list

    if game['queue'] == "quickplay":
        mongo.db['GameData'].update_one({"gameId": game_id}, {"$set": {"maps": maps}})
        new_maps = maps  # Assign maps to new_maps
    else:
        if game['queue'] == "competitive":
            if button_id == custom_ids.shuffle_map_1:
                # shuffle map 1
                new_maps = [maps[0], game['maps'][1]]
            elif button_id == custom_ids.shuffle_map_2:
                new_maps = [game['maps'][0], maps[0]]
            mongo.db['GameData'].update_one({"gameId": game_id}, {"$set": {"maps": new_maps}})

    return new_maps


def choose_different_map(game_id, _map):
    maps = [_map]
    mongo.db['GameData'].update_one({"gameId": game_id}, {"$set": {"maps": maps}})


def cancel_game(member):
    game_id = get_game_id_from_user(member)
    mongo.db['GameData'].delete_one({"gameId": game_id})
    mongo.db['Ingame'].delete_many({"gameId": game_id})


def delete(game_id):
    mongo.db['GameData'].delete_one({"gameId": game_id})
    mongo.db['Ingame'].delete_many({"gameId": game_id})


def override_timestamps(game_id, timestamp: datetime):
    mongo.db['GameData'].update_one({"gameId": game_id}, {"$set": {"started": timestamp, "ended": timestamp}})


def raw_member_inqueue(member):
    if mongo.db['Queue'].find_one({"username": member}):
        return True
    else:
        return False


def remove_raw_member_from_queue(member):
    mongo.db['Queue'].delete_one({"username": member})


def get_recent_games(num_games) -> List[EmptyGame]:
    data = mongo.db['GameData'].find().sort("ended", pymongo.DESCENDING).limit(num_games)
    return [EmptyGame(game['gameId'], game['started'], Queue(game['queue']), game.get('ended'),
                      GameStatus(game['status']), game.get('maps')) for game in data]


def update_game_suggested_server(game_id, server):
    mongo.db['GameData'].update_one({"gameId": game_id}, {"$set": {"server": server}})


def get_game_server(game_id):
    return mongo.db['GameData'].find_one({"gameId": game_id})['server']
