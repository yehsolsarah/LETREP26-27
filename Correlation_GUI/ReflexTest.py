# Correlation test program (based off PIGUI.py, basis for main.py)

import tkinter as tk
import numpy as np
import pandas as pd
import struct
import time
import serial
import serial.tools.list_ports
import threading
import matplotlib.pyplot as plt
from datetime import datetime
from toolbox import delsys_api_client as api
from numpy.fft import fft, fftfreq
from scipy.fft import fft, fftfreq
from scipy import signal, stats


class ReflexApp:
    def __init__(self, root):
        """Initializes floating main window and hardware communication"""
        self.root = root
        self.root.title('Reflex Test Control Panel')
        
        # 1. Window Configuration (Floating)
        # Set a fixed size and center it (approximately)
        window_width = 450
        window_height = 600
        self.root.geometry(f"{window_width}x{window_height}")
        self.root.resizable(False, False)
        self.root.configure(bg='#f0f0f0')

        self.lock = threading.Lock()
        self.ser = None
        self.raw_force = pd.DataFrame()

        # 2. UI Layout
        tk.Label(
            self.root, 
            text="Reflex Test Control", 
            font=('Helvetica', 18, 'bold'), 
            bg='#f0f0f0',
            pady=20
        ).pack()

        self.build_controls()

        # 3. Initialize Hardware after 100ms
        self.root.after(100, self.Load_Force)

    def Load_Force(self):
        """Establishes Serial Comm for force reading"""
        ESP32_VID = 0x10C4 
        ports = [p.device for p in serial.tools.list_ports.comports() if p.vid == ESP32_VID]
        SERIAL_PORT = ports[0] if ports else None
        
        if not SERIAL_PORT:
            print("x ESP32 not found! Check connection.")
            return

        try:
            self.ser = serial.Serial(SERIAL_PORT, 921600, timeout=0.01)
            time.sleep(2) 
            print(f"v Connected to ESP32 on {SERIAL_PORT}")
        except Exception as e:
            print(f"x Serial Error: {e}")

    def build_controls(self):
        """Creates buttons on the main window"""
        btn_frame = tk.Frame(self.root, relief=tk.RAISED, borderwidth=2)
        btn_frame.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)

        # Style configurations
        btn_opts = {'width': 25, 'padx': 10, 'pady': 8, 'font': ('Helvetica', 11)}

        # Setup Buttons
        tk.Label(btn_frame, text="1. Configuration", font=('Helvetica', 10, 'italic')).pack(pady=(10, 0))
        tk.Button(btn_frame, text="Pair EMG Sensors", command=lambda: api.pair_sensors(self.root), **btn_opts).pack(pady=5)
        tk.Button(btn_frame, text="Scan for Sensors", command=api.scan_sensors, **btn_opts).pack(pady=5)

        # Collection Buttons
        tk.Label(btn_frame, text="2. Execution", font=('Helvetica', 10, 'italic')).pack(pady=(20, 0))
        tk.Button(btn_frame, text="START COLLECTION", bg="#2ecc71", fg="white", 
                  font=('Helvetica', 12, 'bold'), command=self.start_collect, width=22).pack(pady=10, ipady=5)
        
        tk.Button(btn_frame, text="STOP COLLECTION", bg="#e74c3c", fg="white", 
                  font=('Helvetica', 12, 'bold'), command=self.stop_collect, width=22).pack(pady=10, ipady=5)

        # App Control
        tk.Button(self.root, text="Exit Application", command=self.root.destroy, bg="#bdc3c7").pack(pady=20)

    def start_collect(self):
        print("--- Starting Collection ---")
        with self.lock:
            api.start_collect() 
        
        if not self.send_command_with_ack(b'S'):
            print("x ESP32 start failed")

    def stop_collect(self):
        print("--- Stopping Collection ---")
        if not self.send_command_with_ack(b'T'):
            print("x ESP32 stop failed")

        with self.lock:
            raw_emg = api.stop_collect()

        self.raw_force = self._fetch_esp32_force()
        self.analysis(raw_emg, self.raw_force)

    def _fetch_esp32_force(self):
        if not self.ser:
            return pd.DataFrame(columns=['timestamp_us', 'force_V'])
        
        self.ser.reset_input_buffer()
        self.ser.write(b'D')

        start_wait = time.time()
        while self.ser.in_waiting == 0:
            if (time.time() - start_wait) > 2.0: return pd.DataFrame()
            time.sleep(0.01)

        if self.ser.read(1) != b'A': return pd.DataFrame()

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

    def send_command_with_ack(self, cmd: bytes) -> bool:
        if not self.ser: return False
        self.ser.reset_input_buffer()
        self.ser.write(cmd)
        self.ser.flush()
        self.ser.timeout = 2.0
        return self.ser.read(1) == b'A'

    def analysis(self, emg_df, force_df):
        print("Processing data...")
        try:
            # Processing EMG data
            emg_fs = 2148.148   # (Hz) Sampling frequency of emg sensors
            emg_val = emg_df["value"].to_numpy(dtype=float)
            rect_emg = np.abs(emg_val)
            emg_envelope = signal.savgol_filter(rect_emg, window_length=int(0.05*emg_fs)|1, polyorder=3) #lessened window length from .2 to .05
            emg_time = emg_df['time'].to_numpy(dtype=float) * 1000 
            emg_time = np.arange(len(emg_time)) * 1000 / emg_fs # (ms) There was an issue with time stamps. This fixes it
            envelope_time = np.arange(len(emg_envelope)) * 1000 / 2148.148

            # Processing Force Data
            f_val_raw = force_df['force_V'].to_numpy(dtype=float)
            force_val = (f_val_raw / (0.009 * 51))
            force_val = force_val - np.mean(force_val)
            force_val = np.abs(force_val)

            # Lowpass filter
            force_nyq = 2148/2
            force_lpc = 150 #Hz
            force_nco = force_lpc / force_nyq
            force_lp_b, force_lp_a = signal.butter(4, force_nco, btype='low', analog=False)
            lp_filtered_force = signal.filtfilt(force_lp_b, force_lp_a, force_val)
            
            force_time = force_df['timestamp_us'].to_numpy(dtype=float) / 1000
            sample_num = len(force_time)
            force_interval = 1/2148

            # Force FFT
            yf = fft(force_val)
            xf = fftfreq(sample_num, force_interval)

            # File Name based on time stamp
            fname = f"reflex_trial_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            # Compiling relevant data to a single data frame
            combined_df = pd.DataFrame({
                'EMG_time_ms': pd.Series(emg_time),
                'EMG_value': pd.Series(emg_val),
                'FORCE_time_ms': pd.Series(force_time),
                'FORCE_newtons': pd.Series(force_val),
                'Force_LPF': pd.Series(lp_filtered_force),
                'ENVELOPE_time_ms': pd.Series(envelope_time),
                'EMG_Envelope': pd.Series(emg_envelope)
            })
            
            # Saving data frame to csv
            combined_df.to_csv(fname, index=False)

            # Sending data to plotter
            self.plotter(combined_df, emg_envelope, xf, yf, lp_filtered_force)
            
            print(f"SUCCESS: Data saved to {fname}")
        except Exception as e:
            print(f"x Analysis Error: {e}")

    def plotter(self, combined_df, emg_envelope, xf, yf, filtered_force):
        # 1. Setup the figure (2 rows, 1 column)
        fig, axs  = plt.subplots(2, 3, figsize=(12, 10), sharex=False)

        # 2. Plot EMG Data (Top Subplot)
        axs[0, 0].plot(combined_df['EMG_time_ms'], combined_df['EMG_value'], 
                color='blue', linewidth=0.8, label='Raw EMG')
        axs[0, 0].set_title('Electromyography (EMG) Signal')
        axs[0, 0].set_xlim(combined_df['EMG_time_ms'].min(), combined_df['EMG_time_ms'].max())
        axs[0, 0].set_ylabel('Voltage (mV)')
        axs[0, 0].grid(True, alpha=0.3)
        axs[0, 0].legend(loc='upper right')

        # 3. Plot Force Data (Bottom Subplot)
        axs[1, 0].plot(combined_df['FORCE_time_ms'], combined_df['FORCE_newtons'], 
                color='red', linewidth=1.5, label='Force (N)')
        axs[1, 0].set_title('Force Sensor Output')
        axs[1, 0].set_xlim(combined_df['EMG_time_ms'].min(), combined_df['EMG_time_ms'].max())
        axs[1, 0].set_xlabel('Time (ms)')
        axs[1, 0].set_ylabel('Force (Newtons)')
        axs[1, 0].grid(True, alpha=0.3)
        axs[1, 0].legend(loc='upper right')

        # 4. Plot Force FFT
        axs[0, 1].plot(xf, np.abs(yf), 
                color='purple', linewidth=1.5, label='Frequency (Hz)')
        axs[0, 1].set_xlim(0, 500)
        axs[0, 1].set_xlabel('Frequency (Hz)')
        axs[0, 1].set_ylabel('Amplitude (N/s)')
        axs[0, 1].grid(True, alpha=0.3)
        axs[0, 1].legend(loc='upper right')

        # 5. Plot filtered force
        axs[1, 1].plot(combined_df['FORCE_time_ms'], filtered_force,
                color='teal', linewidth=1.5, label='Filtered Force (N)')
        axs[1, 1].set_xlim(combined_df['EMG_time_ms'].min(), combined_df['EMG_time_ms'].max())
        axs[1, 1].set_xlabel('Time (ms)')
        axs[1, 1].set_ylabel('Force (N)')
        axs[1, 1].grid(True, alpha=0.3)
        axs[1, 1].legend(loc='upper right')    

        # Plot EMG Envelope
        envelope_time = np.arange(len(emg_envelope)) * 1000 / 2148.148
        axs[0, 2].plot(envelope_time, emg_envelope, 
                color='purple', linewidth=0.8, label='EMG Envelope')   
        axs[0, 2].set_title('Electromyography (EMG) Envelope')
        axs[0, 2].set_xlim(combined_df['EMG_time_ms'].min(), combined_df['EMG_time_ms'].max())
        axs[0, 2].set_ylabel('Voltage (mV)')
        axs[0, 2].grid(True, alpha=0.3)
        axs[0, 2].legend(loc='upper right')

        # Plot EMG envelope and Filtered force overlay
        ax_emg_env = axs[1, 2]
        ax_force_env = ax_emg_env.twinx()
        ax_emg_env.plot(envelope_time, emg_envelope, color='darkblue', alpha=0.7)
        ax_force_env.plot(combined_df['FORCE_time_ms'], filtered_force, color='red', alpha=0.3)
    

        # 6. Clean up and Save
        fname = f"reflex_trial_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.tight_layout()
        plt.savefig(fname, dpi=300)
        plt.show()

if __name__ == "__main__":
    root = tk.Tk()
    app = ReflexApp(root) 
    root.mainloop()