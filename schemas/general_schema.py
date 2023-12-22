from includes import mongo
import datetime


def check_setup_exists(user):
    if mongo.db['Messages'].count_documents({"userId": user.id}) < 1:
        return False
    return True


def add_profile_setup(user, uniqueue_id, stage):
    data = {
        "userId": user.id,
        "uniqueueId": uniqueue_id,
        "created": datetime.datetime.now(),
        "stage": stage
    }

    mongo.db['Messages'].insert_one(data)


def check_custom_id_exists(check_id):
    if mongo.db['Messages'].find_one({"uniqueueId": check_id}):
        return True
    return False


def get_message_stage(stage_id):
    return mongo.db['Messages'].find_one({"uniqueueId": stage_id})['stage']


def update_stage(stage_id, user, stage):
    data = {
        "$set": {
            "stage": stage
        }
    }

    mongo.db['Messages'].update_one({"uniqueueId": stage_id, "userId": user.id}, data)


def remove_setup(remove_id):
    mongo.db['Messages'].delete_one({"uniqueueId": remove_id})


def get_all_setup_messages():
    return mongo.db['Messages'].find({})
