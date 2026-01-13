import struct
import os

file_path = "test_dataset/sub-001/ses-001/image/VPDATA.RAW"


def read_varioport(file_path):
    with open(file_path, "rb") as f:
        # Read File Header (36 bytes)
        file_header = f.read(36)

        # Read Channel Descriptors (3 * 40 bytes = 120 bytes)
        # Total header = 156 bytes
        f.seek(36)
        channels = []
        for i in range(3):
            chan_data = f.read(40)
            name = chan_data[0:10].decode("ascii", errors="ignore").strip()
            channels.append(name)
            print(f"Channel {i}: {name}")

        # Data starts at 156?
        f.seek(156)

        # Read some data
        data_bytes = f.read(2000)

        # Try int16
        count = len(data_bytes) // 2
        values = struct.unpack(f"<{count}h", data_bytes)

        print(f"First 20 values (int16): {values[:20]}")

        # If interleaved 3 channels:
        # Ch0, Ch1, Ch2, Ch0, Ch1, Ch2...
        ch0 = values[0::3]
        ch1 = values[1::3]
        ch2 = values[2::3]

        print(f"Ch0 ({channels[0]}) first 10: {ch0[:10]}")
        print(f"Ch1 ({channels[1]}) first 10: {ch1[:10]}")
        print(f"Ch2 ({channels[2]}) first 10: {ch2[:10]}")


if __name__ == "__main__":
    if os.path.exists(file_path):
        read_varioport(file_path)
    else:
        print(f"File not found: {file_path}")
