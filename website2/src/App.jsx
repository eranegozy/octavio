import { useState, useEffect } from 'react'
import DatePicker from "react-datepicker"
import 'react-datepicker/dist/react-datepicker.css'
import './App.css'

const online_instruments_url = "http://octavio-server.mit.edu:5001/api/online_instruments"
const log_url = "http://octavio-server.mit.edu:5001/api/logs"
const test_url = "http://octavio-server.mit.edu:5001/"

// async function fetchOnlineInstruments() {
//   const response = await fetch(online_instruments_url)
//   return response.text()
// }

// async function fetchLog(date) {
//   const params = {
//     date: date.toISOString().split('T')[0]
//   };
//   const url = new URL(log_url);
//   Object.keys(params).forEach(key => url.searchParams.append(key, params[key]));
//   const response = await fetch(url)
//   return response.text()
// }

function App() {
  const [online_instruments, setOnlineInstruments] = useState([])
  const [date, setDate] = useState(new Date())
  const [session_ids, setSessionIds] = useState(new Set())
  const [log_info, setLogInfo] = useState("")

  async function fetchOnlineInstruments() {
    const response = await fetch(online_instruments_url)
    setOnlineInstruments(await response.text())
  }

  async function fetchLog() {
    const params = {
      date: date.toISOString().split('T')[0]
    };
    const url = new URL(log_url);
    Object.keys(params).forEach(key => url.searchParams.append(key, params[key]));
    const response = await fetch(url)
    const response_text = await response.text();
    const response_json = JSON.parse(response_text);
    const new_session_ids = new Set(response_json.filter(
      (item) => item['operation'] === 'ADD_CHUNK'
    ).map(
      (item) => item['session_id']
    ));
    setLogInfo(response_text);
    setSessionIds(new_session_ids);
  }

  function init() {
    fetchOnlineInstruments();
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
      <div className="logs">
        <DatePicker showIcon selected={date} onChange={(date) => {
          setDate(date);
          fetchLog();
        }}/>
        <div className="session-ids">{'Sessions: {' + Array.from(session_ids).join(', ') + '}'}</div>
        <div className="log-body">{log_info}</div>
      </div>
    </>
  )
}

export default App
