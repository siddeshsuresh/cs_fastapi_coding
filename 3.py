import boto3
import json
import os

workspaces = boto3.client('workspaces')

def lambda_handler(event, context):
    print("Event:", event)
    try:
        body = json.loads(event['body'])
        users = body.get('users', [])

        created = []
        failed = []

        for email in users:
            try:
                response = workspaces.create_workspaces(
                    Workspaces=[
                        {
                            'DirectoryId': os.environ['DIRECTORY_ID'],
                            'UserName': email,
                            'BundleId': os.environ['BUNDLE_ID'],
                            'WorkspaceProperties': {
                                'RunningMode': 'AUTO_STOP',
                                'RunningModeAutoStopTimeoutInMinutes': 60
                            }
                        }
                    ]
                )
                created.append(email)
            except Exception as e:
                print(f"Failed to create workspace for {email}: {str(e)}")
                failed.append({'email': email, 'error': str(e)})

        return {
            'statusCode': 200,
            'headers': { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
            'body': json.dumps({ 'created': created, 'failed': failed })
        }
    except Exception as ex:
        return {
            'statusCode': 500,
            'body': json.dumps({ 'error': str(ex) })
        }
