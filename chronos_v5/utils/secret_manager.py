# chronos_v5/utils/secret_manager.py
import os
import json
import boto3
from botocore.exceptions import ClientError
from chronos_v5.logger_setup import logger

def get_secret(secret_name: str, region_name: str = None) -> dict:
    if not region_name:
        region_name = os.getenv("AWS_REGION", "us-east-1")
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    try:
        response = client.get_secret_value(SecretId=secret_name)
        if 'SecretString' in response:
            return json.loads(response['SecretString'])
        else:
            return json.loads(response['SecretBinary'])
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            logger.warning(f"Secret {secret_name} not found in AWS Secrets Manager")
        else:
            logger.error(f"Error fetching secret {secret_name}: {e}")
        return {}
