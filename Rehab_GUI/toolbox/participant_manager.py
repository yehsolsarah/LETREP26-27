# ============================================================
# PARTICIPANT DATA MANAGER MODULE
# File: participant_manager.py
# ============================================================
# This module handles all participant data management:
# - File/folder structure creation
# - JSON data persistence
# - Participant ID validation
# - CSV file saving to session folders

import os
import json
import re
import shutil
from datetime import datetime
from tkinter import messagebox

# ============================================================
# CONFIGURATION
# ============================================================
DATA_DIR = "Participant_Data"  # Base directory for all participant data
PARTICIPANTS_LOG = "participants_log.json"  # JSON file tracking all participants and entries


# ============================================================
# PARTICIPANT DATA MANAGER CLASS
# ============================================================
class ParticipantDataManager:
    """
    Manages all participant data, file operations, and folder structures.

    Responsibilities:
    - Create and manage participant folder structure
    - Validate participant IDs (00-99)
    - Track entries and sessions in JSON file
    - Save CSV files to appropriate session folders

    Folder Structure Created:
        Participant_Data/
        ├── participants_log.json
        ├── Participant_01/
        │   ├── entry1/
        │   │   ├── baseline/
        │   │   ├── session1/
        │   │   ├── session2/
        │   │   └── session3/
        │   └── entry2/
        │       ├── session1/
        │       ├── session2/
        │       └── session3/
        └── Participant_02/
            └── ...
    """

    def __init__(self, base_dir=DATA_DIR):
        """
        Initialize the data manager.

        Parameters:
            base_dir (str): Base directory for all participant data
        """
        self.base_dir = base_dir
        self.log_file = os.path.join(base_dir, PARTICIPANTS_LOG)
        self.participants_data = {}  # Dictionary: {participant_id: [entry1_info, entry2_info, ...]}

        self._ensure_base_directory()
        self.load_data()

    # ============================================================
    # INITIALIZATION METHODS
    # ============================================================

    def _ensure_base_directory(self):
        """Create base directory if it doesn't exist."""
        if not os.path.exists(self.base_dir):
            try:
                os.makedirs(self.base_dir)
                print(f"Created base directory: {self.base_dir}")
            except OSError as e:
                messagebox.showerror("Error", f"Failed to create base directory: {e}")

    def load_data(self):
        """
        Load participant data from JSON file.
        If file doesn't exist or is corrupted, starts with empty data.
        """
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    self.participants_data = json.load(f)
                print(f"Loaded data for {len(self.participants_data)} participants")
            else:
                self.participants_data = {}
                print("No existing data file found. Starting fresh.")
        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Data file is corrupted: {e}\nStarting with empty data.")
            self.participants_data = {}
        except IOError as e:
            messagebox.showerror("Error", f"Failed to load data: {e}")
            self.participants_data = {}

    def save_data(self):
        """
        Save participant data to JSON file.

        Returns:
            bool: True if save successful, False otherwise
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

            # Write data with nice formatting
            with open(self.log_file, 'w') as f:
                json.dump(self.participants_data, f, indent=4)

            print(f"Data saved to {self.log_file}")
            return True

        except IOError as e:
            messagebox.showerror("Error", f"Failed to save data: {e}")
            return False

    # ============================================================
    # VALIDATION METHODS
    # ============================================================

    def validate_participant_id(self, participant_id):
        """
        Validate that participant ID is exactly 2 digits (00-99).

        Parameters:
            participant_id (str): The ID to validate

        Returns:
            tuple: (bool, str) - (is_valid, error_message)
                   If valid: (True, "")
                   If invalid: (False, "error message")

        Validation Rules:
        - Must not be empty
        - Must be exactly 2 digits
        - Must be between 00 and 99
        """
        # Check if empty
        if not participant_id:
            return False, "Participant ID cannot be empty."

        # Check format: exactly 2 digits
        # Pattern ^[0-9]{2}$ means: start with 2 digits and end
        if not re.match(r'^[0-9]{2}$', participant_id):
            return False, "Participant ID must be exactly 2 digits (00-99)"

        # Check range (redundant but safe)
        participant_num = int(participant_id)
        if participant_num < 0 or participant_num > 99:
            return False, "Participant ID must be between 00 and 99"

        # Validation passed
        return True, ""

    # ============================================================
    # DATA RETRIEVAL METHODS
    # ============================================================

    def get_participant_entries(self, participant_id):
        """Get all entries for a specific participant"""
        data = self.participants_data.get(participant_id, [])

        if isinstance(data, dict):
            return data.get("entries",[])
        
        return data

    # ============================================================
    # ENTRY CREATION METHODS
    # ============================================================

    def create_new_entry(self, participant_id):
        """
        Create a new entry for a participant.
        Creates complete folder structure and initializes session folders.

        First entry includes: baseline + session1 + session2 + session3
        Subsequent entries include: session1 + session2 + session3 (no baseline)

        Parameters:
            participant_id (str): Validated participant ID (e.g., "01", "42")

        Returns:
            tuple: (entry_folder_path, sessions_list)
                   entry_folder_path (str): Full path to created entry folder
                   sessions_list (list): List of session names for this entry
                   Returns (None, []) if creation fails
        """
        # -------------------- Create Participant Folder --------------------
        participant_folder = os.path.join(self.base_dir, f"Participant_{participant_id}")

        try:
            os.makedirs(participant_folder, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Error", f"Failed to create participant folder: {e}")
            return None, []

        # -------------------- Determine Entry Number --------------------
        existing_entries = self.participants_data.get(participant_id, [])
        entry_count = len(existing_entries) + 1
        entry_name = f"entry{entry_count}"
        entry_folder = os.path.join(participant_folder, entry_name)

        # -------------------- Create Entry Folder --------------------
        try:
            os.makedirs(entry_folder, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Error", f"Failed to create entry folder: {e}")
            return None, []

        # -------------------- Determine Sessions --------------------
        # First entry gets baseline, subsequent entries don't
        sessions = ["session1", "session2", "session3"]
        if entry_count == 1:
            sessions = ["baseline"] + sessions

        # -------------------- Create Session Folders --------------------
        for session in sessions:
            session_folder = os.path.join(entry_folder, session)
            try:
                os.makedirs(session_folder, exist_ok=True)
            except OSError as e:
                messagebox.showerror("Error", f"Failed to create session folder '{session}': {e}")
                return None, []

        # -------------------- Update Tracking Data --------------------
        entry_info = {
            "entry_number": entry_count,
            "sessions": sessions,
            "created": datetime.now().isoformat(),  # ISO format: YYYY-MM-DDTHH:MM:SS
            "entry_folder": entry_folder
        }

        # Add to participants data
        # setdefault creates empty list if participant doesn't exist
        self.participants_data.setdefault(participant_id, []).append(entry_info)

        # Save updated data to file
        self.save_data()

        # Log creation
        print(f"  Created entry {entry_count} for participant {participant_id}")
        print(f"  Folder: {entry_folder}")
        print(f"  Sessions: {', '.join(sessions)}")

        return entry_folder, sessions

    # ============================================================
    # FILE SAVING METHODS
    # ============================================================

    def save_csv_to_session(self, participant_id, entry_index, session_name, source_csv_path, fig, axs):
        """
        Copy CSV file to the appropriate session folder with timestamp.
        Creates timestamped filename to prevent overwrites.

        Parameters:
            participant_id (str): Participant ID (e.g., "01")
            entry_index (int): Index of entry (0 = first entry, 1 = second, etc.)
            session_name (str): Session name (e.g., "baseline", "session1")
            source_csv_path (str): Full path to source CSV file to copy

        Returns:
            tuple: (bool, str) - (success, result_message)
                   If successful: (True, "path/to/saved/file.csv")
                   If failed: (False, "error message")

        Example:
            Source file: /home/user/data.csv
            Destination: Participant_Data/Participant_01/entry1/baseline/baseline_data_20241114_153045.csv
        """
        try:
            # -------------------- Validate Inputs --------------------
            if participant_id not in self.participants_data:
                return False, f"Participant {participant_id} not found in database"

            entries = self.participants_data[participant_id]
            if entry_index >= len(entries):
                return False, f"Entry index {entry_index} out of range (only {len(entries)} entries exist)"

            entry_info = entries[entry_index]
            entry_folder = entry_info["entry_folder"]

            # -------------------- Create Destination Path --------------------
            session_folder = os.path.join(entry_folder, session_name)

            # Create session folder if it doesn't exist (safety check)
            os.makedirs(session_folder, exist_ok=True)

            # Create timestamped filename to prevent overwrites
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # Format: YYYYMMDD_HHMMSS
            original_filename = os.path.basename(source_csv_path)
            name, ext = os.path.splitext(original_filename)
            dest_filename = f"{session_name}_data_{timestamp}{ext}"
            dest_path = os.path.join(session_folder, dest_filename)

            # -------------------- Copy File --------------------
            # shutil.copy2 preserves file metadata (creation date, etc.)
            shutil.copy2(source_csv_path, dest_path)

            print(f"Saved CSV to: {dest_path}")
            return True, dest_path

        except FileNotFoundError as e:
            return False, f"Source file not found: {e}"
        except IOError as e:
            return False, f"Failed to copy file: {e}"
        except Exception as e:
            return False, f"Unexpected error: {e}"
        
# ============================================================
# THRESHOLD STUFF
# ============================================================       
    def get_threshold(self, participant_id):
        """
        Retrieves curent active threshold for a given participant.
        Defaults to 0.0 if not set yet. 
        """
        data = self.participants_data.get(participant_id, [])
        if isinstance(data, dict):
            return data.get("active_threshold", 0.0)
        return 0.0
    
    def update_threshold(self, participant_id, new_threshold):
        """
        Updates the participant's threshold in JSON log.
        """
        if participant_id not in self.participants_data:
            self.participants_data[participant_id] = {"entries": [], "active_threshold": 0.0}

        current_data = self.participants_data[participant_id]
        
        if isinstance(current_data, list):
            self.participants_data[participant_id] = {
                "entries": current_data,
                "active_threshold": round(new_threshold, 4)
            }
        else:
            self.participants_data[participant_id]["active_threshold"] = round(new_threshold, 4)

        self.save_data()
        print(f"Threshold for {participant_id} updated to: {new_threshold}")

# ============================================================
# MODULE TEST (Optional)
# ============================================================
if __name__ == "__main__":
    """
    Test the data manager independently.
    Run: python participant_manager.py
    """
    print("Testing ParticipantDataManager...")

    manager = ParticipantDataManager()

    # Test validation
    test_ids = ["01", "99", "00", "1", "100", "abc", ""]
    for test_id in test_ids:
        valid, msg = manager.validate_participant_id(test_id)
        status = "v" if valid else "x"
        print(f"{status} ID '{test_id}': {msg if msg else 'Valid'}")

    # Test entry creation
    print("\nCreating test entry...")
    folder, sessions = manager.create_new_entry("01")
    if folder:
        print(f"Created: {folder}")
        print(f"  Sessions: {sessions}")

    print("\nTest complete!")