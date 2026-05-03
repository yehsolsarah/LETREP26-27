# Main Rehab GUI 

import tkinter as tk
from tkinter import messagebox, filedialog
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import sys
import subprocess
import os
import ctypes
import serial
import serial.tools.list_ports
import time
# REMOVED: from win32inetcon import API_WRITE_DATA  # Windows-only library

#===========================
# Import function libraries
#===========================
from analysis_tests.EMG_SpecAnn import select_and_load_csv
from toolbox.participant_manager import ParticipantDataManager
from toolbox.login_popup import ParticipantLoginPopup
from toolbox import delsys_api_client as api
#from Python import letrepEMGAPI as api # not neccesary without the working API
from analysis.session_logic import SessionManager
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from analysis.plotter import LivePlotter # the live plotter class from the plotter.py
motor = ctypes.CDLL("/home/letrep/Downloads/Linux_Software/sFoundation/libMotor_working3.so")

#======================
# Import Theme
#======================
from toolbox.theme import COLORS, FONTS

#======================
# Main app class
#======================
class ParticipantApp:
    """
    Only handles UI components and event handlers.
    Data management and processing are in separate modules.
    """

    def __init__(self, root):
        """Initializes main window"""
        self.root = root
        self.root.title('LETREP26 GUI')
        
        # Modified fullscreen for Raspberry Pi 5 / wayland  # different window commands than normal linux or pi 3 for some reason
        # 1. Basic configuration
        self.root.configure(bg=COLORS['bg_main'])

        # 2. Force the window to initialize so Linux/Wayland recognizes it
        self.root.update_idletasks()

        # 3. Apply Fullscreen Logic for Pi 5 / Wayland
        try:
            # This is the standard request
            self.root.attributes('-fullscreen', True)
            
            # If standard fullscreen is ignored by Wayland,this forces the window to at least fill the usable space
            self.root.state('zoomed') 
            
            # OPTIONAL: Uncomment the line below for "Kiosk" mode (hides top bar)
            self.root.overrideredirect(True) 
        except tk.TclError as e:
            print(f"Window scaling error: {e}")

        # Bind Escape key to exit fullscreen
        self.root.bind("<Escape>", lambda e: self._exit_fullscreen())

        # -------State variables-------
        self.current_participant = None
        self.current_entry_index = 0
        self.current_session = None
        self.current_csv_path = None
        self.trial_in_progress = False

        #-------Initialize data manager-------
        self.data_manager = ParticipantDataManager()
        self.sm = SessionManager(self.data_manager, self.update_ui_callback)

        #--------Build UI components--------
        self._create_status_bar()
        self._create_button_frame()
        self._create_plot_frame()

        #--------Run on Startup--------
        self.root.after(100, motor.setup_and_home(30000))  #allow motor to find home position  # uncomment after ensuring functionality
        self.root.after(100, self.Load_API)  #Launches API on start up
        self.root.after(100, self.Load_Force)   # Initializes the Serial Comm
    
    def Load_Force(self):   # Establishes Serial Comm for force reading
        ESP32_VID = 0x10C4 # Specific Vendor ID of ESP32 port will not matter
        # Find the port matching that VID
        ports = [p.device for p in serial.tools.list_ports.comports() if p.vid == ESP32_VID]
        SERIAL_PORT = ports[0] if ports else None
        if not SERIAL_PORT:
            print("x ESP32 not found! Is it plugged in?")
            exit()
        # --- Initialization ---
        self.ser = serial.Serial(SERIAL_PORT, 921600, timeout=0.01)
        time.sleep(2)
        print(f"v Connected to ESP32 on {SERIAL_PORT}")
        self.sm.ser = self.ser

    def Load_API(self):  # Loads EMG API (change name of API file)
        # Now we're going to build a GUI
        window = tk.Tk()
        window.title("LETREP26 Pair EMGs...")
        window.geometry("400x450")
        window.resizable(False, False)
        window.configure(bg=COLORS['bg_main'])

        # Asthetics
        (tk.Label(
            window,
            text='EMG Sensor Pairing',
            relief=tk.SUNKEN,
            borderwidth=2,
            font=FONTS['title'],
            bg=COLORS['bg_frame'],
            fg=COLORS['text_primary']
        )
         .pack(padx=10, pady=30, ipadx=5, ipady=5))

        pair_btn_frame = tk.Frame(
            window,
            relief=tk.RAISED,
            borderwidth=2,
            bg=COLORS['bg_raised']
        )
        pair_btn_frame.pack(padx=15, pady=15)

        # Pair Sensors Button
        tk.Button(
            pair_btn_frame,
            text="Pair Sensors",
            font=FONTS['button'],
            bg=COLORS['purple_btn'],
            fg=COLORS['text_primary'],
            activebackground=COLORS['purple_active'],
            activeforeground=COLORS['text_secondary'],
            command=lambda: api.pair_sensors(window)
        ).grid(row=0, column=0, padx=20, pady=15, ipadx=15, ipady=15)

        # Scan Sensors Button
        tk.Button(
            pair_btn_frame,
            text="Scan for Sensors",
            font=FONTS['button'],
            bg=COLORS['blue_btn'],
            fg=COLORS['text_primary'],
            activebackground=COLORS['blue_active'],
            activeforeground=COLORS['text_secondary'],
            command=api.scan_sensors
        ).grid(row=1, column=0, padx=20, pady=15, ipadx=15, ipady=15)

        # Exit API Button (no EMG Pairing)
        tk.Button(
            pair_btn_frame,
            text="Exit Pairing Window",
            font=FONTS['button'],
            bg=COLORS['danger'],
            fg=COLORS['text_primary'],
            activebackground=COLORS['danger_active'],
            activeforeground=COLORS['text_secondary'],
            command=window.destroy
        ).grid(row=2, column=0, padx=20, pady=15, ipadx=15, ipady=15)

    def _exit_fullscreen(self):
        """Handle exiting fullscreen on Raspberry Pi"""
        try:
            self.root.attributes('-fullscreen', False)
        except tk.TclError:
            self.root.attributes('-zoomed', False)

    #=====================================
    # UI component creation
    #=====================================
    def _create_status_bar(self):
        """Creates status bar showing current participant/entry/session."""
        self.status_frame = tk.Frame(
            self.root,
            bg=COLORS['bg_frame'],
            relief=tk.SUNKEN,
            bd=2
        )
        self.status_frame.pack(fill=tk.X, padx=10, pady=5)

        self.status_label = tk.Label(
            self.status_frame,
            text="No Participant Selected",
            font=FONTS['label_1'],
            bg=COLORS['bg_frame'],
            fg=COLORS['text_primary'],
            anchor='w'
        )
        self.status_label.pack(fill=tk.X, padx=5, pady=2)

    def _create_button_frame(self):
        """Create frame for main buttons with proper active colors and depressed look."""
        button_frame = tk.Frame(
            self.root,
            bg=COLORS['bg_raised'],
            relief=tk.RAISED,
            bd=2
        )
        button_frame.pack(padx=10, pady=10)

        # Start Session button (green, depressed initially)
        self.load_btn = tk.Button(
            button_frame,
            text="Start Session",
            font=FONTS['button'],
            bg=COLORS['success'],
            fg=COLORS['text_primary'],
            activebackground=COLORS['success_active'],
            activeforeground=COLORS['text_primary'],
            command=self.Start_session,
            state=tk.DISABLED,
            width=15, height=2,
            relief=tk.SUNKEN
        )
        self.load_btn.grid(row=0, column=0, padx=10, pady=10)

        # Change entry entry button (blue, depressed initially) (was save_btn)
        self.save_btn = tk.Button(
            button_frame,
            text="Change Session",
            font=FONTS['button'],
            bg=COLORS['blue_btn'],
            fg=COLORS['text_primary'],
            activebackground=COLORS['blue_active'],
            activeforeground=COLORS['text_primary'],
            command=self.trigger_session_change,  # incriments the entry index
            state=tk.DISABLED,
            width=15, height=2,
            relief=tk.SUNKEN
        )
        self.save_btn.grid(row=0, column=1, padx=10, pady=10)
        
        # Change entry entry button (always active)
        self.api_btn = tk.Button(
            button_frame,
            text="Reconnect EMG",
            font=FONTS['button'],
            bg=COLORS['indigo_btn'],
            fg=COLORS['text_primary'],
            activebackground=COLORS['indigo_active'],
            activeforeground=COLORS['text_primary'],
            command=self.Load_API,  # incriments the entry index
            width=15, height=2,
        )
        self.api_btn.grid(row=0, column=2, padx=10, pady=10)

        # Change Participant button (always active, unless trial in session)
        self.change_participant_btn = tk.Button(
            button_frame,
            text="Change Participant",
            font=FONTS['button'],
            bg=COLORS['purple_btn'],
            fg=COLORS['text_primary'],
            activebackground=COLORS['purple_active'],
            activeforeground=COLORS['text_primary'],
            command=self.show_login_popup,
            width=18, height=2
        )
        self.change_participant_btn.grid(row=0, column=3, padx=10, pady=10)

        # Exit button (always active)
        self.exit_btn = tk.Button(
            button_frame,
            text='Exit',
            font=FONTS['button'],
            bg=COLORS['danger'],
            fg=COLORS['text_primary'],
            activebackground=COLORS['danger_active'],
            activeforeground=COLORS['text_primary'],
            command=self.close_window,
            width=15, height=2
        )
        self.exit_btn.grid(row=0, column=4, padx=10, pady=10)

    def _create_plot_frame(self):
        """Create frame for plot and a side-panel for live trial stats."""
        # Main container for both plot and stats
        self.main_content_frame = tk.Frame(self.root, bg=COLORS['bg_main'])
        self.main_content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 1. Plot Frame (Left Side)
        self.plot_frame = tk.Frame(
            self.main_content_frame,
            bg=COLORS['bg_frame'],
            relief=tk.SUNKEN,
            bd=2
        )
        self.plot_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 2. Stats Panel (Right Side - Matching the button frame look)
        self.stats_panel = tk.Frame(
            self.main_content_frame,
            bg=COLORS['bg_raised'], # Same as button frame
            relief=tk.RAISED,
            bd=2,
            width=200
        )
        self.stats_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        self.stats_panel.pack_propagate(False) # Keeps the width consistent

        # Add Labels to Stats Panel
        tk.Label(self.stats_panel, text="SESSION STATS", font=FONTS['label_1'], 
                 bg=COLORS['bg_raised'], fg=COLORS['text_primary']).pack(pady=10)

        # Success Label
        self.success_count_label = tk.Label(
            self.stats_panel, text="Success: 0", font=FONTS['title'],
            bg=COLORS['bg_frame'], fg=COLORS['success'], # Green text
            relief=tk.SUNKEN, bd=2, width=12
        )
        self.success_count_label.pack(pady=10, padx=10)

        # Fail Label
        self.fail_count_label = tk.Label(
            self.stats_panel, text="Failed: 0", font=FONTS['title'],
            bg=COLORS['bg_frame'], fg=COLORS['danger'], # Red text
            relief=tk.SUNKEN, bd=2, width=12
        )
        self.fail_count_label.pack(pady=10, padx=10)

        # Initialize Plotter in the left frame
        self.plot_manager = LivePlotter(self.plot_frame)
        self.canvas = FigureCanvasTkAgg(self.plot_manager.fig, master=self.plot_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill=tk.BOTH, expand=True)
        self.canvas.draw()

    #===============================
    # Event Handlers
    #===============================
    def show_login_popup(self):
        """Shows login popup using ParticipantLoginPopup class."""
        popup = ParticipantLoginPopup(
            self.root, self.data_manager,
            on_success=self.on_login_success
        )

    def trigger_session_change(self):
        """Re-opens the session selection from your existing popup file."""
        if self.current_participant:
            # 1. Start the popup handler
            popup = ParticipantLoginPopup(
                self.root, self.data_manager,
                on_success=self.on_login_success
            )
            
            # 2. THE TRICK: Reach into the popup we just made, 
            # set the ID and Entry to the current ones, 
            # and jump straight to the session screen.
            popup.selected_participant = self.current_participant
            popup.selected_entry_index = self.current_entry_index
            
            # Close the number pad that automatically opened
            popup.popup.destroy() 
            
            # Ask the data manager for the sessions and show that screen
            entries = self.data_manager.get_participant_entries(self.current_participant)
            sessions = entries[self.current_entry_index]["sessions"]
            popup._show_session_selection_popup(sessions)

    def Open_entry_only(self): # maybe won't need
        """
        Increments the entry index (0=Baseline, 1-3=Trials) 
        without restarting the whole login process.
        """
        if self.current_participant:
            # Increment index (0, 1, 2, 3)
            # This handles your 4 entries (Baseline + 3 normal)
            if self.current_entry_index < 3:
                self.current_entry_index += 1
                
                # Update the display
                self.update_status()
                
                # Feedback to user
                entry_label = "Baseline" if self.current_entry_index == 0 else f"Trial {self.current_entry_index}"
                #messagebox.showinfo("Entry Changed", f"Switched to {entry_label}")
            else:
                # If they hit the limit, offer to restart at Baseline or stay put
                if messagebox.askyesno("Session Limit", "All 4 entries completed. Restart at Baseline?"):
                    self.current_entry_index = 0
                    self.update_status()

    def on_login_success(self, participant_id, entry_index, session):
        """Called when user successfully logs in and selects a session."""
        self.current_participant = participant_id
        self.current_entry_index = entry_index
        self.current_session = session

        self.update_status()

        # Enable buttons and switch to normal colors/RAISED relief
        self.load_btn.config(   # start session button
            state=tk.NORMAL,
            bg=COLORS['success'],
            activebackground=COLORS['success_active'],
            relief=tk.RAISED
        )
        self.save_btn.config(  # change entry button
            state=tk.NORMAL,
            bg=COLORS['blue_btn'],
            activebackground=COLORS['blue_active'],
            relief=tk.RAISED
        )

        #messagebox.showinfo(
        #    "Ready",
        #    f"Participant: {participant_id}\n"
        #    f"Entry: {entry_index + 1}\nMode: {session}"
        #)

    def load_csv_file(self):  # not used
        """Open file dialog, load CSV, and display plot."""
        file_path = filedialog.askopenfilename(
            title="Select CSV file",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )

        if not file_path:
            return

        try:
            fig = select_and_load_csv(file_path)
            self.current_csv_path = file_path

            for widget in self.plot_frame.winfo_children():
                widget.destroy()

            canvas = FigureCanvasTkAgg(fig, self.plot_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

            toolbar = NavigationToolbar2Tk(canvas, self.plot_frame)
            toolbar.update()

            # Enable save button if CSV is loaded
            self.save_btn.config(
                state=tk.NORMAL,
                bg=COLORS['blue_btn'],
                activebackground=COLORS['blue_active'],
                relief=tk.RAISED
            )

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load CSV: {e}")

    def save_to_session(self):
        """Save current CSV to selected session folder."""
        if not self.current_csv_path:
            messagebox.showwarning("No Data", "Please load a CSV file first.")
            return

        success, result = self.data_manager.save_csv_to_session(
            self.current_participant,
            self.current_entry_index,
            self.current_session,
            self.current_csv_path
        )

        if success:
            messagebox.showinfo("Success", f"Data successfully saved to:\n{result}")
            self.save_btn.config(state=tk.DISABLED)
            self.current_csv_path = None
        else:
            messagebox.showerror("Error", f"Failed to save data to:\n{result}")

    motor.shutdown_node()   #shutoff motor after each session (tentative)

    def close_window(self):
        """Show exit confirmation popup."""
        popup = tk.Toplevel(self.root)
        popup.title("Confirm Exit")
        popup.geometry("450x250")
        popup.resizable(False, False)
        popup.grab_set()
        popup.configure(bg=COLORS['bg_main'])

        tk.Label(
            popup,
            text="Are you sure you want to quit?",
            relief=tk.SUNKEN,
            borderwidth=2,
            font=FONTS['title'],
            bg=COLORS['bg_frame'],
            fg=COLORS['text_primary']
        ).pack(padx=10, pady=30, ipadx=5, ipady=5)

        button_frame = tk.Frame(
            popup,
            relief=tk.RAISED,
            borderwidth=2,
            bg=COLORS['bg_raised']
        )
        button_frame.pack(padx=10, pady=10)

        # Back button
        tk.Button(
            button_frame,
            text="No",
            font=FONTS['button'],
            bg=COLORS['danger'],
            fg=COLORS['text_primary'],
            activebackground=COLORS['danger_active'],
            activeforeground=COLORS['text_primary'],
            command=popup.destroy,
            width=10,
            height=2
        ).grid(row=0, column=0, padx=10, pady=5)

        # Quit button
        tk.Button(
            button_frame,
            text="Yes",
            font=FONTS['button'],
            bg=COLORS['success'],
            fg=COLORS['text_primary'],
            activebackground=COLORS['success_active'],
            activeforeground=COLORS['text_primary'],
            command=lambda: [self.root.destroy(), sys.exit()],
            width=10,
            height=2
        ).grid(row=0, column=1, padx=10, pady=5)

    def update_status(self):
        """Update status bar with current participant/entry/session info."""
        if self.current_participant and self.current_session:
            entry_display = "Baseline" if self.current_entry_index == 0 else f"Trial {self.current_entry_index}"
            status_text = (
                f"Participant: {self.current_participant} | "
                f"Entry: {self.current_entry_index + 1} | " #there is a naming issue, ths variable refers to a session, not an entry
                f"Session: {self.current_session}"              #same as above, but inverted   self.current_entry_index + 1
            )
        elif self.current_participant:
            status_text = f"Participant: {self.current_participant} | No session selected"
        else:
            status_text = "No participant selected"

        self.status_label.config(text=status_text)

    def Start_session(self):
        #session determined by current_session variable
        if not self.current_session:
            messagebox.showwarning("No Session Type Selected","Please Select A Session Type")
            return
        
        self.total_trials_needed = self.sm.prepare_session(
            self.current_participant,
            self.current_entry_index,
            self.current_session
            )

        self.current_trial_count = 0
        self.session_success_count = 0 # keep for now
        self.session_fail_count = 0    # keep for now

        # Lock UI so buttons cant be pressed while motors and sesnors are running
        self.load_btn.config(state=tk.DISABLED, text="Running...")
        self.save_btn.config(state=tk.DISABLED)
        self.change_participant_btn.config(state=tk.DISABLED)
        # self.exit_btn.config(state=tk.DISABLED) #prevents exit while entry is running

        # start the loop
        self.run_trial_cycle()

    def run_trial_cycle(self): #look back at session_logic.py
        """runs one trial, updates the plot, then shedules the next trial to keep GUI alive"""
        # If a trial is still running in the background, just wait
        if getattr(self, 'trial_in_progress', False):
            self.root.after(100, self.run_trial_cycle)
            return

        if self.current_trial_count < self.total_trials_needed:
            self.trial_in_progress = True # Set the lock
            self.current_trial_count += 1
            
            # Start the threaded trial
            #self.sm.run_single_trial()
            if not api.ready_to_stream(): # Ensures that the API is ready to stream
                delay_start = time.time()
                while not api.ready_to_stream() and time.time() - delay_start < 2.0:
                    time.sleep(0.005)
                    # Check if it actually became ready
                    if not api.ready_to_stream():
                        print("x API failed to become ready within 2 seconds")
                        self.Load_API # should pop up the EMG connection popup
                        return 
                else:
                    print("v API is ready")
            else:
                self.sm.run_single_trial()
                
            # Re-check in a bit
            self.root.after(100, self.run_trial_cycle)
        else:
            self._finalize_entry()

    def _finalize_entry(self):
        """runs once all trials are done"""
        #calculate all thresholds

        # Unlock UI
        self.load_btn.config(state=tk.NORMAL, text="Start Session")
        self.save_btn.config(state=tk.NORMAL)
        self.change_participant_btn.config(state=tk.NORMAL)
        # self.exit_btn.config(state=tk.NORMAL)

        messagebox.showinfo("Complete", f"Entry complete! {self.total_trials_needed} trials saved.")

    def update_ui_callback(self, current_maxes, threshold, successes, failures):
        """
        This is called by session_logic after every trial to update the screen.
        """
        # Update the Plotter with the list of max values
        self.plot_manager.update(current_maxes, threshold)
        self.canvas.draw()

        # update specific labels on the right
        self.success_count_label.config(text=f"Successes: {successes}")
        self.fail_count_label.config(text=f"Fails: {failures}")

        # signal that hardware thread is finished
        self.trial_in_progress = False

#==========================================
# Main entry point
#==========================================
if __name__ == "__main__":
    root = tk.Tk()
    app = ParticipantApp(root)
    root.mainloop()