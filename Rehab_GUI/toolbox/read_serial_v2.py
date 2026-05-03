import serial
import serial.tools.list_ports
import time

# Target the specific Vendor ID (VID) for your ESP32 (10c4)
# This ignores the Teknic Hub (2890) entirely.
ESP32_VID = 0x10C4

# Find the port matching that VID
ports = [p.device for p in serial.tools.list_ports.comports() if p.vid == ESP32_VID]
SERIAL_PORT = ports[0] if ports else None

if not SERIAL_PORT:
    print("x ESP32 not found! Is it plugged in?")
    exit()

# --- Initialization ---
ser = serial.Serial(SERIAL_PORT, 115200, timeout=0.01)
time.sleep(2)
print(f"v Connected to ESP32 on {SERIAL_PORT}")

    
### Sampling Method: This is the important thing!! ###
def read_serial():
    line_raw = ser.readline().decode('utf-8').strip()
    if line_raw:
        try:
            return float(line_raw)
        except ValueError:
            return None # Handles partial/garbage strings
    return None # Return None explicitly if no data was read

### Conditions for Test ###
read = True
force_reading = []

### Sample Sampling Loop ###

while read:
    force_reading.append(read_serial())
    print(f"Force is {force_reading}")
