import serial
import time
import csv
import threading
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque

# --- Settings ---
SERIAL_PORT = '/dev/ttyUSB0'
BAUD_RATE =  2148.148     # High-speed serial
BUFFER_SIZE = 1000      # Number of points to keep in live plot

# --- Serial Setup ---
ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.001)
time.sleep(2)

# --- CSV Logging Setup ---
csv_filename = 'data_log.csv'
file = open(csv_filename, mode='a', newline='')
writer = csv.writer(file)
writer.writerow(["Timestamp", "Force Reading"])

print(f"Listening for sensor data... Writing to {csv_filename} and plotting live.")

# --- Data buffers (thread-safe) ---
data_buffer = deque(maxlen=BUFFER_SIZE)  # For plotting
log_buffer = deque()                     # For logging

# --- Serial reading thread ---
def read_serial():
    while True:
        try:
            while ser.in_waiting:
                line_raw = ser.readline().decode('utf-8').strip()
                if line_raw:
                    try:
                        value = float(line_raw)
                        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                        data_buffer.append(value)
                        log_buffer.append((timestamp, value))
                    except ValueError:
                        pass
        except serial.SerialException:
            break  # stop if serial port disconnects

threading.Thread(target=read_serial, daemon=True).start()

# --- Plot setup ---
plt.style.use('seaborn-v0_8-darkgrid')
fig, ax = plt.subplots()
x_data = list(range(BUFFER_SIZE))
y_data = [0]*BUFFER_SIZE
line, = ax.plot(x_data, y_data, 'r-', linewidth=2)
ax.set_title("Live Force Sensor Data")
ax.set_xlabel("Sample")
ax.set_ylabel("Force Reading")
ax.set_ylim(0, 5000)

# --- Update function for animation ---
def update(frame):
    # Update plot data
    while data_buffer:
        y_data.append(data_buffer.popleft())
        y_data.pop(0)
    line.set_ydata(y_data)

    # Write to CSV
    while log_buffer:
        writer.writerow(log_buffer.popleft())
    file.flush()

    return line,

ani = FuncAnimation(fig, update, blit=True, interval=10)  # 50 Hz plot updates
plt.show()

# --- Cleanup ---
file.close()
ser.close()
