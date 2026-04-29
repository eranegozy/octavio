import os
import sys
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import transkun.transcribe as tk
import subprocess
import numpy as np

from scipy.io.wavfile import read

def wav_to_np(wav_filename):
    file_contents = read(wav_filename)
    file_data = np.array(file_contents[1]) / 2 ** 15
    return file_data

def tk_subprocess(input_fname, output_fname):
    subprocess.run([
        "python3.10", "-m", "transkun.transcribe", input_fname, output_fname
    ])

def is_silent(input, window_length = 2048, threshold = 0.001):
    padding = window_length - (len(input) % window_length)
    data = np.pad(input, (0, padding), mode='constant')
    windows = data.reshape(-1, window_length)
    energy = np.mean(windows ** 2, axis=1)
    return np.all(energy < threshold)

if __name__ == "__main__":
    # tk_subprocess("./lohi.wav", "./lohi.mid")
    lohi = wav_to_np("./lohi.wav")
    chords = wav_to_np("./chords.wav")
    scale = wav_to_np("./scale.wav")
    background_noise = wav_to_np("./background_noise.wav")
    much_background_noise = wav_to_np("./much_background_noise.wav")
    print('lohi: ', is_silent(lohi))
    print('chords: ', is_silent(chords))
    print('scale: ', is_silent(scale))
    print('background_noise: ', is_silent(background_noise))
    print('much_background_noise: ', is_silent(much_background_noise))