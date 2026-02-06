import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from flask import Flask, request, current_app, send_file
from flask_cors import CORS
import numpy as np
import pyaudio
import wave
import shutil
import utils
import datetime
import pathlib
import logging
import db_queries
from dotenv import dotenv_values
from io import BytesIO
import json
import mido
import boto3
from botocore.exceptions import ClientError

root = logging.getLogger()
for handler in root.handlers[:]:
    root.removeHandler(handler)
root.setLevel(logging.CRITICAL)

logger = logging.getLogger("octavio")
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(handler)

app = Flask(__name__)
CORS(app)
file_counter = 0

###
instrument_info = {}
###

# Set prod-server or test-server (default=prod)
app.config['is_test'] = False

# Load environment variables
if os.path.isfile("./.env"):
	logger.info("Loading environment variables from .env")
	app.config = {
	    **app.config,
	    **dotenv_values(".env")
	}
for k, v in app.config.items():
    if str(v).strip().lower() == 'true':
        app.config[k] = True
    elif str(v).strip().lower() == 'false':
        app.config[k] = False

@app.route("/")
def hello_world():
    return 'Bingo'
    
@app.route("/heartbeat", methods=['POST'])
def add_heartbeat():
    j = request.json
    
    iid = j['instrument_id']
    now = j['time']
    instrument_info[iid] = now
    
    logger.info(f"Heartbeat receieved from piano {iid}")
    s3_client = get_aws_client()
    if not append_log_aws(
        s3_client,
        datetime.date.today(),
        {
            'instrument_id': str(iid),
            'time': str(now),
            'operation': 'ADD_HEARTBEAT'
        }
    ):
        logger.warning(f"Failed to update log for piano {iid}")
    s3_client.close()
    
    return 'Success'

@app.route("/piano", methods=['POST'])
def add_piano_music():
    is_test = current_app.config['is_test']

    j = request.json

    iid = j['instrument_id']
    session_id = j['session_id']
    chunk = j['chunk']
    messages = j['messages']
    time_recorded = j['time']
    ticks_per_beat = j['ticks_per_beat']

    logger.info(f"MIDI receieved from piano {iid} in session {session_id}")

    if app.config['USE_AWS']:
        s3_client = get_aws_client()
        if not write_midi_to_file_aws(
            s3_client, 
            utils.deserialize_midi_object(messages, ticks_per_beat), 
            get_chunk_filename_aws(iid, session_id, chunk),
            metadata={
                'chunk': str(chunk),
                'instrument_id': str(iid),
                'session_id': str(session_id),
                'time': str(time_recorded)
            }
        ):
            logger.warning(f"Failed to write chunk {chunk} for piano {iid} in session {session_id}... aborting")
        if not append_log_aws(
            s3_client,
            datetime.date.today(),
            {
                'instrument_id': str(iid),
                'session_id': str(session_id),
                'chunk': str(chunk),
                'time': str(time_recorded),
                'operation': 'ADD_CHUNK'
            }
        ):
            logger.warning(f"Failed to update log for piano {iid} in session {session_id}")
        s3_client.close()

    official_data_dir = './data'
    os.makedirs(official_data_dir, exist_ok=True)
    official_session_filename = f'{official_data_dir}/{session_id}_{iid}.mid'

    session_dir = f'./partials/instr_{iid}/session_{session_id}'
    session_exists = os.path.isdir(session_dir)
    session_populated = session_exists
    if session_exists:
        files = os.listdir(session_dir)
        running_mid_filename = next( (file for file in files if file.startswith('running') and file.endswith('.mid')), None )
        session_populated = session_populated and running_mid_filename != None
    else:
        os.makedirs(session_dir, exist_ok=True)
        logger.info(f"Session not found, starting one")

    if not session_populated:
        if session_exists:
            print("Session existed, but was corrupted (no running file found). Starting over with most recent data.)")
        current_date = str(datetime.date.today())
        date_filename = f'{session_dir}/{current_date}.txt'
        pathlib.Path(date_filename).touch()

        midi_filename = f'{session_dir}/running_0.mid'
        utils.deserialize_midi_file(msgs=messages, ticks_per_beat=ticks_per_beat, out_filename=midi_filename)
        logger.info(f"Added starting MIDI to new session")

        shutil.copyfile(midi_filename, official_session_filename)
        db_queries.add_or_refresh_db_session(session_id=session_id, instrument_id=iid, is_test=is_test)
        logger.info(f"Adding session {session_id} from instrument {iid} to DB for the first time")

        return 'Success'

    # files = os.listdir(session_dir)
    # running_mid_filename = next( (file for file in files if file.startswith('running') and file.endswith('.mid')), None )

    # if running_mid_filename is None:
    #     logger.info(f'No running file for session {session_id} found to attach to')
    #     return 'Failure'

    running_mid_filepath = f'{session_dir}/{running_mid_filename}'
    temp_mid_filepath = f'{session_dir}/temp_{chunk}.mid'
    out_filename = f'{session_dir}/running_{chunk}.mid'

    utils.deserialize_midi_file(msgs=messages, ticks_per_beat=ticks_per_beat, out_filename=temp_mid_filepath)
    utils.combine_midi(running_mid_filepath, temp_mid_filepath, output_filename=out_filename)

    for filename in (running_mid_filepath, temp_mid_filepath):
        try:
            os.remove(filename)
        except FileNotFoundError:
            logger.info(f'{filename} already deleted')
    logger.info(f"Successfully added chunk {chunk} to piano {iid}'s existing session {session_id}")

    shutil.copyfile(out_filename, official_session_filename)
    db_queries.add_or_refresh_db_session(session_id=session_id, instrument_id=iid, is_test=is_test)
    logger.info(f"Refreshing session {session_id} from instrument {iid} in DB")

    # utils.display_midi(out_filename)
    return 'Success'

@app.route("/api/instruments", methods=['GET'])
def get_instruments():
    is_test = current_app.config['is_test']
    instruments = db_queries.get_db_instruments(is_test)
    return instruments

@app.route('/api/midi', methods=['GET'])
def get_midi():
    query_params = request.args
    sid = query_params['session_id']
    iid = query_params['instrument_id']
    midi_filename = f'{sid}_{iid}.mid'
    # midi_filename = 'leit50a4t1_1.mid'
    midi_filesource = f'./data/{midi_filename}'

    if app.config['USE_AWS']:
        s3_client = get_aws_client()
        create_session_aws(s3_client, iid, sid)
        merge_chunks_aws(s3_client, iid, sid)
        purge_chunks_aws(s3_client, iid, sid)
        read_result = read_midi_from_file_aws(s3_client, get_cumulative_filename_aws(iid, sid))
        if read_result is None:
            return "MIDI file not found", 404
        else:
            midi_object, _, __ = read_result
            buffer = BytesIO()
            midi_object.save(file=buffer)
            buffer.seek(0)
            midi_filesource = buffer
        s3_client.close()

    return send_file(
        midi_filesource,
        mimetype='audio/midi',
        as_attachment=False,
        download_name=midi_filename
    )

@app.route('/api/instrument', methods=['GET'])
def get_instrument_data():
    is_test = current_app.config['is_test']
    query_params = request.args
    iid = query_params['instrument_id']
    sessions = db_queries.get_instrument_sessions(instrument_id=iid, is_test=is_test)
    return sessions
    
@app.route('/api/whatsup', methods=['GET'])
def get_whats_up():
    return instrument_info

@app.route("/keyboard", methods=['POST'])
def add_keyboard_music():
    raise NotImplementedError

@app.route("/merge", methods=['PATCH'])
def do_merge():
    if app.config['USE_AWS']:
        j = request.json
        sid = j['session_id']
        iid = j['instrument_id']
        s3_client = get_aws_client()
        create_session_aws(s3_client, iid, sid)
        success = merge_chunks_aws(s3_client, iid, sid)
        purge_chunks_aws(s3_client, iid, sid)
        s3_client.close()
        return "Success" if success else "Aborted"
    else:
        return "Aborted"

def get_aws_client():
    return boto3.client(
        's3',
        aws_access_key_id=app.config['AWS_ACCESS_KEY_ID'],
        aws_secret_access_key=app.config['AWS_SECRET_ACCESS_KEY'],
        region_name=app.config['AWS_REGION']
    )

def write_midi_to_file_aws(s3_client, midi_object, target_key, metadata={}, etag=None):
    buffer = BytesIO()
    midi_object.save(file=buffer)
    buffer.seek(0)
    try:
        if etag is not None:
            s3_client.put_object(
                Bucket=app.config['BUCKET'],
                Key=target_key,
                Body=buffer.read(),
                Metadata=metadata,
                IfMatch=etag
            )
            return True
        else:
            s3_client.put_object(
                Bucket=app.config['BUCKET'],
                Key=target_key,
                Body=buffer.read(),
                Metadata=metadata,
                IfNoneMatch='*'
            )
            return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "PreconditionFailed":
            return False
        raise

def read_midi_from_file_aws(s3_client, target_key):
    """
    Returns a tuple (midi object, metadata, etag) or None if the key doesn't exist
    """
    buffer = BytesIO()
    try:
        response = s3_client.get_object(
            Bucket=app.config['BUCKET'],
            Key=target_key
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return None
        raise
    buffer.seek(0)
    buffer = BytesIO(response['Body'].read())
    return mido.MidiFile(file=buffer), response['Metadata'], response['ETag']

def get_chunk_filename_aws(iid, session_id, chunk):
    db_type = 'prod' if app.config['IS_PROD'] else 'test'
    instrument_directory = f'ins_{iid}'
    session_directory = f'{session_id}'
    chunk_file=f'chunk_{chunk}'
    return f'{db_type}/{instrument_directory}/{session_directory}/{chunk_file}'

def get_cumulative_filename_aws(iid, session_id):
    db_type = 'prod' if app.config['IS_PROD'] else 'test'
    instrument_directory = f'ins_{iid}'
    session_directory = f'{session_id}'
    return f'{db_type}/{instrument_directory}/{session_directory}/main'

def get_log_filename_aws(date):
    db_type = 'prod' if app.config['IS_PROD'] else 'test'
    year = str(date.year)
    month = str(date.month)
    day = str(date.day)
    return f'{db_type}/logs/{year}/{month}/{day}.txt'

def append_log_aws(s3_client, date, json_object):
    """
    Appends a json object to the log file for the given day.
    Creates the log file if it doesn't exist.
    The log file is a text file where each line is a separate json object.

    Returns true on success, false on failure.
    """
    log_key = get_log_filename_aws(date)
    response = None
    etag = None
    existing_logs = ""
    try:
        response = s3_client.get_object(Bucket=app.config['BUCKET'], Key=log_key)
        buffer = BytesIO(response['Body'].read())
        existing_logs = buffer.getvalue().decode('utf-8')
        etag = response['ETag']
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            existing_logs = ""
        else:
            raise
    log_to_write = existing_logs + json.dumps(json_object) + '\n'
    try:
        if etag is None:
            s3_client.put_object(
                Bucket=app.config['BUCKET'],
                Key=log_key,
                Body=log_to_write.encode('utf-8'),
                IfNoneMatch='*',
            )
        else:
            s3_client.put_object(
                Bucket=app.config['BUCKET'],
                Key=log_key,
                Body=log_to_write.encode('utf-8'),
                IfMatch=etag,
            )
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "PreconditionFailed":
            return False
        raise


def create_session_aws(s3_client, iid, session_id):
    """
    Returns true on success, false if the session already exists
    """
    try:
        s3_client.head_object(Bucket=app.config['BUCKET'], Key=get_cumulative_filename_aws(iid, session_id))  
        logger.warning(f"Session for piano {iid} with id {session_id} already exists... aborting") 
        return False
    except ClientError as e:
        if e.response["Error"]["Code"] != "404":
            raise

    # Create file for caching combined chunks
    mid = mido.MidiFile()
    buffer = BytesIO()
    mid.save(file=buffer)
    buffer.seek(0)
    try:
        s3_client.put_object(
            Bucket=app.config['BUCKET'],
            Key=get_cumulative_filename_aws(iid, session_id),
            Body=buffer.read(),
            Metadata={
                'max_chunk': '-1',
                'instrument_id': str(iid),
                'session_id': str(session_id),
                'time_updated': datetime.datetime.now().isoformat(),
            },
            IfNoneMatch='*'
        )
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code != "PreconditionFailed":
            raise
        return False

def merge_chunks_aws(s3_client, iid, session_id):
    """
    Attempts to merge chunks.
    """
    db_type = 'prod' if app.config['IS_PROD'] else 'test'
    instrument_directory = f'ins_{iid}'
    session_directory = f'{session_id}'
    prefix = f'{db_type}/{instrument_directory}/{session_directory}/'
    response = s3_client.list_objects(Bucket=app.config['BUCKET'], Prefix=prefix, Delimiter='/')
    chunks = []
    for c in response['Contents']:
        fname = c['Key'].split('/')[-1]
        if fname.startswith('chunk_'):
            chunk = int(fname[len('chunk_'):])
            chunks.append(chunk)
    chunks.sort()
    if len(chunks) == 0:
        return True

    read_result = read_midi_from_file_aws(
        s3_client,
        get_cumulative_filename_aws(iid, session_id)
    )
    if read_result is None:
        logger.warning(f"Failed to read cumulative MIDI file... aborting merge for instrument {iid} and session {session_id}")
        return False
    cumulative_mid, metadata, etag = read_result

    merge_mid = cumulative_mid
    max_chunk = int(metadata['max_chunk'])
    for chunk in chunks:
        if chunk == max_chunk + 1:
            read_result = read_midi_from_file_aws(s3_client, get_chunk_filename_aws(iid, session_id, chunk))
            if read_result is None:
                logger.warning(f"Found missing chunk... aborting merge for instrument {iid} and session {session_id}")
                return False
            chunk_mid, chunk_meta, _ = read_result
            merge_mid = utils.combine_midi_objects(cumulative_mid, chunk_mid)
            metadata['time_updated'] = chunk_meta['time']
            max_chunk += 1
    
    metadata['max_chunk'] = str(max_chunk)
    
    return write_midi_to_file_aws(
        s3_client, 
        merge_mid, 
        get_cumulative_filename_aws(iid, session_id),
        metadata,
        etag
    )

def purge_chunks_aws(s3_client, iid, session_id):
    response = None
    try:
        response = s3_client.head_object(Bucket=app.config['BUCKET'], Key=get_cumulative_filename_aws(iid, session_id))  
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            logger.warning(f"Session for piano {iid} with id {session_id} not found... aborting")
            return False
        raise
    
    max_chunk = int(response['Metadata']['max_chunk'])

    db_type = 'prod' if app.config['IS_PROD'] else 'test'
    instrument_directory = f'ins_{iid}'
    session_directory = f'{session_id}'
    prefix = f'{db_type}/{instrument_directory}/{session_directory}/'
    response = s3_client.list_objects(Bucket=app.config['BUCKET'], Prefix=prefix, Delimiter='/')
    chunks = []
    for c in response['Contents']:
        fname = c['Key'].split('/')[-1]
        if fname.startswith('chunk_'):
            chunk = int(fname[len('chunk_'):])
            if chunk <= max_chunk:
                try:
                    s3_client.delete_object(Bucket=app.config['BUCKET'], Key=c['Key'])
                except ClientError as e:
                    if e.response["Error"]["Code"] == "NoSuchKey":
                        logger.info(f"Chunk {chunk} for piano {iid} in session {session_id} already deleted")
                        continue
                    raise
    return True