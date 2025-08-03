import json
import boto3
import os
import urllib.parse

s3 = boto3.client('s3')
BUCKET_NAME = 'workspace-csv-uploader-secure'  # Update if needed

def lambda_handler(event, context):
    params = event.get('queryStringParameters', {})
    filename = params.get('filename')
    
    if not filename:
        return {
            'statusCode': 400,
            'body': 'Missing filename'
        }

    # Optional: sanitize the filename
    filename = urllib.parse.quote(filename)
    object_key = f"uploads/{filename}"

    url = s3.generate_presigned_url('put_object',
        Params={'Bucket': BUCKET_NAME, 'Key': object_key, 'ContentType': 'text/csv'},
        ExpiresIn=900  # 15 mins
    )

    return {
        'statusCode': 200,
        'headers': { 'Access-Control-Allow-Origin': '*' },
        'body': url
    }
