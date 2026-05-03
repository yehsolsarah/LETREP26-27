# This is called new_data_ann.py
import threading
import time
import random #for testing
import csv
import os

class Session_Manager: # pass the data_manager into the init
    def __init__(self, data_manager, participant_id):
        self.dm = data_manager
        self.participant_id = participant_id
        
        self.is_recording = False
        self.emg_bucket = []
        self.force_bucket = []
        self.running = True

        #start the background thread once when the object is created
        self.thread = threading.Thread(target=self._sensor_worker, daemon=True)
        self.thread.start()

    def _sensor_worker(self): # Internal background collector
        while self.running:
            if self.is_recording:
                #simulating sensor reads
                self.emg_bucket.append(random.uniform(-5.0, 5.0)) #set up sensor comunication
                self.force_bucket.append(random.uniform(0,100)) # ^^^^^^
            time.sleep(0.01)

    def run_baseline(self, move_duration): # Runs 50 motor moves and collects data
        baseline_summary = [] # to store all rectified data, max force and max emg
        for i in range(50):
            # reset and start
            self.emg_bucket = []
            self.force_bucket = []
            self.is_recording = True

            # move motor
            time.sleep(move_duration) # figure out how to do this with ctypes

            # stop and process
            self.is_recording = False

            rectified = [abs(x) for x in self.emg_bucket]
            max_emg = max(rectified) if rectified else 0
            max_force = max(self.force_bucket) if self.force_bucket else 0

            #store results of this specific run
            baseline_summary.append({
                "run": i +1,
                "max_emg": max_emg,
                "max_force": max_force,
                "raw_rectified": rectified # keeping this for the csv
            })

        return baseline_summary
        
    def run_normal(self,move_duration): 
        entry_summary = []
        for i in range(75):
            # reset and start
            self.emg_bucket = []
            self.force_bucket = []
            self.is_recording = True

            # move motor
            time.sleep(move_duration)

            # stop and process
            self.is_recording = False

            rectified = [abs(x) for x in self.emg_bucket]
            max_emg = max(rectified) if rectified else 0
            max_force = max(self.force_bucket) if self.force_bucket else 0
            #store results of this specific run

            entry_summary.append({
                "run": i +1,
                "max_emg": max_emg,
                "max_force": max_force,
                "raw_rectified": rectified # keeping this for the csv
            })

        return entry_summary
        