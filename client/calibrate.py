"""Audio calibration and noise-gating utility module.

This module provides tools to record audio via PyAudio, calculate the Root Mean 
Square (RMS) profiles of signals, calibrate baseline environmental noise versus 
target signals, and apply a calibrated noise gate to denoise audio arrays.
"""

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
    """Finds the index of the first available audio input device detected by PyAudio.

    Returns:
        int: The index of the recording device if found; otherwise, -1.
    """
    with log_utils.no_stderr():
        p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):   # search through all connected audio devices
        dev = p.get_device_info_by_index(i)
        if dev['maxInputChannels'] > 0:     # device with at least one input channel is the recording device
            return i
    return -1

def write_recording_device_index(device_index):
    """Updates the infrastructure configuration file './infra.json' with the given device index.
    Args:
        device_index (int): The index of the audio recording device to save.
    Raises:
        FileNotFoundError: If the './infra.json' file does not exist.
        json.JSONDecodeError: If the JSON file contains invalid syntax.
    """
    with open('./infra.json', 'r') as f:
        j = json.load(f)

    j['RECORDING_DEVICE_INDEX'] = device_index

    with open('./infra.json', 'w') as f:
        json.dump(j, f)
        f.write('\n')

def record_audio(record_seconds=30, device_index=None):
    """Records mono audio (22050Hz, 16-bit) into a NumPy array.

    Args:
        record_seconds (int): Duration of the recording. Defaults to 30.
        device_index (int, optional): Hardware device index. If None, auto-detects.

    Returns:
        np.ndarray: 1D array of np.int16 audio samples.

    Raises:
        RuntimeError: If device_index is None and no recording device is found.
    """
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

def rms(arr):
    return np.sqrt(np.mean(np.square(arr, dtype=np.float64)))

def chunk_and_rms_sound(full_sound, window_size=2048):
    """Computes RMS values across the audio signal using a 50% overlapping sliding window.

    Args:
        full_sound (np.ndarray): 1D array of audio samples.
        window_size (int): Size of each analysis window. Defaults to 2048.

    Returns:
        list[float]: RMS values for each window.
    """
    hop_size = window_size // 2

    rmses = []
    for window_start in range(0, len(full_sound), hop_size):
        window_end = window_start + window_size
        window = full_sound[window_start:window_end]
        window_rms = rms(window)
        rmses.append(window_rms)
    return rmses

def measure_calibration(device_index = None):
    """Interactively records and analyzes baseline noise and signal levels for calibration.

    Prompts the user to record a 30-second noise trial followed by a 60-second 
    signal trial. Computes and prints the RMS-based quartiles, mean, and 
    standard deviation for both environments.

    Args:
        device_index (int, optional): Hardware device index for recording. 
            If None, auto-detects.

    Returns:
        tuple: A 6-element tuple containing:
            - noise_quartiles (list[float]): Quartiles of the noise RMS values.
            - noise_mean (float): Mean of the noise RMS values.
            - noise_std (float): Standard deviation of the noise RMS values.
            - signal_quartiles (list[float]): Quartiles of valid signal RMS values.
            - signal_mean (float): Mean of all signal RMS values.
            - signal_std (float): Standard deviation of all signal RMS values.
    """
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
    """Saves the calculated noise and signal calibration metrics to 'infra.json'.

    Args:
        noise_quartiles (list[float]): 25th, 50th, and 75th percentiles for noise.
        noise_mean (float): Mean of the noise RMS values.
        noise_std (float): Standard deviation of the noise RMS values.
        signal_quartiles (list[float]): 25th, 50th, and 75th percentiles for signal.
        signal_mean (float): Mean of the signal RMS values.
        signal_std (float): Standard deviation of the signal RMS values.
    """
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
    """Mutes low-volume regions of an audio signal based on calibration medians.

    Computes a noise gate threshold from the medians, evaluates the signal's RMS 
    profile using a sliding window, and zeros out frames below the threshold whose neighbors
    are also below the threshold.

    Args:
        signal (np.ndarray): The 1D input audio array (np.float64) to be denoised.
        noise_quartiles (list[float]): Noise calibration metrics containing the median.
        signal_quartiles (list[float]): Signal calibration metrics containing the median.

    Returns:
        np.ndarray: A modified copy of the input signal with gated regions muted.
    """

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
