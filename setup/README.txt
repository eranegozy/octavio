Setting up the client Raspberry Pi requires a bit of work

CLIENT SETUP
1. use raspberry pi imager or something to download the OS onto the SD
2. ssh into raspberry pi
    2a. connect pi to keyboard, monitor, and network
    2b. run "sudo raspi-config", and in interface options enable ssh
    2c. use "hostname -I" to find out IP address of pi
    2d. ssh
3. clone repo
    3a. may need to generate ssh key if you want to push changes from pi
4. in setup_connection.sh and setup_installation.sh, change variables to correct values
    4a. look at SUDO_USER to OCTAVIO_PROJECT_PATH
    4b. also look at admin_scripts/refresh_client.sh if you care about that
5. run setup_connection.sh
6. downgrade python version (tflite-runtime latest version only works up to python 3.10)
    Option 1:
        6a. install pyenv https://www.samwestby.com/tutorials/rpi-pyenv
        6b. may need to install some build dependencies, see https://github.com/pyenv/pyenv/wiki#suggested-build-environment section on Ubuntu/Debian/Mint
        6c. install python 3.10
        6d. run "pyenv global 3.10" to allow python3.10 command
    Option 2:
        6a. run setup_python.sh
7. run setup_installation.sh
    7a. may need to change some package versions around (check client_requirements.txt)