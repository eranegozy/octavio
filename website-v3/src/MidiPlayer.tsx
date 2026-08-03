import React, { useEffect, useState, useRef, memo, useCallback } from "react";
import * as Tone from "tone"
import PianoRoll from "react-piano-roll";
import { useParams } from "react-router";
import { loadAndFormatMidi } from "./MidiLoader.tsx";

const MemoPianoRoll = memo(
  React.forwardRef((props, ref) => <PianoRoll ref={ref} {...props} />)
);

const SERVER_URL = "http://octavio-server.mit.edu:5001"
const MIDI_ROOT_URL = `${SERVER_URL}/api/midi`

export default function MidiPlayer() {
  const [loading, setLoading] = useState(true);
  const [isPlaying, setPlaying] = useState(false);
  const [midiData, setMidiData] = useState({ notes: [], bpm: 120 });

  const playbackRef = useRef(null);
  const synthRef = useRef(null);

  const {iid, sid} = useParams();

  useEffect(() => {
    const synth = new Tone.PolySynth(Tone.Synth).toDestination();
    synthRef.current = synth;

    return () => {
      Tone.getTransport().cancel();
      synth.dispose();
    };
  }, []);

  const midiUrl = `${MIDI_ROOT_URL}?instrument_id=${iid}&session_id=${sid}`

  useEffect(() => {
    let isMounted = true;

    Tone.getTransport().stop();
    Tone.getTransport().cancel();

    loadAndFormatMidi(midiUrl)
      .then(({ notes, bpm }) => {
        if (!isMounted) return;

        Tone.getTransport().bpm.value = bpm;

        // Schedule audio playback in Tone.js
        notes.forEach(([time, note, duration]) => {
          Tone.getTransport().schedule((timeRef) => {
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
    if (Tone.getContext().state !== "running") {
      await Tone.start();
    }

    setPlaying((currentlyPlaying) => {
      if (currentlyPlaying) {
        Tone.getTransport().pause();
        playbackRef.current?.pause();
        return false;
      } else {
        Tone.getTransport().start();
        playbackRef.current?.play();
        return true;
      }
    });
  }, []);

  const stopPlayback = useCallback(() => {
    Tone.getTransport().stop();
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
    //   width={1200}
    //   height={660}
      key={midiUrl}
      noteData={midiData.notes}
      ref = {playbackRef}
      bpm= {midiData.bpm}
    />
    </div>
  );
}