import pathlib

from amt import AMTModel
from basic_pitch.inference import predict, predict_and_save, Model
from basic_pitch import ICASSP_2022_MODEL_PATH

BP_REQUIRED_KEYS = {
    'TRANSCRIPTION_PARAMS.AMT_PARAMS.basic_pitch.min_frequency', 'TRANSCRIPTION_PARAMS.AMT_PARAMS.basic_pitch.max_frequency', 
    'TRANSCRIPTION_PARAMS.AMT_PARAMS.basic_pitch.onset_threshold', 'TRANSCRIPTION_PARAMS.AMT_PARAMS.basic_pitch.frame_threshold', 
}

class BasicPitchAMT(AMTModel):
    # TODO: TEST IF THIS WORKS
    def __init__(self):
        self.basic_pitch_model = Model(ICASSP_2022_MODEL_PATH)

        # transcription parameters (tweak as needed)
        self.minimum_frequency = 27.5   # A0 lowest note on standard piano
        self.maximum_frequency = 4186   # C8 highest note on standard piano

        self.onset_threshold = 0.7      # minimum energy to register pressed note (onset)
        self.frame_threshold = 0.2      # minimum energy to register held note (frame)

    def transcribe(self, input_audio_path, output_midi_path):
        output_midi_dir = pathlib.Path(output_midi_path).parent
        predict_and_save(
            # logistics
            audio_path_list=[input_audio_path],
            output_directory=output_midi_dir,
            save_midi=True,             # save MIDI to output path
            sonify_midi=False,          # don't save WAV render of MIDI
            save_model_outputs=False,   # don't save raw model output
            save_notes=False,           # don't save note events as CSV
            model_or_model_path=self.basic_pitch_model,
            
            # transcription parameters
            minimum_frequency=self.minimum_frequency,
            maximum_frequency=self.maximum_frequency,
            onset_threshold=self.onset_threshold,
            frame_threshold=self.frame_threshold
        )
        try:
            expected_bp_output_filename = pathlib.Path(input_audio_path).with_suffix("").name
            expected_bp_output_path = pathlib.Path(output_midi_dir / (expected_bp_output_filename + "_basic_pitch.mid"))
            print(expected_bp_output_path)
            expected_bp_output_path.rename(output_midi_path)
        except FileNotFoundError:
            print("Error: The source file does not exist.")