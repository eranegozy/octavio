import { useState, useEffect } from 'react'
import './App.css'

const online_instruments_url = "http://octavio-server.mit.edu:5001/api/online_instruments"
const test_url = "http://octavio-server.mit.edu:5001/"

async function fetchOnlineInstruments() {
  const response = await fetch(online_instruments_url)
  return response.text()
}

function App() {
  const [online_instruments, setOnlineInstruments] = useState([])

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
      <div></div>
    </>
  )
}

export default App
