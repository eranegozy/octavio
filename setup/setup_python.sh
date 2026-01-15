#!/bin/bash
set -e

# replace with correct path
export CLIENT_USERNAME="eric"
export USER_DIRECTORY="/home/$CLIENT_USERNAME"

if [ -d "$USER_DIRECTORY/.pyenv" ]; then
echo "Found pyenv, skipping install"
else
echo "Installing pyenv"
curl https://pyenv.run | bash
fi

echo

echo "Installing pyenv dependencies"
sudo apt update
sudo apt install make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev curl git \
libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev

echo

echo "Installing python 3.10"
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv virtualenv-init -)"
pyenv update
pyenv install 3.10
pyenv global 3.10



