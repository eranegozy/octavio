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
import queue
import json
import signal
import datetime
import wave
import time
import pathlib

import requests                         # pip install requests
import dotenv          # pip install python-dotenv
import pyaudio
import numpy as np
import scipy.io.wavfile
import psutil

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
    script_dir = pathlib.Path(__file__).parent
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
        dotenv.load_dotenv(dotenv_dir)
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
        self.shutdown_requested = threading.Event()
        self.critical_failure_encountered = threading.Event()
        
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
        self.thread_aliases = {}
        
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

        current_process = psutil.Process(os.getpid())
        threads = current_process.threads()
        print(threads)

        def get_thread_cpu_usage(interval=10.0):
            p = psutil.Process(os.getpid())

            # First snapshot: Total process CPU time and individual thread times
            t1_proc = sum(p.cpu_times())
            t1_threads = {t.id: t.user_time + t.system_time for t in p.threads()}

            time.sleep(interval)

            # Second snapshot
            t2_proc = sum(p.cpu_times())
            t2_threads = {t.id: t.user_time + t.system_time for t in p.threads()}

            # Total process utilization percentage over the interval
            proc_percent = p.cpu_percent()
            print(proc_percent)

            proc_time_delta = t2_proc - t1_proc
            if proc_time_delta <= 0:
                return {}

            # Distribute the overall process CPU % among the threads
            thread_percentages = {}
            for t_id, t2_time in t2_threads.items():
                t1_time = t1_threads.get(t_id, 0)
                thread_time_delta = t2_time - t1_time

                # Percentage = (Thread Time Delta / Total Process Time Delta) * Total Process CPU %
                thread_percentages[t_id] = (
                    thread_time_delta / proc_time_delta
                )

            return thread_percentages


        # Example execution
        print(get_thread_cpu_usage())
        print(self.thread_aliases)

    def handle_shutdown_signal(self, signum, frame):
        logger.info(f'Received signal {signum}. Shutting down...')
        self.shutdown_requested.set()
    
    def run_heartbeat(self):
        self.thread_aliases[threading.get_native_id()] = "run_heartbeat"
        logger.info("Heartbeat script running")
        while not self.shutdown_requested.wait(timeout=10):
            if self.use_server:
                logger.info(f"Sending heartbeat to {self.heartbeat_endpoint_url}")
                request_data = {
                    'time': datetime.datetime.now().isoformat(),
                    'session': self.session_manager.get_session_id(),
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
                logger.info(f"Local heartbeat message at time {datetime.datetime.now().isoformat()} and session {self.session_manager.get_session_id()}")
                        
        logger.info("Heartbeat script exiting")
    
    # def run_session_manager(self): #TODO: currently unused, current session manager is fully synchronous and only updates on actions involving session state
    #     session_manager = get_session_manager()
    #     while not self.shutdown_requested.wait(timeout=4):
    #         logger.info("I'm managing the session")
    #         session_manager.handle_recording_activity()
    #     logger.info("Session manager successfully exited")

    def run_recording(self):
        self.thread_aliases[threading.get_native_id()] = "run_recording"
        
        p = pyaudio.PyAudio()

        # Find audio input device and set sampling rate
        device_index = -1
        sampling_rate = None
        for i in range(p.get_device_count()):   # search through all connected audio devices
            device_info = p.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:     # device with at least one input channel is the recording device
                sampling_rate = int(device_info['defaultSampleRate'])
                device_index = i
                logger.info(f'Found audio input device {device_info["name"]}(ID {device_index}) with sampling rate {sampling_rate} Hz')
                break
        if device_index == -1:
            raise RuntimeError("Could not find recording device")
        if not sampling_rate:
            raise RuntimeError("Could not determine sampling rate of recording device")

        # Callback function and thread-safe audio queue for PyAudio non-blocking mode
        buffers_to_concatenate = queue.Queue(maxsize=50) # each queue item is a full buffer with CHUNK # of samples
        buffer_critical_overflow = False

        def stream_callback(in_data, frame_count, time_info, status):
            nonlocal buffer_critical_overflow
            try:
                buffers_to_concatenate.put_nowait(in_data)
                return (None, pyaudio.paContinue)
            except queue.Full:
                critical_overflow = True
                logger.error("Main loop fell behind! Buffer overflow detected.")
                return (None, pyaudio.paAbort)

        # Starting PyAudio recording in non-blocking mode (runs stream_callback in a separate thread)
        FRAMES_PER_BUFFER = 4096 # TODO: refactor to use config
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        
        stream = p.open(
            format=FORMAT, 
            channels=CHANNELS, 
            rate=sampling_rate,
            input=True, 
            input_device_index=device_index, 
            frames_per_buffer=FRAMES_PER_BUFFER,
            stream_callback=stream_callback # non-blocking mode
        )
        chunk_start_time = datetime.datetime.now()
        chunk_ctr = 0
        logger.info("Recording... Press Ctrl+C to stop.")

        CHUNK_DURATION = 10 # 30 seconds

        buffers_per_chunk = int(CHUNK_DURATION * sampling_rate / FRAMES_PER_BUFFER)

        audio_buffers = []

        save_paths = [pathlib.Path(sys.path[0]) / "client" / "recordings_transcription_queue"]

        while not self.shutdown_requested.is_set():
            buffer_bytes = buffers_to_concatenate.get()
            samples = np.frombuffer(buffer_bytes, dtype=np.int16)
            
            audio_buffers.append(samples)

            # Once enough buffers accumulated for given duration chunk, write chunk to .wav file(s)
            if len(audio_buffers) >= buffers_per_chunk:
                file_name = f"{chunk_start_time:%Y.%m.%d-%H.%M.%S}.wav"
                chunk_start_time = datetime.datetime.now()  # Update ASAP for next chunk before doing additional processing

                self.session_manager.handle_recording_activity()
                session_id = self.session_manager.get_session_id()

                if session_id:
                    logger.info(f"Audio chunk captured in session {session_id}")
                    chunk_ctr += 1

                    audio_frames = np.concatenate(audio_buffers)
                    audio_buffers = []

                    for save_path in save_paths:
                        if not os.path.exists(save_path):
                            os.makedirs(save_path)
                            
                        file_path = save_path / file_name

                        chunk_start_time = datetime.datetime.now()

                        scipy.io.wavfile.write(file_path, sampling_rate, audio_frames)
                        logger.info(f"Successfully write audio chunk to {file_path}")
                    logger.info("Privacy has been requested, recording chunk discarded")

                


        # Clean up resources safely
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        logger.info("Recording successfully exited")

    def run_transcription(self):
        self.thread_aliases[threading.get_native_id()] = "run_transcription"

        audio_path = pathlib.Path(sys.path[0]) / "client" / "recordings_transcription_queue"
        save_paths = [pathlib.Path(sys.path[0]) / "client" / "transcriptions_upload_queue"]

        file_names = sorted([p.name for p in audio_path.iterdir() if p.suffix == ".wav"])
        for file_name in file_names:
            for save_path in save_paths:
                if not os.path.exists(save_path):
                    os.makedirs(save_path)
                self.Model.transcribe(audio_path / file_name, (save_path / file_name).with_suffix(".mid"))

                if config["TRANSCRIPTION_PARAMS.KEEP_TRANSCRIBED_AUDIO"]:
                    audio_save_path = pathlib.Path(sys.path[0]) / "client" / "recordings_saved" / file_name
                    audio_source = audio_path / file_name
                    audio_source.rename(audio_save_path)
                else:
                    audio_source.unlink()

        while not self.shutdown_requested.wait(timeout=6):
            logger.info("I'm transcribing")
        logger.info("Transcription successfully exited")

    def run_upload(self):
        self.thread_aliases[threading.get_native_id()] = "run_upload"

        while not self.shutdown_requested.wait(timeout=7):
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