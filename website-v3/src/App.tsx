import { useState, useEffect } from 'react'
// import DatePicker from "react-datepicker"
// import 'react-datepicker/dist/react-datepicker.css'
import './App.css'

import InstrumentSelector from './InstrumentSelector.tsx'

const SERVER_URL = "http://octavio-server.mit.edu:5001"
const instrument_data_url = `${SERVER_URL}/api/instrument`
const online_instruments_url = `${SERVER_URL}/api/online_instruments`
const log_url = `${SERVER_URL}/api/logs`


function App() {
  const [online_instruments, setOnlineInstruments] = useState([])
  const [instrument_choices, setInstrumentChoices] = useState([])
  const [latest_sessions, setLatestSessions] = useState([])
  const [date, setDate] = useState(new Date())
  const [session_ids, setSessionIds] = useState(new Map())
  const [log_info, setLogInfo] = useState("")

  async function fetchOnlineInstruments() {
    const response = await fetch(online_instruments_url)
    setOnlineInstruments(await response.text())
  }

  async function fetchInstrumentChoices() {
    const response = await fetch(online_instruments_url)
    const response_json = await response.json()

    const formattedOptions = response_json.map(item => ({
      value: item.id || item, 
      label: item.name || item
    }));

    setInstrumentChoices(formattedOptions);
  }
  
  async function fetchLatestSessions(id) {
    const response = await fetch(`${instrument_data_url}?instrument_id=${id}`);
    const response_text = await response.text();
    setLatestSessions(response_text);
  }

  async function fetchLog(date) {
    const params = {
      date: date.toISOString().split('T')[0]
    };
    const url = new URL(log_url);
    Object.keys(params).forEach(key => url.searchParams.append(key, params[key]));
    const response = await fetch(url)
    const response_text = await response.text();
    const response_json = JSON.parse(response_text);
    const instruments = new Set(response_json.map((item) => item['instrument_id']));
    const new_session_ids = new Map([...instruments].map((iid) => [iid, [...new Set(
      response_json.filter(
        (item) => item['operation'] === 'ADD_CHUNK' && item['instrument_id'] === iid
      ).map(
        (item) => item['session_id']
      )
    )]]));
    setLogInfo(response_text);
    setSessionIds(new_session_ids);
  }

  function init() {
    fetchOnlineInstruments();
    fetchInstrumentChoices();
    fetchLatestSessions('10');
    fetchLog();
  }

  useEffect(() => {
    init();
    const intervalId = setInterval(fetchOnlineInstruments, 30 * 1000) // 30 seconds
    return () => clearInterval(intervalId);
  }, [])

  return (
    <>
      <h1>Octavio Website</h1>
      <h2>Online Instruments: {online_instruments}</h2>
      <h2>{date.toDateString()}, {date.toTimeString()}</h2>
      {/* <div className="logs">
        <DatePicker showIcon selected={date} onChange={(date) => {
          setDate(date);
          fetchLog(date);
        }}/>
        
        <details>
          <div className="session-ids">{'Sessions: {\n' + Array.from(session_ids).map(([key, value]) => String(key) + ': [' + value.join(', ') + ']').join('\n') + '\n}'}</div>
          <div className="log-body">{log_info}</div>
        </details>

        <details>
          <div className="last-sessions">{'Sessions: \n' + latest_sessions}</div>
        </details>
      </div> */}
      <InstrumentSelector all_instruments={instrument_choices}/>
    </>
  )
}

export default App
