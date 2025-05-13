import requests
import json
import csv
import boto3
import os
from datetime import datetime

s3_client = boto3.client('s3')
ses_client = boto3.client('ses')

def get_nexthink_token():
    url = f"{os.environ['NEXTHINK_API_URL']}/oauth2/token"
    client_id = os.environ['CLIENT_ID']
    client_secret = os.environ['CLIENT_SECRET']

    response = requests.post(
        url,
        data={'grant_type': 'client_credentials'},
        auth=(client_id, client_secret)
    )
    return response.json().get("access_token")


def execute_nql_query(token, query_id):
    api_url = f"{os.environ['NEXTHINK_API_URL']}/v1/queries/{query_id}/execute"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    response = requests.post(api_url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error executing query {query_id}: {response.status_code} - {response.text}")


def generate_report(data):
    file_name = os.environ.get("REPORT_FILE_NAME", "laptop_statistics_report.csv")
    with open(f"/tmp/{file_name}", "w", newline="") as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(["Category", "Details"])
        for key, value in data.items():
            csv_writer.writerow([key, value])
    
    return f"/tmp/{file_name}"


def upload_to_s3(file_path):
    bucket_name = os.environ['S3_BUCKET_NAME']
    file_name = os.path.basename(file_path)
    s3_client.upload_file(file_path, bucket_name, file_name)
    return f"s3://{bucket_name}/{file_name}"


def send_email(report_url):
    ses_client.send_email(
        Source=os.environ['RECIPIENT_EMAIL'],
        Destination={'ToAddresses': [os.environ['RECIPIENT_EMAIL']]},
        Message={
            'Subject': {'Data': 'Daily Laptop Statistics Report'},
            'Body': {
                'Text': {
                    'Data': f"Dear Manager,\n\nPlease find your daily laptop statistics report here: {report_url}"
                }
            }
        }
    )


def lambda_handler(event, context):
    token = get_nexthink_token()
    
    # Query IDs (replace with your query IDs)
    query_ids = {
        "Updates Count": "YOUR_UPDATES_QUERY_ID",
        "Application Crashes": "YOUR_CRASHES_QUERY_ID",
        "DEX Score": "YOUR_DEX_SCORE_QUERY_ID",
        "Memory and CPU Utilization": "YOUR_UTILIZATION_QUERY_ID",
        "Network Issues": "YOUR_NETWORK_ISSUES_QUERY_ID"
    }
    
    data = {}
    for key, query_id in query_ids.items():
        result = execute_nql_query(token, query_id)
        data[key] = result
    
    # Generate CSV report
    report_path = generate_report(data)
    
    # Upload to S3
    report_url = upload_to_s3(report_path)
    
    # Send Email
    send_email(report_url)
    
    return {
        'statusCode': 200,
        'body': json.dumps('Report generated and sent successfully.')
    }
