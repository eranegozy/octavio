import { useState } from 'react';
import Select from 'react-select';

const SERVER_URL = "http://octavio-server.mit.edu:5001"
const instrument_data_url = `${SERVER_URL}/api/instrument`
const MIDI_URL = `${SERVER_URL}/api/midi`
import MidiPlayer from './MidiPlayer.tsx'

const dropdownStyle = {
  option: provided => ({
    ...provided,
    color: 'black'
  }),
}

const InstrumentSelector = ({ all_instruments }) => {
  const [selectedInstrument, setSelectedInstrument] = useState(null);
  
  const [sessionOptions, setSessionOptions] = useState([]);
  const [selectedSession, setSelectedSession] = useState(null);

  const [showMIDI, setShowMidi] = useState(false)

  async function fetchLatestSessions(id) {
    try {
      const response = await fetch(`${instrument_data_url}?instrument_id=${id}`);
      const response_json = await response.json();

      const formattedOptions = response_json.map(item => ({
          value: item.session_id || item, 
          label: item.id || item
      }));

      setSessionOptions(formattedOptions);
    } catch (error) {
      console.error("Failed to fetch sessions:", error);
    }
  }

  const handleInstrumentChange = (instrumentOption) => {
    setSelectedInstrument(instrumentOption);
    setSelectedSession(null); // Clear previous session choice
    setSessionOptions([]);
    setShowMidi(false);

    if (instrumentOption) {
      fetchLatestSessions(instrumentOption.value);
    }
  };

  const handleSessionChange = (sessionOption) => {
    setSelectedSession(sessionOption);
    setShowMidi(false);
  };

  const handleClick = () => {
    const chosenInstrument = selectedInstrument
    const chosenSession = selectedSession
    // console.log(`${selectedInstrument.value}, ${selectedSession.value}`)
    if (chosenInstrument === null || chosenSession === null)
      return alert(`Could not retrieve session MIDI. Please select ${(chosenInstrument === null) ? 'an instrument' : 'a session'}.`)
    setShowMidi(true);
  };

  return (
    <div style={{ maxWidth: '400px', margin: '20px auto', display: 'flex', flexDirection: 'column', gap: '15px' }}>
      
      <div>
        <label>Select Instrument:</label>
        <Select
          value={selectedInstrument}
          styles={dropdownStyle}
          onChange={handleInstrumentChange}
          options={all_instruments}
          isClearable
        />
      </div>

      <div>
        <label>Select Session:</label>
        <Select
          value={selectedSession}
          styles={dropdownStyle}
          onChange={handleSessionChange}
          options={sessionOptions} // Pass the fetched state array here
          isDisabled={!selectedInstrument} // Disable until instrument is chosen
          isClearable
        />
      </div>
    <button onClick={() => handleClick()}>Go</button>
    {showMIDI && <MidiPlayer midiUrl={`${MIDI_URL}?instrument_id=${selectedInstrument.value}&session_id=${selectedSession.value}`}/>}
    </div>
  );
};

export default InstrumentSelector;