import { Midi } from "@tonejs/midi";
import * as Tone from "tone";

/**
 * Fetches a MIDI file from a URL, parses it, and formats the notes to work with the
 * react-piano-roll schema
 * (https://github.com/carperbr/react-piano-roll#notedata--arrayarraytransporttime-note-noteduration).
 * @param {string} url - Direct URL to the .mid file
 * @returns {Promise<{ notes: Array<[string, string, string]>, bpm: number }>} (a Promise containing)
 *      formatted note data: an array of [transportTime, note, noteDuration] & detected BPM
 */
export async function loadAndFormatMidi(url: string) {
    console.log(url)
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load MIDI file from ${url}: ${response.statusText}`);
  }
  const arrayBuffer = await response.arrayBuffer();
  const midi = new Midi(arrayBuffer);
  const bpm = midi.header.tempos[0]?.bpm || 120;
  const formattedNotes: Array<[string, string, string]> = [];

  midi.tracks.forEach((track) => {
    track.notes.forEach((note) => {
        const totalBeats = note.time / 60 * bpm;
        const bars = Math.floor(totalBeats / 4);
        const quarters = Math.floor(totalBeats % 4);
        // Approximate remaining beats into 16th notes
        const sixteenths = Math.floor(((totalBeats % 4) - quarters) * 4)

        const transportTime = `${bars}:${quarters}:${sixteenths}`;
        const noteName = note.name; // e.g. "C4"
        // Slang notation (https://github.com/kylestetz/slang#rhythm-and-note-values) used for
        // duration values
        const duration = Tone.Time(note.duration).toNotation();

      formattedNotes.push([transportTime, noteName, duration]);
    });
  });

  return { notes: formattedNotes, bpm: bpm };
}