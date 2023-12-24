import datetime
from itertools import combinations
import random
from typing import List
import hashlib
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
TEAM_SIZE = NUM_OFFENSE_NEEDED + NUM_CHASE_NEEDED + NUM_HOME_NEEDED


class Player:
    def __init__(self, user_id=0, username="", r=Rating(), position="", captain_status=False):
        self.rating = r
        self.username = username
        self.user_id = user_id
        self.position = position
        self.is_captain = captain_status

    def __repr__(self):
        return f"Player(user_id='{self.user_id}', username='{self.username}')"

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
        "reshuffles": 0,
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


def form_team_by_preferences(team_comb, required_positions):
    team = {'offense': [], 'chase': [], 'home': []}
    flexible_players = []
    assigned_positions = {}

    for player in team_comb:
        if player.position in team and len(team[player.position]) < required_positions[player.position]:
            team[player.position].append(player)
            assigned_positions[player] = player.position
        elif player.position == 'flexible':
            flexible_players.append(player)

    for position, needed in required_positions.items():
        while len(team[position]) < needed and flexible_players:
            player = flexible_players.pop(0)
            team[position].append(player)
            assigned_positions[player] = position

    return team['offense'] + team['chase'] + team['home'], assigned_positions


def calculate_match_balance(team1, team2, assigned_positions):
    avg_rating_team1 = sum(player.rating.mu for player in team1) / len(team1)
    avg_rating_team2 = sum(player.rating.mu for player in team2) / len(team2)
    avg_uncertainty_team1 = sum(player.rating.sigma for player in team1) / len(team1)
    avg_uncertainty_team2 = sum(player.rating.sigma for player in team2) / len(team2)
    balance = abs(avg_rating_team1 - avg_rating_team2)
    uncertainty_difference = abs(avg_uncertainty_team1 - avg_uncertainty_team2)

    position_penalty = sum(assigned_positions[player] != player.position for player in team1 + team2)
    weight = 0.1
    return balance + uncertainty_difference + weight * position_penalty


def hash_team_combination(team):
    player_ids = sorted(player.user_id for player in team)
    return hashlib.md5(','.join(map(str, player_ids)).encode()).hexdigest()


def generate_match_combinations(players: List[Player], game_id, reshuffle_count: int = 0):
    required_positions = {'offense': NUM_OFFENSE_NEEDED, 'chase': NUM_CHASE_NEEDED, 'home': NUM_HOME_NEEDED}
    game_data = mongo.db['GameData'].find_one({"gameId": game_id})
    previous_hashes = set(game_data.get("previous_team_hashes", []))
    players.sort(key=lambda player: player.rating.mu, reverse=True)
    all_matches = []

    for team1_comb in combinations(players, TEAM_SIZE):
        team1, assigned_positions1 = form_team_by_preferences(team1_comb, required_positions)
        remaining_players = [player for player in players if player not in team1]
        team2, assigned_positions2 = form_team_by_preferences(remaining_players, required_positions)

        team1_hash = hash_team_combination(team1)
        team2_hash = hash_team_combination(team2)

        if team1_hash not in previous_hashes and team2_hash not in previous_hashes:
            all_matches.append((team1, team2))

    all_matches.sort(key=lambda match: calculate_match_balance(
        match[0], match[1], {**assigned_positions1, **assigned_positions2}))
    reshuffle_count = min(reshuffle_count, len(all_matches) - 1)
    return all_matches[reshuffle_count] if all_matches else None


def set_teams_for_game(game_id, players, reshuffles):
    best_match = generate_match_combinations(players, game_id, reshuffles)
    if best_match:
        team1, team2 = best_match
        team1_hash = hash_team_combination(team1)
        team2_hash = hash_team_combination(team2)

        mongo.db["GameData"].update_one(
            {"gameId": game_id},
            {"$set": {"reshuffles": reshuffles},
             "$push": {"previous_team_hashes": [team1_hash, team2_hash]}}
        )

        team1_captain = next((player for player in team1 if player.is_captain), random.choice(team1))
        team2_captain = next((player for player in team2 if player.is_captain), random.choice(team2))

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
    else:
        print("No unique team combinations available for reshuffling.")


def shuffle_teams(game_id):
    game = get_game(game_id)
    reshuffles = game["reshuffles"] + 1

    current_captains = get_captains(game_id)
    captain_ids = {captain['userId'] for captain in current_captains}

    players = []
    for player_data in game["players"]:
        player_profile = mongo.db['Profiles'].find_one({"userId": player_data['userId']})
        player_rank = mongo.db['Ranks'].find_one({"userId": player_data['userId']})

        captain_status = player_data['userId'] in captain_ids

        players.append(Player(player_rank['userId'], player_rank['username'],
                              Rating(player_rank['rank'], player_rank['confidence']),
                              player_profile['position'], captain_status=captain_status))

    mongo.db['Ingame'].delete_many({"gameId": game_id})
    set_teams_for_game(game_id, players, reshuffles)


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
            "username": target.display_name
        }
    })

    mongo.db["Ingame"].update_one({"_id": target_data["_id"]}, {
        "$set": {
            "userId": user.id,
            "username": user.display_name
        }
    })


def sub_player(user, member):
    mongo.db['Ingame'].update_one({"userId": member.id}, {"$set": {"userId": user.id, "username": user.name}})
    mongo.db['Queue'].delete_many({"userId": user.id})


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
    new_maps = []

    if game['queue'] == "quickplay":
        if button_id == custom_ids.shuffle_map_1:
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
