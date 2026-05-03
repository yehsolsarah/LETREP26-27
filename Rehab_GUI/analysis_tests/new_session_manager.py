#==============================================
# session_manager.py - Motor Control & Data Collection
#==============================================

import time
import numpy as np

# Import API and motor libraries
#from Python import letrepEMGAPI as api
#import ctypes
#motorlibrary = ctypes.CDLL("path_to_motor_library")

#==============================================
# GLOBAL STATE
#==============================================

class SessionState:
    """Track current session state."""
    def __init__(self):
        self.participant_id = None
        self.entry_index = None
        self.session_type = None
        self.all_trials = []  # Store all trial data for current session

_session_state = SessionState()

#==============================================
# MOTOR CONTROL & DATA COLLECTION FUNCTIONS
#==============================================

def baseline_motors(entry_index, participant_id):
    """
    Run baseline session: motor control + data collection.
    Returns all collected EMG and force data.
    """
    print(f"Starting baseline for participant {participant_id}, entry {entry_index}")
    
    # Initialize state
    _session_state.participant_id = participant_id
    _session_state.entry_index = entry_index
    _session_state.session_type = "baseline"
    
    emg_data_buffer = []
    force_data_buffer = []
    
    # Run 50 motor iterations
    for i in range(50):
        print(f"Baseline iteration {i+1}/50")
        
        # Motor control
        # motorlibrary.baseline_movement()
        time.sleep(0.5)
    
    # After all motor iterations, collect data while motors still active
    print("Collecting baseline data while motors active...")
    
    # Start data collection
    # api.start_collect()
    time.sleep(1.0)  # Collect for 1 second
    
    # Get collected data
    # emg_data_buffer = api.get_emg_data()
    # force_data_buffer = api.get_force_data()
    
    # api.stop_collect()
    
    print("Baseline motor control and data collection complete")
    
    return {
        'emg_data': emg_data_buffer,
        'force_data': force_data_buffer,
        'participant_id': participant_id,
        'entry_index': entry_index
    }


def normal_motors(entry_index, participant_id, session_type="session1"):
    """
    Run normal session: motor control + data collection for each trial.
    Returns list of all trials with their data.
    """
    print(f"Starting {session_type} for participant {participant_id}, entry {entry_index}")
    
    # Initialize state
    _session_state.participant_id = participant_id
    _session_state.entry_index = entry_index
    _session_state.session_type = session_type
    _session_state.all_trials = []
    
    # Run 75 trials
    for i in range(75):
        print(f"\nTrial {i+1}/75")
        
        # Motor control for this trial
        # motorlibrary.trial_movement()
        time.sleep(0.5)
        
        # Collect data at END of trial while motors still active
        # api.start_collect()
        time.sleep(0.5)  # Collect for 0.5 seconds
        
        # Get trial data
        # emg_trial = api.get_emg_data()
        # force_trial = api.get_force_data()
        
        # api.stop_collect()
        
        emg_trial = []  # Placeholder for now
        force_trial = []  # Placeholder for now
        
        # Store trial data
        trial_data = {
            'trial_number': i + 1,
            'emg_data': emg_trial,
            'force_data': force_trial
        }
        
        _session_state.all_trials.append(trial_data)
        
        print(f"Trial {i+1} motor control and data collection complete")
    
    print(f"\nSession {session_type} complete: {len(_session_state.all_trials)} trials collected")
    
    return {
        'trials': _session_state.all_trials,
        'participant_id': participant_id,
        'entry_index': entry_index,
        'session_type': session_type
    }


#==============================================
# HELPER FUNCTIONS
#==============================================

def get_current_trials():
    """Get all trials collected so far in current session."""
    return _session_state.all_trials


def get_session_info():
    """Get current session information."""
    return {
        'participant_id': _session_state.participant_id,
        'entry_index': _session_state.entry_index,
        'session_type': _session_state.session_type,
        'trial_count': len(_session_state.all_trials)
    }
