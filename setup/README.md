# Octavio Setup Guide

This directory contains setup scripts and templates for provisioning new Raspberry Pi clients and deploying the server.

## Client Setup (Raspberry Pi)

**1. Flash the SD card**

Flash Raspberry Pi OS using [Raspberry Pi Imager](https://www.raspberrypi.com/software/). Enable SSH and set a username/password in the OS Customisation menu before writing.

**2. Connect to the Pi**

On first boot, connect a keyboard, monitor, and network. Then:
```bash
sudo raspi-config        # Interface Options → SSH → Enable
hostname -I              # find the Pi's IP address
ssh <username>@<ip>      # connect from your laptop
```

**3. Clone the repo**
```bash
git clone <repo-url>
```
Generate an SSH key first (`ssh-keygen -t ed25519`) if you want to push changes from the Pi.

**4. Configure the setup scripts**

Edit `setup_connection.sh` and `setup_installation.sh` and set:
- `SUDO_USER`, `CLIENT_USERNAME`, `USER_DIRECTORY`, `OCTAVIO_PROJECT_PATH`

Also update `admin_scripts/refresh_client.sh` if you'll use it for remote updates.

**5. Run the connection setup**

Sets up Wi-Fi profiles, exchanges SSH keys with the server, and installs the reverse tunnel service:
```bash
bash setup/setup_connection.sh
```

**6. Install Python 3.10**

Required — `tflite-runtime` only supports up to Python 3.10.

*Option A — via setup script:*
```bash
bash setup/setup_python.sh
```

*Option B — manually via pyenv:*
```bash
# Install pyenv: https://www.samwestby.com/tutorials/rpi-pyenv
# Install build deps: https://github.com/pyenv/pyenv/wiki#suggested-build-environment
pyenv install 3.10
pyenv global 3.10
```

**7. Run the installation script**

Creates the virtualenv, installs dependencies, and registers the `octavio` systemd service:
```bash
bash setup/setup_installation.sh
```
Check `client/client_requirements.txt` if any package versions need adjustment.

**8. Create `client/infra.json`**

Use `setup/infra_template.txt` as a starting point:
```json
{
  "INSTRUMENT_ID": <unique integer>,
  "RECORDING_DEVICE_INDEX": <index of USB audio device>
}
```
Then run calibration to populate noise/signal stats:
```bash
python3.10 client/calibrate.py
```

**9. Create `client/.env`**
```
DO_RECORD=true
DO_HEARTBEAT=true
SERVER_URL=http://octavio-server.mit.edu:5001
```

**10. Start the service**
```bash
sudo systemctl start octavio
```

---

## Server Setup

**1. Clone the repo** on the server PC.

**2. Create a virtualenv and install dependencies**
```bash
python3 -m venv ~/.envs/octavio
source ~/.envs/octavio/bin/activate
pip install -r server/server_requirements.txt
```

**3. Create `server/.env`**
```
USE_AWS=false          # set to true to enable S3 storage
IS_PROD=true
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=...
BUCKET=...
```

**4. Initialize the database**
```bash
cd server && python3 init_db.py
```

**5. Register and start the systemd service**

Use `setup/server_template.txt` as a template, then:
```bash
sudo systemctl enable octavio-server
sudo systemctl start octavio-server
```

**6. Updating a running server**
```bash
bash admin_scripts/refresh_server.sh
```

---

## SSH Access to Pi Clients

Each Pi maintains a persistent reverse SSH tunnel to the server (systemd service: `lab-tunnel`). Tunnel port = `2000 + INSTRUMENT_ID`.

From the server:
```bash
ssh -p <tunnel_port> <client_username>@localhost
```

From a laptop:
```bash
ssh -J <user>@octavio-server.mit.edu -p <tunnel_port> <client_username>@localhost
```

---

*This file was written with assistance from AI tools.*
