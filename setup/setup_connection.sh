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

# Create WIFI connections

MIT_NETWORK_NAME="MIT"
if nmcli connection show "$MIT_NETWORK_NAME" > /dev/null 2>&1; then
    echo "Connection $MIT_NETWORK_NAME already exists. Adjusting settings and skipping connection."
    nmcli connection modify "$MIT_NETWORK_NAME" connection.autoconnect yes
    nmcli connection modify "$MIT_NETWORK_NAME" connection.autoconnect-priority 8
else
    echo "Enter your password for the MIT network:"
    read MIT_PASSWORD
    printf "Creating the following connection:\n\tSSID: $MIT_NETWORK_NAME\n\tPassword: $MIT_PASSWORD\n"
    nmcli connection add type wifi con-name "$MIT_NETWORK_NAME" ssid "$MIT_NETWORK_NAME"
    nmcli connection modify "$MIT_NETWORK_NAME" wifi-sec.key-mgmt wpa-psk
    nmcli connection modify "$MIT_NETWORK_NAME" wifi-sec.psk "$MIT_PASSWORD"
    nmcli connection modify "$MIT_NETWORK_NAME" connection.autoconnect yes
    nmcli connection modify "$MIT_NETWORK_NAME" connection.autoconnect-priority 8
fi

echo

echo "Would you like to enter a mobile hotspot? If so, enter the SSID:"
read HOTSPOT_SSID
if [ -z "$HOTSPOT_SSID" ]; then
    echo "No hotspot provided. Skipping connection."
elif nmcli connection show "$HOTSPOT_SSID" > /dev/null 2>&1; then
    echo "Connection $HOTSPOT_SSID already exists. Adjusting settings and skipping connection."
    nmcli connection modify "$HOTSPOT_SSID" connection.autoconnect yes
    nmcli connection modify "$HOTSPOT_SSID" connection.autoconnect-priority 10
else
    echo "Enter your password for the mobile hotspot:"
    read HOTSPOT_PASSWORD
    printf "Creating the following connection:\n\tSSID: $HOTSPOT_SSID\n\tPassword: $HOTSPOT_PASSWORD\n"
    nmcli connection add type wifi con-name "$HOTSPOT_SSID" ssid "$HOTSPOT_SSID"
    nmcli connection modify "$HOTSPOT_SSID" wifi-sec.key-mgmt wpa-psk
    nmcli connection modify "$HOTSPOT_SSID" wifi-sec.psk "$HOTSPOT_PASSWORD"
    nmcli connection modify "$HOTSPOT_SSID" connection.autoconnect yes
    nmcli connection modify "$HOTSPOT_SSID" connection.autoconnect-priority 10
fi

echo

echo "Would you like to enter a home network? If so, enter the SSID:"
read HOME_SSID
if [ -z "$HOME_SSID" ]; then
    echo "No home network provided. Skipping connection."
elif nmcli connection show "$HOME_SSID" > /dev/null 2>&1; then
    echo "Connection $HOME_SSID already exists. Adjusting settings and skipping connection."
    nmcli connection modify "$HOME_SSID" connection.autoconnect yes
    nmcli connection modify "$HOME_SSID" connection.autoconnect-priority 5
else
    echo "Enter your password for the home network:"
    read HOME_PASSWORD
    printf "Creating the following connection:\n\tSSID: $HOME_SSID\n\tPassword: $HOME_PASSWORD\n"
    nmcli connection add type wifi con-name "$HOME_SSID" ssid "$HOME_SSID"
    nmcli connection modify "$HOME_SSID" wifi-sec.key-mgmt wpa-psk
    nmcli connection modify "$HOME_SSID" wifi-sec.psk "$HOME_PASSWORD"
    nmcli connection modify "$HOME_SSID" connection.autoconnect yes
    nmcli connection modify "$HOME_SSID" connection.autoconnect-priority 5
fi

echo

# Generate SSH keys on Pi and exchange with server

if ! [ -f $USER_DIRECTORY/.ssh/id_ed25519.pub ]; then
    echo "SSH keys don't exist on device. Creating them now."
    sudo -u "$SUDO_USER" ssh-keygen -t ed25519 -C "\"Raspberry Pi $DEVICE_NUM\""
else
    echo "Existing SSH keys present. Using found keys for transfer."
fi
echo "Copying SSH keys to lab server"
sudo -u "$SUDO_USER" ssh-keyscan -H $SERVER_HOSTNAME >> $USER_DIRECTORY/.ssh/known_hosts
ssh-copy-id -i $USER_DIRECTORY/.ssh/id_ed25519.pub $SERVER_USERNAME@$SERVER_HOSTNAME

echo

# Install autossh for lab tunnel

echo "Installing necessary packages"
# sudo rm -vrf /var/lib/apt/lists/* # Might need for corrupt lists?
sudo apt update
sudo apt install -y autossh

# Setup tunnel-to-lab systemd service

echo "Establishing tunnel to lab server"
TUNNEL_SERVICE_NAME="lab-tunnel"
envsubst < "$OCTAVIO_PROJECT_PATH/setup/tunnel_template.txt" | sudo tee /etc/systemd/system/$TUNNEL_SERVICE_NAME.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable $TUNNEL_SERVICE_NAME.service
sudo systemctl start $TUNNEL_SERVICE_NAME.service

echo

echo "Connection steps complete"

# Reboot Pi now to test whether tunnel functions correctly
