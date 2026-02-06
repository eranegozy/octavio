import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import statistics
import json
import numpy as np
import pyaudio
import scipy.ndimage
import log_utils
import wave

def find_recording_device_index():
    with log_utils.no_stderr():
        p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev['maxInputChannels'] > 0:
            return i
    return -1

def record_audio(record_seconds=30, device_index=None):
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 22050

    with log_utils.no_stderr():
        p = pyaudio.PyAudio()
    if device_index is None:
        device_index = find_recording_device_index()
        if device_index == -1:
            raise RuntimeError("Could not find recording device")
    stream = p.open(input=True, input_device_index=device_index, format=FORMAT, channels=CHANNELS, rate=RATE)

    print('Recording...')
    total_samples = RATE * record_seconds
    full_recording = np.empty(total_samples, dtype=np.int16)
    num_iters = (total_samples + CHUNK - 1) // CHUNK
    for i in range(num_iters):
        start_chunk_pos = i * CHUNK
        to_read = min(CHUNK, total_samples - start_chunk_pos)
        mic_input = stream.read(to_read)
        data = np.frombuffer(mic_input, dtype=np.int16)
        full_recording[start_chunk_pos: start_chunk_pos + to_read] = data
    print('Done')

    stream.close()
    p.terminate()

    return full_recording

if __name__ == '__main__':
    recording = record_audio()
    wav_file = wave.open('./temps/temp_recording.wav', 'wb')
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(22050)
    wav_file.writeframes(recording.tobytes())
    wav_file.close()