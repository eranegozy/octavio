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
    
    return 'Success'

@app.route("/piano", methods=['POST'])
def add_piano_music():
    is_test = current_app.config['is_test']

    j = request.json

    iid = j['instrument_id']
    session_id = j['session_id']
    chunk = j['chunk']
    messages = j['messages']
    ticks_per_beat = j['ticks_per_beat']

    logger.info(f"MIDI receieved from piano {iid} in session {session_id}")

    if app.config['USE_AWS']:
        s3_client = get_aws_client()
        write_midi_to_file_aws(
            s3_client, 
            utils.deserialize_midi_object(messages, ticks_per_beat), 
            get_chunk_filename_aws(iid, session_id, chunk)
        )
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
    midi_filepath = f'./data/{midi_filename}'

    if app.config['USE_AWS']:
        s3_client = get_aws_client()
        merge_chunks_aws(s3_client, iid, sid)
        s3_client.close()

    return send_file(
        midi_filepath,
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
        success = merge_chunks_aws(s3_client, iid, sid)
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

def write_midi_to_file_aws(s3_client, midi_object, target_key, etag=None):
    buffer = BytesIO()
    midi_object.save(file=buffer)
    buffer.seek(0)
    try:
        if etag is not None:
            s3_client.put_object(
                Bucket=app.config['BUCKET'],
                Key=target_key,
                Body=buffer.read(),
                IfMatch=etag
            )
            return True
        else:
            s3_client.put_object(
                Bucket=app.config['BUCKET'],
                Key=target_key,
                Body=buffer.read(),
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
    Returns a tuple (midi object, etag) or None if the key doesn't exist
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
    return mido.MidiFile(file=buffer), response['ETag']

def get_chunk_filename_aws(iid, session_id, chunk):
    db_type = 'prod' if app.config['IS_PROD'] else 'test'
    instrument_directory = f'ins_{iid}'
    session_directory = f'{session_id}'
    chunk_file=f'chunk_{chunk}'
    return f'{db_type}/{instrument_directory}/{session_directory}/{chunk_file}'

def get_meta_filename_aws(iid, session_id):
    db_type = 'prod' if app.config['IS_PROD'] else 'test'
    instrument_directory = f'ins_{iid}'
    session_directory = f'{session_id}'
    return f'{db_type}/{instrument_directory}/{session_directory}/meta'

def get_cumulative_filename_aws(iid, session_id, version_number):
    db_type = 'prod' if app.config['IS_PROD'] else 'test'
    instrument_directory = f'ins_{iid}'
    session_directory = f'{session_id}'
    return f'{db_type}/{instrument_directory}/{session_directory}/main_{version_number}'

def create_session_aws(s3_client, iid, session_id):
    # Create meta file
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta_dict = {
        'max_chunk_processed': -1,
        'time_created': now,
        'last_updated': now,
        'version_number': 0,
    }
    try:
        s3_client.put_object(
            Bucket=app.config['BUCKET'],
            Key=get_meta_filename_aws(iid, session_id),
            Body=json.dumps(meta_dict).encode('utf-8'),
            IfNoneMatch='*'
        )
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code != "PreconditionFailed":
            raise
    
    prefix = get_cumulative_filename_aws(iid, session_id, 0)[:-1]
    response = s3_client.list_objects(Bucket=app.config['BUCKET'], Prefix=prefix, Delimiter='/')
    if 'Contents' in response and len(response['Contents']) > 0:
        # main MIDI file already exists
        return

    # Create file for caching combined chunks
    mid = mido.MidiFile()
    buffer = BytesIO()
    mid.save(file=buffer)
    buffer.seek(0)
    try:
        s3_client.put_object(
            Bucket=app.config['BUCKET'],
            Key=get_cumulative_filename_aws(iid, session_id, 0),
            Body=buffer.read(),
            IfNoneMatch='*'
        )
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code != "PreconditionFailed":
            raise

def get_session_meta_aws(s3_client, iid, session_id):
    """
    Returns a tuple (json object, etag) or None if the key doesn't exist
    """
    try:
        response = s3_client.get_object(
            Bucket=app.config['BUCKET'],
            Key=get_meta_filename_aws(iid, session_id)
        )
        return json.loads(response['Body'].read().decode("utf-8")), response['ETag']
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return None
        raise

def set_session_meta_aws(s3_client, iid, session_id, meta_dict, etag):
    try:
        s3_client.put_object(
            Bucket=app.config['BUCKET'],
            Key=get_meta_filename_aws(iid, session_id),
            Body=json.dumps(meta_dict).encode('utf-8'),
            IfMatch=etag
        )
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "PreconditionFailed":
            return False
        raise

def merge_chunks_aws(s3_client, iid, session_id):
    """
    Attempts to merge chunks. The write to the meta file for the session is the commit point.
    """
    read_result = get_session_meta_aws(s3_client, iid, session_id)
    if read_result is None:
        logger.warning(f"Failed to read meta file... aborting merge for instrument {iid} and session {session_id}")
        return False
    meta_dict, meta_etag = read_result

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
        elif fname.startswith('main_'):
            version = int(fname[len('main_'):])
            if version != meta_dict['version_number']:
                # it may be possible to see higher version numbers if the write to the meta didn't go through
                s3_client.delete_object(Bucket=app.config['BUCKET'], Key=get_cumulative_filename_aws(iid, session_id, version))
    chunks.sort()
    if len(chunks) == 0:
        return True

    read_result = read_midi_from_file_aws(
        s3_client,
        get_cumulative_filename_aws(iid, session_id, meta_dict['version_number'])
    )
    if read_result is None:
        logger.warning(f"Failed to read cumulative MIDI file... aborting merge for instrument {iid} and session {session_id}")
        return False
    cumulative_mid, _ = read_result

    merge_mid = cumulative_mid
    for chunk in chunks:
        if chunk <= meta_dict['max_chunk_processed']:
            s3_client.delete_object(Bucket=app.config['BUCKET'], Key=get_chunk_filename_aws(iid, session_id, chunk))
        elif chunk == meta_dict['max_chunk_processed'] + 1:
            read_result = read_midi_from_file_aws(s3_client, get_chunk_filename_aws(iid, session_id, chunk))
            if read_result is None:
                logger.warning(f"Found missing chunk... aborting merge for instrument {iid} and session {session_id}")
                return False
            chunk_mid, _ = read_result
            merge_mid = utils.combine_midi_objects(cumulative_mid, chunk_mid)
            meta_dict['max_chunk_processed'] = chunk
    
    meta_dict['version_number'] += 1
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    meta_dict['last_updated'] = now
    if write_midi_to_file_aws(
        s3_client, 
        merge_mid, 
        get_cumulative_filename_aws(iid, session_id, meta_dict['version_number'])
    ):
        return set_session_meta_aws(s3_client, iid, session_id, meta_dict, meta_etag)
    else:
        return False

