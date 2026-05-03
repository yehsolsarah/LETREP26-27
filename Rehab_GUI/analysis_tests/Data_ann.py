#==================
# analysis_manager.py - Data Analysis Only
#==================
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.signal import find_peaks
import os
from datetime import datetime
import json

#==============================================
# CONFIGURATION
#==============================================
SAMPLING_RATE = 2148.148
FILTER_LOW = 20
FILTER_HIGH = 75
BASELINE_THRESHOLD_PERCENT = 0.65
SUCCESS_THRESHOLD_REDUCTION = 0.35
SUCCESS_RATE_TARGET = 0.75

#==============================================
# GLOBAL STATE
#==============================================
class AnalysisState:
    def __init__(self):
        self.participant_id = None
        self.entry_index = None
        self.session_type = None
        self.baseline_stats = None
        self.current_threshold = None
        self.current_session_trials = []
        self.trial_count = 0
        self.data_dir = None

_analysis_state = AnalysisState()

#==============================================
# SIGNAL PROCESSING
#==============================================
def apply_bandpass_filter(signal, sampling_rate, low_cut, high_cut):
    """Apply FFT bandpass filter."""
    n = len(signal)
    dt = 1 / sampling_rate
    fhat = np.fft.fft(signal, n)
    freq = np.fft.fftfreq(n, d=dt)
    band_mask = (np.abs(freq) >= low_cut) & (np.abs(freq) <= high_cut)
    fhat_filtered = fhat * band_mask
    return np.fft.ifft(fhat_filtered).real

def rectify_and_find_peaks(signal):
    """Rectify and find peaks."""
    signal_rectified = np.abs(signal)
    peaks, _ = find_peaks(signal_rectified, prominence=0.001, distance=10)
    return signal_rectified, peaks

#==============================================
# MAIN FUNCTIONS
#==============================================
def baseline_collection(entry_index, participant_id, emg_data_stream, force_data_stream=None):
    """Process baseline and create threshold."""
    global _analysis_state
    
    _analysis_state.participant_id = participant_id
    _analysis_state.entry_index = entry_index
    _analysis_state.session_type = "baseline"
    
    # Create directory
    base_path = "participant_data"
    entry_dir = os.path.join(base_path, f"participant_{participant_id}", f"entry_{entry_index}")
    os.makedirs(entry_dir, exist_ok=True)
    _analysis_state.data_dir = entry_dir
    
    # Process EMG
    if isinstance(emg_data_stream, list):
        emg_data_stream = np.array(emg_data_stream)
    
    emg_filtered = apply_bandpass_filter(emg_data_stream, SAMPLING_RATE, FILTER_LOW, FILTER_HIGH)
    emg_rectified, peaks = rectify_and_find_peaks(emg_filtered)
    
    if len(peaks) == 0:
        raise ValueError("No peaks found in baseline")
    
    # Calculate baseline
    peak_magnitudes = emg_rectified[peaks]
    baseline_avg = np.mean(peak_magnitudes)
    threshold = baseline_avg * BASELINE_THRESHOLD_PERCENT
    
    _analysis_state.baseline_stats = {
        'baseline_average': baseline_avg,
        'initial_threshold': threshold,
        'current_threshold': threshold,
        'peak_count': len(peaks),
        'timestamp': datetime.now().isoformat()
    }
    _analysis_state.current_threshold = threshold
    
    # Save
    with open(os.path.join(entry_dir, "baseline.json"), 'w') as f:
        json.dump({
            'baseline_stats': _analysis_state.baseline_stats,
            'participant_id': participant_id,
            'entry_index': entry_index
        }, f, indent=4)
    
    print(f"Baseline: Avg={baseline_avg:.4f} mV, Threshold={threshold:.4f} mV")
    return _analysis_state.baseline_stats

def normal_collection(entry_index, participant_id, session_type="session1"):
    """Initialize normal session."""
    global _analysis_state
    
    _analysis_state.participant_id = participant_id
    _analysis_state.entry_index = entry_index
    _analysis_state.session_type = session_type
    _analysis_state.current_session_trials = []
    _analysis_state.trial_count = 0
    
    # Load baseline
    base_path = "participant_data"
    entry_dir = os.path.join(base_path, f"participant_{participant_id}", f"entry_{entry_index}")
    _analysis_state.data_dir = entry_dir
    
    baseline_file = os.path.join(entry_dir, "baseline.json")
    if not os.path.exists(baseline_file):
        raise FileNotFoundError(f"No baseline found. Run baseline first.")
    
    with open(baseline_file, 'r') as f:
        data = json.load(f)
        _analysis_state.baseline_stats = data['baseline_stats']
        _analysis_state.current_threshold = _analysis_state.baseline_stats['current_threshold']
    
    print(f"Session {session_type} initialized. Threshold={_analysis_state.current_threshold:.4f} mV")

def process_trial(emg_trial_data, force_trial_data=None):
    """Process single trial."""
    global _analysis_state
    _analysis_state.trial_count += 1
    
    if isinstance(emg_trial_data, list):
        emg_trial_data = np.array(emg_trial_data)
    
    emg_filtered = apply_bandpass_filter(emg_trial_data, SAMPLING_RATE, FILTER_LOW, FILTER_HIGH)
    emg_rectified, peaks = rectify_and_find_peaks(emg_filtered)
    
    magnitude = np.max(emg_rectified[peaks]) if len(peaks) > 0 else np.max(emg_rectified)
    is_success = magnitude < _analysis_state.current_threshold
    
    trial_result = {
        'trial_number': _analysis_state.trial_count,
        'magnitude': magnitude,
        'threshold': _analysis_state.current_threshold,
        'success': is_success,
        'timestamp': datetime.now().isoformat()
    }
    
    if force_trial_data is not None:
        if isinstance(force_trial_data, list):
            force_trial_data = np.array(force_trial_data)
        trial_result['force_max'] = np.max(force_trial_data)
        trial_result['force_avg'] = np.mean(force_trial_data)
    
    _analysis_state.current_session_trials.append(trial_result)
    update_threshold()
    
    return trial_result

def update_threshold():
    """Update threshold based on success rate."""
    global _analysis_state
    
    if len(_analysis_state.current_session_trials) == 0:
        return
    
    successes = sum(1 for t in _analysis_state.current_session_trials if t['success'])
    success_rate = successes / len(_analysis_state.current_session_trials)
    
    if success_rate >= SUCCESS_RATE_TARGET:
        old = _analysis_state.current_threshold
        _analysis_state.current_threshold = old * (1 - SUCCESS_THRESHOLD_REDUCTION)
        print(f"Threshold reduced: {old:.4f} → {_analysis_state.current_threshold:.4f} mV")

def save_session_data():
    """Save session to file."""
    global _analysis_state
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_file = os.path.join(_analysis_state.data_dir, f"{_analysis_state.session_type}_{timestamp}.json")
    
    successes = sum(1 for t in _analysis_state.current_session_trials if t['success'])
    success_rate = (successes / len(_analysis_state.current_session_trials)) if _analysis_state.current_session_trials else 0
    
    with open(session_file, 'w') as f:
        json.dump({
            'participant_id': _analysis_state.participant_id,
            'entry_index': _analysis_state.entry_index,
            'session_type': _analysis_state.session_type,
            'timestamp': timestamp,
            'baseline_stats': _analysis_state.baseline_stats,
            'trials': _analysis_state.current_session_trials,
            'summary': {
                'total_trials': len(_analysis_state.current_session_trials),
                'successful_trials': successes,
                'success_rate': success_rate * 100,
                'final_threshold': _analysis_state.current_threshold
            }
        }, f, indent=4)
    
    print(f"Session saved: {session_file}")
    return session_file

#==============================================
# GUI HELPER FUNCTIONS
#==============================================
def get_current_trials():
    return _analysis_state.current_session_trials

def get_current_threshold():
    return _analysis_state.current_threshold

def get_baseline_stats():
    return _analysis_state.baseline_stats

def get_session_summary():
    if not _analysis_state.current_session_trials:
        return None
    successes = sum(1 for t in _analysis_state.current_session_trials if t['success'])
    total = len(_analysis_state.current_session_trials)
    return {
        'total_trials': total,
        'successful_trials': successes,
        'success_rate': (successes / total * 100) if total > 0 else 0,
        'current_threshold': _analysis_state.current_threshold
    }

def load_csv_as_stream(csv_path):
    """Load CSV for testing."""
    df = pd.read_csv(csv_path, skiprows=2, header=None)
    return df.iloc[:, 0].values

def create_session_plot(trials=None):
    """Create plot."""
    global _analysis_state
    if trials is None:
        trials = _analysis_state.current_session_trials
    if not trials:
        return None
    
    fig, ax = plt.subplots(figsize=(10, 6))
    trial_numbers = [t['trial_number'] for t in trials]
    magnitudes = [t['magnitude'] for t in trials]
    thresholds = [t['threshold'] for t in trials]
    
    ax.plot(trial_numbers, thresholds, 'b-', linewidth=2, label='Threshold')
    
    for trial in trials:
        if trial['success']:
            ax.plot(trial['trial_number'], trial['magnitude'], 'go', markersize=12, 
                   markeredgecolor='darkgreen', markeredgewidth=2)
        else:
            ax.plot(trial['trial_number'], trial['magnitude'], 'rx', markersize=12, 
                   markeredgewidth=3)
    
    ax.set_xlabel('Trial Number')
    ax.set_ylabel('Magnitude (mV)')
    ax.set_title('EMG Trial Performance')
    ax.grid(True, alpha=0.3)
    ax.legend()
    plt.tight_layout()
    return fig