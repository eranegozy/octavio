#!/bin/bash
# lists all open processes on client ports (client ports hardcoded to 2001 thru 2020)

MAX_DEVICE_NUM=20
sudo lsof -i :2001-$((2000+$MAX_DEVICE_NUM))
