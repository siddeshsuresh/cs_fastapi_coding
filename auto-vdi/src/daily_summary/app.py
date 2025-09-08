
import os
import logging
from datetime import datetime, timezone
import boto3
from .config import load_config
from .audit import query_today_actions, get_today_snapshot_pointer, write_created_csv

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)
ses = boto3.client("ses")
s3 = boto3.client("s3")

def handler(event, context):
    cfg = load_config()
    items = query_today_actions()

    created = [i["sk"]["S"].split("#",1)[1] for i in items if i.get("action", {}).get("S") == "created"]
    errors  = [i for i in items if i.get("action", {}).get("S") == "error"]

    snap = get_today_snapshot_pointer()
    group_count = None
    group_link = None
    if snap:
        bucket = snap["s3_bucket"]["S"]
        key = snap["s3_key"]["S"]
        group_count = _count_csv_rows(bucket, key) - 1  # minus header
        group_link = f"s3://{bucket}/{key}"

    created_key = write_created_csv(cfg.report_bucket, created)
    created_link = f"s3://{cfg.report_bucket}/{created_key}"

    body = _render_body(group_count, len(created), len(errors), group_link, created_link)
    _send_email(cfg.email_sender, cfg.email_recipients.split(","), "Daily Auto-VDI Summary", body)
    return {"ok": True, "group_count": group_count, "created": len(created), "errors": len(errors)}

def _count_csv_rows(bucket: str, key: str) -> int:
    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj["Body"].read().decode("utf-8", errors="ignore")
    return sum(1 for _ in body.splitlines())

def _render_body(group_count, created_count, error_count, group_link, created_link) -> str:
    today = datetime.now(timezone.utc).astimezone().date().isoformat()
    lines = [
        f"Auto-VDI Summary for {today}",
        "",
        f"Group size (at last run): {group_count if group_count is not None else 'N/A'}",
        f"WorkSpaces created today: {created_count}",
        f"Failures today: {error_count}",
        "",
        f"Group members CSV: {group_link or 'N/A'}",
        f"Created users CSV: {created_link}",
        "",
        "— AutoVDI Bot"
    ]
    return "\n".join(lines)

def _send_email(sender: str, recipients, subject: str, body: str):
    ses.send_email(
        Source=sender,
        Destination={"ToAddresses": recipients},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body}},
        },
    )
