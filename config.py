import json
import os
from pathlib import Path
from dotenv import load_dotenv

CONFIG_PATH = Path(__file__).parent / "config.json"
load_dotenv(CONFIG_PATH.parent / ".env")

with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

config["token"] = os.environ.get("DISCORD_TOKEN", "")
config["api"] = os.environ.get("WARERA_API_KEY", "")
config["AWS_ACCESS_KEY_ID"] = os.environ.get("AWS_ACCESS_KEY_ID", "")
config["AWS_SECRET_ACCESS_KEY"] = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
config["AWS_SESSION_TOKEN"] = os.environ.get("AWS_SESSION_TOKEN", "")
config["AWS_REGION"] = os.environ.get("AWS_REGION", "eu-west-1")
config["DYNAMO_USERS_TABLE"] = os.environ.get("DYNAMO_USERS_TABLE", "users")
config["DYNAMO_DIPLOMACIES_TABLE"] = os.environ.get("DYNAMO_DIPLOMACIES_TABLE", "diplomacies")
config["DYNAMO_NAPS_TABLE"] = os.environ.get("DYNAMO_NAPS_TABLE", "naps")
