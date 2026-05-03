# Gilon Kraft

# LETREP26 - Software Subteam

# Date Started: 11/14/2025



"""This program implements the Delsys API

First, it establishes a connection with the EMG sensors"""



import sys

import time

import tkinter as tk

from tkinter import simpledialog

import pandas as pd

import numpy as np

from datetime import datetime



from socketserver import ThreadingMixIn

from xmlrpc.server import SimpleXMLRPCServer

from xmlrpc.client import Binary



# Import the *correct* class names

from external.AeroPy.DataManager import DataKernel  # <-- FIX 1: The class is DataKernel

from external.AeroPy.TrignoBase import TrignoBase



class ThreadedXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer):

    pass



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

def pair_sensors(sensor_number):

    init_time = datetime.now()

    while init_time + 15000 > datetime.now():

        TrigBase.PairSensor(True)

        TrigBase.PairSensor(sensor_number)



# function to return an array of the sensors paired

def get_sensor_names():

    list = TrigBase.GetSensorNames()

    return list



# function that returns a Bool based if the sensor has paired successfully

def check_pair_status():

    paired = TrigBase.CheckPairStatus()

    return paired



# function that returns a Bool if at least one sensor is connected and pipeline is armed

def ready_to_stream():

    ready = TrigBase.IsReadyToStartStream()

    return ready



# function to scan for previously paired sensors

def scan_sensors():

    TrigBase.ScanSensors()



# returns sensors to the stage where they can pair

def reset_pipeline():

    TrigBase.ResetPipeline()



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
    TrigBase.ResetPipeline()

   

    # convert .NET ValueTuple to DataFrame (concise and robust)

    df = pd.DataFrame([(str(k), s.Item1, s.Item2) for k in net.Keys for s in net[k]], columns=["guid", "time", "value"])

    df.to_csv('output.csv', index=False)

    df = df.drop(columns=["guid"])

    df["samples"] = df.index  # <-- ADD THIS

   

    # Extract Columns

    sample_numbers = df["samples"].to_numpy(dtype=np.int32) # integers

    timestamps = df["time"].to_numpy(dtype=np.float64) # floats

    values = df["value"].to_numpy(dtype=np.float32) # floats, can be negative

   

    result = {

        "samples": Binary(sample_numbers.tobytes()),

        "timestamps": Binary(timestamps.tobytes()),

        "values": Binary(values.tobytes()),

        "sample_dtype": str(sample_numbers.dtype),

        "time_dtype": str(timestamps.dtype),

        "value_dtype": str(values.dtype),

        "length": len(df) # for reshaping

    }

    return(result)

   

def get_pipeline_state():

    state = TrigBase.GetPipelineState()

    return state



if __name__ == "__main__":

    server = ThreadedXMLRPCServer(("0.0.0.0", 8000), allow_none=True, logRequests=True)



    server.register_function(pair_sensors, "pair_sensors")

    server.register_function(scan_sensors, "scan_sensors")

    server.register_function(start_collect, "start_collect")

    server.register_function(stop_collect, "stop_collect")

    server.register_function(get_sensor_names, "get_sensor_names")

    server.register_function(check_pair_status, "check_pair_status")

    server.register_function(get_pipeline_state, "get_pipeline_state")

    server.register_function(reset_pipeline, "reset_pipeline")

    server.register_function(ready_to_stream, "ready_to_stream")

    print("XML-RPC server listening on port 8000...")

    server.serve_forever()