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