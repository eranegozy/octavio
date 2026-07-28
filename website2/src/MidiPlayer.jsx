import React, { useEffect, useState, useRef, useCallback } from "react";
import { Midi } from "@tonejs/midi";
import * as Tone from "tone"
import PianoRoll from "react-piano-roll";

export default function MidiPlayer({ midiUrl }) {
  const [formattedNotes, setFormattedNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isPlaying, setPlaying] = useState(false);
  const playbackRef = useRef();
  const synthRef = useRef();

  useEffect(() => {
    async function loadAndConvertMidi() {
        /**
         * @param {number} duration The duration of the note, in seconds. Must be >= 0.
         * @param {number} bpm The BPM to run the conversion on. Must be > 0, defaults to 120.
         * @returns A string representing the (nearest plausible) rhythm value, in Slang notation
         *  (see: https://github.com/kylestetz/slang#rhythm-and-note-values)
         */
        function secondsToRhythmValue(duration, bpm = 120) {
          let beatDuration = duration / 60 * bpm
          
          // Rounding handles minor MIDI float precision deviations
          beatDuration = Math.round(beatDuration * 100) / 100;

          // TODO: make this conversion more powerful (support triplets, etc.)
          switch (true){
            case (beatDuration >= 4): return "1n" // Whole
            case (beatDuration >= 2): return "2n" // Half
            case (beatDuration >= 1): return "4n" // Quarter
            case (beatDuration >= 0.5): return "8n" // 8th
            case (beatDuration >= 0.25): return "16n" // 16th
            case (beatDuration >= 0.125): return "32n" // 32nd
            case (beatDuration >= 0.0625): return "64n" // 64th
            default: return "" // 64th (untranscribable/very short notes)
          }
        }
      try {
        const midi = await Midi.fromUrl(midiUrl);
        const bpm = midi.header.tempos[0]?.bpm || 120;
        const secondsPerBeat = 60 / bpm;

        const allNotes = [];

        midi.tracks.forEach((track) => {
          track.notes.forEach((note) => {
            const totalBeats = note.time / secondsPerBeat;

            const bars = Math.floor(totalBeats / 4);
            const quarters = Math.floor(totalBeats % 4);
            // Approximate remaining beats into 16th notes
            const sixteenths = Math.floor(((totalBeats % 4) - quarters) * 4);

            const transportTime = `${bars}:${quarters}:${sixteenths}`;

            // See:
            // https://github.com/dpren/react-piano-roll#notedata--arrayarraytransporttime-note-noteduration
            // for noteData information
            allNotes.push([
              transportTime, 
              note.name,       // Note value (using raw MIDI number)
              secondsToRhythmValue(note.duration, bpm)
            ]);
          });
        });

        setFormattedNotes(allNotes);
        setLoading(false);
      } catch (error) {
        console.error("Error parsing MIDI file:", error);
        setLoading(false);
      }
    }

    loadAndConvertMidi();
  }, [midiUrl]);

  useEffect(() => {
    const synth = new Tone.PolySynth(Tone.Synth).toDestination();
    synthRef.current = synth;

    formattedNotes.forEach(([time, note, duration]) => {
      Tone.Transport.schedule((timeRef) => {
        synth.triggerAttackRelease(note, duration, timeRef);
      }, time);
    });

    return () => {
      Tone.Transport.cancel();
      synth.dispose();
    };
  }, [formattedNotes]);

  const togglePlayback = async () => {
    if (Tone.context.state !== "running") {
      await Tone.start();
    }

    if (isPlaying) { // Pause
      Tone.Transport.pause();
      if (playbackRef.current) {
        playbackRef.current.pause();
      }
      setPlaying(false);
    } else { // Play
      Tone.Transport.start();
      if (playbackRef.current) {
        playbackRef.current.play();
      }
      setPlaying(true);
    }
  };

  const stopPlayback = useCallback(() => {
    Tone.Transport.stop();
    playbackRef.current?.seek("0:0:0");
    playbackRef.current?.pause();
    setPlaying(false);
  }, []);

  if (loading) return <div>Loading MIDI data...</div>;

  return (<div>
    <div>
        <button onClick={togglePlayback}> {isPlaying ? "Pause" : "Play"} </button>
        <button onClick={stopPlayback}> Stop </button>
      </div>
    <PianoRoll
    //   width={1200}
    //   height={660}
      noteData={formattedNotes}
      ref = {playbackRef}
    />
    </div>
  );
}