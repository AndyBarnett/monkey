#!/bin/bash

function adb {
    "$sdk/platform-tools/adb" "$@"
}

function dup {
    while read -r; do
        echo "$REPLY"
        echo "$REPLY" >&2
    done
}

function filter_devices {
    while read -r; do
        local line=($REPLY)
        local blacklisted=0
        [ "${line[0]}" = "????????????" -o "${line[1]}" != "device" ] && continue
        for device in "${blacklist[@]}"; do
            if [ "${line[0]}" = "$device" ]; then
                blacklisted=1
                break
            fi
        done
        [ $blacklisted -ne 0 ] && continue
        echo "${line[0]}"
    done
}
