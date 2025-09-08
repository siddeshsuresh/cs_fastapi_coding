# src/daily_summary/email_sns.py
import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)
sns = boto3.client("sns")


def send_email_via_sns(html_body: str, context, mail_to: str, subject: str) -> str:
    """
    Matches your pattern:
      - Build a 'message' dict with: mail_to, subject, body (HTML), sender_arn
      - Wrap it as {"default": json.dumps(message)}
      - Publish with MessageStructure='json' to SNS topic (from env SNS_TOPIC_ARN)
    """
    try:
        sender_arn = context.invoked_function_arn if context else "auto-vdi"
        message = {
            "mail_to": mail_to,             # comma-separated string
            "subject": subject,
            "body": html_body,              # HTML
            "sender_arn": sender_arn,
        }
        sns_message = {"default": json.dumps(message)}
        logger.info("SNS structured payload: %s", json.dumps(sns_message, indent=2))

        resp = sns.publish(
            TargetArn=os.environ["SNS_TOPIC_ARN"],
            Message=json.dumps(sns_message),
            MessageStructure="json",
        )
        logger.info("SNS Email sent. Message ID: %s", resp.get("MessageId"))
        return resp.get("MessageId")
    except Exception as e:
        logger.exception("Error while publishing to SNS: %s", e)
        raise
