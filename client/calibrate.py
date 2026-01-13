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

def find_recording_device_index():
    with log_utils.no_stderr():
        p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        if dev['maxInputChannels'] > 0:
            return i
    return -1

def write_recording_device_index(device_index):
    with open('./infra.json', 'r') as f:
        j = json.load(f)

    j['RECORDING_DEVICE_INDEX'] = device_index

    with open('./infra.json', 'w') as f:
        json.dump(j, f)
        f.write('\n')

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
    full_recording = np.empty(RATE * record_seconds)
    for i in range(0, RATE // CHUNK * record_seconds):
        mic_input = stream.read(CHUNK)
        data = np.frombuffer(mic_input, dtype=np.int16)
        start_chunk_pos = i * CHUNK
        end_chunk_position = i * CHUNK + CHUNK
        full_recording[start_chunk_pos : end_chunk_position] = data
    print('Done')

    stream.close()
    p.terminate()

    return full_recording

def rms(arr):
    return (np.sum(np.square(arr)) / np.size(arr)) ** (1/2)

def chunk_and_rms_sound(full_sound, window_size=2048):
    hop_size = window_size // 2

    rmses = []
    for window_start in range(0, len(full_sound), hop_size):
        window_end = window_start + window_size
        window = full_sound[window_start:window_end]
        window_rms = rms(window)
        rmses.append(window_rms)
    return rmses

def measure_calibration(device_index = None):
    noise_trial_duration = 30
    signal_trial_duration = 60

    input('Measuring noise: hit [ENTER] to start')
    noise_trial = record_audio(record_seconds=noise_trial_duration, device_index = device_index)
    noise_rmses = chunk_and_rms_sound(full_sound=noise_trial)
    noise_quartiles = statistics.quantiles(noise_rmses)
    noise_mean = statistics.mean(noise_rmses)
    noise_std = statistics.stdev(noise_rmses)

    print(f'Noise quartiles: {noise_quartiles}')
    print(f'Noise mean and stdev: {noise_mean}, {noise_std}')

    input('Measuring signal: hit [ENTER] to start')
    signal_trial = record_audio(record_seconds=signal_trial_duration, device_index=device_index)
    signal_rmses = chunk_and_rms_sound(full_sound=signal_trial)
    baseline_signal_threshold = 2.0
    valid_signal_rmses = [rms for rms in signal_rmses if rms >= baseline_signal_threshold]
    signal_quartiles = statistics.quantiles(valid_signal_rmses)
    signal_mean = statistics.mean(signal_rmses)
    signal_std = statistics.stdev(signal_rmses)

    print(f'Signal quartiles: {signal_quartiles}')
    print(f'Signal mean and stdev: {signal_mean}, {signal_std}')

    return noise_quartiles, noise_mean, noise_std, signal_quartiles, signal_mean, signal_std

def apply_calibration(noise_quartiles, noise_mean, noise_std, signal_quartiles, signal_mean, signal_std):
    with open('./infra.json', 'r') as f:
        j = json.load(f)

    noise_25th, noise_50th, noise_75th = noise_quartiles
    signal_25th, signal_50th, signal_75th = signal_quartiles

    j['NOISE_25TH_PERCENTILE'] = noise_25th
    j['NOISE_50TH_PERCENTILE'] = noise_50th
    j['NOISE_75TH_PERCENTILE'] = noise_75th
    j['NOISE_MEAN'] = noise_mean
    j['NOISE_STD'] = noise_std

    j['SIGNAL_25TH_PERCENTILE'] = signal_25th
    j['SIGNAL_50TH_PERCENTILE'] = signal_50th
    j['SIGNAL_75TH_PERCENTILE'] = signal_75th
    j['SIGNAL_MEAN'] = signal_mean
    j['SIGNAL_STD'] = signal_std

    with open('./infra.json', 'w') as f:
        json.dump(j, f)
        f.write('\n')

def denoise_signal(signal, noise_quartiles, signal_quartiles):
    # Accepts and returns an np.float64 array

    _, noise_median, _ = noise_quartiles
    _, signal_median, _ = signal_quartiles

    alpha = 0.5
    threshold = alpha * signal_median + (1 - alpha) * noise_median

    window_size = 2048
    hop_size = window_size // 2
    window_rmses = np.array(chunk_and_rms_sound(signal, window_size=window_size))
    initial_mask = window_rmses >= threshold

    context = 1
    smoothed_mask = scipy.ndimage.maximum_filter1d(initial_mask, size=2 * context + 1)

    denoised_signal = np.copy(signal)
    for window_start, is_piano in zip(
        range(0, len(signal), hop_size),
        smoothed_mask
    ):
        window_end = window_start + window_size
        if not is_piano:
            denoised_signal[window_start:window_end] = 0

    return denoised_signal

if __name__ == '__main__':
    ...
    device_index = find_recording_device_index()
    write_recording_device_index(device_index)
    noise_quartiles, noise_mean, noise_std, signal_quartiles, signal_mean, signal_std = measure_calibration()
    apply_calibration(noise_quartiles, noise_mean, noise_std, signal_quartiles, signal_mean, signal_std)
