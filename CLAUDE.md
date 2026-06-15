# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Octavio is a distributed piano activity logging system. Raspberry Pi devices are placed on acoustic pianos and record audio. **Raw audio never leaves the Pi** — the client runs an Automatic Music Transcription (AMT) model on-device to extract MIDI, which is then POSTed as JSON to a central server. The server stores MIDI data and exposes an API consumed by a React frontend.

## Architecture

```
Raspberry Pi (client/)       Server PC (server/)        Frontend (website2/)
─────────────────────        ──────────────────         ────────────────────
Audio → AMT → MIDI JSON  →  Flask API + SQLite     →   React + Vite
                         →  AWS S3 (optional)
```

### Three-tier storage on the server
1. **Local disk** (`./partials/`, `./data/`) — rolling MIDI files merged per chunk received
2. **SQLite** (`octavio_prod.db` / `octavio_test.db`) — session metadata only, no MIDI; used by the frontend API
3. **AWS S3** (optional, `USE_AWS=true`) — chunk objects + cumulative `main` MIDI per session + daily newline-delimited JSON logs

### Key design constraints
- Client requires **Python 3.10** (tflite-runtime only supports up to 3.10)
- Client and server have **separate virtualenvs and requirements files**
- `infra.json` (gitignored) on each Pi stores `INSTRUMENT_ID`, `RECORDING_DEVICE_INDEX`, and calibration stats
- `.env` (gitignored) on both client and server stores config/credentials

### Client session lifecycle
- A session is a continuous recording identified by a random 10-char ID
- Every 30 seconds, `mic_callback` fires: silence check → noise-gate → Basic Pitch AMT → POST `/piano`
- Sessions end when: silence accumulates ≥ 10 chunks (5 min), session reaches 45 min cap, server fails persistently, or user presses the physical button
- Button press toggles privacy mode for 30 minutes (LED turns red, recording pauses)
- A background thread POSTs to `/heartbeat` every 30 seconds regardless of recording state

### MIDI chunk merging (server)
- Local mode: each incoming chunk is deserialized and combined into a rolling `running_{n}.mid` file via `utils.combine_midi_objects`, which handles boundary note deduplication
- S3 mode: chunks are stored individually as `chunk_{n}` objects; merging into `main` happens lazily on `GET /api/midi` or explicitly via `PATCH /merge`

### Shared utilities (`utils.py`, `log_utils.py`)
`utils.py` lives at repo root and is used by both client and server. It handles WAV I/O, Basic Pitch invocation, MIDI serialization/deserialization, chunk stitching, and silence detection. `log_utils.py` suppresses stderr at the OS fd level to silence noisy AMT model imports.

## Running Things

### Server
```bash
cd server
# development
flask --app server run --debug --host=0.0.0.0 --port=5001
# production (systemd service: octavio-server)
sudo systemctl start octavio-server
```

### Client (on Pi, Python 3.10 venv required)
```bash
cd client
python3.10 client.py
# production (systemd service: octavio)
sudo systemctl start octavio
```

### Frontend
```bash
cd website2
npm install
npm run dev      # development server
npm run build    # production build
npm run lint     # ESLint
```

### One-off client utilities
```bash
# First-time calibration (run from client/ directory, writes to infra.json)
python3.10 calibrate.py

# Mic sanity check (saves ./temps/temp_recording.wav)
python3.10 mic_test.py

# Hardware (LED/button) REPL test
python3.10 hardware.py

# Initialize the SQLite database
cd server && python3.10 init_db.py
```

### Updating deployed services
```bash
# On the Pi
bash admin_scripts/refresh_client.sh

# On the server PC
bash admin_scripts/refresh_server.sh
```

## Configuration Files

### `infra.json` (Pi only, gitignored)
Created from `setup/infra_template.txt`. Contains `INSTRUMENT_ID`, optionally `RECORDING_DEVICE_INDEX`, and noise/signal calibration percentiles written by `calibrate.py`.

### `.env` (gitignored, both client and server)
- Client: `DO_RECORD`, `DO_HEARTBEAT`, `SERVER_URL`
- Server: `USE_AWS`, `IS_PROD`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `BUCKET`

## SSH Access to Pi Clients

The Pis maintain a persistent reverse SSH tunnel to the server via `autossh` (systemd service: `lab-tunnel`). Each Pi gets a unique tunnel port at `2000 + INSTRUMENT_ID`. To SSH into a Pi from the server:

```bash
ssh -p <tunnel_port> <client_username>@localhost
```

From a laptop, jump through the server:
```bash
ssh -J <user>@octavio-server.mit.edu -p <tunnel_port> <client_username>@localhost
```

## S3 Layout

```
{prod|test}/
  ins_{instrument_id}/
    {session_id}/
      chunk_{n}       # individual 30s MIDI chunks (deleted after merge)
      main            # cumulative merged MIDI for the session
  logs/
    {year}/{month}/{day}.txt   # newline-delimited JSON (ADD_CHUNK, ADD_HEARTBEAT)
```

## Frontend API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/piano` | Receive MIDI chunk from Pi |
| POST | `/heartbeat` | Receive heartbeat from Pi |
| GET | `/api/instruments` | All instruments (SQLite) |
| GET | `/api/instrument?instrument_id=X` | Sessions for one instrument (SQLite, ≥2 min, last 5) |
| GET | `/api/midi?session_id=X&instrument_id=Y` | Download cumulative MIDI file |
| GET | `/api/online_instruments` | Instruments with heartbeat in last 5 min (S3 logs) |
| GET | `/api/logs?date=YYYY-MM-DD` | Raw daily log entries (S3) |
| GET | `/api/whatsup` | In-memory last-heartbeat map (lost on restart) |
| PATCH | `/merge` | Manually trigger S3 chunk merge |
