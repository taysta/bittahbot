import os

# Override db name before any tests get executed
os.environ["BITTAH_MONGO_DATABASE_NAME"] = "Bittah_test"
