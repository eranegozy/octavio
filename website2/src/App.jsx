import { useState, useEffect } from 'react'
import DatePicker from "react-datepicker"
import 'react-datepicker/dist/react-datepicker.css'
import './App.css'

const online_instruments_url = "http://octavio-server.mit.edu:5001/api/online_instruments"
const log_url = "http://octavio-server.mit.edu:5001/api/logs"
const test_url = "http://octavio-server.mit.edu:5001/"

async function fetchOnlineInstruments() {
  const response = await fetch(online_instruments_url)
  return response.text()
}

async function fetchLog(date) {
  const params = {
    date: date.toISOString().split('T')[0]
  };
  const url = new URL(log_url);
  Object.keys(params).forEach(key => url.searchParams.append(key, params[key]));
  const response = await fetch(url)
  return response.text()
}

function App() {
  const [online_instruments, setOnlineInstruments] = useState([])
  const [date, setDate] = useState(new Date())
  const [log_info, setLogInfo] = useState("")

  useEffect(() => {
    fetchOnlineInstruments().then(data => setOnlineInstruments(data));
    const intervalId = setInterval(() => {
      fetchOnlineInstruments().then(data => setOnlineInstruments(data))
    }, 30 * 1000) // 30 seconds
    return () => clearInterval(intervalId);
  }, [])
  return (
    <>
      <h1>Octavio Website</h1>
      <h2>Online Instruments: {online_instruments}</h2>
      <div className="logs">
        <DatePicker showIcon selected={date} onChange={(date) => {
          setDate(date)
          fetchLog(date).then(data=>setLogInfo(data))
        }}/>
        <div className="log-body">{log_info}</div>
      </div>
    </>
  )
}

export default App
