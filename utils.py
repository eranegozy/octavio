"""Shared audio processing utilities for MIDI extraction, serialization, and combination.

Handles the full pipeline from raw PyAudio bytes to serialized MIDI JSON ready
for transmission, as well as stitching consecutive MIDI chunks together.

Note: documentation in this file was written with assistance from AI tools.
"""

import os
import sys
client_directory = os.path.abspath(os.path.join(os.path.dirname(__file__), "./client"))
if client_directory not in sys.path:
    sys.path.insert(0, client_directory)

import log_utils
import string
import datetime
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

import subprocess
# Transkun is invoked as a subprocess (see convert_to_midi_tk) rather than
# imported directly, since it's a separate torch-based package that is not
# part of the client's default requirements.

def generate_id():
    """Generates a random 10-character alphanumeric ID.

    Returns:
        str: A lowercase alphanumeric string of length 10.
    """
    id_options = string.ascii_lowercase + string.digits
    return ''.join(random.choices(population=id_options, k=10))

def wav_to_np(wav_filename):
    """Loads a WAV file into a NumPy array.

    Args:
        wav_filename (str): Path to the WAV file.

    Returns:
        np.ndarray: Array of audio samples.
    """
    file_contents = read(wav_filename)
    file_data = np.array(file_contents[1])
    return file_data

# def write_wav(filename, audio_array):
#     int16_audio = np.int16(audio_array)
#     scipy.io.wavfile.write(filename, 22050, int16_audio)

def write_wav(input_data, filename):
    """Saves a float64 audio array as a 16-bit mono WAV file at 22050 Hz.

    Args:
        input_data (np.ndarray): 1D array of np.float64 audio samples.
        filename (str): Output file path.
    """
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
    """Runs Basic Pitch AMT on a WAV file and returns the output MIDI path.

    Args:
        input_audio (str): Path to the input WAV file.
        output_dir (str): Directory where Basic Pitch writes its output.
        bp_model (Model): Pre-loaded Basic Pitch TFLite model instance.

    Returns:
        str: Path to the generated MIDI file.
    """
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

def convert_to_midi_tk(input_audio, output_dir, device='cpu'):
    """Runs Transkun AMT on a WAV file and returns the output MIDI path.

    Mirrors convert_to_midi_bp's contract (same args shape, same return
    type) so the two backends are interchangeable at call sites. Unlike
    Basic Pitch, Transkun is invoked as a subprocess via `python3.10 -m
    transkun.transcribe` rather than an in-process model call, since it's a
    separate, torch-based package that is not part of the client's default
    requirements (see CLAUDE.md / utils.py import comment).

    Args:
        input_audio (str): Path to the input WAV file.
        output_dir (str): Directory where the output MIDI is written.
        device (str): Compute device passed to transkun ('cpu' or 'cuda').
            Defaults to 'cpu'.

    Returns:
        str: Path to the generated MIDI file.

    Raises:
        RuntimeError: If the transkun subprocess exits non-zero, e.g.
            because the `transkun` package isn't installed in whatever
            `python3.10` resolves to on PATH.
    """
    os.makedirs(output_dir, exist_ok=True)
    tk_out_path = os.path.join(output_dir, f'{Path(input_audio).stem}_transkun.mid')

    result = subprocess.run(
        [
            "python3.10", "-m", "transkun.transcribe",
            input_audio, tk_out_path,
            "--device", device,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"transkun transcription failed on {input_audio} "
            f"(exit {result.returncode}): {result.stderr.strip()}"
        )

    return tk_out_path

def display_midi(midi_filename):
    """Loads a MIDI file for inspection. Currently a no-op placeholder.

    Args:
        midi_filename (str): Path to the MIDI file.
    """
    mid = mido.MidiFile(midi_filename)
    # for msg in mid:
    #     print(msg)

def copy_midi_object(mid):
    """Returns a deep copy of a MidiFile object.

    Args:
        mid (mido.MidiFile): The MIDI object to copy.

    Returns:
        mido.MidiFile: A new MidiFile with independent copies of all tracks and messages.
    """
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
    """Concatenates two MidiFile objects, reconciling boundary note clipping.

    Notes cut off at the end of midi1 that reappear at the start of midi2
    (within START_END_THRESHOLD seconds) are deduplicated to avoid double
    note-on events at the seam.

    Args:
        midi1 (mido.MidiFile): The earlier MIDI chunk.
        midi2 (mido.MidiFile): The later MIDI chunk to append.

    Returns:
        mido.MidiFile: A new MidiFile containing the merged content.
    """
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
    """File-level wrapper for combine_midi_objects. Loads, merges, and saves.

    Args:
        midi_filename1 (str): Path to the earlier MIDI file.
        midi_filename2 (str): Path to the later MIDI file.
        output_filename (str): Path to write the merged output.
    """
    mid1 = mido.MidiFile(midi_filename1)
    mid2 = mido.MidiFile(midi_filename2)
    output_mid = combine_midi_objects(mid1, mid2)

    output_mid.save(output_filename)

def preprocess_audio(input_data, noise_quartiles, signal_quartiles):
    """Applies calibrated noise-gating to an audio array.

    Args:
        input_data (np.ndarray): 1D float64 audio samples.
        noise_quartiles (tuple): (25th, 50th, 75th) RMS percentiles from noise calibration.
        signal_quartiles (tuple): (25th, 50th, 75th) RMS percentiles from signal calibration.

    Returns:
        np.ndarray: Denoised float64 audio array.
    """
    # Expects an np.float64 array, outputs one as well
    denoised = calibrate.denoise_signal(signal=input_data, noise_quartiles=noise_quartiles, signal_quartiles=signal_quartiles)
    return denoised


PENDING_AUDIO_TIMESTAMP_FORMAT = '%Y%m%d%H%M%S%f'

def make_pending_audio_filename(session_id, chunk, device_index, timestamp):
    """Builds a sortable filename for a queued pending-audio WAV file.

    The timestamp is placed first so that alphabetically sorting the
    pending-audio directory yields strict chronological (FIFO) order across
    all sessions, which is what the transcription worker relies on to drain
    the queue in the order chunks were recorded. The recording device index
    (not instrument_id, which is irrelevant to recording/transcription and
    is constant for the client process anyway) is included for traceability.

    Args:
        session_id (str): Session identifier the chunk belongs to.
        chunk (int): Index of this chunk within the session.
        device_index (int): Index of the recording device used.
        timestamp (datetime.datetime): Time the chunk was recorded.

    Returns:
        str: A filename of the form '{timestamp}_{device_index}_{session_id}_{chunk}.wav'.
    """
    ts = timestamp.strftime(PENDING_AUDIO_TIMESTAMP_FORMAT)
    return f'{ts}_{device_index}_{session_id}_{chunk:06d}.wav'

def parse_pending_audio_filename(filename):
    """Recovers chunk metadata encoded in a pending-audio filename.

    Args:
        filename (str): A filename produced by make_pending_audio_filename
            (basename only; directory components are ignored).

    Returns:
        dict: Keys 'timestamp' (datetime.datetime), 'device_index' (str),
            'session_id' (str), and 'chunk' (int).
    """
    stem = Path(filename).stem
    ts_str, device_index, session_id, chunk_str = stem.split('_')
    return {
        'timestamp': datetime.datetime.strptime(ts_str, PENDING_AUDIO_TIMESTAMP_FORMAT),
        'device_index': device_index,
        'session_id': session_id,
        'chunk': int(chunk_str),
    }

def save_pending_audio(input_data, noise_quartiles, signal_quartiles, pending_dir, session_id, chunk, device_index, timestamp):
    """Denoises a raw audio chunk and enqueues it as a WAV file for transcription.

    This is the producer side of the pending-audio queue: every recorded
    chunk is written here unconditionally, regardless of research mode. A
    separate transcription worker dequeues and processes these files.

    Args:
        input_data (np.ndarray): 1D float64 audio samples for one chunk.
        noise_quartiles (tuple): (25th, 50th, 75th) RMS percentiles from noise calibration.
        signal_quartiles (tuple): (25th, 50th, 75th) RMS percentiles from signal calibration.
        pending_dir (str): Directory backing the pending-audio queue.
        session_id (str): Current session identifier.
        chunk (int): Index of this chunk within the session.
        device_index (int): Index of the recording device used.
        timestamp (datetime.datetime): Time the chunk was recorded.

    Returns:
        str: Path to the written WAV file.
    """
    os.makedirs(pending_dir, exist_ok=True)
    preprocessed_audio = preprocess_audio(input_data=input_data, noise_quartiles=noise_quartiles, signal_quartiles=signal_quartiles)
    filename = make_pending_audio_filename(session_id=session_id, chunk=chunk, device_index=device_index, timestamp=timestamp)
    path = os.path.join(pending_dir, filename)
    write_wav(input_data=preprocessed_audio, filename=path)
    return path

def transcribe_pending_audio(wav_path, bp_model, transcription_dir, research_mode=False, finished_audio_dir='./finished-audio'):
    """Transcribes one queued WAV file to MIDI and dequeues it.

    This is the consumer side of the pending-audio queue. The MIDI output is
    written to transcription_dir under the same base name as the WAV file.
    The WAV file is always removed from the queue: in research mode it is
    moved to finished_audio_dir for later inspection, otherwise it is deleted.

    Args:
        wav_path (str): Path to the queued WAV file (in the pending-audio dir).
        bp_model: Loaded Basic Pitch model used for transcription.
        transcription_dir (str): Directory where the output MIDI is written.
        research_mode (bool): If True, preserve the WAV in finished_audio_dir
            instead of deleting it. Defaults to False.
        finished_audio_dir (str): Directory where preserved WAVs are moved
            when research_mode is True. Defaults to './finished-audio'.

    Returns:
        dict: MIDI info with keys 'ticks_per_beat', 'messages', and 'is_empty'.
    """
    os.makedirs(transcription_dir, exist_ok=True)
    filename = os.path.basename(wav_path)
    stem = Path(filename).stem

    bp_out_path = convert_to_midi_bp(input_audio=wav_path, output_dir=transcription_dir, bp_model=bp_model)
    mid_path = os.path.join(transcription_dir, f'{stem}.mid')
    os.replace(bp_out_path, mid_path)

    empty = midi_is_empty(midi_filename=mid_path)
    serialized_msgs, tpb = serialize_midi_file(midi_filename=mid_path)

    if research_mode:
        os.makedirs(finished_audio_dir, exist_ok=True)
        shutil.move(wav_path, os.path.join(finished_audio_dir, filename))
    else:
        os.remove(wav_path)

    return {
        'ticks_per_beat': tpb,
        'messages': serialized_msgs,
        'is_empty': empty
    }

def transcribe_pending_audio_tk(wav_path, transcription_dir, research_mode=False, finished_audio_dir='./finished-audio', device='cpu'):
    """Transcribes one queued WAV file to MIDI using Transkun, and dequeues it.

    Transkun counterpart to transcribe_pending_audio: identical signature
    (minus bp_model, plus device) and identical return format, so the two
    AMT backends can be swapped at call sites without touching downstream
    code (serialization, chunk merging, server API all stay the same).
    Requires the `transkun` package to be installed in whatever `python3.10`
    is on PATH — it is not part of the client's default requirements.

    Args:
        wav_path (str): Path to the queued WAV file (in the pending-audio dir).
        transcription_dir (str): Directory where the output MIDI is written.
        research_mode (bool): If True, preserve the WAV in finished_audio_dir
            instead of deleting it. Defaults to False.
        finished_audio_dir (str): Directory where preserved WAVs are moved
            when research_mode is True. Defaults to './finished-audio'.
        device (str): Compute device passed to transkun. Defaults to 'cpu'.

    Returns:
        dict: MIDI info with keys 'ticks_per_beat', 'messages', and 'is_empty'.
    """
    os.makedirs(transcription_dir, exist_ok=True)
    filename = os.path.basename(wav_path)
    stem = Path(filename).stem

    tk_out_path = convert_to_midi_tk(input_audio=wav_path, output_dir=transcription_dir, device=device)
    mid_path = os.path.join(transcription_dir, f'{stem}.mid')
    os.replace(tk_out_path, mid_path)

    empty = midi_is_empty(midi_filename=mid_path)
    serialized_msgs, tpb = serialize_midi_file(midi_filename=mid_path)

    if research_mode:
        os.makedirs(finished_audio_dir, exist_ok=True)
        shutil.move(wav_path, os.path.join(finished_audio_dir, filename))
    else:
        os.remove(wav_path)

    return {
        'ticks_per_beat': tpb,
        'messages': serialized_msgs,
        'is_empty': empty
    }

def serialize_midi_object(midi_object):
    """Serializes a MidiFile to a JSON-compatible list of messages and ticks_per_beat.

    Meta messages are serialized as dicts; regular messages as strings.
    Multi-track files are merged into a single track before serialization.

    Args:
        midi_object (mido.MidiFile): The MIDI object to serialize.

    Returns:
        tuple: (list[str | dict], int) — messages and ticks_per_beat.
    """
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
    """File-level wrapper for serialize_midi_object.

    Args:
        midi_filename (str): Path to the MIDI file.

    Returns:
        tuple: (list[str | dict], int) — messages and ticks_per_beat.
    """
    mid = mido.MidiFile(midi_filename)
    return serialize_midi_object(mid)

def deserialize_midi_object(msgs, ticks_per_beat):
    """Reconstructs a MidiFile from a serialized message list.

    Args:
        msgs (list[str | dict]): Serialized messages as returned by serialize_midi_object.
        ticks_per_beat (int): MIDI timing resolution.

    Returns:
        mido.MidiFile: The reconstructed MIDI object.
    """
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
    """Deserializes a message list and saves the result to a MIDI file.

    Args:
        msgs (list[str | dict]): Serialized messages as returned by serialize_midi_object.
        ticks_per_beat (int): MIDI timing resolution.
        out_filename (str): Path to write the output MIDI file.
    """
    mid = deserialize_midi_object(msgs, ticks_per_beat)
    mid.save(out_filename)

def midi_is_empty(midi_filename):
    """Returns True if the MIDI file contains no note_on events.

    Args:
        midi_filename (str): Path to the MIDI file.

    Returns:
        bool: True if no notes are present, False otherwise.
    """
    mid = mido.MidiFile(midi_filename)
    for msg in mid:
        if msg.type == 'note_on':
            return False
    return True

def is_silent(input_bytes, window_length = 2048, threshold = 0.001):
    """Returns True if all energy windows in the audio are below the threshold.

    Args:
        input_bytes (bytes): Raw audio bytes from PyAudio (paInt16 format).
        window_length (int): Analysis window size in samples. Defaults to 2048.
        threshold (float): Energy threshold for silence detection. Defaults to 0.001.

    Returns:
        bool: True if the audio is silent, False otherwise.
    """
    input_data = np.frombuffer(input_bytes, dtype=np.int16).astype(np.float64)
    input_data /= 2 ** 15
    padding = window_length - (len(input_data) % window_length)
    data = np.pad(input_data, (0, padding), mode='constant')
    windows = data.reshape(-1, window_length)
    energy = np.mean(windows ** 2, axis=1)
    return np.all(energy < threshold)

if __name__ == '__main__':
    pass

    # mf1 = '../misc/output/scalesA.mid'

    # s, tpb = serialize_midi_file(midi_filename=mf1)
    # # print(s)
    # deserialize_midi_file(msgs=s, ticks_per_beat=tpb, out_filename='./yeet.mid')
    # display_midi('./yeet.mid')
