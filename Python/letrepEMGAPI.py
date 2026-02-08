# Gilon Kraft
# LETREP26 - Software Subteam
# Date Started: 11/14/2025
# Modified for serial communication

"""This program implements the Delsys API
First, it establishes a connection with the EMG sensors"""

import sys
import time
import tkinter as tk
from tkinter import simpledialog
import pandas as pd

# Import the *correct* class names
from AeroPy.DataManager import DataKernel  # <-- FIX 1: The class is DataKernel
from AeroPy.TrignoBase import TrignoBase
from serial_comm_Win import SerialComm  # Import serial module

# --- This is the correct 3-step setup ---

# Step 1: Create the TrignoBase *first*, but pass 'None' for the handler.
base = TrignoBase(None)

# Step 2: Create the DataKernel and pass it the 'base' object.
# This works now because 'base' is not None.
dataHandler = DataKernel(base)

# Step 3: Complete the circle by setting the handler on the 'base' object.
base.collection_data_handler = dataHandler

# --- Your original logic, corrected ---

# The correct property is 'TrigBase' (capital T)
TrigBase = base.TrigBase

# Call the connection method *on the 'base' object*
print("Connecting to base...")
base.Connect_Callback()
print("Connection complete.")


# function to pair sensors
def pair_sensors():
    
    sensor_number = simpledialog.askinteger(
        title="Pair a Sensor",
        prompt="Enter the sensor number (1-16):",
        parent=window
    )
    TrigBase.PairSensor(True)
    TrigBase.PairSensor(sensor_number)


# function to scan for previously paired sensors
def scan_sensors():
    TrigBase.ScanSensors()

# function to initiate data collection
def start_collect(): 
    TrigBase.SelectAllSensors() 
    TrigBase.Configure(starttrigger=False, stoptrigger=False) 
    # wait up to 2 seconds for pipeline to arm 
    t0 = time.time() 
    while not TrigBase.IsPipelineConfigured() and time.time() - t0 < 2.0: 
        time.sleep(0.02) 
    if TrigBase.IsPipelineConfigured(): 
        TrigBase.Start(ytdata=True) 
        print("Collection started") 
    else: 
        print("Pipeline failed to arm; state:", TrigBase.GetPipelineState())

# function to stop data collection
def stop_collect(): # give the pipeline a short moment to produce packets 
    time.sleep(0.15) 
    net = TrigBase.PollYTData() 
    TrigBase.Stop() 
    
    # convert .NET ValueTuple to DataFrame (concise and robust) 
    df = pd.DataFrame([(str(k), s.Item1, s.Item2) for k in net.Keys for s in net[k]], columns=["guid", "time", "value"]) 
    df.to_csv("data.csv", index=False)
    window.last_df = df 
    return df

# The GUI in this file can, and should be deleted  
# Now we're going to build a GUI
window = tk.Tk()
window.title("LETREP26 Pair EMGs...")
window.geometry("960x540")

# Pair Sensors Button
pair_button = tk.Button(master=window, text="Pair Sensors", command=pair_sensors)
pair_button.pack()

# Scan Sensors Button
scan_button = tk.Button(master=window, text="Scan for Sensors", command=scan_sensors)
scan_button.pack()

# Start Collect Button
collect_button = tk.Button(master=window, text="Start Collection", command=start_collect)
collect_button.pack()

# Stop Collect Button
stop_button = tk.Button(master=window, text="Stop Collection", command=stop_collect)
stop_button.pack()

window.mainloop()
