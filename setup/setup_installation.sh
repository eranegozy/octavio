#!/bin/bash
set -e

# Setting up useful variables

export SUDO_USER="eric"
export SERVER_USERNAME="ayyub"
export SERVER_HOSTNAME="octavio-server.mit.edu"
export CLIENT_USERNAME="eric"
export USER_DIRECTORY="/home/$CLIENT_USERNAME"
export OCTAVIO_PROJECT_PATH="$USER_DIRECTORY/octavio"

# Establish device information

echo "What is the unique device number?"
read DEVICE_NUM
export DEVICE_NUM
export TUNNEL_PORT=$(( $DEVICE_NUM + 2000 ))
echo "SSH tunnel port will be $TUNNEL_PORT"

echo

# Do separate installs (e.g. audio stuff) necessary

echo "Installing necessary packages"
sudo apt install -y portaudio19-dev

echo

# Make and populate venv environment

echo "Constructing virtual environment"
mkdir -p $USER_DIRECTORY/.envs
python3.10 -m venv $USER_DIRECTORY/.envs/octavio/
sudo chown -R $CLIENT_USERNAME:$CLIENT_USERNAME $USER_DIRECTORY/.envs/

echo

echo "Populating virtual environment"
source $USER_DIRECTORY/.envs/octavio/bin/activate
python3.10 -m pip install --upgrade pip setuptools wheel
pip install -r "$OCTAVIO_PROJECT_PATH/client/client_requirements.txt"

echo

# Construct project-specific files

echo "Creating project-specific files (infra.py, etc)"
envsubst < "$OCTAVIO_PROJECT_PATH/setup/infra_template.txt" > "$OCTAVIO_PROJECT_PATH/client/infra.json"

echo

# Create and activate client systemd service

echo "Creating and activating client service"
CLIENT_SERVICE_NAME="octavio"
envsubst < "$OCTAVIO_PROJECT_PATH/setup/client_template.txt" | sudo tee /etc/systemd/system/$CLIENT_SERVICE_NAME.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable $CLIENT_SERVICE_NAME.service
sudo systemctl start $CLIENT_SERVICE_NAME.service

echo

# Adding helper scripts and extras to .bashrc

echo "Adding helper command rs which automatically pulls latest code and restarts service (and extras to bashrc)"
printf "\nexport PYTHONIOENCODING=utf-8\n" >> $USER_DIRECTORY/.bashrc
printf "\nalias rs='source $OCTAVIO_PROJECT_PATH/admin_scripts/refresh_client.sh'\n" >> $USER_DIRECTORY/.bashrc

echo

echo "Installation steps complete"
