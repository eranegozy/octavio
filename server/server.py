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
    
    ###
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    instrument_info[iid] = now
    ###

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
