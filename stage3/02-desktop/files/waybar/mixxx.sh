#!/bin/bash

if ! pgrep -x "mixxx" > /dev/null
then
    /usr/local/bin/mixpi-mixxx
fi
