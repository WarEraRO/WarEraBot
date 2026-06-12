import os
import json
from typing import Optional, Dict, List
from config import config

import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError

# Table name overrides via environment (useful for staging/prod separation)
_USERS_TABLE_NAME = config.get("DYNAMO_USERS_TABLE", "users")
_DIPLOMACIES_TABLE_NAME = config.get("DYNAMO_DIPLOMACIES_TABLE", "diplomacies")

# Module-level cached resource to avoid re-creating sessions on every call
_resource = None

def _get_resource():
    global _resource
    if _resource is None:
        region = config.get("AWS_REGION") or "eu-west-1"
        _resource = boto3.resource(
            "dynamodb",
            region_name=region,
            aws_access_key_id=config.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=config.get("AWS_SECRET_ACCESS_KEY"),
            aws_session_token=config.get("AWS_SESSION_TOKEN"),
        )
    return _resource


def _users():
    return _get_resource().Table(_USERS_TABLE_NAME)


def _diplomacies():
    return _get_resource().Table(_DIPLOMACIES_TABLE_NAME)


def _parse_diplomacy_list(raw) -> List:
    """Normalize a DynamoDB diplomacy value to a Python list."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return []
    return []


# ---------------------------------------------------------------------------
# Users CRUD
# ---------------------------------------------------------------------------

def save_user(
    discord_username: Optional[str],
    display_name: Optional[str],
    api_id: str,
    discord_id=None,
) -> None:
    """Insert or update a user record keyed by api_id."""
    if api_id is None:
        return

    update_parts: List[str] = []
    expr_names: Dict[str, str] = {}
    expr_values: Dict[str, str] = {}

    if discord_username is not None:
        update_parts.append("#du = :du")
        expr_names["#du"] = "discord_username"
        expr_values[":du"] = discord_username

    if display_name is not None:
        update_parts.append("#dn = :dn")
        expr_names["#dn"] = "display_name"
        expr_values[":dn"] = display_name

    if discord_id is not None:
        update_parts.append("#di = :di")
        expr_names["#di"] = "discord_id"
        expr_values[":di"] = str(discord_id)

    if not update_parts:
        # Ensure the item exists with just the primary key
        _users().put_item(Item={"api_id": api_id}, ConditionExpression="attribute_not_exists(api_id)")
        return

    _users().update_item(
        Key={"api_id": api_id},
        UpdateExpression="SET " + ", ".join(update_parts),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )


def find_api_id_by_discord_id(discord_id) -> Optional[str]:
    """Scan users table for a matching discord_id (no GSI required)."""
    resp = _users().scan(
        FilterExpression=Attr("discord_id").eq(str(discord_id)),
        ProjectionExpression="api_id",
    )
    items = resp.get("Items", [])
    return items[0]["api_id"] if items else None


def find_api_id_by_display_name(display_name: str) -> Optional[str]:
    resp = _users().query(
        IndexName="display_name-index",
        KeyConditionExpression=Key("display_name").eq(display_name),
        ProjectionExpression="api_id",
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0]["api_id"] if items else None


def find_api_id_by_discord_username(discord_username: str) -> Optional[str]:
    resp = _users().query(
        IndexName="discord_username-index",
        KeyConditionExpression=Key("discord_username").eq(discord_username),
        ProjectionExpression="api_id",
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0]["api_id"] if items else None


def get_record_by_api_id(api_id: str) -> Optional[Dict]:
    resp = _users().get_item(Key={"api_id": api_id})
    item = resp.get("Item")
    if not item:
        return None
    return {
        "discord_username": item.get("discord_username"),
        "display_name": item.get("display_name"),
        "api_id": item["api_id"],
        "discord_id": item.get("discord_id"),
    }


# ---------------------------------------------------------------------------
# Diplomacies CRUD
# ---------------------------------------------------------------------------

def get_all_diplomacies() -> Dict[str, Dict]:
    """Return a mapping of country_name -> record dict for all diplomacies."""
    resp = _diplomacies().scan()
    out: Dict[str, Dict] = {}
    for item in resp.get("Items", []):
        country = item["country_name"]
        out[country] = {
            "status": item.get("status"),
            "description": item.get("description"),
            "diplomacy": _parse_diplomacy_list(item.get("diplomacy")),
        }
    return out


def get_diplomacy(country_name: str) -> Optional[Dict]:
    resp = _diplomacies().get_item(Key={"country_name": country_name})
    item = resp.get("Item")
    if not item:
        return None
    return {
        "country_name": item["country_name"],
        "status": item.get("status"),
        "description": item.get("description"),
        "diplomacy": _parse_diplomacy_list(item.get("diplomacy")),
    }


def update_diplomacy(
    country_name: str,
    status: Optional[str] = None,
    description: Optional[str] = None,
) -> None:
    """Insert or update a diplomacy record, creating it if it does not exist."""
    update_parts: List[str] = [
        "#dp = if_not_exists(#dp, :empty_list)",
    ]
    expr_names: Dict[str, str] = {"#dp": "diplomacy"}
    expr_values: Dict = {":empty_list": []}

    if status is not None:
        update_parts.append("#s = :s")
        expr_names["#s"] = "status"
        expr_values[":s"] = status

    if description is not None:
        update_parts.append("#d = :d")
        expr_names["#d"] = "description"
        expr_values[":d"] = description

    _diplomacies().update_item(
        Key={"country_name": country_name},
        UpdateExpression="SET " + ", ".join(update_parts),
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values,
    )


def add_diplomacy_entry(country_name: str, info: str, entry_date: str) -> None:
    """Append an entry to a country's diplomacy list, creating the record if needed."""
    entry = {"text": info, "date": entry_date}
    _diplomacies().update_item(
        Key={"country_name": country_name},
        UpdateExpression="SET #dp = list_append(if_not_exists(#dp, :empty_list), :entry)",
        ExpressionAttributeNames={"#dp": "diplomacy"},
        ExpressionAttributeValues={":entry": [entry], ":empty_list": []},
    )


def remove_diplomacy_entry(country_name: str, position: int) -> bool:
    """Remove entry at 1-based position from the diplomacy list. Returns True if removed."""
    resp = _diplomacies().get_item(Key={"country_name": country_name})
    item = resp.get("Item")
    if not item:
        return False

    entries = _parse_diplomacy_list(item.get("diplomacy"))
    idx = position - 1
    if idx < 0 or idx >= len(entries):
        return False

    entries.pop(idx)

    _diplomacies().update_item(
        Key={"country_name": country_name},
        UpdateExpression="SET #dp = :dp",
        ExpressionAttributeNames={"#dp": "diplomacy"},
        ExpressionAttributeValues={":dp": entries},
    )
    return True


def delete_diplomacy(country_name: str) -> bool:
    """Delete the diplomacy record for a country. Returns True if a row was deleted."""
    resp = _diplomacies().delete_item(
        Key={"country_name": country_name},
        ReturnValues="ALL_OLD",
    )
    return bool(resp.get("Attributes"))


# ---------------------------------------------------------------------------
# Table provisioning
# ---------------------------------------------------------------------------

def ensure_tables(
    users_table: str = _USERS_TABLE_NAME,
    diplomacies_table: str = _DIPLOMACIES_TABLE_NAME,
    region: Optional[str] = None,
) -> bool:
    """Ensure both users and diplomacies tables exist in DynamoDB.

    Returns True if at least one table was confirmed/created.
    Returns False if AWS credentials are missing.
    """
    access_key = config.get("AWS_ACCESS_KEY_ID")
    secret_key = config.get("AWS_SECRET_ACCESS_KEY")
    session_token = config.get("AWS_SESSION_TOKEN")
    region = region or config.get("AWS_REGION") or "eu-west-1"

    if not access_key or not secret_key:
        return False

    client = boto3.client(
        "dynamodb",
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        aws_session_token=session_token,
    )

    created_any = False

    # ------------------------------------------------------------------
    # Users table  (hash key: api_id)
    # GSIs: discord_username-index, display_name-index
    # discord_id lookups use Scan (field is sparse/optional)
    # ------------------------------------------------------------------
    try:
        client.describe_table(TableName=users_table)
        created_any = True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            raise
        try:
            client.create_table(
                TableName=users_table,
                AttributeDefinitions=[
                    {"AttributeName": "api_id", "AttributeType": "S"},
                    {"AttributeName": "discord_username", "AttributeType": "S"},
                    {"AttributeName": "display_name", "AttributeType": "S"},
                ],
                KeySchema=[{"AttributeName": "api_id", "KeyType": "HASH"}],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "discord_username-index",
                        "KeySchema": [{"AttributeName": "discord_username", "KeyType": "HASH"}],
                        "Projection": {"ProjectionType": "ALL"},
                    },
                    {
                        "IndexName": "display_name-index",
                        "KeySchema": [{"AttributeName": "display_name", "KeyType": "HASH"}],
                        "Projection": {"ProjectionType": "ALL"},
                    },
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            client.get_waiter("table_exists").wait(
                TableName=users_table, WaiterConfig={"Delay": 2, "MaxAttempts": 25}
            )
            created_any = True
        except ClientError as ce:
            if ce.response.get("Error", {}).get("Code") == "ResourceInUseException":
                created_any = True
            else:
                raise

    # ------------------------------------------------------------------
    # Diplomacies table  (hash key: country_name)
    # GSI: status-index  (sparse — items with no status won't be indexed)
    # ------------------------------------------------------------------
    try:
        client.describe_table(TableName=diplomacies_table)
        created_any = True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
            raise
        try:
            client.create_table(
                TableName=diplomacies_table,
                AttributeDefinitions=[
                    {"AttributeName": "country_name", "AttributeType": "S"},
                    {"AttributeName": "status", "AttributeType": "S"},
                ],
                KeySchema=[{"AttributeName": "country_name", "KeyType": "HASH"}],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "status-index",
                        "KeySchema": [{"AttributeName": "status", "KeyType": "HASH"}],
                        "Projection": {"ProjectionType": "ALL"},
                    },
                ],
                BillingMode="PAY_PER_REQUEST",
            )
            client.get_waiter("table_exists").wait(
                TableName=diplomacies_table, WaiterConfig={"Delay": 2, "MaxAttempts": 25}
            )
            created_any = True
        except ClientError as ce:
            if ce.response.get("Error", {}).get("Code") == "ResourceInUseException":
                created_any = True
            else:
                raise

    return created_any
