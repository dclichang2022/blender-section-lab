#!/usr/bin/env sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
BLENDER=${BLENDER_EXE:-}

if [ -z "$BLENDER" ]; then
    if command -v blender >/dev/null 2>&1; then
        BLENDER=$(command -v blender)
    elif [ -x /Applications/Blender.app/Contents/MacOS/Blender ]; then
        BLENDER=/Applications/Blender.app/Contents/MacOS/Blender
    fi
fi

if [ -z "$BLENDER" ] || [ ! -x "$BLENDER" ]; then
    echo "Blender was not found. Set BLENDER_EXE to your Blender executable." >&2
    exit 1
fi

exec "$BLENDER" "$PROJECT_DIR/section_lab.blend" --python "$PROJECT_DIR/section_lab_blender.py"
