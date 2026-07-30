"""Main Octavio client — records audio, extracts MIDI on-device, and transmits to server.

Runs on a Raspberry Pi connected to an audio recording device. Manages recording
sessions, silence detection, user-triggered privacy mode via a physical button,
and a background heartbeat thread. Raw audio never leaves the device; only
serialized MIDI JSON is sent to the server.

Note: documentation in this file was written with assistance from AI tools.
"""

import os
import sys
import logging
import threading
import time
import json
import signal
import datetime
import asyncio
from pathlib import Path

import requests                         # pip install requests
from dotenv import load_dotenv          # pip install python-dotenv

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from amt import get_amt_model
from session_manager import get_session_manager

from amt_basic_pitch import BP_REQUIRED_KEYS
from amt_transkun import TK_REQUIRED_KEYS
CLIENT_REQUIRED_KEYS = {
    'RED_PIN', 'GREEN_PIN', 'BUTTON_PIN', 
    'DO_RECORDING', 'RECORDING_PARAMS.RECORDING_SESSION_MODE', 'RECORDING_PARAMS.CHUNK_SECS', 'RECORDING_PARAMS.SESSION_CAP_MINUTES', 'RECORDING_PARAMS.SILENCE_THRESHOLD', 'RECORDING_PARAMS.PRIVACY_MINUTES', 
    'DO_HEARTBEAT', 
    'DO_TRANSCRIPTION', 'TRANSCRIPTION_PARAMS.KEEP_TRANSCRIBED_AUDIO', 'TRANSCRIPTION_PARAMS.AMT_MODEL', 
    'DO_UPLOAD', 'UPLOAD_PARAMS.NUM_SERVER_ATTEMPTS', 'UPLOAD_PARAMS.SERVER_RETRY_WAIT_SECONDS', 'UPLOAD_PARAMS.SERVER_FAILURE_WAIT_SECONDS', 'UPLOAD_PARAMS.HARDWARE_INTERACTION_WAIT_SECONDS',
    'SERVER_URL'
}

# set up Octavio logger
logging.basicConfig(
    level=logging.WARNING,  # Let third-party libraries report warnings/errors
    handlers=[logging.NullHandler()],  # Don't let the root logger spam stdout/stderr
    force=True  # Automatically purges any pre-existing root handlers safely
)

logger = logging.getLogger("octavio")
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(handler)

def flatten_json(nested_json, separator='.'):
    out = {}
    
    def flatten(x, name=''):
        if isinstance(x, dict):
            for a in x:
                flatten(x[a], f"{name}{a}{separator}")
        elif isinstance(x, list):
            for i, a in enumerate(x):
                flatten(a, f"{name}{i}{separator}")
        else:
            out[name[:-1]] = x

    flatten(nested_json)
    return out

def load_configs():
    script_dir = Path(__file__).parent
    config_json_dir = script_dir / "config.json"
    logger.info(f"Loading client config from {config_json_dir}")
    try:
        with open(config_json_dir, "r") as file:
            config = json.load(file)
        logger.info("Successfully loaded client config")
    except Exception as e:
        logger.error(f"Failed to load client config: {e}")

    dotenv_dir = script_dir / ".env"

    logger.info(f"Loading environment variables from {dotenv_dir}")
    try:
        load_dotenv(dotenv_dir)
        config.update(dict(os.environ))
        logger.info("Successfully loaded client environment variables")
    except Exception as e:
        logger.error(f"Failed to load client environment variables: {e}")

    return config


def validate_configs(config: dict, required_keys: set) -> None:
    missing = required_keys - config.keys()
    if missing:
        raise SystemExit(f"Missing configs: {sorted(missing)}")
    else:
        logger.info("All required configs found")


class OctavioClient:
    """Orchestrates audio capture, on-device MIDI extraction, and server transmission.

    Class-level constants define audio format, chunk duration, session limits,
    silence thresholds, privacy timeout, and server retry behavior. Calibration
    stats are loaded from infra.json at startup if available; defaults are used
    otherwise.
    """

    def __init__(
        self, 
        *,
        do_recording: bool, 
        recording_session_mode: str | None,
        do_heartbeat: bool, 
        do_transcription: bool,
        amt_model: str | None,
        keep_transcribed_audio: bool | None,
        do_upload: bool,
        server_url: str | None
    ):
        self.session_id = None
        
        self.do_heartbeat = do_heartbeat

        self.do_recording = do_recording
        if do_recording and recording_session_mode is None:
            raise ValueError("RECORDING_SESSION_MODE is required when DO_RECORDING is true")
        self.recording_session_mode = recording_session_mode
        
        self.do_transcription = do_transcription
        if do_transcription and amt_model is None:
            raise ValueError("AMT_MODEL is required when DO_TRANSCRIPTION is true")
        self.amt_model = amt_model
        if do_transcription and keep_transcribed_audio is None:
            raise ValueError("KEEP_TRANSCRIBED_AUDIO is required when DO_TRANSCRIPTION is true")
        self.keep_transcribed_audio = keep_transcribed_audio

        self.do_upload = do_upload

        if server_url:
            self.use_server = True
            self.server_url = server_url
            self.midi_path = '/piano'
            self.heartbeat_path = '/heartbeat'
            self.midi_endpoint_url = f'{self.server_url}{self.midi_path}'
            self.heartbeat_endpoint_url = f'{self.server_url}{self.heartbeat_path}'
        else:
            self.use_server = False

        # The atomic flag to signal all threads to exit
        self.exit_flag = threading.Event()
        
        # Register both SIGINT and SIGTERM to the same cleanup mechanism
        signal.signal(signal.SIGINT, self.handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self.handle_shutdown_signal)

        if self.do_heartbeat:
            self.heartbeat_thread = threading.Thread(target = self.run_heartbeat, daemon=True)
        if self.do_recording:
#            self.session_manager_thread = threading.Thread(target = self.run_session_manager, daemon=True) #TODO: currently unused, session manager is fully synchronous and updates when called instead of being a thread
            self.recording_thread = threading.Thread(target = self.run_recording, daemon=False)             # Must finish before program exit, no partial recordings
        if self.do_transcription:
            self.transcription_thread = threading.Thread(target = self.run_transcription, daemon=False)     # Must finish before program exit, no partial transcriptions
        if self.do_upload:
            self.upload_thread = threading.Thread(target = self.run_upload, daemon=False)                   # Must finish before program exit, no partial uploads
    
    def start(self):
        logger.info("Starting client")

        self.session_manager = get_session_manager()
        logger.info("Started session manager")

        if self.do_heartbeat:
            self.heartbeat_thread.start()
            logger.info("Started heartbeat")

        if self.do_recording:
            self.recording_thread.start()
            logger.info("Started recording")

        if self.do_transcription:
            self.Model = get_amt_model(self.amt_model)
            self.transcription_thread.start()
            logger.info("Started transcription")

        if self.do_upload:
            self.upload_thread.start()

    def handle_shutdown_signal(self, signum, frame):
        logger.info(f'Received signal {signum}. Shutting down...')
        self.exit_flag.set()
    
    def run_heartbeat(self):
        logger.info("Heartbeat script running")
        while not self.exit_flag.wait(timeout=30):
            if self.use_server:
                logger.info(f"Sending heartbeat to {self.heartbeat_endpoint_url}")
                request_data = {
                    'time': datetime.datetime.now().isoformat(),
                    'session': self.session_id,
                }
                headers = {
                    'Content-Type': 'application/json'
                }
                try:
                    r = requests.post(
                        self.heartbeat_endpoint_url,
                        json=request_data,
                        headers=headers,
                        timeout=10
                    )
                except Exception as e:
                    logger.info(f"Failed to send heartbeat: {e}")
                else:
                    logger.info("Successfully sent heartbeat")
            else:
                logger.info(f"Local heartbeat message at time {datetime.datetime.now().isoformat()}")
                        
        logger.info("Heartbeat script exiting")
    
    def run_session_manager(self): #TODO: currently unused, current session manager is fully synchronous and only updates on actions involving session state
        session_manager = get_session_manager()
        while not self.exit_flag.wait(timeout=4):
            logger.info("I'm managing the session")
            session_manager.handle_recording_activity()
        logger.info("Session manager successfully exited")

    def run_recording(self):
        while not self.exit_flag.wait(timeout=5):
            logger.info("I'm recording")
        logger.info("Recording successfully exited")

    def run_transcription(self):
        while not self.exit_flag.wait(timeout=6):
            logger.info("I'm transcribing")
        logger.info("Transcription successfully exited")

    def run_upload(self):
        while not self.exit_flag.wait(timeout=7):
            logger.info("I'm uploading")
        logger.info("Uploading successfully exited")


if __name__ == '__main__':

    config = flatten_json(load_configs())

    required_keys = CLIENT_REQUIRED_KEYS | BP_REQUIRED_KEYS | TK_REQUIRED_KEYS

    validate_configs(config, required_keys)

    if config["SERVER_URL"] == "":
        config["SERVER_URL"] = None
        logger.warning("Environment field SERVER_URL empty, launching client without pinging server. Heartbeat and MIDI uploads will not occur for this session.")

    client = OctavioClient(
        do_recording=config["DO_RECORDING"],
        recording_session_mode=config["RECORDING_PARAMS.RECORDING_SESSION_MODE"],
        do_heartbeat=config["DO_HEARTBEAT"],
        do_transcription=config["DO_TRANSCRIPTION"],
        amt_model=config["TRANSCRIPTION_PARAMS.AMT_MODEL"],
        keep_transcribed_audio=config["TRANSCRIPTION_PARAMS.KEEP_TRANSCRIBED_AUDIO"],
        do_upload=config["DO_UPLOAD"],
        server_url=config["SERVER_URL"]
    )
    client.start()