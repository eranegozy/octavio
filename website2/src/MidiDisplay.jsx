import React, { useEffect, useState } from "react";
import { Midi } from "@tonejs/midi";
import PianoRoll from "react-piano-roll";

export default function MidiPianoRollPlayer({ midiUrl }) {
  const [formattedNotes, setFormattedNotes] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadAndConvertMidi() {
        function secondsToNoteDuration(durationInSeconds, bpm = 120) {
            const secondsPerBeat = 60 / bpm;
            const beats = durationInSeconds / secondsPerBeat;

            // Rounding handles minor MIDI float precision deviations
            const roundedBeats = Math.round(beats * 100) / 100;

            // Map beat lengths to standard Tone.js duration strings
            if (roundedBeats >= 4) return "1n";       // Whole note (4 beats)
            if (roundedBeats >= 2) return "2n";       // Half note (2 beats)
            if (roundedBeats >= 1) return "4n";       // Quarter note (1 beat)
            if (roundedBeats >= 0.5) return "8n";     // Eighth note (0.5 beats)
            if (roundedBeats >= 0.25) return "16n";   // Sixteenth note (0.25 beats)
            
            return "32n";                             // Fallback for short notes
        }
      try {
        // Fetch and parse the MIDI file from the URL
        const midi = await Midi.fromUrl(midiUrl);

        const allNotes = [];

        midi.tracks.forEach((track) => {
          track.notes.forEach((note) => {
            console.log(note)
            // 1. Calculate Bars:Quarters:Sixteenths from note.time (seconds)
            const bpm = midi.header.tempos[0]?.bpm || 120;
            const secondsPerBeat = 60 / bpm;
            const totalBeats = note.time / secondsPerBeat;

            const bars = Math.floor(totalBeats / 4);
            const quarters = Math.floor(totalBeats % 4);
            // Approximate remaining beats into 16th notes (4 sixteenths per quarter)
            const sixteenths = Math.floor(((totalBeats % 4) - quarters) * 4);

            const transportTime = `${bars}:${quarters}:${sixteenths}`;

            // 2. Push formatted array element matching react-piano-roll's schema

            console.log(`totalBeats = ${totalBeats}`)
            allNotes.push([
              transportTime, 
              note.name,       // Note value (using raw MIDI number)
              secondsToNoteDuration(note.duration)    // Duration (raw value in seconds)
            ]);
          });
        });

        console.log(allNotes)

        setFormattedNotes(allNotes);
        setLoading(false);
      } catch (error) {
        console.error("Error parsing MIDI file:", error);
        setLoading(false);
      }
    }

    loadAndConvertMidi();
  }, [midiUrl]);

  if (loading) return <div>Loading MIDI data...</div>;

  return (
    <PianoRoll
    //   width={1200}
    //   height={660}
      noteData={formattedNotes}
    />
  );
}