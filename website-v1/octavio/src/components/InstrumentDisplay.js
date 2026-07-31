'use client';

import { Accordion, AccordionDetails, AccordionSummary, Box, Stack, Typography } from "@mui/material";
import { useEffect, useRef, useState } from "react";
// import * as mm from '@magenta/music';
import { Player, PianoRollSVGVisualizer, midiToSequenceProto } from '@magenta/music';
import SessionVisualizer from '@/components/SessionVisualizer';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';

export default function InstrumentDisplay({ instrument_id }) {
    const [ instrument_sessions, setInstrumentSessions ] = useState(null);
    const [expanded, setExpanded] = useState(null); // track which panel is open

    const handleAccordionChange = (panel) => (event, isExpanded) => {
        setExpanded(isExpanded ? panel : null);
    };

    useEffect(() => {
        fetch(`http://octavio-server.mit.edu:5001/api/instrument?instrument_id=${instrument_id}`)
            .then(res => res.json())
            .then(sessions => setInstrumentSessions(sessions))
    }, []);

    // const selectedInstrument

    const vizContainers = !!instrument_sessions && instrument_sessions.map(
        session => {
            const containerIsExpanded = expanded === session.session_id
            return (
                <Box key={session.id} sx={{ width: "75%" }}>
                    <Accordion expanded={containerIsExpanded} onChange={handleAccordionChange(session.session_id)}>
                        <AccordionSummary
                            expandIcon={<ArrowDropDownIcon />}
                            aria-controls="panel1-content"
                            id="panel1-header"
                        >
                            <Typography component="span" variant="h3">
                                Session <Box component="span" sx={{fontStyle: "italic"}}>{session.session_id}</Box>
                            </Typography>
                        </AccordionSummary>
                        <AccordionDetails>
                            {containerIsExpanded && <SessionVisualizer session={session} />}
                        </AccordionDetails>
                    </Accordion>
                </Box>

                // <Accordion key={session.id}>
                //     {/* <SessionVisualizer key={session.id} session_id={'leit50a4t1'} instrument_id={'1'} /> */}
                //     <SessionVisualizer session={session} />
                // </Accordion>
            )
        }
    )

    return (
        <Box padding={12}>
            <Stack gap={5}>
                <Typography variant="h1">Recent sessions from Instrument {instrument_id}</Typography>
                <Stack rowGap={5}>
                    {vizContainers}
                </Stack>
            </Stack>


            {/* {!!instrument_sessions && instrument_sessions.map(session => <SessionVisualizer key={session.id} session_id={'leit50a4t1'} instrument_id={'1'} />)} */}
            {/* <SessionVisualizer session_id={'leit50a4t1'} instrument_id={'1'} /> */}
            {/* <Box sx={{ width: '800px', height: '200px', overflowX: 'auto', overflowY: 'hidden' }}>
                <svg ref={svgRef} width={800} height={200} />
            </Box>
            <button onClick={handlePlay} disabled={!player || !midiSequence}>
                Play
            </button> */}
        </Box>
    )
}
