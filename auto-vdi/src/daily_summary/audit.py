
import os
import json
import csv
import io
import logging
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Set
import boto3

logger = logging.getLogger(__name__)

ddb = boto3.client("dynamodb")
s3 = boto3.client("s3")

TABLE = os.environ.get("AUDIT_TABLE", "AutoVdiAudit")

def today_str() -> str:
    return datetime.now(timezone.utc).astimezone().date().isoformat()

def _pk_date(date_str: Optional[str] = None) -> str:
    return f"DATE#{date_str or today_str()}"

def _sk_user(username: str) -> str:
    return f"USER#{username}"

def already_processed_today(username: str) -> bool:
    try:
        resp = ddb.get_item(
            TableName=TABLE,
            Key={"pk": {"S": _pk_date()}, "sk": {"S": _sk_user(username)}},
            ProjectionExpression="pk"
        )
        return "Item" in resp
    except ddb.exceptions.ResourceNotFoundException:
        logger.warning("Audit table %s not found; treating as not processed", TABLE)
        return False

def record_action(username: str, action: str, **extra):
    item = {
        "pk": {"S": _pk_date()},
        "sk": {"S": _sk_user(username)},
        "action": {"S": action},
        "ts": {"S": datetime.utcnow().isoformat()+'Z'},
    }
    for k, v in extra.items():
        if v is None:
            continue
        if isinstance(v, (int, float)):
            item[k] = {"N": str(v)}
        else:
            item[k] = {"S": str(v)}
    ddb.put_item(TableName=TABLE, Item=item)

def put_group_snapshot_to_s3(bucket: str, group_usernames: Iterable[str]) -> str:
    """
    Writes the daily group snapshot as CSV to S3.
    Returns the s3 key.
    """
    date_str = today_str()
    key = f"snapshots/group_members_{date_str}.csv"
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["username"])
    for u in sorted(group_usernames):
        w.writerow([u])
    s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue().encode("utf-8"), ContentType="text/csv")
    # store a pointer item for summary lambda
    ddb.put_item(
        TableName=TABLE,
        Item={
            "pk": {"S": f"SNAPSHOT#{date_str}"},
            "sk": {"S": "GROUP"},
            "s3_bucket": {"S": bucket},
            "s3_key": {"S": key},
            "ts": {"S": datetime.utcnow().isoformat()+'Z'}
        }
    )
    return key

def write_created_csv(bucket: str, created_usernames: Iterable[str]) -> str:
    date_str = today_str()
    key = f"reports/created_workspaces_{date_str}.csv"
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["username"])
    for u in sorted(created_usernames):
        w.writerow([u])
    s3.put_object(Bucket=bucket, Key=key, Body=buf.getvalue().encode("utf-8"), ContentType="text/csv")
    return key

def query_today_actions() -> List[Dict]:
    # Scan very small partition (pk by date)
    resp = ddb.query(
        TableName=TABLE,
        KeyConditionExpression="#pk = :v",
        ExpressionAttributeNames={"#pk": "pk"},
        ExpressionAttributeValues={":v": {"S": _pk_date()}}
    )
    return resp.get("Items", [])

def get_today_snapshot_pointer() -> Optional[Dict]:
    resp = ddb.get_item(
        TableName=TABLE,
        Key={"pk": {"S": f"SNAPSHOT#{today_str()}"}, "sk": {"S": "GROUP"}}
    )
    return resp.get("Item")
