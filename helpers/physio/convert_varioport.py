import struct
import json
import argparse
import numpy as np
import pandas as pd
import pyedflib
import math


def read_varioport_header(f, override_base_freq=None):
    """
    Reads the Varioport file header and channel definitions.
    Based on the R code 'read_vpd.R' and inspection of VPDATA.RAW.
    """
    f.seek(0)

    # 1. File Header
    # Byte 2: Header Length
    f.seek(2)
    hdrlen = struct.unpack(">H", f.read(2))[0]

    # Byte 4: Channel Offset
    f.seek(4)
    choffs = struct.unpack(">H", f.read(2))[0]

    # Byte 6: Header Type
    f.seek(6)
    hdrtype = struct.unpack(">B", f.read(1))[0]

    # Byte 7: Channel Count
    f.seek(7)
    chcnt = struct.unpack(">B", f.read(1))[0]

    # Byte 20: Global Scan Rate (Not in R code, but found in file)
    f.seek(20)
    file_scnrate = struct.unpack(">H", f.read(2))[0]
    
    if override_base_freq:
        scnrate = override_base_freq
        print(f"Using overridden base frequency: {scnrate} Hz (File says: {file_scnrate})")
    else:
        # FORCE 512 Hz base rate to achieve 256 Hz effective rate (since scnfac=2)
        # This overrides the file header (usually 150) based on technician's note and PI's duration confirmation.
        print(f"Forcing Base Rate to 512 Hz (File says: {file_scnrate}). Effective fs will be 256 Hz.")
        scnrate = 512

    print(
        f"Header Info: Length={hdrlen}, Type={hdrtype}, Channels={chcnt}, BaseRate={scnrate}"
    )

    # 2. Channel Definitions
    channels = []
    for i in range(chcnt):
        offset = choffs + i * 40
        f.seek(offset)
        ch_def = f.read(40)

        name = ch_def[0:6].decode("ascii", errors="ignore").strip()
        unit = ch_def[6:10].decode("ascii", errors="ignore").strip()
        # data_size: 0=uint8, 1=uint16. Actual bytes = val + 1
        dsize_code = ch_def[11]
        dsize = dsize_code + 1

        scnfac = ch_def[12]
        strfac = ch_def[14]

        mul = struct.unpack(">H", ch_def[16:18])[0]
        doffs = struct.unpack(">H", ch_def[18:20])[0]
        div = struct.unpack(">H", ch_def[20:22])[0]

        # Offset to data (relative to some base, R code adds hdrlen)
        offs_val = struct.unpack(">I", ch_def[24:28])[0]
        abs_offs = offs_val + hdrlen

        chlen = struct.unpack(">I", ch_def[28:32])[0]

        # Calculate effective sampling rate
        # chscnrate = scnrate / scnfac
        # chstrrate = chscnrate / strfac
        if scnfac == 0:
            scnfac = 1
        if strfac == 0:
            strfac = 1
        fs = scnrate / (scnfac * strfac)

        chan_info = {
            "index": i,
            "name": name,
            "unit": unit,
            "dsize": dsize,
            "scnfac": scnfac,
            "strfac": strfac,
            "mul": mul,
            "doffs": doffs,
            "div": div,
            "abs_offs": abs_offs,
            "chlen": chlen,
            "fs": fs,
        }
        channels.append(chan_info)
        print(
            f"Channel {i}: {name} ({unit}), fs={fs:.2f}Hz, len={chlen}, dsize={dsize}"
        )

    return hdrlen, hdrtype, channels


def get_default_scaling(name):
    """
    Returns default scaling parameters based on Varioport Toolbox (MATLAB).
    Used if file header contains invalid values (e.g. mul=0).
    """
    # Defaults from Varioport_Toolbox load_channel_data.m
    # offset = 32767
    defaults = {
        "EDA": {"doffs": 32767, "mul": 10, "div": 6400},
        "EMG1": {"doffs": 32767, "mul": 1297, "div": 10000},
        "EMG2": {"doffs": 32767, "mul": 1297, "div": 10000},
        "AUX": {
            "doffs": 32767,
            "mul": 1,
            "div": 1,
        },  # Toolbox says "no factors given... possible to omit offset", but code uses offset.
        "UBATT": {
            "doffs": 0,
            "mul": 127,
            "div": 10000,
        },  # Toolbox doesn't subtract offset for UBATT
        "BATT": {"doffs": 0, "mul": 127, "div": 10000},  # Alias
    }

    # Check for partial matches (e.g. "EDA " or "EDA1")
    for key in defaults:
        if name.upper().startswith(key):
            return defaults[key]
    return None


def convert_varioport(raw_path, output_path, sidecar_path, task_name="rest", base_freq=None):
    """
    Converts a Varioport .RAW file to BIDS .edf and .json.
    """

    with open(raw_path, "rb") as f:
        hdrlen, hdrtype, channels = read_varioport_header(f, override_base_freq=base_freq)

        # Identify active channels
        # In the test file, EKG has len=-1 (0xFFFFFFFF), others have 0.
        # We assume only channels with len != 0 are active.
        # BUT: Marker channel often has len=0 but is present in Type 7 streams (checking file size divisibility).
        active_channels = []
        for c in channels:
            if c["chlen"] != 0:
                active_channels.append(c)
            elif "marker" in c["name"].lower():
                # Force include marker if it looks like it might be in the stream
                # We'll verify block alignment later
                print(f"Force-including channel {c['name']} despite len=0")
                active_channels.append(c)

        if not active_channels:
            print(
                "No active channels found (all have length 0). Assuming all are active?"
            )
            active_channels = channels

        # Filter out unsupported dsize
        supported_channels = []
        for c in active_channels:
            if c["dsize"] in [1, 2]:
                supported_channels.append(c)
            else:
                print(f"Warning: Skipping channel {c['name']} with unsupported dsize {c['dsize']}")
        
        active_channels = supported_channels

        print(
            f"Found {len(active_channels)} active supported channels: {[c['name'] for c in active_channels]}"
        )

        # Check if all active channels have the same sampling rate
        if not active_channels:
            print("Error: No channels to process.")
            return

        # Determine effective sampling rate
        # We assume the stream is uniform with the highest rate found (usually EKG).
        # This handles the case where Marker is 1Hz in header but interleaved 1-to-1 with 256Hz EKG.
        effective_fs = max(c["fs"] for c in active_channels)
        print(f"Effective sampling rate for all channels: {effective_fs} Hz")

        # Prepare EDF headers
        signal_headers = []
        for c in active_channels:
            header = {
                'label': c["name"],
                'dimension': c["unit"],
                'sample_frequency': effective_fs,
                'physical_max': 32767, 
                'physical_min': -32768,
                'digital_max': 32767,
                'digital_min': -32768,
                'transducer': 'Varioport',
                'prefilter': ''
            }
            
            # Set reasonable physical ranges to avoid clipping
            if "ekg" in c["name"].lower():
                header['physical_min'] = -50000
                header['physical_max'] = 50000
            elif "marker" in c["name"].lower():
                header['physical_min'] = 0
                header['physical_max'] = 255
            elif "batt" in c["name"].lower():
                header['physical_min'] = 0
                header['physical_max'] = 20
            else:
                header['physical_min'] = -32768
                header['physical_max'] = 32767
                
            signal_headers.append(header)

        # Initialize EDF Writer
        try:
            f_edf = pyedflib.EdfWriter(output_path, len(active_channels), file_type=pyedflib.FILETYPE_EDFPLUS)
            f_edf.setSignalHeaders(signal_headers)
        except Exception as e:
            print(f"Error initializing EDF writer: {e}")
            return

        channel_data = {} # Only used for Type 6

        if hdrtype == 6:
            # Type 6: Reconfigured / Demultiplexed
            # Data for each channel is at specific offsets
            print(
                "Detected Type 6 (Reconfigured) file. Reading channels independently."
            )

            for ch in active_channels:
                name = ch["name"]
                print(f"Processing channel: {name}")

                data_start = ch["abs_offs"]
                data_len_bytes = ch["chlen"]

                f.seek(data_start)
                raw_bytes = f.read(data_len_bytes)

                dsize = ch["dsize"]
                num_samples = len(raw_bytes) // dsize

                if dsize == 2:
                    # Big Endian uint16
                    fmt = f">{num_samples}H"
                    raw_values = struct.unpack(fmt, raw_bytes[: num_samples * dsize])
                elif dsize == 1:
                    fmt = f">{num_samples}B"
                    raw_values = struct.unpack(fmt, raw_bytes[: num_samples * dsize])
                else:
                    print(f"Skipping channel {name}: Unsupported data size {dsize}")
                    continue

                # Apply scaling
                doffs = ch["doffs"]
                mul = ch["mul"]
                div = ch["div"]

                # Check for invalid scaling parameters and apply defaults if needed
                if mul == 0 or div == 0:
                    print(
                        f"  Warning: Invalid scaling (mul={mul}, div={div}). Checking defaults..."
                    )
                    defaults = get_default_scaling(name)
                    if defaults:
                        doffs = defaults["doffs"]
                        mul = defaults["mul"]
                        div = defaults["div"]
                        print(
                            f"  Applied defaults for {name}: doffs={doffs}, mul={mul}, div={div}"
                        )
                    else:
                        print(
                            f"  No defaults found for {name}. Using raw values (mul=1, div=1, doffs=0)."
                        )
                        doffs = 0
                        mul = 1
                        div = 1

                if div == 0:
                    div = 1  # Safety

                data_array = np.array(raw_values, dtype=float)
                data_array = (data_array - doffs) * mul / div

                channel_data[name] = data_array
            
            # Write Type 6 data to EDF
            # We need to pad to match lengths if they differ
            lengths = [len(d) for d in channel_data.values()]
            max_len = max(lengths)
            
            signals = []
            for h in signal_headers:
                name = h['label']
                data = channel_data.get(name, np.array([]))
                if len(data) < max_len:
                    padding = np.zeros(max_len - len(data))
                    data = np.concatenate([data, padding])
                signals.append(data)
            
            f_edf.writeSamples(signals)
            f_edf.close()

        else:
            # Type 7: Raw / Multiplexed (or other)
            # The data starts after the header and is interleaved.
            print(
                f"Detected Type {hdrtype} (Raw/Multiplexed). Streaming data to EDF..."
            )

            data_start = hdrlen
            f.seek(data_start)
            
            block_size = sum(c["dsize"] for c in active_channels)
            
            # Define chunk size (e.g. 60 seconds)
            # Must be multiple of effective_fs to align with 1s records
            chunk_duration = 60 # seconds
            samples_per_chunk = int(chunk_duration * effective_fs)
            bytes_per_chunk = samples_per_chunk * block_size
            
            # Prepare dtype for numpy
            dtype_list = []
            for c in active_channels:
                fmt = '>u2' if c["dsize"] == 2 else '>u1'
                safe_name = c["name"].replace(" ", "_").replace("(", "").replace(")", "")
                dtype_list.append((safe_name, fmt))
            dt = np.dtype(dtype_list)
            
            total_samples = 0
            
            while True:
                raw_bytes = f.read(bytes_per_chunk)
                if not raw_bytes:
                    break
                
                read_len = len(raw_bytes)
                num_blocks = read_len // block_size
                
                if num_blocks == 0:
                    break
                
                valid_bytes = num_blocks * block_size
                
                try:
                    raw_data = np.frombuffer(raw_bytes[:valid_bytes], dtype=dt)
                except Exception as e:
                    print(f"Error parsing buffer: {e}")
                    break
                
                chunk_signals = []
                for i, c in enumerate(active_channels):
                    safe_name = dtype_list[i][0]
                    raw_vals = raw_data[safe_name]
                    
                    # Scaling
                    doffs = c["doffs"]
                    mul = c["mul"]
                    div = c["div"]
                    
                    if mul == 0 or div == 0:
                        defaults = get_default_scaling(c["name"])
                        if defaults:
                            doffs = defaults["doffs"]
                            mul = defaults["mul"]
                            div = defaults["div"]
                        else:
                            doffs, mul, div = 0, 1, 1
                    if div == 0: div = 1
                    
                    data_array = raw_vals.astype(float)
                    data_array = (data_array - doffs) * mul / div
                    chunk_signals.append(data_array)
                
                # Write chunk
                try:
                    f_edf.writeSamples(chunk_signals)
                except Exception as e:
                    print(f"Error writing chunk to EDF: {e}")
                    break
                
                total_samples += num_blocks
                print(f"Processed {total_samples} samples...", end='\r')
            
            print(f"\nFinished streaming. Total samples: {total_samples}")
            f_edf.close()

        # Create Sidecar JSON
        sidecar = {
            "TaskName": task_name,
            "SamplingFrequency": effective_fs,
            "StartTime": 0,
            "Columns": [h['label'] for h in signal_headers],
            "Manufacturer": "Becker Meditec",
            "ManufacturersModelName": "Varioport",
            "Note": "Converted from VPDATA.RAW. Forced Base Rate 512Hz (Effective 256Hz).",
        }

        with open(sidecar_path, "w") as jf:
            json.dump(sidecar, jf, indent=4)

        print("Conversion complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Varioport RAW to BIDS")
    parser.add_argument("input_file", help="Path to VPDATA.RAW")
    parser.add_argument("output_edf", help="Path to output .edf")
    parser.add_argument("output_json", help="Path to output .json")
    parser.add_argument("--base-freq", type=float, help="Override base frequency (e.g. 1000)")

    args = parser.parse_args()

    convert_varioport(args.input_file, args.output_edf, args.output_json, base_freq=args.base_freq)
