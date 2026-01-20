import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    
import boto3
from botocore.exceptions import ClientError
from dotenv import dotenv_values

config = {
    **dotenv_values(".env")
}

s3_client = boto3.client(
    's3',
    aws_access_key_id=config['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=config['AWS_SECRET_ACCESS_KEY'],
    region_name=config['AWS_REGION']
)
def list_prefix(prefix):
    response = s3_client.list_objects(Bucket=config['BUCKET'], Prefix=prefix)
    if 'Contents' in response:
        return [c['Key'] for c in response['Contents']]
    else:
        return []

def purge_prefix(prefix):
    for key in list_prefix(prefix):
        try:
            s3_client.delete_object(Bucket=config['BUCKET'], Key=key)
        except ClientError as e:
            continue

if __name__ == '__main__':
    # purge_prefix('test/ins_10/u')
    # print(list_prefix('test'))