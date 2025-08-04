def lambda_handler(event, context):
    import urllib.parse

    print("Event received:", event)
    
    # Check for query param use case
    if 'queryStringParameters' in event and event['queryStringParameters']:
        bucket = 'your-bucket-name'  # Replace with your actual bucket name
        key = urllib.parse.unquote_plus(event['queryStringParameters'].get('filename', ''))
    else:
        # Fallback to S3 trigger format
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = event['Records'][0]['s3']['object']['key']

    # Download file from S3
    obj = s3.get_object(Bucket=bucket, Key=key)
    file_content = obj['Body'].read().decode('utf-8')
    reader = csv.reader(io.StringIO(file_content))

    token = get_graph_token()
    found = []
    not_found = []

    for row in reader:
        email = row[0].strip()
        if check_user_exists(email, token):
            print(f"Found: {email}")
            found.append(email)
        else:
            print(f"Not Found: {email}")
            not_found.append(email)

    return {
        'statusCode': 200,
        'body': json.dumps({
            'found': found,
            'not_found': not_found
        }),
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        }
    }
