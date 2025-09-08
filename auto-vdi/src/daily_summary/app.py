# src/daily_summary/app.py
import os
import logging
from datetime import datetime, timezone

import boto3

from .config import load_config
from .audit import query_today_actions, get_today_snapshot_pointer, write_created_csv
from .email_sns import send_email_via_sns

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

s3 = boto3.client("s3")


def handler(event, context):
    cfg = load_config()

    # Read today's actions from DynamoDB
    items = query_today_actions()
    created = [i["sk"]["S"].split("#", 1)[1] for i in items if i.get("action", {}).get("S") == "created"]
    failed  = [i for i in items if i.get("action", {}).get("S") == "error"]

    # Read the pointer to the group snapshot CSV (if any) and count rows
    snap = get_today_snapshot_pointer()
    group_count, group_link = None, None
    if snap:
        bucket = snap["s3_bucket"]["S"]
        key = snap["s3_key"]["S"]
        group_count = _count_csv_rows(bucket, key) - 1  # minus header
        group_link = f"s3://{bucket}/{key}"

    # Always (re)write created list CSV so the link is deterministic
    created_key  = write_created_csv(cfg.report_bucket, created)
    created_link = f"s3://{cfg.report_bucket}/{created_key}"

    html_body = _build_html_email(
        group_count=group_count,
        created_count=len(created),
        fail_count=len(failed),
        group_link=group_link,
        created_link=created_link,
    )

    # Use your SNS pattern (JSON 'default' payload)
    send_email_via_sns(
        html_body=html_body,
        context=context,
        mail_to=cfg.email_recipients,                 # comma-separated string
        subject="Daily Auto-VDI Summary",
    )
    return {"ok": True, "group_count": group_count, "created": len(created), "failed": len(failed)}


def _count_csv_rows(bucket: str, key: str) -> int:
    obj = s3.get_object(Bucket=bucket, Key=key)
    body = obj["Body"].read().decode("utf-8", errors="ignore")
    return sum(1 for _ in body.splitlines())


def _build_html_email(*, group_count, created_count, fail_count, group_link, created_link) -> str:
    """
    HTML styled to mirror your Nexthink email screenshots:
    - Arial
    - rounded white card on light background
    - 2-column table: Metric | Value
    - link rows for CSVs
    """
    today = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
    # Inline CSS (kept minimal and compatible with email clients)
    return f"""
<!DOCTYPE html>
<html>
  <body style="margin:0;padding:0;background:#f9f9f9;font-family:Arial,sans-serif;color:#333;">
    <div style="max-width:800px;margin:24px auto;background:#fff;border-radius:10px;padding:20px;border:1px solid #ddd;">
      <h2 style="margin:0 0 12px 0;color:#0B5EC2;">Daily Auto-VDI Summary</h2>
      <div style="margin:0 0 16px 0;color:#666;">Date: {today}</div>

      <table style="width:100%;border-collapse:collapse;margin-top:10px;">
        <thead>
          <tr>
            <th style="text-align:left;padding:8px;border-bottom:1px solid #e0e0e0;width:40%;">Metric</th>
            <th style="text-align:left;padding:8px;border-bottom:1px solid #e0e0e0;">Value</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;">Group size (last snapshot)</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;">{group_count if group_count is not None else "N/A"}</td>
          </tr>
          <tr>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;">WorkSpaces created today</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;">{created_count}</td>
          </tr>
          <tr>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;">Failures today</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;">{fail_count}</td>
          </tr>
          <tr>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;">Group members CSV</td>
            <td style="padding:8px;border-bottom:1px solid #f0f0f0;">
              { (f'<a href="{group_link}" style="color:#0B5EC2;">{group_link}</a>') if group_link else "N/A" }
            </td>
          </tr>
          <tr>
            <td style="padding:8px;">Created users CSV</td>
            <td style="padding:8px;">
              <a href="{created_link}" style="color:#0B5EC2;">{created_link}</a>
            </td>
          </tr>
        </tbody>
      </table>

      <div style="margin-top:24px;color:#888;font-size:12px;">
        Sent automatically by <strong>Auto-VDI Lambda</strong>
      </div>
    </div>
  </body>
</html>
""".strip()
