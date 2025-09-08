
import json
import logging
import os
from datetime import datetime
import boto3

from .config import load_config
from .graph import GraphClient
from .workspaces import list_usernames, create_workspaces
from .audit import already_processed_today, record_action, put_group_snapshot_to_s3, write_created_csv
from .util import chunks

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)
ses = boto3.client("ses")

def handler(event, context):
    cfg = load_config()
    logger.info("AutoVDI Reconciler started. DryRun=%s", cfg.dry_run)

    graph = GraphClient(cfg.azure_secret_name)
    group_usernames = graph.list_group_usernames(cfg.group_id)
    existing_ws_users = list_usernames(cfg.directory_id)

    missing = sorted(group_usernames - existing_ws_users)
    if not missing:
        logger.info("No missing users. Nothing to do.")
        put_group_snapshot_to_s3(cfg.report_bucket, group_usernames)
        return {"created": 0, "missing": 0}

    to_create = missing[: cfg.max_creates_per_run]
    created = []
    failed = []

    if cfg.dry_run:
        logger.info("[DryRun] Would create %d workspaces", len(to_create))
    else:
        for batch in chunks(to_create, 25):
            final_batch = []
            for u in batch:
                if already_processed_today(u):
                    logger.info("Skip %s: already processed today", u)
                    continue
                req = {
                    "DirectoryId": cfg.directory_id,
                    "UserName": u,
                    "BundleId": cfg.bundle_id,
                    "WorkspaceProperties": {
                        "RunningMode": cfg.running_mode,
                        "RunningModeAutoStopTimeoutInMinutes": cfg.running_mode_timeout,
                    },
                    "Tags": [
                        {"Key": "ProvisionedBy", "Value": "AutoVDI"},
                    ],
                }
                final_batch.append(req)

            if not final_batch:
                continue
            try:
                resp = create_workspaces(final_batch)
            except Exception as e:
                logger.exception("CreateWorkspaces API failed: %s", e)
                for r in final_batch:
                    record_action(r["UserName"], "error", error=str(e))
                    failed.append({"user": r["UserName"], "error": str(e)})
                continue

            for pr in resp.get("PendingRequests", []):
                u = pr["UserName"]
                record_action(u, "created", request_id=pr.get("WorkspaceRequestId"))
                created.append(u)
            for fr in resp.get("FailedRequests", []):
                u = fr.get("UserName", "unknown")
                msg = fr.get("ErrorMessage", "unknown")
                record_action(u, "error", error=msg, code=fr.get("ErrorCode"))
                failed.append({"user": u, "error": msg})

    # write snapshot & today created CSV (even if empty, for consistency)
    put_group_snapshot_to_s3(cfg.report_bucket, group_usernames)
    created_key = write_created_csv(cfg.report_bucket, created)

    logger.info("Run summary: created=%d failed=%d missingInitially=%d", len(created), len(failed), len(missing))
    return {
        "created": len(created),
        "failed": len(failed),
        "created_key": created_key,
        "missing_initially": len(missing)
    }
