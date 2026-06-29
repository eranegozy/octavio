"""Main Octavio client — records audio, extracts MIDI on-device, and transmits to server.

Runs on a Raspberry Pi connected to an audio recording device. Manages recording
sessions, silence detection, user-triggered privacy mode via a physical button,
and a background heartbeat thread. Raw audio never leaves the device; only
serialized MIDI JSON is sent to the server.

Note: documentation in this file was written with assistance from AI tools.
"""

import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import log_utils
import logging
# import RPi.GPIO as GPIO
import pyaudio
import math
import time
import threading
import requests
import datetime
from dotenv import dotenv_values
import numpy as np
import shutil
import signal
# import infra
import json
from hardware import OctavioHardware
import utils
with log_utils.no_stderr():
    from basic_pitch import build_icassp_2022_model_path, FilenameSuffix
    from basic_pitch.inference import predict_and_save, Model

root = logging.getLogger()
for handler in root.handlers[:]:
    root.removeHandler(handler)
root.setLevel(logging.CRITICAL)

logger = logging.getLogger("octavio")
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(handler)

# placeholder, should set up .env
config = {
    'DO_RECORD': True,
    'DO_HEARTBEAT': True,
    'RESEARCH_MODE': False,
    'SERVER_URL': None,
}
if os.path.isfile("./.env"):
    logger.info("Loading environment variables from .env")
    config = { **dotenv_values(".env") }

# Sanitize string inputs into boolean
for k, v in config.items():
    if str(v).strip().lower() == 'true':
        config[k] = True
    elif str(v).strip().lower() == 'false':
        config[k] = False

class OctavioClient:
    """Orchestrates audio capture, on-device MIDI extraction, and server transmission.

    Class-level constants define audio format, chunk duration, session limits,
    silence thresholds, privacy timeout, and server retry behavior. Calibration
    stats are loaded from infra.json at startup if available; defaults are used
    otherwise.
    """

    format = pyaudio.paInt16
    num_channels = 1
    sampling_rate = 22050
    chunk_secs = 30
    session_cap_minutes = 45
    silence_threshold = 10
    privacy_minutes = 30
    num_server_attempts = 3
    server_retry_wait_seconds = 15
    server_failure_wait_seconds = 60
    hardware_interaction_wait_seconds = 1.5

    default_noise_quartiles = (3.80, 3.85, 4.00)
    default_noise_mean = 4.14
    default_noise_std = 2.26
    default_signal_quartiles = (9.70, 34.39, 91.24)
    default_signal_mean = 73.10
    default_signal_std = 125.83

    temp_dir = './temps'
    pending_audio_dir = './pending-audio'
    transcription_dir = './transcription'
    finished_audio_dir = './finished-audio'

    server_url = config['SERVER_URL']
    midi_endpoint_url = '/piano'
    heartbeat_endpoint_url = '/heartbeat'
    midi_request_url = f'{server_url}{midi_endpoint_url}'
    heartbeat_request_url = f'{server_url}{heartbeat_endpoint_url}'

    def __init__(self):
        """Loads config from infra.json, initializes hardware, and warms up the AMT model."""

        # Initialize hardware

        self.hardware = OctavioHardware()
        self.hardware.shine_green()
        signal.signal(signal.SIGTERM, lambda signum, frame: self.on_shutdown())
        signal.signal(signal.SIGINT, lambda signum, frame: self.on_shutdown())

        # Start session

        self.privacy_last_requested = None
        self.last_hardware_interaction = time.time()
        self.is_recording = True
        self.stream = None

        self.session = utils.generate_id()
        self.chunks_sent = 0
        self.silence = 0
        self.end_stream_flag = False

        # Load PyAudio
        
        with log_utils.no_stderr():
            self.audio = pyaudio.PyAudio()

        # Load infra.json values

        with open('./infra.json', 'r') as f:
            self.infra = json.load(f)

        self.instrument_id = self.infra['INSTRUMENT_ID']
        if 'RECORDING_DEVICE_INDEX' in self.infra:
            self.device_index = self.infra['RECORDING_DEVICE_INDEX']
        else:
            self.device_index = self.identify_recording_device()

        if 'NOISE_25TH_PERCENTILE' in self.infra:
            self.noise_quartiles = (
                self.infra['NOISE_25TH_PERCENTILE'],
                self.infra['NOISE_50TH_PERCENTILE'],
                self.infra['NOISE_75TH_PERCENTILE']
            )
            self.noise_mean = self.infra['NOISE_MEAN']
            self.noise_std = self.infra['NOISE_STD']

            self.signal_quartiles = (
                self.infra['SIGNAL_25TH_PERCENTILE'],
                self.infra['SIGNAL_50TH_PERCENTILE'],
                self.infra['SIGNAL_75TH_PERCENTILE']
            )
            self.signal_mean = self.infra['SIGNAL_MEAN']
            self.signal_std = self.infra['SIGNAL_STD']
        else:
            self.noise_quartiles = self.default_noise_quartiles
            self.noise_mean = self.default_noise_mean
            self.noise_std = self.default_noise_std
            self.signal_quartiles = self.default_signal_quartiles
            self.signal_mean = self.default_signal_mean
            self.signal_std = self.default_signal_std

        if os.path.isdir(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        os.makedirs(self.temp_dir, exist_ok=True)

        os.makedirs(self.pending_audio_dir, exist_ok=True)
        os.makedirs(self.transcription_dir, exist_ok=True)

        if config.get('RESEARCH_MODE', False):
            logger.info(f"Research mode enabled, finished recordings will be preserved in {self.finished_audio_dir}")
            os.makedirs(self.finished_audio_dir, exist_ok=True)


        # Initializing model

        _tflite_path = build_icassp_2022_model_path(FilenameSuffix.tflite)
        self.bp_model = Model(_tflite_path)

        logger.info("AMT model attempting to warm up")

        warmup_frames = np.zeros(self.sampling_rate)
        warmup_filename = f'{self.temp_dir}/warmup.wav'
        utils.write_wav(warmup_frames, warmup_filename)
        warmup_midi = utils.convert_to_midi_bp(input_audio=warmup_filename, output_dir=self.temp_dir, bp_model=self.bp_model)
        os.remove(warmup_midi)

        logger.info("AMT model successfully warmed up")

        # try:
        #     self.device_index = infra.RECORDING_DEVICE_INDEX
        # except NameError:
        #     self.device_index = self.identify_recording_device()

        logger.info("System initialized successfully")
        logger.info(f"System starting session is {self.session}")

        # heartbeat
        self.heartbeat_thread = threading.Thread(target = self.heartbeat, daemon=True)
        self.exit_flag = threading.Event()

        # transcription worker (drains the pending-audio queue on its own thread)
        self.transcription_thread = threading.Thread(target = self.transcription_worker, daemon=True)

    def on_shutdown(self):
        """SIGTERM/SIGINT handler. Deactivates LEDs, signals threads, and exits."""
        logger.info('System shutting down, performing hardware teardown')
        self.hardware.deactivate_light()
        self.exit_flag.set()
        sys.exit(0)

    def create_new_session(self):
        """Generates a new session ID and resets chunk and silence counters."""
        session_id = utils.generate_id()
        logger.info(f"Creating new session {session_id}")

        self.session = session_id
        self.chunks_sent = 0
        self.silence = 0

    def end_stream(self):
        """Creates a new session and closes the current audio stream."""
        self.create_new_session()

        logger.info("System closing audio stream")
        self.stream.close()
        self.stream = None

    def update_session(self, current_time):
        """Checks end-of-session conditions and handles button presses.

        Sets end_stream_flag if the silence threshold or session cap is reached.
        Toggles privacy mode on/off when the button is pressed with debounce.

        Args:
            current_time (float): Current time.time() value.
        """
        session_duration = (self.chunks_sent * self.chunk_secs) / 60
        if (
            (self.silence >= self.silence_threshold and self.chunks_sent > 0) or
            (session_duration >= self.session_cap_minutes)
        ):
            self.end_stream_flag = True
        elif (self.hardware.button_pressed and
              self.is_recording and
              current_time - self.last_hardware_interaction >= self.hardware_interaction_wait_seconds
        ):
            self.privacy_last_requested = current_time
            self.last_hardware_interaction = current_time
            self.end_stream_flag = True
            logger.info(f"User requested privacy")
        elif (
            self.hardware.button_pressed and
            not self.is_recording and
            current_time - self.last_hardware_interaction >= self.hardware_interaction_wait_seconds
        ):
            self.privacy_last_requested = None
            self.last_hardware_interaction = current_time
            logger.info(f"User de-requested privacy")

    def refresh_client_state(self):
        """Updates session state and syncs the LED color to the current recording status."""
        current_time = time.time()
        self.update_session(current_time)

        self.is_recording = (
            self.privacy_last_requested is None or
            (current_time - self.privacy_last_requested) / 60 >= self.privacy_minutes
        )
        self.hardware.shine_green() if self.is_recording else self.hardware.shine_red()

    def identify_recording_device(self):
        """Prints available audio input devices and prompts the user to select one.

        Returns:
            int: The selected device index.
        """
        print("----------------------Recording device list---------------------")

        info = self.audio.get_host_api_info_by_index(0)
        num_devices = info.get('deviceCount')
        for i in range(0, num_devices):
            if (self.audio.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
                print("Input Device id ", i, " - ", self.audio.get_device_info_by_host_api_device_index(0, i).get('name'))
        print("-------------------------------------------------------------")

        device_index = int(input())
        return device_index

    def record_audio(self):
        """Opens a PyAudio stream that enqueues 30-second chunks via mic_callback.

        Each non-silent chunk is denoised and written to the pending-audio
        queue directory; transcription and server transmission happen later,
        off this thread, in transcription_worker.

        Returns:
            pyaudio.Stream: The active audio input stream.
        """
        def mic_callback(input_data, frame_count, time_info, flags):
            now = datetime.datetime.now()

            if utils.is_silent(input_data):
                logger.info("Audio chunk was silent, skipping recording")
                self.silence += self.chunk_secs
                return None, pyaudio.paContinue

            self.silence = 0
            input_array = np.frombuffer(input_data, dtype=np.int16).astype(np.float64)

            logger.info("Queuing audio chunk for transcription")
            utils.save_pending_audio(
                input_data=input_array,
                noise_quartiles=self.noise_quartiles,
                signal_quartiles=self.signal_quartiles,
                pending_dir=self.pending_audio_dir,
                session_id=self.session,
                chunk=self.chunks_sent,
                device_index=self.device_index,
                timestamp=now
            )
            self.chunks_sent += 1
            return None, pyaudio.paContinue

        chunk_frames = int(math.ceil(self.chunk_secs * self.sampling_rate))
        stream = self.audio.open(
                            input=True,
                            input_device_index=self.device_index,
                            format=self.format,
                            channels=self.num_channels,
                            rate=self.sampling_rate,
                            frames_per_buffer=chunk_frames,
                            stream_callback=mic_callback
        )
        return stream

    def run(self):
        """Main loop. Opens and manages the audio stream based on recording state."""
        logger.info("Client running")
        while True:
            self.refresh_client_state()
            if self.stream is None and self.is_recording and config['DO_RECORD']:
                logger.info("System starting a new audio stream")
                self.stream = self.record_audio()
            elif self.end_stream_flag:
                self.end_stream_flag = False
                self.end_stream()
    
    def run_heartbeat(self):
        """Starts the heartbeat daemon thread."""
        self.heartbeat_thread.start()

    def run_transcription_worker(self):
        """Starts the transcription daemon thread."""
        self.transcription_thread.start()

    def transcription_worker(self):
        """Drains the pending-audio queue, oldest file first, until the exit flag is set.

        Pending-audio filenames are timestamp-prefixed (see
        utils.make_pending_audio_filename), so an alphabetical directory
        listing is equivalent to chronological recording order across all
        sessions. This keeps recording (mic_callback) decoupled from the
        comparatively slow AMT transcription step.
        """
        logger.info("Transcription worker running")
        while not self.exit_flag.is_set():
            pending_files = sorted(
                f for f in os.listdir(self.pending_audio_dir) if f.endswith('.wav')
            )
            if not pending_files:
                self.exit_flag.wait(timeout=1)
                continue

            wav_path = os.path.join(self.pending_audio_dir, pending_files[0])
            try:
                self.process_pending_audio(wav_path)
            except Exception as e:
                logger.info(f"Failed to process {wav_path}: {e}")
                time.sleep(1)

        logger.info("Transcription worker exiting")

    def process_pending_audio(self, wav_path):
        """Transcribes one queued WAV file and transmits the resulting MIDI.

        Args:
            wav_path (str): Path to a WAV file in pending_audio_dir.
        """
        metadata = utils.parse_pending_audio_filename(os.path.basename(wav_path))
        logger.info(f"Transcribing chunk {metadata['chunk']} of session {metadata['session_id']}")

        midi_info = utils.transcribe_pending_audio(
            wav_path=wav_path,
            bp_model=self.bp_model,
            transcription_dir=self.transcription_dir,
            research_mode=config.get('RESEARCH_MODE', False),
            finished_audio_dir=self.finished_audio_dir
        )
        logger.info(f"MIDI extracted for chunk {metadata['chunk']} of session {metadata['session_id']}")

        self.send_midi_chunk(
            instrument_id=self.instrument_id,
            session_id=metadata['session_id'],
            chunk=metadata['chunk'],
            time_iso=metadata['timestamp'].isoformat(),
            midi_info=midi_info
        )

    def send_midi_chunk(self, instrument_id, session_id, chunk, time_iso, midi_info):
        """POSTs one transcribed chunk's MIDI to the server, retrying on failure.

        On persistent failure, sets end_stream_flag so the main loop resets
        the recording session, mirroring the previous synchronous behavior.

        Args:
            instrument_id: Instrument identifier.
            session_id (str): Session the chunk belongs to.
            chunk (int): Index of this chunk within its session.
            time_iso (str): ISO-formatted recording timestamp.
            midi_info (dict): Output of utils.transcribe_pending_audio.
        """
        request_data = {
            'instrument_id': instrument_id,
            'session_id': session_id,
            'chunk': chunk,
            'time': time_iso,
            **midi_info
        }
        headers = {
            'Content-Type': 'application/json'
        }

        logger.info(f"Attempting to transmit MIDI for session {session_id}")

        for i in range(self.num_server_attempts):
            try:
                requests.post(
                    self.midi_request_url,
                    json=request_data,
                    headers=headers
                )
            except Exception as e:
                logger.info(f"Failed attempt {i + 1} to contact server with request, retrying...")
                time.sleep(self.server_retry_wait_seconds)
            else:
                logger.info(f"MIDI transmitted successfully for session {session_id}")
                return

        logger.info("Failed to contact server with request. Restarting...")
        time.sleep(self.server_failure_wait_seconds)
        self.end_stream_flag = True

    def heartbeat(self):
        """Sends a POST to /heartbeat every 30 seconds until the exit flag is set."""
        logger.info("Heartbeat script running")
        while not self.exit_flag.wait(timeout=30):
            logger.info("Sending heartbeat")
            request_data = {
                'instrument_id': self.instrument_id,
                'time': datetime.datetime.now().isoformat(),
            }
            headers = {
                'Content-Type': 'application/json'
            }
            try:
                r = requests.post(
                    self.heartbeat_request_url,
                    json=request_data,
                    headers=headers,
                    timeout=10
                )
            except Exception as e:
                logger.info(f"Failed to send heartbeat: {e}")
            else:
                logger.info("Successfully sent heartbeat")
                
        logger.info("Heartbeat script exiting")

if __name__ == '__main__':
    ...

    client = OctavioClient()
    if config['DO_HEARTBEAT']:
        client.run_heartbeat()
    client.run_transcription_worker()
    client.run()
