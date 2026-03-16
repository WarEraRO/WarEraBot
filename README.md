# WarEraRO bot

A Discord bot for WarEraRO's community management. It syncs guild roles based on player data, tracks military-unit membership, reports takeover opportunities, watches buff expiry for fighters, and provides a `/fightstatus` command with filtering and pagination.

## How to run

### 1) Configure environment and config
Create a `.env` file in the project root:

```env
DISCORD_TOKEN=your_discord_bot_token
WARERA_API_KEY=your_warera_api_key
```

The bot also expects guild/role/channel settings in `config.json`.

### 2) Run with Docker
Build the image:

```bash
docker build -t warera-bot .
```

Run the container with your `.env` file:

```bash
docker run --rm --env-file .env warera-bot
```

### 3) Run natively (Python)
Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip3 install -r requirements.txt
```

Start the bot:

```bash
python3 run.py
```

If you don't have `python3` as a binary, try with just `python`, or `py3`, or `py`. Same for `pip3` and `pip`.
