
import os
from dataclasses import dataclass

@dataclass
class Config:
    group_id: str
    directory_id: str
    bundle_id: str
    region: str
    azure_secret_name: str
    report_bucket: str
    email_sender: str
    email_recipients: str  # comma-separated
    max_creates_per_run: int
    running_mode: str
    running_mode_timeout: int  # minutes; used for AUTO_STOP
    dry_run: bool

def load_config() -> "Config":
    return Config(
        group_id=os.environ["GROUP_ID"],
        directory_id=os.environ["DIRECTORY_ID"],
        bundle_id=os.environ["BUNDLE_ID"],
        region=os.environ.get("AWS_REGION", "us-west-2"),
        azure_secret_name=os.environ["AZURE_SECRET_NAME"],
        report_bucket=os.environ["REPORT_BUCKET"],
        email_sender=os.environ["EMAIL_SENDER"],
        email_recipients=os.environ["EMAIL_RECIPIENTS"],
        max_creates_per_run=int(os.environ.get("MAX_CREATES_PER_RUN", "50")),
        running_mode=os.environ.get("RUNNING_MODE", "AUTO_STOP"),
        running_mode_timeout=int(os.environ.get("RUNNING_MODE_TIMEOUT", "60")),
        dry_run=os.environ.get("DRY_RUN", "false").lower() == "true",
    )
