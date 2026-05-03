#==================
# session_manager.py - Motor Control Only
#==================
import time
import Data_ann as da

def baseline_motors(entry_index, participant_id):
    """Run baseline with motors + collect data at the end."""
    print(f"Starting baseline for participant {participant_id}")
    
    # Motor control for 50 iterations
    for i in range(50):
        # motorlibrary.do_baseline_movement()
        time.sleep(0.5)
        print(f"Baseline iteration {i+1}/50")
    
    # AFTER motors finish, collect data while motors still active
    print("Collecting baseline data...")
    # api.start_collect()
    time.sleep(1.0)  # Collect for 1 second while motors still on
    # emg_data = api.get_emg_data()
    # force_data = api.get_force_data()
    # api.stop_collect()
    
    # For testing:
    emg_data = da.load_csv_as_stream("data.csv")
    force_data = None
    
    # Process the data
    baseline_stats = da.baseline_collection(entry_index, participant_id, emg_data, force_data)
    
    print(f"Baseline complete! Threshold: {baseline_stats['initial_threshold']:.4f} mV")
    return 50


def normal_motors(entry_index, participant_id, session_type="session1"):
    """Run normal session - collect data at end of EACH trial."""
    print(f"Starting {session_type} for participant {participant_id}")
    
    # Initialize session
    da.normal_collection(entry_index, participant_id, session_type)
    
    # 75 trials
    for i in range(75):
        # Motor control for this trial
        # motorlibrary.do_trial_movement()
        time.sleep(0.5)
        
        # AFTER movement, collect data while motors still active
        # api.start_collect()
        time.sleep(0.5)  # Collect for 0.5 seconds
        # emg_data = api.get_emg_data()
        # force_data = api.get_force_data()
        # api.stop_collect()
        
        # For testing:
        test_data = da.load_csv_as_stream("data.csv")
        segment = len(test_data) // 75
        emg_data = test_data[i*segment:(i+1)*segment]
        force_data = None
        
        # Process trial
        result = da.process_trial(emg_data, force_data)
        
        if result['success']:
            print(f"Trial {i+1}: SUCCESS ✓")
            # motorlibrary.success_feedback()
        else:
            print(f"Trial {i+1}: FAIL ✗")
            # motorlibrary.fail_feedback()
    
    # Save all data
    da.save_session_data()
    
    summary = da.get_session_summary()
    print(f"Session complete! Success rate: {summary['success_rate']:.1f}%")
    return 75