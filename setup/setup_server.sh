#!/bin/bash
set -e

# Setting up useful variables

export SUDO_USER="ayyub"
export SERVER_USERNAME="ayyub"
export SERVER_HOSTNAME="octavio-server.mit.edu"
export USER_DIRECTORY="/home/$SERVER_USERNAME"
export OCTAVIO_PROJECT_PATH="$USER_DIRECTORY/octavio"

echo

# Make and populate venv environment

echo "Constructing virtual environment"
mkdir -p $USER_DIRECTORY/.envs
python3.10 -m venv $USER_DIRECTORY/.envs/octavio/
# sudo chown -R $SERVER_USERNAME:$SERVER_USERNAME $USER_DIRECTORY/.envs/

echo

echo "Populating virtual environment"
source $USER_DIRECTORY/.envs/octavio/bin/activate
python3.10 -m pip install --upgrade pip setuptools wheel
pip install -r "$OCTAVIO_PROJECT_PATH/server/server_requirements.txt"

echo

# Create and activate server systemd service

echo "Creating and activating server service"
SERVER_SERVICE_NAME="octavio-server"
envsubst < "$OCTAVIO_PROJECT_PATH/setup/server_template.txt" | sudo tee /etc/systemd/system/$SERVER_SERVICE_NAME.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable $SERVER_SERVICE_NAME.service
sudo systemctl start $SERVER_SERVICE_NAME.service

echo

# Adding helper scripts and extras to .bashrc

echo "Adding helper commands to bashrc"
printf "\nalias rs='source $OCTAVIO_PROJECT_PATH/admin_scripts/refresh_client.sh'\n" >> $USER_DIRECTORY/.bashrc
printf "\nalias kt='sudo bash $OCTAVIO_PROJECT_PATH/admin_scripts/kill_tunnels.sh'\n" >> $USER_DIRECTORY/.bashrc
printf "\nalias st='sudo bash $OCTAVIO_PROJECT_PATH/admin_scripts/show_tunnels.sh'\n" >> $USER_DIRECTORY/.bashrc

echo

echo "Installation steps complete"
