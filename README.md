# WarEraRO bot

A Discord bot for WarEraRO's community management. It syncs guild roles based on player data, tracks military-unit membership, reports takeover opportunities, watches buff expiry for fighters, and provides a `/fightstatus` command with filtering and pagination.

## How to run

### 1) Configure environment and config
Create a `.env` file in the project root:

```env
DISCORD_TOKEN=your_discord_bot_token
WARERA_API_KEY=your_warera_api_key
```

Optionally, to enable automatic AWS DynamoDB table creation at startup, add these environment variables:

```env
AWS_ACCESS_KEY_ID=your_aws_access_key_id
AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
AWS_REGION=us-east-1  # optional, defaults to us-east-1
```

The bot also expects guild/role/channel settings in `config.json`.

### Languages
The bot speaks English (default) and Romanian. Members with the Developer role (`roles.developer` in `config.json`) pick the language of a server with `/setlang <English|Romanian>`. The choice is saved per server in the `guild_settings` table (SQLite, or DynamoDB when AWS credentials are set, table name overridable with `DYNAMO_GUILD_SETTINGS_TABLE`) and applies to command responses, buttons, reports, alerts and the DMs the server triggers.

All texts live in `locales/en.json` and `locales/ro.json`. Code looks them up through `utils/i18n.py` (`tr = await get_translator(guild)`, then `tr("section.key", name=value)`); a key missing in Romanian falls back to English. Slash-command descriptions are shown in Romanian to members whose Discord client is set to Romanian (from the `slash` section of `ro.json`), since Discord picks those by client language.

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
