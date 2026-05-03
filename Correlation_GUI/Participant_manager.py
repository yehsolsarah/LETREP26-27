# Participant_manager.py

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
        Creates a flat folder: Participant_Data/Participant_XX/entryN/
        """
        # 1. Create/Verify Participant Folder
        participant_folder = os.path.join(self.base_dir, f"Participant_{participant_id}")
        try:
            os.makedirs(participant_folder, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Error", f"Failed to create participant folder: {e}")
            return None, []

        # 2. Determine Entry Number
        existing_entries = self.get_participant_entries(participant_id)
        entry_count = len(existing_entries) + 1
        entry_name = f"entry{entry_count}"
        entry_folder = os.path.join(participant_folder, entry_name)

        # 3. Create Entry Folder (This is now the final data folder)
        try:
            os.makedirs(entry_folder, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Error", f"Failed to create entry folder: {e}")
            return None, []

        # 4. Update Tracking Data (Removed sessions list)
        entry_info = {
            "entry_number": entry_count,
            "created": datetime.now().isoformat(),
            "entry_folder": entry_folder,
            "status": "active"
        }

        # Add to participants data
        if participant_id not in self.participants_data:
            self.participants_data[participant_id] = {"entries": [], "active_threshold": 0.0}
        
        # Handle if data is currently a list or a dict (compatibility check)
        if isinstance(self.participants_data[participant_id], list):
             self.participants_data[participant_id] = {
                 "entries": self.participants_data[participant_id],
                 "active_threshold": 0.0
             }
        
        self.participants_data[participant_id]["entries"].append(entry_info)
        self.save_data()

        print(f"Created {entry_name} for participant {participant_id}")
        # We return an empty list for sessions since they no longer exist
        return entry_folder, []
    # ============================================================
    # FILE SAVING METHODS
    # ============================================================

    def save_csv_to_session(self, participant_id, entry_index, session_name, source_csv_path, fig, axs):
        """
        Saves CSV and Plot directly to the entry folder.
        'session_name' is ignored but kept in signature to avoid breaking main.py
        """
        try:
            entries = self.get_participant_entries(participant_id)
            if entry_index >= len(entries):
                return False, "Entry index out of range"

            entry_info = entries[entry_index]
            dest_folder = entry_info["entry_folder"] # Points to .../entryN/

            # Create timestamp for unique naming
            timestamp = datetime.now().strftime("%H%M%S")
            original_filename = os.path.basename(source_csv_path)
            
            # Destination Path for CSV
            dest_csv_path = os.path.join(dest_folder, f"trial_{timestamp}_{original_filename}")

            # 1. Save CSV
            shutil.copy2(source_csv_path, dest_csv_path)

            # 2. Save Plot (Same name as CSV but .png)
            plot_path = dest_csv_path.rsplit('.', 1)[0] + ".png"
            fig.savefig(plot_path)

            print(f"Saved Data and Plot to: {dest_folder}")
            return True, dest_csv_path

        except Exception as e:
            print(f"Save error: {e}")
            return False, str(e)
        
