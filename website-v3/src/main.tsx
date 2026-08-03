import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router'; 
import './index.css'
import App from './App.tsx'
import MidiPlayer from './MidiPlayer.tsx';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<App />} />
        <Route path="/roll/:iid/:sid" element={<MidiPlayer />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)