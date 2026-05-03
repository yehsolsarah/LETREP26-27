#==============================================
# data_analysis.py - Data Processing, Analysis, and Plotting
#==============================================

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
import os
from datetime import datetime
import json
import pandas as pd

#==============================================
# CONFIGURATION
#==============================================

SAMPLING_RATE = 2148.148  # Hz
FILTER_LOW = 20  # Hz
FILTER_HIGH = 75  # Hz
BASELINE_THRESHOLD_PERCENT = 0.65  # 65% of baseline average
SUCCESS_THRESHOLD_REDUCTION = 0.35  # 35% reduction after 75% success
SUCCESS_RATE_TARGET = 0.75  # 75% success rate triggers threshold reduction

#==============================================
# GLOBAL ANALYSIS STATE
#==============================================

class AnalysisState:
    """Track analysis results."""
    def __init__(self):
        self.participant_id = None
        self.entry_index = None
        self.session_type = None
        self.baseline_stats = None
        self.current_threshold = None
        self.analyzed_trials = []  # Trials with success/fail results
        self.data_dir = None

_analysis_state = AnalysisState()

#==============================================
# SIGNAL PROCESSING
#==============================================

def apply_bandpass_filter(signal, sampling_rate, low_cut, high_cut):
    """Apply FFT bandpass filter to remove noise."""
    n = len(signal)
    dt = 1 / sampling_rate
    
    fhat = np.fft.fft(signal, n)
    freq = np.fft.fftfreq(n, d=dt)
    
    band_mask = (np.abs(freq) >= low_cut) & (np.abs(freq) <= high_cut)
    fhat_filtered = fhat * band_mask
    
    return np.fft.ifft(fhat_filtered).real


def rectify_and_find_peaks(signal):
    """Rectify signal and find local maxima."""
    signal_rectified = np.abs(signal)
    peaks, _ = find_peaks(signal_rectified, prominence=0.001, distance=10)
    return signal_rectified, peaks


#==============================================
# ANALYSIS FUNCTIONS
#==============================================

def analyze_baseline(baseline_data):
    """
    Analyze baseline data and establish threshold.
    
    Args:
        baseline_data: Dictionary with 'emg_data', 'force_data', 'participant_id', 'entry_index'
    
    Returns:
        baseline_stats dictionary
    """
    global _analysis_state
    
    participant_id = baseline_data['participant_id']
    entry_index = baseline_data['entry_index']
    emg_data = baseline_data['emg_data']
    
    print(f"Analyzing baseline for participant {participant_id}, entry {entry_index}")
    
    # Initialize state
    _analysis_state.participant_id = participant_id
    _analysis_state.entry_index = entry_index
    _analysis_state.session_type = "baseline"
    
    # Create directory
    base_path = "participant_data"
    entry_dir = os.path.join(base_path, f"participant_{participant_id}", f"entry_{entry_index}")
    os.makedirs(entry_dir, exist_ok=True)
    _analysis_state.data_dir = entry_dir
    
    # Convert to numpy array if needed
    if isinstance(emg_data, list):
        emg_data = np.array(emg_data)
    
    if len(emg_data) == 0:
        raise ValueError("No EMG data provided for baseline")
    
    # Apply bandpass filter
    emg_filtered = apply_bandpass_filter(emg_data, SAMPLING_RATE, FILTER_LOW, FILTER_HIGH)
    
    # Rectify and find peaks
    emg_rectified, peaks = rectify_and_find_peaks(emg_filtered)
    
    if len(peaks) == 0:
        raise ValueError("No peaks found in baseline data")
    
    # Calculate baseline from rectified maximums (peaks)
    peak_magnitudes = emg_rectified[peaks]
    baseline_avg = np.mean(peak_magnitudes)
    threshold = baseline_avg * BASELINE_THRESHOLD_PERCENT  # 65% of baseline
    
    _analysis_state.baseline_stats = {
        'baseline_average': baseline_avg,
        'initial_threshold': threshold,
        'current_threshold': threshold,
        'peak_count': len(peaks),
        'timestamp': datetime.now().isoformat()
    }
    _analysis_state.current_threshold = threshold
    
    # Save baseline
    baseline_file = os.path.join(entry_dir, "baseline.json")
    with open(baseline_file, 'w') as f:
        json.dump({
            'baseline_stats': _analysis_state.baseline_stats,
            'participant_id': participant_id,
            'entry_index': entry_index
        }, f, indent=4)
    
    print(f"✓ Baseline analyzed: Avg={baseline_avg:.4f} mV, Threshold={threshold:.4f} mV")
    print(f"✓ Baseline saved to: {baseline_file}")
    
    return _analysis_state.baseline_stats


def analyze_session(session_data):
    """
    Analyze all trials in a session.
    
    Args:
        session_data: Dictionary with 'trials', 'participant_id', 'entry_index', 'session_type'
    
    Returns:
        List of analyzed trials with success/fail results
    """
    global _analysis_state
    
    participant_id = session_data['participant_id']
    entry_index = session_data['entry_index']
    session_type = session_data['session_type']
    trials = session_data['trials']
    
    print(f"Analyzing {session_type} for participant {participant_id}, entry {entry_index}")
    
    # Initialize state
    _analysis_state.participant_id = participant_id
    _analysis_state.entry_index = entry_index
    _analysis_state.session_type = session_type
    _analysis_state.analyzed_trials = []
    
    # Set data directory
    base_path = "participant_data"
    entry_dir = os.path.join(base_path, f"participant_{participant_id}", f"entry_{entry_index}")
    _analysis_state.data_dir = entry_dir
    
    # Load baseline
    baseline_file = os.path.join(entry_dir, "baseline.json")
    if not os.path.exists(baseline_file):
        raise FileNotFoundError("No baseline found. Run baseline first.")
    
    with open(baseline_file, 'r') as f:
        data = json.load(f)
        _analysis_state.baseline_stats = data['baseline_stats']
        _analysis_state.current_threshold = _analysis_state.baseline_stats['current_threshold']
    
    print(f"✓ Loaded baseline. Initial threshold: {_analysis_state.current_threshold:.4f} mV")
    
    # Analyze each trial
    for i, trial in enumerate(trials):
        analyzed_trial = analyze_single_trial(trial)
        _analysis_state.analyzed_trials.append(analyzed_trial)
        
        # Print progress every 10 trials
        if (i + 1) % 10 == 0 or (i + 1) == len(trials):
            print(f"  Analyzed {i + 1}/{len(trials)} trials...")
    
    # Save session
    save_session()
    
    print(f"✓ Session analysis complete: {len(_analysis_state.analyzed_trials)} trials analyzed")
    
    return _analysis_state.analyzed_trials


def analyze_single_trial(trial_data):
    """
    Analyze a single trial and determine success/fail.
    
    Args:
        trial_data: Dictionary with 'trial_number', 'emg_data', 'force_data'
    
    Returns:
        Analyzed trial with success/fail result
    """
    global _analysis_state
    
    trial_number = trial_data['trial_number']
    emg_data = trial_data['emg_data']
    force_data = trial_data.get('force_data')
    
    # Convert to numpy array if needed
    if isinstance(emg_data, list):
        emg_data = np.array(emg_data)
    
    if len(emg_data) == 0:
        # No data for this trial - mark as fail
        return {
            'trial_number': trial_number,
            'magnitude': 0,
            'threshold': _analysis_state.current_threshold,
            'success': False,
            'timestamp': datetime.now().isoformat()
        }
    
    # Apply bandpass filter
    emg_filtered = apply_bandpass_filter(emg_data, SAMPLING_RATE, FILTER_LOW, FILTER_HIGH)
    
    # Rectify and find peaks
    emg_rectified, peaks = rectify_and_find_peaks(emg_filtered)
    
    # Get maximum magnitude
    magnitude = np.max(emg_rectified[peaks]) if len(peaks) > 0 else np.max(emg_rectified)
    
    # Success if magnitude is BELOW threshold
    is_success = magnitude < _analysis_state.current_threshold
    
    result = {
        'trial_number': trial_number,
        'magnitude': magnitude,
        'threshold': _analysis_state.current_threshold,
        'success': is_success,
        'timestamp': datetime.now().isoformat()
    }
    
    # Add force data if available
    if force_data is not None:
        if isinstance(force_data, list):
            force_data = np.array(force_data)
        if len(force_data) > 0:
            result['force_max'] = np.max(force_data)
            result['force_avg'] = np.mean(force_data)
    
    # Update threshold if needed
    update_threshold()
    
    return result


def update_threshold():
    """Update threshold based on success rate."""
    global _analysis_state
    
    if len(_analysis_state.analyzed_trials) == 0:
        return
    
    successes = sum(1 for t in _analysis_state.analyzed_trials if t['success'])
    success_rate = successes / len(_analysis_state.analyzed_trials)
    
    # If 75% or higher success, reduce threshold by 35%
    if success_rate >= SUCCESS_RATE_TARGET:
        old = _analysis_state.current_threshold
        _analysis_state.current_threshold = old * (1 - SUCCESS_THRESHOLD_REDUCTION)
        print(f"  → Threshold reduced: {old:.4f} → {_analysis_state.current_threshold:.4f} mV (Success rate: {success_rate*100:.1f}%)")


def save_session():
    """Save analyzed session to file."""
    global _analysis_state
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_file = os.path.join(_analysis_state.data_dir, f"{_analysis_state.session_type}_{timestamp}.json")
    
    successes = sum(1 for t in _analysis_state.analyzed_trials if t['success'])
    success_rate = (successes / len(_analysis_state.analyzed_trials)) if _analysis_state.analyzed_trials else 0
    
    with open(session_file, 'w') as f:
        json.dump({
            'participant_id': _analysis_state.participant_id,
            'entry_index': _analysis_state.entry_index,
            'session_type': _analysis_state.session_type,
            'timestamp': timestamp,
            'baseline_stats': _analysis_state.baseline_stats,
            'trials': _analysis_state.analyzed_trials,
            'summary': {
                'total_trials': len(_analysis_state.analyzed_trials),
                'successful_trials': successes,
                'success_rate': success_rate * 100,
                'final_threshold': _analysis_state.current_threshold
            }
        }, f, indent=4)
    
    print(f"✓ Session saved to: {session_file}")


#==============================================
# GETTER FUNCTIONS (for GUI)
#==============================================

def get_analyzed_trials():
    """Get all analyzed trials."""
    return _analysis_state.analyzed_trials


def get_baseline_stats():
    """Get baseline statistics."""
    return _analysis_state.baseline_stats


def get_current_threshold():
    """Get current threshold."""
    return _analysis_state.current_threshold


def get_session_summary():
    """Get session summary."""
    if not _analysis_state.analyzed_trials:
        return None
    
    successes = sum(1 for t in _analysis_state.analyzed_trials if t['success'])
    total = len(_analysis_state.analyzed_trials)
    
    return {
        'total_trials': total,
        'successful_trials': successes,
        'success_rate': (successes / total * 100) if total > 0 else 0,
        'current_threshold': _analysis_state.current_threshold
    }


#==============================================
# PLOTTING FUNCTIONS
#==============================================

def plot_session(trials=None):
    """
    Create plot showing trial magnitudes vs threshold.
    Green O = success (magnitude < threshold)
    Red X = fail (magnitude >= threshold)
    """
    global _analysis_state
    
    if trials is None:
        trials = _analysis_state.analyzed_trials
    
    if not trials:
        print("No trials to plot")
        return None
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    trial_numbers = [t['trial_number'] for t in trials]
    magnitudes = [t['magnitude'] for t in trials]
    thresholds = [t['threshold'] for t in trials]
    
    # Plot threshold line
    ax.plot(trial_numbers, thresholds, 'b-', linewidth=2, label='Threshold')
    
    # Plot successes and failures
    for trial in trials:
        if trial['success']:
            ax.plot(trial['trial_number'], trial['magnitude'], 'go', markersize=12,
                   markeredgecolor='darkgreen', markeredgewidth=2)
        else:
            ax.plot(trial['trial_number'], trial['magnitude'], 'rx', markersize=12,
                   markeredgewidth=3)
    
    # Custom legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color='b', linewidth=2, label='Threshold'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='g', markersize=10,
               markeredgecolor='darkgreen', markeredgewidth=2, label='Success'),
        Line2D([0], [0], marker='x', color='r', markersize=10, markeredgewidth=3, label='Fail')
    ]
    ax.legend(handles=legend_elements, loc='best')
    
    ax.set_xlabel('Trial Number', fontsize=12)
    ax.set_ylabel('Magnitude (mV)', fontsize=12)
    ax.set_title('EMG Trial Performance', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    return fig


#==============================================
# MAIN TEST
#==============================================

if __name__ == "__main__":
    import new_session_manager as sm
    
    print("=" * 60)
    print("TESTING DATA_ANALYSIS.PY")
    print("=" * 60)
    print()
    
    print("--- BASELINE ANALYSIS ---")
    baseline_data = sm.baseline_motors_test(0, "00")
    baseline_stats = analyze_baseline(baseline_data)
    print(f"  Baseline average: {baseline_stats['baseline_average']:.4f} mV")
    print(f"  Initial threshold: {baseline_stats['initial_threshold']:.4f} mV")
    print()
    
    print("--- SESSION ANALYSIS ---")
    session_data = sm.normal_motors_test(0, "00", "session1")
    analyzed_trials = analyze_session(session_data)
    print()
    
    summary = get_session_summary()
    print("SESSION SUMMARY:")
    print(f"  Total trials: {summary['total_trials']}")
    print(f"  Successful trials: {summary['successful_trials']}")
    print(f"  Success rate: {summary['success_rate']:.1f}%")
    print(f"  Final threshold: {summary['current_threshold']:.4f} mV")
    print()
    
    print("--- GENERATING PLOT ---")
    fig = plot_session()
    print("✓ Plot created")
    print()
    
    print("All data_analysis tests passed! ✓")
    print()
    print("Displaying plot...")
    plt.show()

    #==============================================
# CSV TESTING FUNCTIONS
#==============================================

def load_csv_for_testing(csv_path="data.csv"):
    """Load CSV data for testing."""
    df = pd.read_csv(csv_path, skiprows=2, header=None)
    return df.iloc[:, 0].values


def create_test_baseline_data(participant_id, entry_index, csv_path="data.csv"):
    """
    Create baseline data structure from CSV for testing.
    Simulates what new_session_manager.baseline_motors() would return.
    """
    emg_data = load_csv_for_testing(csv_path)
    
    return {
        'emg_data': emg_data,
        'force_data': None,
        'participant_id': participant_id,
        'entry_index': entry_index
    }


def create_test_session_data(participant_id, entry_index, session_type="session1", csv_path="data.csv", num_trials=10):
    """
    Create session data structure from CSV for testing.
    Simulates what new_session_manager.normal_motors() would return.
    """
    full_emg = load_csv_for_testing(csv_path)
    
    # Divide EMG data into trials
    segment_length = len(full_emg) // num_trials
    trials = []
    
    for i in range(num_trials):
        start_idx = i * segment_length
        end_idx = start_idx + segment_length
        emg_trial = full_emg[start_idx:end_idx]
        
        trials.append({
            'trial_number': i + 1,
            'emg_data': emg_trial,
            'force_data': None
        })
    
    return {
        'trials': trials,
        'participant_id': participant_id,
        'entry_index': entry_index,
        'session_type': session_type
    }


#==============================================
# MAIN TEST
#==============================================

if __name__ == "__main__":
    print("=" * 60)
    print("TESTING DATA_ANALYSIS.PY WITH CSV DATA")
    print("=" * 60)
    print()
    
    print("--- BASELINE ANALYSIS ---")
    baseline_data = create_test_baseline_data("00", 0, "data.csv")
    baseline_stats = analyze_baseline(baseline_data)
    print(f"  Baseline average: {baseline_stats['baseline_average']:.4f} mV")
    print(f"  Initial threshold: {baseline_stats['initial_threshold']:.4f} mV")
    print()
    
    print("--- SESSION ANALYSIS ---")
    session_data = create_test_session_data("00", 0, "session1", "data.csv", num_trials=10)
    analyzed_trials = analyze_session(session_data)
    print()
    
    summary = get_session_summary()
    print("SESSION SUMMARY:")
    print(f"  Total trials: {summary['total_trials']}")
    print(f"  Successful trials: {summary['successful_trials']}")
    print(f"  Success rate: {summary['success_rate']:.1f}%")
    print(f"  Final threshold: {summary['current_threshold']:.4f} mV")
    print()
    
    print("--- GENERATING PLOT ---")
    fig = plot_session()
    print("✓ Plot created")
    print()
    
    print("All data_analysis tests passed! ✓")
    print()
    print("Displaying plot...")
    plt.show()