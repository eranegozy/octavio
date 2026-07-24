import { useParams } from 'react-router';
import { useState } from 'react';
import Select from 'react-select';
import DatePicker from 'react-datepicker';
import 'html-midi-player';

import 'react-datepicker/dist/react-datepicker.css'

const log_url = "http://octavio-server.mit.edu:5001/api/logs"
const midi_url = "http://octavio-server.mit.edu:5001/api/midi"

function InstrumentInfo() {
    const [date, setDate] = useState(new Date())
    const [session_ids, setSessionIds] = useState(new Set())
    const [selection, setSelection] = useState(null)
    const [midi, setMidi] = useState(null)

    const { iid } = useParams();

    async function fetchLog(date) {
        const params = {
            date: date.toISOString().split('T')[0]
        };
        const url = new URL(log_url);
        Object.keys(params).forEach(key => url.searchParams.append(key, params[key]));
        const response = await fetch(url)
        const response_text = await response.text();
        const response_json = JSON.parse(response_text);
        const new_session_ids = new Set(response_json.filter(
            (item) => item['operation'] === 'ADD_CHUNK' && item['instrument_id'] === iid
        ).map(
            (item) => item['session_id']
        ));
        setSessionIds(new_session_ids);
    }

    async function fetchMidi(session_id) {
        const params = {
            instrument_id: iid,
            session_id: session_id,
        }
        const url = new URL(midi_url);
        Object.keys(params).forEach(key => url.searchParams.append(key, params[key]));
        const response = await fetch(url);
        const response_file = await response.blob();
        const response_url = URL.createObjectURL(response_file);
        console.log(url);
        setMidi(response_url);
    }

    return (
        <>
            <h1>Instrument ID: {iid}</h1>
            <DatePicker showIcon selected={date} 
                        onChange={(date) => {
                            setDate(date);
                            fetchLog(date);
                        }
            }/>
            <Select options = {[...session_ids].map((sid) => ({value: sid, label: sid}))}
                    value = {selection}
                    onChange = {
                        (option) => {
                            setSelection(option.value)
                            fetchMidi(option.value)
                        }
                    }
                    placeholder = 'Select Session'
            />
            <h3>{selection}</h3>
            <a href = {midi} download>Download MIDI</a>
            <midi-player src={midi} />
            <midi-visualizer type="piano-roll" src={midi} />
            {/* <ReactMidiVisualizer url={midi} width={800} height={400} /> */}
        </>
    )
}

export default InstrumentInfo