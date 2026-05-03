# ============================================================
# LOGIN POPUP MODULE (FULLY FIXED)
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from toolbox.theme import COLORS, FONTS


class ParticipantLoginPopup:
    """
    Manages:
      1. ID entry with number pad
      2. New vs existing entry selection
      3. Existing entry selection list
      4. Session selection
      5. Callback on success
    """

    def __init__(self, parent, data_manager, on_success, participant_id=None, force_new_entry=False):
        self.parent = parent
        self.data_manager = data_manager
        self.on_success = on_success

        self.selected_participant = participant_id
        self.selected_entry_index = None

        if participant_id and force_new_entry:
            # SHORTCUT: We already have a participant and want a new entry
            self._force_new_entry_flow(participant_id)
        elif participant_id:
            # Show entry selection for a known participant (Existing Entry flow)
            entries = self.data_manager.get_participant_entries(participant_id)
            self._show_entry_selection_popup(entries)
        else:
            # Standard flow: Start with the number pad
            self._show_number_pad_popup()

    def _force_new_entry_flow(self, pid):
        """Creates a new entry immediately and jumps to session selection."""
        entry_folder, sessions = self.data_manager.create_new_entry(pid)
        if entry_folder:
            entries = self.data_manager.get_participant_entries(pid)
            self.selected_entry_index = len(entries) - 1
            # Note: We don't need self.popup.destroy() here because 
            # the popup hasn't been built yet in this flow.
            self._show_session_selection_popup(sessions)

    # ============================================================
    # NUMBER PAD POPUP
    # ============================================================

    def _show_number_pad_popup(self):
        self.popup = tk.Toplevel(self.parent)
        self.popup.title("Participant Login")
        self.popup.geometry("900x450") 
        self.popup.resizable(False, False)
        self.popup.grab_set()
        self.popup.configure(bg=COLORS['bg_main'])
        self.popup.transient(self.parent)

        self.popup.update_idletasks()
        x = (self.popup.winfo_screenwidth() // 2) - (self.popup.winfo_width() // 2)
        y = (self.popup.winfo_screenheight() // 2) - (self.popup.winfo_height() // 2)
        self.popup.geometry(f"+{x}+{y}")

        # --- SECTION 1: NUMPAD (Fixed Left) ---
        numpad_container = tk.Frame(self.popup, bg=COLORS['bg_main'])
        numpad_container.pack(side=tk.LEFT, padx=(30, 10), pady=20)
        self._create_number_pad(numpad_container)

        # --- SECTION 2: CONTROLS (Middle) ---
        # Reduced padding to bring it closer to the ID section
        control_container = tk.Frame(self.popup, bg=COLORS['bg_main'])
        control_container.pack(side=tk.LEFT, padx=10)

        self.entry_type_var = tk.StringVar(value="new")
        self._create_entry_type_selection(control_container)

        tk.Button(
            control_container,
            text="CONTINUE",
            font=FONTS['button'],
            bg=COLORS['success'],
            activebackground=COLORS['success_active'],
            fg=COLORS['text_primary'],
            width=14, 
            height=3,
            relief=tk.RAISED,
            bd=4,
            command=self._on_continue_clicked
        ).pack(pady=20)

        # --- SECTION 3: FEEDBACK (Right - Expanded) ---
        feedback_group = tk.Frame(self.popup, bg=COLORS['bg_main'])
        feedback_group.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(10, 30))

        tk.Label(
            feedback_group, 
            text="PARTICIPANT ID", 
            font=FONTS['title'],
            bg=COLORS['bg_main'], 
            fg=COLORS['text_primary'],
            wraplength=250,  # Prevents text from cutting off by wrapping if needed
            justify=tk.CENTER
        ).pack(pady=(110, 5))

        self.entry_var = tk.StringVar()
        display_frame = tk.Frame(feedback_group, relief=tk.RAISED, borderwidth=3, bg=COLORS['bg_raised'])
        display_frame.pack()

        # Increased width from 4 to 6 to make the window feel less narrow
        entry_display = tk.Label(
            display_frame, 
            textvariable=self.entry_var, 
            font=('calibri', 72, 'bold'),
            bg=COLORS['numpad_btn'], 
            fg=COLORS['text_numpad'],
            width=6, 
            anchor='center', 
            relief=tk.SUNKEN, 
            borderwidth=2
        )
        entry_display.pack(padx=10, pady=15)

    def _create_number_pad(self, parent):
        # We pass the 'interaction_zone' frame as 'parent'
        numpad_frame = tk.Frame(parent, bg=COLORS['bg_main'])
        numpad_frame.pack(pady=10)

        def add_digit(d):
            if len(self.entry_var.get()) < 2:
                self.entry_var.set(self.entry_var.get() + str(d))

        def clear_entry(): self.entry_var.set("")
        def backspace(): self.entry_var.set(self.entry_var.get()[:-1])

        for i in range(9):
            num = i + 1
            tk.Button(
                numpad_frame, text=str(num), font=FONTS['numpad'],
                width=6, height=2, # Slightly wider buttons for thumb accuracy
                bg=COLORS['numpad_btn'], activebackground=COLORS['numpad_active'],
                fg=COLORS['text_numpad'], relief=tk.RAISED, bd=2,
                command=lambda n=num: add_digit(n)
            ).grid(row=i // 3, column=i % 3, padx=4, pady=4)

        tk.Button(numpad_frame, text="CLR", font=FONTS['numpad'], width=6, height=2,
                  bg=COLORS['danger'], fg=COLORS['text_primary'], command=clear_entry
                 ).grid(row=3, column=0, padx=4, pady=4)

        tk.Button(numpad_frame, text="0", font=FONTS['numpad'], width=6, height=2,
                  bg=COLORS['numpad_btn'], fg=COLORS['text_numpad'], 
                  command=lambda: add_digit(0)).grid(row=3, column=1, padx=4, pady=4)

        tk.Button(numpad_frame, text="⌫", font=FONTS['numpad'], width=6, height=2,
                  bg=COLORS['danger'], fg=COLORS['text_primary'], command=backspace
                 ).grid(row=3, column=2, padx=4, pady=4)

    def _create_entry_type_selection(self, parent):
        frame = tk.Frame(parent, bg=COLORS['bg_main'])
        frame.pack(pady=5)

        style = ttk.Style()
        style.configure('Login.TRadiobutton', font=FONTS['label_1'],
                        background=COLORS['bg_main'], foreground=COLORS['text_secondary'])

        # Added small pady to the buttons themselves for easier tapping
        ttk.Radiobutton(frame, text="New Entry", variable=self.entry_type_var,
                        value="new", style='Login.TRadiobutton').pack(anchor='w', pady=5)
        ttk.Radiobutton(frame, text="Existing Entry", variable=self.entry_type_var,
                        value="existing", style='Login.TRadiobutton').pack(anchor='w', pady=5)

    # ============================================================
    # CONTINUE LOGIC
    # ============================================================

    def _on_continue_clicked(self):
        pid = self.entry_var.get().strip()

        valid, err = self.data_manager.validate_participant_id(pid)
        if not valid:
            messagebox.showwarning("Invalid Input", err)
            return

        self.selected_participant = pid

        if self.entry_type_var.get() == "new":
            entry_folder, sessions = self.data_manager.create_new_entry(pid)
            if entry_folder:
                entries = self.data_manager.get_participant_entries(pid)
                self.selected_entry_index = len(entries) - 1
                self.popup.destroy()
                self._show_session_selection_popup(sessions)
            return

        # Existing entry
        entries = self.data_manager.get_participant_entries(pid)
        if not entries:
            messagebox.showwarning("No Entries",
                f"No entries found for {pid}. Creating new entry…")
            entry_folder, sessions = self.data_manager.create_new_entry(pid)
            self.selected_entry_index = 0
            self.popup.destroy()
            self._show_session_selection_popup(sessions)
            return

        self.popup.destroy()
        self._show_entry_selection_popup(entries)

    # ============================================================
    # ENTRY SELECTION POPUP
    # ============================================================

    def _show_entry_selection_popup(self, entries):
        self.popup = tk.Toplevel(self.parent)
        self.popup.title("Select Entry")
        self.popup.geometry("400x500")
        self.popup.resizable(False, False)
        self.popup.grab_set()
        self.popup.configure(bg=COLORS['bg_main'])

        tk.Label(
            self.popup,
            text="Select Entry:",
            font=FONTS['title'],
            bg=COLORS['bg_main'],
            fg=COLORS['text_primary']
        ).pack(padx=10, pady=20)

        frame = tk.Frame(self.popup)
        frame.pack(padx=20, pady=10, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(
            frame,
            font=FONTS['label_1'],
            bg=COLORS['bg_frame'],
            fg=COLORS['text_primary'],
            yscrollcommand=scrollbar.set
        )
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        for i, entry_info in enumerate(entries):
            created = entry_info.get("created", "Unknown")
            try:
                created = datetime.fromisoformat(created).strftime("%Y-%m-%d %H:%M")
            except:
                pass
            listbox.insert(tk.END, f"Entry {i + 1} – {created}")

        listbox.select_set(0)

        def select():
            sel = listbox.curselection()
            if sel:
                self.selected_entry_index = sel[0]
                sessions = entries[self.selected_entry_index]["sessions"]
                self.popup.destroy()
                self._show_session_selection_popup(sessions)

        tk.Button(
            self.popup,
            text="SELECT",
            font=FONTS['button'],
            bg=COLORS['success'],
            activebackground=COLORS['success_active'],
            fg=COLORS['text_primary'],
            width=15,
            height=2,
            relief=tk.RAISED,
            bd=3,
            command=select
        ).pack(pady=10)

    # ============================================================
    # SESSION SELECTION POPUP
    # ============================================================

    def _show_session_selection_popup(self, sessions):
        self.popup = tk.Toplevel(self.parent)
        self.popup.title("Select Session")
        self.popup.geometry("400x450")
        self.popup.resizable(False, False)
        self.popup.grab_set()
        self.popup.configure(bg=COLORS['bg_main'])

        tk.Label(
            self.popup,
            text="Select Session:",
            font=FONTS['title'],
            bg=COLORS['bg_main'],
            fg=COLORS['text_primary']
        ).pack(padx=10, pady=20)

        session_var = tk.StringVar(value=sessions[0])

        style = ttk.Style()
        style.configure(
            'Session.TRadiobutton',
            font=FONTS['label_1'],
            background=COLORS['bg_main'],
            foreground=COLORS['text_secondary']
        )

        for session in sessions:
            ttk.Radiobutton(
                self.popup,
                text=session.capitalize(),
                variable=session_var,
                value=session,
                style='Session.TRadiobutton'
            ).pack(pady=5)

        def start():
            self.popup.destroy()
            self.on_success(
                self.selected_participant,
                self.selected_entry_index,
                session_var.get()
            )

        tk.Button(
            self.popup,
            text="OPEN SESSION",
            font=FONTS['button'],
            bg=COLORS['success'],
            activebackground=COLORS['success_active'],
            fg=COLORS['text_primary'],
            width=18,
            height=2,
            relief=tk.RAISED,
            bd=3,
            command=start
        ).pack(pady=20)


# ============================================================
# OPTIONAL TEST HARNESS
# ============================================================

if __name__ == "__main__":
    from toolbox.participant_manager import ParticipantDataManager

    def callback(pid, entry_i, session):
        print("SUCCESS:", pid, entry_i, session)
        root.quit()

    root = tk.Tk()
    root.withdraw()

    manager = ParticipantDataManager()
    ParticipantLoginPopup(root, manager, callback)

    root.mainloop()