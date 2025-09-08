
import os
import json
import logging
from typing import Dict, List, Set
import requests
import boto3
from .util import backoff_retry

logger = logging.getLogger(__name__)
sm = boto3.client("secretsmanager")

class GraphClient:
    def __init__(self, secret_name: str):
        self._secret_name = secret_name
        self._token = None
        self._tenant = None
        self._client_id = None
        self._client_secret = None
        self._load_secret()

    def _load_secret(self):
        resp = sm.get_secret_value(SecretId=self._secret_name)
        data = json.loads(resp["SecretString"])
        self._tenant = data["tenant_id"]
        self._client_id = data["client_id"]
        self._client_secret = data["client_secret"]

    @backoff_retry
    def _fetch_token(self) -> str:
        url = f"https://login.microsoftonline.com/{self._tenant}/oauth2/v2.0/token"
        body = {
            "client_id": self._client_id,
            "client_secret": self._client_secret,
            "grant_type": "client_credentials",
            "scope": "https://graph.microsoft.com/.default"
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        r = requests.post(url, data=body, headers=headers, timeout=20)
        r.raise_for_status()
        tok = r.json()["access_token"]
        logger.info("Fetched Microsoft Graph token successfully")
        return tok

    def _get_token(self) -> str:
        if not self._token:
            self._token = self._fetch_token()
        return self._token

    @backoff_retry
    def _get(self, url: str) -> Dict:
        headers = {"Authorization": f"Bearer {self._get_token()}"}
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 401:
            # refresh token once
            self._token = self._fetch_token()
            headers = {"Authorization": f"Bearer {self._token}"}
            r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def list_group_usernames(self, group_id: str) -> Set[str]:
        """
        Returns a set of "usernames" derived from userPrincipalName (left of '@').
        Uses transitiveMembers to include nested groups.
        """
        usernames: Set[str] = set()
        url = f"https://graph.microsoft.com/v1.0/groups/{group_id}/transitiveMembers?$select=id,displayName,userPrincipalName&$top=999"
        while url:
            data = self._get(url)
            for obj in data.get("value", []):
                upn = obj.get("userPrincipalName")
                if not upn:
                    continue
                name = upn.split("@")[0]
                if name:
                    usernames.add(name)
            url = data.get("@odata.nextLink")
        logger.info("Discovered %d group usernames from Entra ID", len(usernames))
        return usernames
