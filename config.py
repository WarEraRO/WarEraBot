"""Load the bot configuration from config.json and secrets from the environment.

Running with ``--test`` (``python run.py --test``) loads config.test.json instead,
and utils.db then uses the local SQLite database in database/ instead of DynamoDB.
"""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# config is imported by run.py and every cog, so the flag is read from argv here
TEST_MODE = "--test" in sys.argv
CONFIG_PATH = Path(__file__).parent / ("config.test.json" if TEST_MODE else "config.json")
load_dotenv(CONFIG_PATH.parent / ".env")

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

config["token"] = os.environ.get("DISCORD_TOKEN", "")
config["api"] = os.environ.get("WARERA_API_KEY", "")
config["AWS_ACCESS_KEY_ID"] = os.environ.get("AWS_ACCESS_KEY_ID", "")
config["AWS_SECRET_ACCESS_KEY"] = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
config["AWS_SESSION_TOKEN"] = os.environ.get("AWS_SESSION_TOKEN", "")
config["AWS_REGION"] = os.environ.get("AWS_REGION", "eu-west-1")
config["DYNAMO_USERS_TABLE"] = os.environ.get("DYNAMO_USERS_TABLE", "warera-ro-discordbot_prod_users")
config["DYNAMO_DIPLOMACIES_TABLE"] = os.environ.get("DYNAMO_DIPLOMACIES_TABLE", "warera-ro-discordbot_prod_diplomacies")
config["DYNAMO_NAPS_TABLE"] = os.environ.get("DYNAMO_NAPS_TABLE", "warera-ro-discordbot_prod_naps")
config["DYNAMO_GUILD_SETTINGS_TABLE"] = os.environ.get("DYNAMO_GUILD_SETTINGS_TABLE", "warera-ro-discordbot_prod_guild_settings")
config["DYNAMO_JOB_SUBSCRIPTIONS_TABLE"] = os.environ.get("DYNAMO_JOB_SUBSCRIPTIONS_TABLE", "warera-ro-discordbot_prod_job_subscriptions")
config["DYNAMO_CONTESTS_TABLE"] = os.environ.get("DYNAMO_CONTESTS_TABLE", "warera-ro-discordbot_prod_contests")
