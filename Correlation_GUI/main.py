# Main Correlation GUI

import tkinter as tk
from tkinter import messagebox
import pandas as pd
import threading
import os
from datetime import datetime
import numpy as np
from scipy import signal
import time
import struct
import ctypes

# Matplotlib Embedding
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- LOCAL IMPORTS ---
from Themes import COLORS, FONTS  
from Participant_manager import ParticipantDataManager
from login_Popup import ParticipantLoginPopup, EntryPickerPopup
import delsys_reader as delsys



class ReflexApp:
    def __init__(self, root):
        self.root = root
        self.root.title('Reflex Test Control Panel')
        
        # 1. Window Setup
        self.root.geometry("800x480")
        self.root.configure(bg=COLORS['bg_main'])
        self.root.bind("<Escape>", self.toggle_fullscreen)
        self.root.protocol("WM_DELETE_WINDOW", self.exit_application)
        
        # Grid Config
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        # 2. State Management
        self.manager = ParticipantDataManager()
        self.ser = None 
        self.is_collecting = False
        self.force_data = []
        self.trial_counter = 0
        self.current_participant = "NONE"
        self.current_entry_index = 0

        # 3. Build UI
        self.build_dashboard()

        # 4. Hardware Initialization
        self.root.after(50, self.delayed_init)

    def delayed_init(self):
        self.root.attributes("-fullscreen", True)
        threading.Thread(target=self.init_hardware_background, daemon=True).start()
        
    def init_hardware_background(self):
        self.motor = ctypes.CDLL("/home/letrep/Downloads/Linux_Software/sFoundation/libMotor_working3.so")
        print("Performing hardware check...")
        ESP32_VID = 0x10C4 
        import serial.tools.list_ports
        ports = [p.device for p in serial.tools.list_ports.comports() if p.vid == ESP32_VID]
        SERIAL_PORT = ports[0] if ports else None
        
        if SERIAL_PORT:
            try:
                # MATCHING YOUR WORKING CODE: 921600 baud
                self.ser = serial.Serial(SERIAL_PORT, 921600, timeout=0.01)
                time.sleep(2) 
                print(f"v Connected to ESP32 on {SERIAL_PORT}")
            except Exception as e:
                print(f"x Serial Error: {e}")
        else:
            print("x ESP32 VID 0x10C4 not found.")

        self.motor.setup_and_home(30000)

    def toggle_fullscreen(self, event=None):
        self.root.attributes("-fullscreen", False)
        self.root.geometry("800x480")

    def open_login(self):
        ParticipantLoginPopup(self.root, self.manager, self.on_login_success)

    def change_entry(self):
        if not self.current_participant or self.current_participant == "NONE":
            messagebox.showwarning("Warning", "Please login with a Participant ID first.")
            self.open_login()
        else:
            EntryPickerPopup(self.root, self.manager, self.current_participant, self.on_login_success)

    def on_login_success(self, pid, entry_idx):
        self.current_participant = pid
        self.current_entry_index = entry_idx
        self.trial_counter = 0
        
        # Get the actual folder path from the manager's data
        entries = self.manager.get_participant_entries(pid)
        if entry_idx < len(entries):
            # This ensures we use the "Participant_Data/Participant_XX/entryN" path
            self.current_entry_path = entries[entry_idx]["entry_folder"]
        else:
            messagebox.showerror("Error", "Could not locate entry folder.")
            return

        self.id_label.config(text=f"ID: {self.current_participant}")
        self.entry_label.config(text=f"ENTRY: {int(self.current_entry_index) + 1}")
        self.start_btn.config(state=tk.NORMAL, text="START TRIAL 1")
        
        self.ax1.clear()
        self.ax2.clear()
        self.canvas.draw()

    def build_dashboard(self):
        self.sidebar = tk.Frame(self.root, bg=COLORS['bg_main'], width=200, padx=15, pady=15)
        self.sidebar.grid(row=0, column=0, sticky="nsw") 
        self.sidebar.grid_propagate(False) 

        tk.Label(self.sidebar, text="REFLEX", font=FONTS['title'], bg=COLORS['bg_main'], fg=COLORS['text_primary']).pack(pady=(0, 10))

        self.id_label = tk.Label(self.sidebar, text=f"ID: {self.current_participant}", font=FONTS['label_1'], bg=COLORS['bg_main'], fg="white")
        self.id_label.pack()
        self.entry_label = tk.Label(self.sidebar, text=f"ENTRY: {self.current_entry_index}", font=FONTS['label_1'], bg=COLORS['bg_main'], fg=COLORS['success'])
        self.entry_label.pack(pady=(0, 20))

        button_configs = [
            ("START TRIAL", COLORS['success'], self.start_trial, True),
            ("CHANGE PARTICIPANT", COLORS['blue_btn'], self.open_login, False),
            ("SELECT ENTRY", COLORS['blue_btn'], self.change_entry, False),
            ("PAIR SENSORS", COLORS['purple_btn'], lambda: delsys.pair_sensors(), False),
            ("SCAN SENSORS", COLORS['purple_btn'], lambda: delsys.scan_sensors(), False),
            ("EXIT APP", COLORS['danger'], self.exit_application, True)
        ]

        for text, color, cmd, is_primary in button_configs:
            btn = tk.Button(self.sidebar, text=text, font=FONTS['label_1'], bg=color, fg="white" if is_primary else COLORS['text_primary'], command=cmd, relief=tk.FLAT)
            btn.pack(fill=tk.X, pady=6, ipady=15 if is_primary else 6)
            if text == "START TRIAL": 
                self.start_btn = btn
                self.start_btn.config(state=tk.DISABLED)

        self.right_panel = tk.Frame(self.root, bg=COLORS['bg_raised'], bd=2, relief=tk.SUNKEN)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(6, 4), dpi=90)
        self.fig.patch.set_facecolor(COLORS['bg_raised'])
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.right_panel)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _run_trial_sequence(self):
        """Background thread to handle timing-sensitive motor and sensor commands"""
        try:
            print("--- Initiating Motor Sequence ---")
            # 1. Pre-positioning
            self.motor.acceleration_velocity_set(1000, 100)
            self.motor.move_counts(-8000, 1) # Move to 45 degrees
            time.sleep(1.5)             # Wait for motion to finish

            # 2. Trigger Sensors
            if not self.send_esp32_command(b'S'):
                print("x ESP32 Start Failed")
            
            # Use self.root.after to call GUI-related start_collect safely
            self.root.after(0, delsys.start_collect)
            self.is_collecting = True
            time.sleep(.3)

            # 3. Pre-load movement
            self.motor.acceleration_velocity_set(500, 30)
            self.motor.move_speed(30)
            time.sleep(.75)

            # 4. Reflex Induction (Quick Strike)
            print("--- Triggering Reflex ---")
            self.motor.acceleration_velocity_set(4000, 2000)
            self.motor.move_counts(-500, 1)
            time.sleep(2.0) # Allow motion to complete  # changed from 1.0 to 2.0

            # 5. Schedule the stop (4 seconds after starting collection)
            # We use root.after because stop_trial interacts with the UI
            self.root.after(0, self.stop_trial)

        except Exception as e:
            print(f"Motor Sequence Error: {e}")
            self.root.after(0, lambda: self.start_btn.config(state=tk.NORMAL, text="RETRY")) 
        
    def stop_trial(self):
        self.is_collecting = False
        self.send_esp32_command(b'T')
        emg_df = delsys.stop_collect()
        
        force_df_raw = self._fetch_esp32_force()
        self.force_data = force_df_raw['force_V'].tolist() if not force_df_raw.empty else []

        self.trial_counter += 1
        
        # USE THE PATH DEFINED DURING LOGIN
        path = self.current_entry_path 
        
        # Generate names
        trial_name = f"{self.current_participant}_{self.current_entry_index}_trial_{self.trial_counter}_{datetime.now().strftime('%H%M%S')}"

        force_df_for_analysis = pd.DataFrame({"force": self.force_data})
        
        # This will now save the PNG and return the DF
        processed_df = self.analysis(emg_df, force_df_for_analysis, path, trial_name)

        # 6. Save the actual CSV data
        if processed_df is not None:
            csv_path = os.path.join(path, f"{trial_name}_data.csv")
            processed_df.to_csv(csv_path, index=False)
            print(f"Successfully saved: {csv_path}")

        self.start_btn.config(state=tk.NORMAL, text=f"START TRIAL {self.trial_counter + 1}")

    def send_esp32_command(self, cmd: bytes) -> bool:
        """Sends command and waits for Acknowledge 'A'"""
        if not self.ser: return False
        try:
            self.ser.reset_input_buffer()
            self.ser.write(cmd)
            self.ser.flush()
            self.ser.timeout = 2.0  # Wait up to 2s for the 'A'
            ack = self.ser.read(1)
            self.ser.timeout = 0.01 # Reset to standard
            return ack == b'A'
        except Exception as e:
            print(f"x Command Error: {e}")
            return False

    def _fetch_esp32_force(self):
        """The specific working binary fetch logic"""
        if not self.ser:
            return pd.DataFrame(columns=['timestamp_us', 'force_V'])
        
        self.ser.reset_input_buffer()
        self.ser.write(b'D') # Request Data Dump

        # Wait for data start signal 'A'
        start_wait = time.time()
        while self.ser.in_waiting == 0:
            if (time.time() - start_wait) > 2.0: 
                print("x Timeout waiting for Data Dump")
                return pd.DataFrame()
            time.sleep(0.01)

        if self.ser.read(1) != b'A': 
            return pd.DataFrame()

        # Read 4-byte sample count
        while self.ser.in_waiting < 4: pass
        sample_count = struct.unpack('<I', self.ser.read(4))[0]
        
        bytes_needed = sample_count * 8
        data_bytes = b''
        while len(data_bytes) < bytes_needed:
            if self.ser.in_waiting > 0:
                data_bytes += self.ser.read(self.ser.in_waiting)
        
        forces, timestamps = [], []
        for i in range(0, len(data_bytes), 8):
            forces.append(struct.unpack('<f', data_bytes[i:i+4])[0])
            timestamps.append(struct.unpack('<I', data_bytes[i+4:i+8])[0])

        return pd.DataFrame({'timestamp_us': timestamps, 'force_V': forces})

    def start_trial(self):
        if self.ser is None:
            messagebox.showerror("Hardware Error", "ESP32 not found.")
            return

        # 1. Trigger ESP32 Internal Recording
        if not self.send_esp32_command(b'S'):
            print("x ESP32 Start Failed")
            messagebox.showwarning("Warning", "ESP32 failed to respond to START.")

        # self.is_collecting = True
        self.force_data = [] 

        # Disable the button immediately
        self.start_btn.config(state=tk.DISABLED, text="RECORDING...")
        # self.root.after(4000, self.stop_trial)

        # Run the motor and data collection sequence in a background thread
        threading.Thread(target=self._run_trial_sequence, daemon=True).start()

    def analysis(self, emg_df, force_df, base_path, base_name):
        try:
            emg_fs = 2148.148
            # 1. Extract raw numpy arrays
            emg_val = emg_df["value"].to_numpy(dtype=float)
            f_raw = force_df['force'].to_numpy(dtype=float)

            if len(emg_val) < 50 or len(f_raw) < 50:
                print(f"Not enough data: EMG({len(emg_val)}), Force({len(f_raw)})")
                return None

            # 2. Create matching Time Arrays
            emg_time = np.arange(len(emg_val)) * 1000 / emg_fs
            f_time = np.linspace(0, emg_time[-1], len(f_raw))

            # 3. Process Envelopes and RMS
            emg_abs = np.abs(emg_val)
            savgol_win = int(0.05 * emg_fs) | 1
            emg_env = signal.savgol_filter(emg_abs, window_length=savgol_win, polyorder=3)
            emg_rms = self.calculate_rms(emg_val, window_size=int(0.05 * emg_fs))

            f_norm = (f_raw / (0.009 * 51))
            f_norm = f_norm - np.mean(f_norm)
            
            nyq = emg_fs / 2
            b, a = signal.butter(4, 150 / nyq, btype='low')
            f_env = signal.filtfilt(b, a, np.abs(f_norm))
            f_rms = self.calculate_rms(f_norm, window_size=int(0.05 * emg_fs))

            # 4. Update the LIVE GUI
            self.update_plot_analysis(emg_time, emg_env, f_time, f_rms)

            # 5. Generate Summary (Using the explicit arrays)
            self.generate_summary_report(
                emg_time, emg_val, emg_env, emg_rms,
                f_time, f_norm, f_env, f_rms,
                base_path, base_name
            )

            # 6. Return DataFrame for CSV saving
            return pd.DataFrame({
                'EMG_time_ms': pd.Series(emg_time),
                'EMG_raw': pd.Series(emg_val),
                'EMG_rms': pd.Series(emg_rms),
                'FORCE_time_ms': pd.Series(f_time),
                'FORCE_raw': pd.Series(f_norm),
                'FORCE_rms': pd.Series(f_rms)
            })
        except Exception as e:
            print(f"Analysis Error: {e}")
            import traceback
            traceback.print_exc()
            return None

    def calculate_rms(self, data, window_size=50):
        if len(data) == 0: return np.array([])
        return np.sqrt(signal.convolve(data**2, np.ones(window_size)/window_size, mode='same'))

    def update_plot_analysis(self, emg_time, emg_env, force_time, force_rms):
        self.ax1.clear(); self.ax2.clear()
        self.ax1.plot(emg_time, emg_env, color='red', linewidth=1.5)
        self.ax1.set_title("EMG Envelope (mV)")
        self.ax1.grid(True, linestyle='--', alpha=0.6)
        self.ax1.set_ylabel("Amplitude (mV)")

        self.ax2.plot(force_time, force_rms, color='blue', linewidth=1.5)
        self.ax2.set_title("Force RMS Envelope (N)")
        self.ax2.grid(True, linestyle='--', alpha=0.6)
        self.ax2.set_ylabel("Amplitude (N)")
        self.ax2.set_xlabel("time (ms)")

        max_t = max(emg_time[-1], force_time[-1]) if len(emg_time)>0 else 4000

        self.ax1.set_xlim(0, max_t); self.ax2.set_xlim(0, max_t)

        self.fig.tight_layout(); self.canvas.draw()

    def generate_summary_report(self, t_emg, emg_raw, emg_env, emg_rms, t_f, f_raw, f_env, f_rms, base_path, base_name):
        """
        Expects 10 arguments (plus self): 
        Time, Raw, Env, RMS for EMG; 
        Time, Raw, Env, RMS for Force; 
        Path and Name.
        """
        fig, axs = plt.subplots(2, 3, figsize=(15, 10))

        # emg_raw = blue       force_raw = darkorange
        # emg_env = darkblue   force_env = red
        # emg_rms = purple     force_rms = darkred
        
        # Row 1: EMG
        axs[0,0].plot(t_emg, emg_raw, color='blue', lw=0.5); axs[0,0].set_title("Raw EMG")
        axs[0,1].plot(t_emg, emg_env, color='darkblue'); axs[0,1].set_title("EMG Envelope")
        
        # EMG/Force Overlay
        ax3_t = axs[0,2].twinx()
        axs[0,2].plot(t_emg, emg_env, color='darkblue', label='EMG')
        ax3_t.plot(t_f, f_env, color='red', alpha=0.6, label='Force')
        axs[0,2].set_title("Overlap: Envelopes")
        
        # Row 2: Force
        axs[1,0].plot(t_f, f_raw, color='darkorange', lw=0.8); axs[1,0].set_title("Raw Force")
        axs[1,1].plot(t_f, f_env, color='red'); axs[1,1].set_title("Force Envelope")
        
        # RMS Overlay
        ax6_t = axs[1,2].twinx()
        axs[1,2].plot(t_emg, emg_rms, color='purple')
        ax6_t.plot(t_f, f_rms, color='darkred', alpha=0.6)
        axs[1,2].set_title("Overlap: RMS")
        
        plt.tight_layout()
        plt.savefig(os.path.join(base_path, f"{base_name}_summary.png"), dpi=200)
        plt.close(fig)

    def exit_application(self):
        if messagebox.askokcancel("Exit", "Stop hardware and exit?"):
            self.is_collecting = False
            if self.ser: self.ser.close()
            self.root.destroy()
            os._exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = ReflexApp(root)
    root.mainloop()