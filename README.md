# Octavio

Octavio is a distributed system for passively logging piano activity across multiple acoustic instruments. Raspberry Pi devices are attached to pianos in a shared space and continuously monitor for playing. When activity is detected, the audio is transcribed to MIDI on-device and transmitted to a central server — raw audio never leaves the instrument.

## Motivation

Understanding how shared acoustic instruments are actually used — how often they're played, for how long, what time of day, by how many people — is difficult to study without invasive recording. Octavio addresses this by performing automatic music transcription (AMT) locally on each device, preserving privacy while still capturing rich structured data about playing sessions.

## How It Works

Each Pi listens continuously through an attached microphone. Every 30 seconds, it checks for piano activity using a calibrated noise gate, runs a Basic Pitch neural AMT model on any detected audio, and POSTs the resulting MIDI to a central Flask server. A physical button on each device lets users pause logging for 30 minutes (indicated by a red LED) without interacting with software.

The server merges incoming MIDI chunks into per-session files, stores session metadata in SQLite, and optionally archives to AWS S3. A React frontend provides a live dashboard showing which instruments are online and browsable session histories.

## System Components

| Component | Location | Description |
|-----------|----------|-------------|
| Pi client | `client/` | Audio capture, AMT, session management, heartbeat |
| Server | `server/` | Flask API, MIDI storage, SQLite, S3 integration |
| Frontend | `website2/` | React dashboard for live status and session browsing |
| Shared utils | `utils.py`, `log_utils.py` | MIDI processing and logging shared by client and server |

## Setup

See [`setup/README.txt`](setup/README.txt) for instructions on provisioning a new Raspberry Pi client and deploying the server.

## Privacy

Audio recordings are processed entirely on the Raspberry Pi and discarded immediately after MIDI extraction. The server receives only symbolic MIDI data (note pitches and timings). No audio is stored or transmitted at any point.

---
*This file was written with assistance from AI tools.*
