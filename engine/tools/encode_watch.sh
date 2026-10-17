#!/bin/bash
# package each library shot as soon as it is finished
cd "$(dirname "$0")/.."
until grep -q CHAIN3DONE frames/chain3.log; do nice -n 10 tools/encode_library.sh > /dev/null 2>&1; sleep 60; done
nice -n 10 tools/encode_library.sh; echo WATCHDONE
