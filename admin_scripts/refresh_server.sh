#!/bin/bash
# stops and reboots the server service when run on the PC
# server username is currently hardcoded (e.g. “ayyub”)

SERVER_USERNAME="ayyub"
USER_DIRECTORY="/home/$SERVER_USERNAME"
OCTAVIO_PROJECT_PATH="$USER_DIRECTORY/code/octavio"
SERVER_SERVICE_NAME="octavio-server"

cd $OCTAVIO_PROJECT_PATH
sudo -E systemctl stop $SERVER_SERVICE_NAME
git pull
sudo -E systemctl start $SERVER_SERVICE_NAME
