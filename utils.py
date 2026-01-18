import os
import sys
client_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), "./client"))
if client_directory not in sys.path:
    sys.path.insert(0, client_directory)

import log_utils
import string
import numpy as np
# import pyaudio
# import wave
from scipy.io.wavfile import read
# import shlex
# import subprocess
import mido
import random
import shutil
from pathlib import Path
# import os
with log_utils.no_stderr():
    from basic_pitch.inference import predict_and_save
import scipy.io
import calibrate

def generate_id():
    id_options = string.ascii_lowercase + string.digits
    return ''.join(random.choices(population=id_options, k=10))

def wav_to_np(wav_filename):
    file_contents = read(wav_filename)
    file_data = np.array(file_contents[1])
    return file_data

# def write_wav(filename, audio_array):
#     int16_audio = np.int16(audio_array)
#     scipy.io.wavfile.write(filename, 22050, int16_audio)

def save_frames_to_file(input_data, filename):
    # Accepts input_data as an np.float64 array

    # audio = pyaudio.PyAudio()
    # FORMAT = pyaudio.paInt16
    # SAMPLING_RATE = 22050
    # NUM_CHANNELS = 1

    # waveFile = wave.open(filename, 'wb')
    # waveFile.setsampwidth(audio.get_sample_size(FORMAT))
    # waveFile.setnchannels(NUM_CHANNELS)
    # waveFile.setframerate(SAMPLING_RATE)
    # waveFile.writeframes(bytes(frame_data))
    # waveFile.close()

    SAMPLING_RATE = 22050
    int16_audio = np.int16(input_data)
    scipy.io.wavfile.write(filename, SAMPLING_RATE, int16_audio)

# def convert_to_midi(input_audio, output_filename, ignore_warnings=True):
#     command = f'transkun {input_audio} {output_filename}'
#     command_args = shlex.split(command)
#     if ignore_warnings:
#         subprocess.run(command_args, stderr=subprocess.DEVNULL)
#     else:
#         subprocess.run(command_args)

def convert_to_midi_bp(input_audio, output_dir, bp_model):
    audio_files = [input_audio]
    predict_and_save(
        audio_path_list=audio_files,
        output_directory=output_dir,
        save_midi=True,
        sonify_midi=False,
        save_model_outputs=False,
        save_notes=False,
        model_or_model_path=bp_model,

        minimum_frequency=27.5,
        maximum_frequency=4186,

        onset_threshold=0.7,
        frame_threshold=0.5
    )
    bp_out_path = f'{str(Path(input_audio).with_suffix(""))}_basic_pitch.mid'
    # target_path = f'{str(Path(input_audio).with_suffix(""))}.mid'
    # os.rename(bp_out_path, target_path)
    return bp_out_path

def display_midi(midi_filename):
    mid = mido.MidiFile(midi_filename)
    # for msg in mid:
    #     print(msg)

def copy_midi_object(mid):
    output = mido.MidiFile(
        type=mid.type,
        ticks_per_beat=mid.ticks_per_beat
    )

    for track in mid.tracks:
        new_track = mido.MidiTrack()
        for msg in track:
            new_track.append(msg.copy())
        output.tracks.append(new_track)

    return output

def combine_midi_objects(midi1, midi2):
    START_END_THRESHOLD = 0.25

    mid1 = midi1
    mid2 = midi2
    mid1.tracks = [mido.merge_tracks(mid1.tracks)]
    mid2.tracks = [mido.merge_tracks(mid2.tracks)]

    output_mid = copy_midi_object(mid1)
    track = mido.MidiTrack()
    output_mid.tracks = [track]

    idxs_1 = set()
    notes_1 = set()
    idxs_2 = set()
    notes_2 = set()

    # Extract clipped notes from beginning of second file
    t = 0
    for idx, msg in enumerate(mid2):
        t += msg.time
        if t > START_END_THRESHOLD:
            break

        if msg.type == 'note_on' and msg.velocity != 0:
            notes_2.add(msg.note)
            idxs_2.add(idx)

    # Extract clipped notes from end of first file
    msgs = list(mid1)[::-1]
    t = 0
    for idx, msg in enumerate(msgs[1:], start=1):
        prev_msg = msgs[idx - 1]
        t += prev_msg.time

        if t > START_END_THRESHOLD:
            break

        if msg.type == 'note_on' and msg.velocity == 0:
            front_idx = len(msgs) - 1 - idx
            idxs_1.add(front_idx)
            notes_1.add(msg.note)

    for idx, msg in enumerate(mid1.tracks[0]):
        excluded_note = idx in idxs_1 and msg.note in notes_2
        if msg.type == 'end_of_track' or excluded_note:
            continue
        new_msg = msg.copy()
        track.append(new_msg)

    lost_time = 0
    for idx, msg in enumerate(mid2.tracks[0]):
        excluded_note = idx in idxs_2 and msg.note in notes_1
        if msg.is_meta or excluded_note:
            lost_time += msg.time
            continue
        new_msg = msg.copy()
        if lost_time > 0:
            new_msg.time += lost_time
            lost_time = 0
        track.append(new_msg)

    return output_mid

def combine_midi(midi_filename1, midi_filename2, output_filename):
    mid1 = midi.MidiFile(midi_filename1)
    mid2 = midi.MidiFile(midi_filename2)
    output_mid = combine_midi_objects(mid1, mid2)

    output_mid.save(output_filename)

def preprocess_audio(input_data, noise_quartiles, signal_quartiles):
    # Expects an np.float64 array, outputs one as well
    denoised = calibrate.denoise_signal(signal=input_data, noise_quartiles=noise_quartiles, signal_quartiles=signal_quartiles)
    return denoised

def extract_midi(input_bytes, bp_model, noise_quartiles, signal_quartiles, temp_dir='./temps'):
    temp_id = generate_id()
    unique_temp_dir = f'{temp_dir}/{temp_id}'
    os.makedirs(unique_temp_dir, exist_ok=True)

    # Handle data preprocessing
    input_data = np.frombuffer(input_bytes, dtype=np.int16).astype(np.float64) # assumes PyAudio dtype is pyaudio.paInt16
    preprocessed_audio = preprocess_audio(input_data=input_data, noise_quartiles=noise_quartiles, signal_quartiles=signal_quartiles)

    wav_filename = f'{unique_temp_dir}/{temp_id}.wav'
    save_frames_to_file(input_data=preprocessed_audio, filename=wav_filename)
    mid_filename = convert_to_midi_bp(input_audio=wav_filename, output_dir=unique_temp_dir, bp_model=bp_model)
    empty = midi_is_empty(midi_filename=mid_filename)

    serialized_msgs, tpb = serialize_midi_file(midi_filename=mid_filename)
    midi_info = {
        'ticks_per_beat': tpb,
        'messages': serialized_msgs,
        'is_empty': empty
    }

    try:
        shutil.rmtree(unique_temp_dir)
    except FileNotFoundError:
        # print(f'{unique_temp_dir} already deleted')
        pass

    # for filename in (wav_filename, mid_filename):
    #     try:
    #         os.remove(filename)
    #     except FileNotFoundError:
    #         print(f'{filename} already deleted')

    return midi_info

def serialize_midi_object(midi_object):
    mid = midi_object
    if len(mid.tracks) > 1:
        mid.tracks = [mido.merge_tracks(mid.tracks)]

    msgs = []
    for msg in mid.tracks[0]:
        serialized = msg.dict() if msg.is_meta else str(msg)
        msgs.append(serialized)
    tpb = mid.ticks_per_beat
    return msgs, tpb

def serialize_midi_file(midi_filename):
    mid = mido.MidiFile(midi_filename)
    serialize_midi_object(mid)

def deserialize_midi_object(msgs, ticks_per_beat):
    track = mido.MidiTrack()
    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat, tracks=[track])

    for serialized_msg in msgs:
        is_meta = isinstance(serialized_msg, dict)
        if is_meta:
            msg = mido.MetaMessage(**serialized_msg)
        else:
            msg = mido.Message.from_str(serialized_msg)
        track.append(msg)
    return mid

def deserialize_midi_file(msgs, ticks_per_beat, out_filename):
    mid = deserialize_midi_object(msgs, ticks_per_beat)
    mid.save(out_filename)

def midi_is_empty(midi_filename):
    mid = mido.MidiFile(midi_filename)
    for msg in mid:
        if msg.type == 'note_on':
            return False
    return True

if __name__ == '__main__':
    pass

    # mf1 = '../misc/output/scalesA.mid'

    # s, tpb = serialize_midi_file(midi_filename=mf1)
    # # print(s)
    # deserialize_midi_file(msgs=s, ticks_per_beat=tpb, out_filename='./yeet.mid')
    # display_midi('./yeet.mid')
