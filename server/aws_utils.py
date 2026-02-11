import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    
import boto3
from botocore.exceptions import ClientError
from dotenv import dotenv_values
import datetime

config = {
    **dotenv_values(".env")
}
for k, v in config.items():
    if str(v).strip().lower() == 'true':
        config[k] = True
    elif str(v).strip().lower() == 'false':
        config[k] = False

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

def info_object(key):
    try:
        response = s3_client.head_object(Bucket=config['BUCKET'], Key=key)
        return response['Metadata']
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return None
        else:
            raise

def retrieve_object(key):
    try:
        response = s3_client.get_object(Bucket=config['BUCKET'], Key=key)
        return response['Body'].read()
    except ClientError as e:
        if e.response['Error']['Code'] == '404':
            return None
        else:
            raise

# def info_chunks(iid, session_id):
#     db_type = 'prod' if config['IS_PROD'] else 'test'
#     instrument_directory = f'ins_{iid}'
#     session_directory = f'{session_id}'
#     prefix = f'{db_type}/{instrument_directory}/{session_directory}/'
#     main_fname = f'{prefix}main'
#     print(config)
#     print(main_fname)

#     response = None
#     try:
#         response = s3_client.head_object(Bucket=config['BUCKET'], Key=main_fname)  
#     except ClientError as e:
#         if e.response["Error"]["Code"] == "404":
#             print(f"Session for piano {iid} with id {session_id} not found... aborting")
#             return False
#         raise
    
#     max_chunk = int(response['Metadata']['max_chunk'])
#     print(max_chunk)

#     response = s3_client.list_objects(Bucket=config['BUCKET'], Prefix=prefix, Delimiter='/')
#     chunks = []
#     for c in response['Contents']:
#         fname = c['Key'].split('/')[-1]
#         if fname.startswith('chunk_'):
#             chunk = int(fname[len('chunk_'):])
#             if chunk <= max_chunk:
#                 print(chunk, fname)
#                 pass
#                 # try:
#                 #     s3_client.delete_object(Bucket=app.config['BUCKET'], Key=fname)
#                 # except ClientError as e:
#                 #     if e.response["Error"]["Code"] == "NoSuchKey":
#                 #         logger.info(f"Chunk {chunk} for piano {iid} in session {session_id} already deleted")
#                 #         continue
#                 #     raise
#     return True

def purge_range(prefix, start, end):
    print(start.isoformat(), end.isoformat())
    for key in list_prefix(prefix):
        fname = key.split('/')[-1]
        metadata = info_object(key)
        if fname.startswith('chunk_'):
            if start <= datetime.datetime.fromisoformat(metadata['time']) <= end:
                try:
                    s3_client.delete_object(Bucket=config['BUCKET'], Key=key)
                except ClientError as e:
                    print('error')
        elif fname == 'main':
            if start <= datetime.datetime.fromisoformat(metadata['time_updated']) <= end:
                try:
                    s3_client.delete_object(Bucket=config['BUCKET'], Key=key)
                except ClientError as e:
                    print('error')
        else:
            print('error')

            

if __name__ == '__main__':
    # purge_prefix('test/ins_10/u')
    # print(len(a))
    # print(len(b))
    print(list_prefix('test/logs'))
    # print(retrieve_object('test/logs/2026/2/7.txt').split('\n'))
    # print(info_object('test/ins_10/ygaudr663g/chunk_1'))
    # info_chunks('10', '99s2zk413r')
    # purge_range('test/ins_10', datetime.datetime(2026, 2, 3, 0, 0, 1), datetime.datetime(2026, 2, 5, 23, 59))
