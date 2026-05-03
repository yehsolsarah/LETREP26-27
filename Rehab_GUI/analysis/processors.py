# handles all the math, rectify, max, and threshold
import os
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import signal, stats
from numpy.fft import fft, fftfreq
from scipy.fft import fft, fftfreq
# from scipy import stats

def _adaptive_amplifier(raw, filtered):
    # 1. Calculate the RMS of both signals
    rms_raw = np.sqrt(np.mean(raw**2))
    rms_filt = np.sqrt(np.mean(filtered**2))

    # 2. calculate the Gain factor
    if rms_filt > 0:
        gain_factor = rms_raw / rms_filt
    else:
        gain_factor = 1.0
    
    # 3. "Safety Cap" keeps from amplifying if signal is just silence or noise
    gain_factor = min(gain_factor, 2.0)

    # 4. Return amplified signal
    return filtered * gain_factor, gain_factor

def analize_trial(emg_df, force_df, active_threshold=0):  #emg_df = raw_emg, force_df = raw_force
    # Processes a single trial
    # emg_data: raw EMG dataframe
    # force_data: raw force data
    # active_threshold: 65% the baseline average for comparison

    # Extract list of EMG magnitude from EMG dataframe
    try:
        # Processing EMG data
        emg_fs = 2148.148   # (Hz) Sampling frequency of emg sensors
        emg_val = emg_df["value"].to_numpy(dtype=float)
        rect_emg = np.abs(emg_val)
        emg_envelope = signal.savgol_filter(rect_emg, window_length=int(0.05*emg_fs)|1, polyorder=3) #lessened window length from .2 to .05
        emg_time = emg_df['time'].to_numpy(dtype=float) * 1000 
        emg_time = np.arange(len(emg_time)) * 1000 / emg_fs # (ms) There was an issue with time stamps. This fixes it
        envelope_time = np.arange(len(emg_envelope)) * 1000 / 2148.148

        # Converting force from a list to an np array
        force_values = force_df['force_V'].to_numpy(dtype = float)
        force_values = force_values / (0.009 * 51)  # Converting volts to Newtons 0.009 V/N sensitivity and removing instrumentation amp gain of 51
        force_mean = np.mean(force_values)
        force_values = force_values - force_mean  # zeros the data... theoretically

        force_timestamps = force_df['timestamp_us'].to_numpy(dtype = float)
        force_timestamps = force_timestamps / 1000  # Convering timestamps from microseconds to milliseconds

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
        return(combined_df)
        fig, axs = d
        print(f"SUCCESS: Data saved to {fname}")
    except Exception as e:
        print(f"x Analysis Error: {e}")
    

def calculate_start_threshold(baseline_maxes):  # doesn't do anything rn
    # takes the list of 50 baseline maxes, finds averaege and returns 65% of that
    if not baseline_maxes:
        return 0
    
    mean_max = sum(baseline_maxes) / len(baseline_maxes)
    threshold_65 = mean_max * 0.65

    return threshold_65

def threshold_adjust(session_success_list, current_threshold):  # doesn't do anything rn
    # if 75% trial success rate, reduce current threshold by 35%
    if not session_success_list:
        return current_threshold
    
    total_trials = len(session_success_list)
    success_count = session_success_list.count(True)
    success_rate = success_count / total_trials

    if success_rate >= 0.75:
        new_threshold = current_threshold  * 0.65 # reduces by 35%
        return new_threshold
    
    return current_threshold

def _debug_plot(combined_df, emg_envelope, xf, yf, filtered_force):
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
        return fig, axs