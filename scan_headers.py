import os
import glob
import struct
import pandas as pd

def read_header_info(f):
    try:
        f.seek(0)
        # Byte 2: Header Length
        f.seek(2)
        hdrlen = struct.unpack(">H", f.read(2))[0]

        # Byte 20: Global Scan Rate
        f.seek(20)
        base_rate = struct.unpack(">H", f.read(2))[0]
        
        # Channel info to get factors
        # Byte 4: Channel Offset
        f.seek(4)
        choffs = struct.unpack(">H", f.read(2))[0]
        
        # Byte 7: Channel Count
        f.seek(7)
        chcnt = struct.unpack(">B", f.read(1))[0]
        
        channels = []
        for i in range(chcnt):
            offset = choffs + i * 40
            f.seek(offset)
            ch_def = f.read(40)
            
            name = ch_def[0:6].decode("ascii", errors="ignore").strip()
            scnfac = ch_def[12]
            strfac = ch_def[14]
            
            if scnfac == 0: scnfac = 1
            if strfac == 0: strfac = 1
            
            fs = base_rate / (scnfac * strfac)
            channels.append(f"{name}:{fs:.1f}Hz")
            
        return base_rate, channels
    except Exception as e:
        return "Error", str(e)

def scan_all_vpd(root_dir):
    files = glob.glob(os.path.join(root_dir, '**', '*.vpd'), recursive=True)
    results = []
    
    print(f"Scanning {len(files)} files...")
    
    for path in files:
        with open(path, "rb") as f:
            base, chans = read_header_info(f)
            results.append({
                "File": os.path.basename(path),
                "BaseRate": base,
                "Channels": str(chans)
            })
            
    df = pd.DataFrame(results)
    return df

if __name__ == "__main__":
    df = scan_all_vpd("/Volumes/Evo/data/VPDATA")
    print(df.to_string())
    
    # Summary
    print("\nSummary of Base Rates:")
    print(df['BaseRate'].value_counts())
