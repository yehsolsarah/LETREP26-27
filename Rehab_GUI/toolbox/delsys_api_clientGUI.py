import xmlrpc.client
import tkinter as tk
from tkinter import simpledialog
import numpy as np
import pandas as pd
import time

server = xmlrpc.client.ServerProxy("http://192.168.1.2:8000")

def pair_sensors():
    
    sensor_number = simpledialog.askinteger(
        title="Pair a Sensor",
        prompt="Enter the sensor number (1-16):",
        parent=window
    )
    server.pair_sensors(sensor_number)
    
def stop_collect():
    start_time = time.time()
    result = server.stop_collect()
    
    samples = np.frombuffer(result["samples"].data, dtype = result["sample_dtype"])
    timestamps = np.frombuffer(result["timestamps"].data, dtype = result["time_dtype"])
    values = np.frombuffer(result["values"].data, dtype = result["value_dtype"])
    
    result = pd.DataFrame({
        "samples": samples,
        "time": timestamps,
        "value": values    
    })
    
    end_time = time.time()

window = tk.Tk()
window.title("LETREP26 Pair EMGs...")
window.geometry("960x540")

# Pair Sensors Button
pair_button = tk.Button(master=window, text="Pair Sensors", command=pair_sensors)
pair_button.pack()

# Scan Sensors Button
scan_button = tk.Button(master=window, text="Scan for Sensors", command=lambda: server.scan_sensors())
scan_button.pack()

# Start Collect Button
collect_button = tk.Button(master=window, text="Start Collection", command=lambda: server.start_collect())
collect_button.pack()

# Stop Collect Button
stop_button = tk.Button(master=window, text="Stop Collection", command=lambda: stop_collect())
stop_button.pack()

window.mainloop()
