#!/bin/bash
#

MAX_DEVICE_NUM=20
sudo lsof -i :2001-$((2000+$MAX_DEVICE_NUM))
