 # runs the loops and runs the motors for the ctypes

import time
import csv
import sys
import os
import threading
import ctypes
import pandas as pd
import struct
from analysis import processors
from toolbox import delsys_api_client as api
from toolbox.participant_manager import ParticipantDataManager
from itertools import zip_longest
#from analysis.processors import emg_envelope, force_envelope, force_timestamps, emg_timestamps


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__),'..')))

class SessionManager:
    def __init__(self, data_manager: ParticipantDataManager, gui_callback):
        """
        data_manager: ParticipantDataManager instance
        gui_callback: A function in the main GUI to update the plot/stats
        """
        self.lock = threading.Lock() # This should make each thread wait it's turn when making API calls

        self.dm = data_manager   #use instance passed from the GUI
        self.gui_update = gui_callback

        # state variables for current active entry
        self.active_threshold = 0.0
        self.session_maxes = []
        self.success_history = []
        self.current_trial_num = 0
        self.total_trials_needed = 0
        self.p_id = None
        self.entry_idx = None
        self.sess_type = None

    def prepare_session(self, p_id, entry_idx, session_type):
        """Sets up the session variables but doesn't run the loop"""
        self.p_id = p_id
        self.entry_idx = entry_idx
        self.sess_type = session_type

        # Load threshold (if there is one saved)
        try:
            self.active_threshold = self.dm.get_threshold(p_id)
        except AttributeError:
            self.active_threshold = 0.0 # fallback if no threshold

        self.session_maxes = []
        self.success_history = []
        self.current_trial_num = 0
        self.total_trials_needed = 50 if session_type == "baseline" else 75
        return self.total_trials_needed

    def run_single_trial(self):
        """Runs one trial, updates GUI and returns True if more trials remain"""
        if self.current_trial_num >= self.total_trials_needed:
            return False
        
        self.current_trial_num += 1

        threading.Thread(target=self._trial_worker, daemon=True).start()
        
        return True

    def _trial_worker(self):
    
        print(f"##########################\n\nPair Status: {api.check_pair_status()}\n\n##########################")
        print(f"##########################\n\nReady to Steam: {api.ready_to_stream()}\n\n##########################")
      
        """this works in parallel to the GUI via threading"""
        # collect data (where motor code and sensor code will live
        motor = ctypes.CDLL("/home/letrep/Downloads/Linux_Software/sFoundation/libMotor_working3.so")

        self.raw_force = []  # Clears the Force Data array before collection

        #initiate and home motors giving a 30000 ms window
        # motor.setup_and_home(30000)                     #allow motor to find home position
        motor.acceleration_velocity_set(1000,100)		#set a and v limits to 1000rpm/s and 500 rpm (medium movement)
        motor.move_counts(-8000,1)                      #move to 45 degrees
        time.sleep(1)                                   #wait for 1 seconds

        # PRE-TRIAL (e.g., Preloading Motors) may be included in base ctypes
        motor.acceleration_velocity_set(500, 30)        #set acceleration and velocity limits to 500rpm/s and 30rpm (slow movement)
        motor.move_speed(30)                            #move at 30 rpm                            
        time.sleep(.75)                                   #move for 3/4 second (check if it acts as a delay or pause)
        
        # Reflex induction and EMG Data Collection
        motor.acceleration_velocity_set(4000, 2000)      #set acceleration and velocity limits to 2000rpm/s and 500 rpm (quick movement)

        with self.lock:
            api.start_collect()  # begins data collection for EMG sensors

        # Begin force collection with ACK check
        if not self.send_command_with_ack(b'S'):
            print("x ESP32 did not ACK start command.")
            return
            
        time.sleep(0.5) # Force Sensor and EMG Sensor Collect for 300 ms prior to collection being enabled
        motor.move_counts(-500, 1)  # move to 500 counts offset from home
        time.sleep(1)                 # allow motion to complete

        # Stop force collection with ACK check
        if not self.send_command_with_ack(b'T'):
            print("x ESP32 did not ACK stop command.")
            return

        # Fetch the binary force data as DataFrame
        self.raw_force = self._fetch_esp32_force()

        with self.lock:
            raw_emg = api.stop_collect()
        
        # This calls the bridge function below
        time.sleep(.5)                                   #wait for 1 seconds (temporarily waits for 2.5 seconds)
        # motor.shutdown_node()

        # ANALYSIS & SAVING
        # fig, axs = processors._debug_plot(combined_df, emg_envelope, xf, yf, filtered_force)
        results = processors.analize_trial(raw_emg, self.raw_force, self.active_threshold)
        #self.session_maxes.append(results["max_emg"])
        #self.success_history.append(results["is_success"])
        
        self._temp_save_and_move(   #this needs to be passed the processed data from processors
            self.p_id, self.entry_idx, self.sess_type, 
            self.current_trial_num, raw_emg, self.raw_force, results)
        
        # UI UPDATE
        successes = self.success_history.count(True)
        fails = self.success_history.count(False)
        self.gui_update(self.session_maxes, self.active_threshold, successes, fails)

        if self.current_trial_num >= self.total_trials_needed:
            self._handle_end_of_session_math()
        
        def _handle_end_of_session_math(self):
            """
            Calculates and saves new thresholds based on performance.
            """
            if self.sess_type == "baseline":
                new_t = processors.calculate_start_threshold(self.session_maxes)

            else:
                # mastery check: if 75% success, reduce threshold by 35%
                new_t = processors.threshold_adjust(self.success_history, self.active_threshold)

            if new_t != self.active_threshold:
                self.dm.update_threshold(self.p_id, new_t)

    def _fetch_esp32_force(self):
        """
        Fetch force and timestamp data from ESP32 over serial and return as a pandas DataFrame.
        Assumes ESP32 sends binary:
        - 4 bytes: uint32 sample count
        - 4 bytes: float force
        - 4 bytes: uint32 timestamp (microseconds)
        """
        if not self.ser:
            return pd.DataFrame(columns=['timestamp_us', 'force_V'])

        # 1. Clear any leftover data
        self.ser.reset_input_buffer()
        
        # 2. Trigger the dump
        self.ser.write(b'D')

        # 3. Wait for ACK byte from ESP32
        start_wait = time.time()
        while self.ser.in_waiting == 0:
            if (time.time() - start_wait) > 2.0:
                print("x ESP32 never acknowledged dump command.")
                return pd.DataFrame(columns=['timestamp_us', 'force_V'])
            time.sleep(0.01)

        ack = self.ser.read(1)
        if ack != b'A':
            print("x Unexpected ACK:", ack)
            return pd.DataFrame(columns=['timestamp_us', 'force_V'])

        # 4. Wait for 4 bytes (sample count)
        while self.ser.in_waiting < 4:
            if (time.time() - start_wait) > 2.0:
                print("x ESP32 never sent sample count.")
                return pd.DataFrame(columns=['timestamp_us', 'force_V'])
            time.sleep(0.01)

        count_bytes = self.ser.read(4)
        sample_count = struct.unpack('<I', count_bytes)[0]
        print(f"v ESP32 reporting {sample_count} samples.")

        # 5. Read all samples (8 bytes each: 4 float + 4 uint32)
        bytes_needed = sample_count * 8
        data_bytes = b''
        start_wait = time.time()
        while len(data_bytes) < bytes_needed:
            if self.ser.in_waiting > 0:
                data_bytes += self.ser.read(self.ser.in_waiting)
            if (time.time() - start_wait) > 5.0:
                print(f"x Timeout: only received {len(data_bytes)//8} of {sample_count} samples.")
                break
            time.sleep(0.001)

        # 6. Unpack data
        forces = []
        timestamps = []
        for i in range(0, len(data_bytes), 8):
            f_bytes = data_bytes[i:i+4]
            t_bytes = data_bytes[i+4:i+8]
            if len(f_bytes) < 4 or len(t_bytes) < 4:
                break
            forces.append(struct.unpack('<f', f_bytes)[0])
            timestamps.append(struct.unpack('<I', t_bytes)[0])

        # 7. Create pandas DataFrame
        df = pd.DataFrame({
            'timestamp_us': timestamps,
            'force_V': forces
        })

        print(f"v Received {len(df)} force samples successfully.")
        return df
    
    def _temp_save_and_move(self, p_id, entry_idx, sess_type, trial_num, emg, force, results):
        temp_name = f"temp_trial_{trial_num}.csv"

        # Convert everything to lists to strip numpy type wrappers
        def ensure_list(data):
            if hasattr(data, "tolist"): return data.tolist()
            return list(data) if data is not None else []

        f_emg = ensure_list(results.get("EMG_Envelope"))
        t_emg = ensure_list(results.get("ENVELOPE_time_ms"))
        f_force = ensure_list(results.get("Forse_LPF"))
        t_force = ensure_list(results.get("FORCE_time_ms"))
        raw_force_v = ensure_list(force['force_V']) if not force.empty else []
        # Ensure raw emg (passed as 'emg') is also handled
        raw_emg = emg["value"].to_numpy(dtype = float)
        raw_emg = ensure_list(emg)

        with open(temp_name, 'w', newline='') as f:
            writer = csv.writer(f)

            # Write Metadata
            writer.writerow(["Trial: ", trial_num])
            #writer.writerow(["Threshold: ", float(self.active_threshold)])
            #writer.writerow(["Maximum EMG: ", float(results.get("max_emg", 0))])   
            #writer.writerow(["Success: ", bool(results.get("is_success"))])                   
            writer.writerow([]) 
            
            # Write Headers
            writer.writerow(["EMG Time","Filtered EMG","Force Time","Filtered Force (N)"]) 
            
            # Zip and Write Rows
            rows = zip_longest(t_emg, f_emg, t_force,  f_force, fillvalue="")
            writer.writerows(rows) # Use writerows for the zipped iterator

        self.dm.save_csv_to_session(p_id, entry_idx, sess_type, temp_name)

        if os.path.exists(temp_name):
            os.remove(temp_name)

    def send_command_with_ack(self, cmd: bytes, timeout=2.0) -> bool:
        """Send a single-byte command and wait for 'A' ACK from ESP32"""
        if not self.ser:
            return False

        # Clear any leftover bytes BEFORE sending
        self.ser.reset_input_buffer()
        
        # Send command
        self.ser.write(cmd)
        self.ser.flush()  # ensure it actually leaves the OS buffer

        # Set read timeout
        self.ser.timeout = timeout

        # Wait for ACK
        ack = self.ser.read(1)
        if ack != b'A':
            print(f"x No ACK for command {cmd}: received {ack}")
            return False

        return True