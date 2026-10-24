#!/bin/bash
# macOS: double-click this in Finder to start TalonSync (the first time, it sets itself up).
cd "$(dirname "$0")"
chmod +x "./Run TalonSync.sh" 2>/dev/null
exec "./Run TalonSync.sh" "$@"
