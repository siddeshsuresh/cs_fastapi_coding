import boto3
import csv
import io
import requests
import os
import json

s3 = boto3.client('s3')
secrets = boto3.client('secretsmanager')

def get_graph_token():
    secret = secrets.get_secret_value(SecretId='azure-ad-auth')
    creds = json.loads(secret['SecretString'])

    url = f"https://login.microsoftonline.com/{creds['tenant_id']}/oauth2/v2.0/token"
    payload = {
        'grant_type': 'client_credentials',
        'client_id': creds['client_id'],
        'client_secret': creds['client_secret'],
        'scope': 'https://graph.microsoft.com/.default'
    }

    response = requests.post(url, data=payload)
    return response.json().get('access_token')

def check_user_exists(email, token):
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(
        f'https://graph.microsoft.com/v1.0/users/{email}',
        headers=headers
    )
    return response.status_code == 200

def lambda_handler(event, context):
    # Extract file info
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    obj = s3.get_object(Bucket=bucket, Key=key)
    file_content = obj['Body'].read().decode('utf-8')

    reader = csv.reader(io.StringIO(file_content))
    token = get_graph_token()

    found = []
    not_found = []

    for row in reader:
        email = row[0].strip()
        if check_user_exists(email, token):
            print(f"✅ Found: {email}")
            found.append(email)
        else:
            print(f"❌ Not Found: {email}")
            not_found.append(email)

    return {
        'statusCode': 200,
        'body': {
            'found': found,
            'not_found': not_found
        }
    }
