import React, { useEffect, useState, useRef, memo, useCallback } from "react";
import { Midi } from "@tonejs/midi";
import * as Tone from "tone"
import PianoRoll from "react-piano-roll";
import { loadAndFormatMidi } from "./MidiLoader";

const MemoPianoRoll = memo(
  React.forwardRef((props, ref) => <PianoRoll ref={ref} {...props} />)
);

export default function MidiPlayer({ midiUrl }) {
  const [loading, setLoading] = useState(true);
  const [isPlaying, setPlaying] = useState(false);
  const [midiData, setMidiData] = useState({ notes: [], bpm: 120 });

  const playbackRef = useRef();
  const synthRef = useRef();
 
  useEffect(() => {
    const synth = new Tone.PolySynth(Tone.Synth).toDestination();
    synthRef.current = synth;

    return () => {
      Tone.Transport.cancel();
      synth.dispose();
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    Tone.Transport.stop();
    Tone.Transport.cancel();

    loadAndFormatMidi(midiUrl)
      .then(({ notes, bpm }) => {
        if (!isMounted) return;

        Tone.Transport.bpm.value = bpm;

        // Schedule audio playback in Tone.js
        notes.forEach(([time, note, duration]) => {
          Tone.Transport.schedule((timeRef) => {
            synthRef.current?.triggerAttackRelease(note, duration || "8n", timeRef);
          }, time);
        });

        setMidiData({ notes, bpm });
        setLoading(false);
      })
      .catch((err) => {
        if (!isMounted) return;
        console.error("MIDI Load Error:", err);
        setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [midiUrl]);

  const togglePlayback = useCallback( async () => {
    if (Tone.context.state !== "running") {
      await Tone.start();
    }

    setPlaying((currentlyPlaying) => {
      if (currentlyPlaying) {
        Tone.Transport.pause();
        playbackRef.current?.pause();
        return false;
      } else {
        Tone.Transport.start();
        playbackRef.current?.play();
        return true;
      }
    });
  }, []);

  const stopPlayback = useCallback(() => {
    Tone.Transport.stop();
    if (playbackRef.current){
      playbackRef.current.seek("0:0:0");
      playbackRef.current.pause();
    }
    setPlaying(false);
  }, []);

  if (loading) return <div>Loading MIDI data...</div>;

  return (<div>
    <div>
        <button onClick={togglePlayback}> {isPlaying ? "Pause" : "Play"} </button>
        <button onClick={stopPlayback}> Reset </button>
      </div>
    <MemoPianoRoll
      width={1200}
      height={660}
      key={midiUrl}
      noteData={midiData.notes}
      ref = {playbackRef}
      bpm= {midiData.bpm}
    />
    </div>
  );
}