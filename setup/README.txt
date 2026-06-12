OCTAVIO SETUP GUIDE
===================

This directory contains setup scripts and templates for provisioning new Raspberry Pi
clients and deploying the server.


CLIENT SETUP (Raspberry Pi)
----------------------------

1. Flash Raspberry Pi OS to an SD card using Raspberry Pi Imager.
   Enable SSH and set a username/password in the imager's OS Customisation menu.

2. Boot the Pi and connect to it:
   - Connect a keyboard, monitor, and network on first boot
   - Run: sudo raspi-config → Interface Options → SSH (enable)
   - Find the IP address: hostname -I
   - SSH in from your laptop: ssh <username>@<ip>

3. Clone the repo:
   git clone <repo-url>
   (Generate an SSH key first if you want to push changes from the Pi)

4. Edit setup_connection.sh and setup_installation.sh:
   - Set SUDO_USER, CLIENT_USERNAME, USER_DIRECTORY, OCTAVIO_PROJECT_PATH
   - Also update admin_scripts/refresh_client.sh if you'll use it for updates

5. Run setup_connection.sh (sets up Wi-Fi, SSH key exchange with server, and reverse tunnel):
   bash setup/setup_connection.sh

6. Install Python 3.10 (required — tflite-runtime only supports up to 3.10):

   Option A — via setup script:
     bash setup/setup_python.sh

   Option B — manually via pyenv:
     Install pyenv: https://www.samwestby.com/tutorials/rpi-pyenv
     Install build dependencies: https://github.com/pyenv/pyenv/wiki#suggested-build-environment
     pyenv install 3.10
     pyenv global 3.10

7. Run setup_installation.sh (creates virtualenv, installs dependencies, registers systemd service):
   bash setup/setup_installation.sh
   (Check client/client_requirements.txt if any package versions need adjustment)

8. Create infra.json in the client/ directory (use setup/infra_template.txt as a starting point):
   {
     "INSTRUMENT_ID": <unique integer>,
     "RECORDING_DEVICE_INDEX": <index of USB audio device>
   }
   Run python3.10 client/calibrate.py to populate noise/signal calibration stats.

9. Create client/.env:
   DO_RECORD=true
   DO_HEARTBEAT=true
   SERVER_URL=http://octavio-server.mit.edu:5001

10. Start the service:
    sudo systemctl start octavio


SERVER SETUP
------------

1. Clone the repo on the server PC.

2. Create a virtualenv and install dependencies:
   python3 -m venv ~/.envs/octavio
   source ~/.envs/octavio/bin/activate
   pip install -r server/server_requirements.txt

3. Create server/.env:
   USE_AWS=false          # set to true to enable S3 storage
   IS_PROD=true
   AWS_ACCESS_KEY_ID=...
   AWS_SECRET_ACCESS_KEY=...
   AWS_REGION=...
   BUCKET=...

4. Initialize the database:
   cd server && python3 init_db.py

5. Register and start the systemd service (use setup/server_template.txt as a template):
   sudo systemctl enable octavio-server
   sudo systemctl start octavio-server

6. To update a running server:
   bash admin_scripts/refresh_server.sh


SSH ACCESS TO PI CLIENTS
-------------------------

Each Pi maintains a persistent reverse SSH tunnel to the server (systemd service: lab-tunnel).
Tunnel port = 2000 + INSTRUMENT_ID.

From the server:
  ssh -p <tunnel_port> <client_username>@localhost

From a laptop:
  ssh -J <user>@octavio-server.mit.edu -p <tunnel_port> <client_username>@localhost
