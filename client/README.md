# Client

The Octavio Pi client. Records audio, runs AMT on-device, and transmits MIDI to the server.

## Requirements

**Python 3.10 is required.** `tflite-runtime` does not support later versions. Always invoke scripts as `python3.10`, not `python3`. The virtualenv is set up by `setup/setup_installation.sh`.

## Config Files

Both files must exist in this directory before running the client.

**`infra.json`** — device identity and calibration (use `setup/infra_template.txt` as a starting point):
```json
{
  "INSTRUMENT_ID": <unique integer>,
  "RECORDING_DEVICE_INDEX": <index of USB audio device>
}
```
Calibration stats (`NOISE_*`, `SIGNAL_*`) are added automatically by `calibrate.py`. If absent, the client falls back to hardcoded defaults.

**`.env`** — runtime config:
```
DO_RECORD=true
DO_HEARTBEAT=true
SERVER_URL=http://octavio-server.mit.edu:5001
```

## Scripts

| Script | When to run |
|--------|-------------|
| `client.py` | Main entrypoint — run once, keeps running as a service |
| `calibrate.py` | First-time setup and after moving the device; writes calibration stats to `infra.json` |
| `mic_test.py` | Sanity-check the microphone; saves a 30s recording to `./temps/temp_recording.wav` |
| `hardware.py` | Test LED and button wiring via an interactive REPL |

## Notes

- `./temps/` is created fresh on each run of `client.py` and should not be used to store anything persistent.
- In production the client runs as the `octavio` systemd service. Use `admin_scripts/refresh_client.sh` to pull updates and restart it.

---

*This file was written with assistance from AI tools.*
