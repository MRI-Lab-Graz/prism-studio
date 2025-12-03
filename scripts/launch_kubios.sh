#!/bin/bash
# Script to launch Kubios HRV with a custom MATLAB Runtime path on macOS
# Usage: ./scripts/launch_kubios.sh [path_to_kubios_app]

# 1. Configure MATLAB Runtime Path
# The user specified this path:
MCR_ROOT="/Volumes/Evo/kubios_matlab/R2024b"

# Auto-detect the version folder (e.g., v917 for R2024b)
if [ -d "$MCR_ROOT" ]; then
    # Check for architecture (Apple Silicon vs Intel)
    if [ -d "$MCR_ROOT/bin/maca64" ]; then
        ARCH="maca64"
        VERSION_DIR="$MCR_ROOT"
    elif [ -d "$MCR_ROOT/bin/maci64" ]; then
        ARCH="maci64"
        VERSION_DIR="$MCR_ROOT"
    else
        # Try to find a subdirectory like v917
        SUB_DIR=$(find "$MCR_ROOT" -maxdepth 1 -name "v*" | head -n 1)
        if [ -n "$SUB_DIR" ]; then
            if [ -d "$SUB_DIR/bin/maca64" ]; then
                ARCH="maca64"
                VERSION_DIR="$SUB_DIR"
            elif [ -d "$SUB_DIR/bin/maci64" ]; then
                ARCH="maci64"
                VERSION_DIR="$SUB_DIR"
            fi
        fi
    fi

    if [ -z "$VERSION_DIR" ] || [ -z "$ARCH" ]; then
        echo "Error: Could not determine MATLAB Runtime structure or architecture (maca64/maci64) in $MCR_ROOT"
        exit 1
    fi
    
    echo "Found MATLAB Runtime: $VERSION_DIR ($ARCH)"
    
    # Set DYLD_LIBRARY_PATH for macOS
    # This tells the system where to find the MATLAB shared libraries
    export DYLD_LIBRARY_PATH="${VERSION_DIR}/runtime/${ARCH}:${VERSION_DIR}/bin/${ARCH}:${VERSION_DIR}/sys/os/${ARCH}:${VERSION_DIR}/extern/bin/${ARCH}:${DYLD_LIBRARY_PATH}"
    
    echo "Environment variables set."
else
    echo "Error: MATLAB Runtime path not found: $MCR_ROOT"
    exit 1
fi

# 2. Find and Launch Kubios
# Try to find Kubios executable. 
# Common paths or passed as argument.

KUBIOS_PATH="$1"

if [ -z "$KUBIOS_PATH" ]; then
    # Default guesses
    POSSIBLE_PATHS=(
        "/Applications/KubiosHRVScientific/application/KubiosHRVScientific.app/Contents/MacOS/KubiosHRVScientific"
        "/Applications/KubiosHRV.app/Contents/MacOS/KubiosHRV"
        "/Applications/Kubios HRV/KubiosHRV.app/Contents/MacOS/KubiosHRV"
        "/Volumes/Evo/KubiosHRV/KubiosHRV.app/Contents/MacOS/KubiosHRV"
        "/Volumes/Evo/software/KubiosHRV/KubiosHRV.app/Contents/MacOS/KubiosHRV"
    )
    
    for path in "${POSSIBLE_PATHS[@]}"; do
        if [ -f "$path" ]; then
            KUBIOS_PATH="$path"
            break
        fi
    done
fi

if [ -n "$KUBIOS_PATH" ] && [ -f "$KUBIOS_PATH" ]; then
    echo "Launching Kubios from: $KUBIOS_PATH"
    "$KUBIOS_PATH"
else
    echo "Error: Could not find Kubios executable."
    echo "Usage: ./scripts/launch_kubios.sh /path/to/KubiosHRV.app/Contents/MacOS/KubiosHRV"
    echo "Or edit this script to set the correct path."
fi
