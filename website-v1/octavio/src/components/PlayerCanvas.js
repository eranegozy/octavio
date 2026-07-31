'use client';

import { Box } from "@mui/material";
import { useEffect, useRef, useState } from "react";
// import * as mm from '@magenta/music';
import { Player, PianoRollSVGVisualizer, midiToSequenceProto } from '@magenta/music';
import SessionDisplay from '@/components/SessionDisplay';

export default function PlayerCanvas({ session_id, instrument_id }) {
    const [ midiSequence, setMidiSequence ] = useState(null);
    const svgRef = useRef(null);
    const [player, setPlayer] = useState(null);
    const [visualizer, setVisualizer] = useState(null);

    useEffect(() => {
        fetch('http://octavio-server.mit.edu:5001/api/midi?session_id=1&instrument_id=2')
            .then(res => res.arrayBuffer())
            .then(arrayBuffer => setMidiSequence(midiToSequenceProto(arrayBuffer)))
    }, []);

    useEffect(() => {
        if (!midiSequence || !svgRef.current) return;

        // Create visualizer
        const vis = new PianoRollSVGVisualizer(
            midiSequence,
            svgRef.current,
            {
                noteHeight: 6,
                pixelsPerTimeStep: 60,
            });
        setVisualizer(vis);

        // Create player with run callback to update visualizer
        const newPlayer = new Player(false, {
            run: (note) => vis.redraw(note),
            stop: () => console.log('Playback finished'),
        });
        setPlayer(newPlayer);
    }, [midiSequence]);

    // const handlePlay = () => {
    //     if (player && midiSequence) {
    //         player.start(midiSequence);
    //     }
    // };

    return <svg ref={svgRef} width={800} height={200} />

    // return (
    //     // <Box>
    //         // <svg ref={svgRef} width={800} height={200} />
    //         {/* <SessionDisplay></SessionDisplay> */}
    //         {/* <Box sx={{ width: '800px', height: '200px', overflowX: 'auto', overflowY: 'hidden' }}>
    //             <svg ref={svgRef} width={800} height={200} />
    //         </Box>
    //         <button onClick={handlePlay} disabled={!player || !midiSequence}>
    //             Play
    //         </button> */}
    //     // </Box>
    // )
}
