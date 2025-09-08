
import logging
from typing import List, Dict, Set
import boto3
from botocore.exceptions import ClientError
from .util import backoff_retry

logger = logging.getLogger(__name__)

ws = boto3.client("workspaces")

def list_usernames(directory_id: str) -> Set[str]:
    usernames: Set[str] = set()
    next_token = None
    while True:
        kwargs = {"DirectoryId": directory_id}
        if next_token:
            kwargs["NextToken"] = next_token
        resp = ws.describe_workspaces(**kwargs)
        for w in resp.get("Workspaces", []):
            if "UserName" in w:
                usernames.add(w["UserName"])
        next_token = resp.get("NextToken")
        if not next_token:
            break
    logger.info("Found %d existing WorkSpaces users", len(usernames))
    return usernames

@backoff_retry
def create_workspaces(requests: List[Dict]) -> Dict:
    return ws.create_workspaces(Workspaces=requests)
