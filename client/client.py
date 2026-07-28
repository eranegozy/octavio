"""Main Octavio client — records audio, extracts MIDI on-device, and transmits to server.

Runs on a Raspberry Pi connected to an audio recording device. Manages recording
sessions, silence detection, user-triggered privacy mode via a physical button,
and a background heartbeat thread. Raw audio never leaves the device; only
serialized MIDI JSON is sent to the server.

Note: documentation in this file was written with assistance from AI tools.
"""

import os
import sys

# from amt import AMTModel, get_amt_model

import logging
import threading
import time
import json
import signal
import datetime
import requests
import asyncio

# Import configs
DEFAULTS = {
    "DO_RECORDING": True,
    "RECORDING_SESSION_MODE": "continuous",

    "DO_HEARTBEAT": True,

    "DO_TRANSCRIPTION": True,
    "AMT_MODEL": "basic_pitch",
    "KEEP_TRANSCRIBED_AUDIO": False,
    "SERVER_URL": None
}

config = DEFAULTS.copy()
try:
    with open("client/config.json", "r") as file:
        data = json.load(file)
        config.update(data)
except FileNotFoundError:
    logging.warning(f"Client config.json not found, using system defaults.")


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
        server_url: str | None
    ):
        self.do_recording = do_recording
        if do_recording and recording_session_mode is None:
            raise ValueError("RECORDING_SESSION_MODE is required when DO_RECORDING is true")
        self.recording_session_mode = recording_session_mode

        self.do_heartbeat = do_heartbeat
        
        self.do_transcription = do_transcription
        if do_transcription and amt_model is None:
            raise ValueError("AMT_MODEL is required when DO_TRANSCRIPTION is true")
        self.amt_model = amt_model
        if do_transcription and keep_transcribed_audio is None:
            raise ValueError("KEEP_TRANSCRIBED_AUDIO is required when DO_TRANSCRIPTION is true")
        self.keep_transcribed_audio = keep_transcribed_audio

        self.server_url = server_url
        self.midi_path = '/piano'
        self.heartbeat_path = '/heartbeat'
        self.midi_endpoint_url = f'{self.server_url}{self.midi_path}'
        self.heartbeat_endpoint_url = f'{self.server_url}{self.heartbeat_path}'

        # The atomic flag to signal all threads to exit
        self.exit_flag = threading.Event()
        
        # Register both SIGINT and SIGTERM to the same cleanup mechanism
        signal.signal(signal.SIGINT, self.handle_shutdown_signal)
        signal.signal(signal.SIGTERM, self.handle_shutdown_signal)
    
    def start(self):
        logging.info("Starting client")

        if self.do_heartbeat:
            self.heartbeat_thread = threading.Thread(target = self.run_heartbeat, daemon=True)
            self.heartbeat_thread.start()
            logging.info("Started heartbeat")

        if self.do_transcription:
            # self.Model = get_amt_model(self.amt_model)
            self.transcription_thread = threading.Thread(target = self.run_transcription, daemon=False) # Must finish before program exit, no partial transcriptions
            self.transcription_thread.start()
            logging.info("Started transcription")
    
        if self.do_recording:
            self.session_manager_thread = threading.Thread(target = self.run_session_manager, daemon=True)
            self.session_manager_thread.start()
            logging.info("Started session manager")

            self.recording_thread = threading.Thread(target = self.run_recording, daemon=False)         # Must finish before program exit, no partial recordings
            self.recording_thread.start()
            logging.info("Started recording")

    def handle_shutdown_signal(self):
        logger.info('System shutting down')
        self.exit_flag.set()
        
    
    async def run_heartbeat(self):
        logger.info("Heartbeat script running")
        while not self.exit_flag.wait(timeout=30):
            logger.info("Sending heartbeat")
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
                        
        logger.info("Heartbeat script exiting")
        while(True):
            print("Badum tssss")
            time.sleep(3)

    async def run_transcription(self):
        raise NotImplementedError
    
    async def run_session_manager(self):
        raise NotImplementedError
    
    async def run_recording(self):
        while(True):
            print("I'm recording")
            time.sleep(30)


if __name__ == '__main__':
    print(config)
    client = OctavioClient(
        do_recording=config["DO_RECORDING"],
        recording_session_mode=config["RECORDING_SESSION_MODE"],
        do_heartbeat=config["DO_HEARTBEAT"],
        do_transcription=config["DO_TRANSCRIPTION"],
        amt_model=config["AMT_MODEL"],
        keep_transcribed_audio=config["KEEP_TRANSCRIBED_AUDIO"],
        server_url=config["SERVER_URL"]
    )
    client.start()
