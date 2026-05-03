import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from Themes import COLORS, FONTS

class ParticipantLoginPopup:
    def __init__(self, parent, data_manager, on_success, participant_id=None):
        self.parent = parent
        self.data_manager = data_manager
        self.on_success = on_success
        
        self.selected_participant = participant_id
        self.selected_entry_index = None

        self._show_login_ui(participant_id)

    def _show_login_ui(self, initial_id):
        self.popup = tk.Toplevel(self.parent)
        self.popup.title("Participant Login")
        self.popup.geometry("900x450") 
        self.popup.resizable(False, False)
        self.popup.grab_set()
        self.popup.configure(bg=COLORS['bg_main'])
        
        # Center on screen
        self.popup.update_idletasks()
        x = (self.popup.winfo_screenwidth() // 2) - (self.popup.winfo_width() // 2)
        y = (self.popup.winfo_screenheight() // 2) - (self.popup.winfo_height() // 2)
        self.popup.geometry(f"+{x}+{y}")

        # --- SECTION 1: NUMPAD ---
        numpad_container = tk.Frame(self.popup, bg=COLORS['bg_main'])
        numpad_container.pack(side=tk.LEFT, padx=(30, 10), pady=20)
        self.entry_var = tk.StringVar(value=initial_id if initial_id else "")
        self._create_number_pad(numpad_container)

        # --- SECTION 2: CONTROLS ---
        control_container = tk.Frame(self.popup, bg=COLORS['bg_main'])
        control_container.pack(side=tk.LEFT, padx=10)

        self.entry_type_var = tk.StringVar(value="new")
        
        # Entry Mode Selection (Border Removed)
        type_frame = tk.Frame(control_container, bg=COLORS['bg_main'], padx=10, pady=10)
        type_frame.pack(pady=10)

        tk.Radiobutton(type_frame, text="Create New Entry", variable=self.entry_type_var,
                       value="new", bg=COLORS['bg_main'], fg="white", font=FONTS['label_1'],
                       selectcolor=COLORS['bg_raised'], activebackground=COLORS['bg_main']).pack(anchor='w', pady=5)
        
        tk.Radiobutton(type_frame, text="Use Existing", variable=self.entry_type_var,
                       value="existing", bg=COLORS['bg_main'], fg="white", font=FONTS['label_1'],
                       selectcolor=COLORS['bg_raised'], activebackground=COLORS['bg_main']).pack(anchor='w', pady=5)

        tk.Button(
            control_container, text="CONTINUE", font=FONTS['button'],
            bg=COLORS['success'], fg=COLORS['text_primary'],
            width=14, height=3, relief=tk.RAISED, bd=4,
            command=self._on_continue_clicked
        ).pack(pady=20)

        # --- SECTION 3: DISPLAY ---
        feedback_group = tk.Frame(self.popup, bg=COLORS['bg_main'])
        feedback_group.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(10, 30))

        tk.Label(feedback_group, text="User ID", font=FONTS['title'],
                 bg=COLORS['bg_main'], fg=COLORS['text_primary']).pack(pady=(110, 5))

        display_frame = tk.Frame(feedback_group, relief=tk.RAISED, borderwidth=3, bg=COLORS['bg_raised'])
        display_frame.pack()

        tk.Label(
            display_frame, textvariable=self.entry_var, font=('calibri', 72, 'bold'),
            bg=COLORS['numpad_btn'], fg=COLORS['text_numpad'],
            width=6, anchor='center', relief=tk.SUNKEN, borderwidth=2
        ).pack(padx=10, pady=15)

    def _create_number_pad(self, parent):
        numpad_frame = tk.Frame(parent, bg=COLORS['bg_main'])
        numpad_frame.pack(pady=10)

        def add_digit(d):
            if len(self.entry_var.get()) < 2:
                self.entry_var.set(self.entry_var.get() + str(d))

        for i in range(9):
            num = i + 1
            tk.Button(
                numpad_frame, text=str(num), font=FONTS['numpad'],
                width=6, height=2, bg=COLORS['numpad_btn'], fg=COLORS['text_numpad'],
                command=lambda n=num: add_digit(n)
            ).grid(row=i // 3, column=i % 3, padx=4, pady=4)

        tk.Button(numpad_frame, text="CLR", font=FONTS['numpad'], width=6, height=2,
                  bg=COLORS['danger'], fg="white", command=lambda: self.entry_var.set("")
                  ).grid(row=3, column=0, padx=4, pady=4)

        tk.Button(numpad_frame, text="0", font=FONTS['numpad'], width=6, height=2,
                  bg=COLORS['numpad_btn'], fg=COLORS['text_numpad'], 
                  command=lambda: add_digit(0)).grid(row=3, column=1, padx=4, pady=4)

        tk.Button(numpad_frame, text="⌫", font=FONTS['numpad'], width=6, height=2,
                  bg=COLORS['danger'], fg="white", command=lambda: self.entry_var.set(self.entry_var.get()[:-1])
                  ).grid(row=3, column=2, padx=4, pady=4)

    def _on_continue_clicked(self):
        pid = self.entry_var.get().strip()
        valid, err = self.data_manager.validate_participant_id(pid)
        
        if not valid:
            messagebox.showwarning("Invalid Input", err)
            return

        if self.entry_type_var.get() == "new":
            self.data_manager.create_new_entry(pid)
            entries = self.data_manager.get_participant_entries(pid)
            self.popup.destroy()
            self.on_success(pid, len(entries) - 1)
        else:
            # Use the new picker logic here too!
            self.popup.destroy()
            EntryPickerPopup(self.parent, self.data_manager, pid, self.on_success)

    def _show_entry_picker(self, pid, entries):
        """Overlay list to pick the entry index"""
        picker = tk.Toplevel(self.popup)
        picker.title("Select Entry")
        picker.geometry("300x400")
        picker.grab_set()
        picker.configure(bg=COLORS['bg_main'])

        tk.Label(picker, text="Select Existing Entry:", font=FONTS['label_1'], 
                 bg=COLORS['bg_main'], fg="white").pack(pady=10)

        lb = tk.Listbox(picker, font=FONTS['label_1'], bg=COLORS['bg_raised'], fg="white")
        lb.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        for i in range(len(entries)):
            lb.insert(tk.END, f"Entry {i+1}")

        def confirm_pick():
            selection = lb.curselection()
            if selection:
                idx = selection[0]
                picker.destroy()
                self.popup.destroy()
                self.on_success(pid, idx)

        tk.Button(picker, text="SELECT", command=confirm_pick, bg=COLORS['success'], 
                  fg="white", font=FONTS['button']).pack(pady=10, fill=tk.X, padx=20)

class EntryPickerPopup:
    def __init__(self, parent, data_manager, participant_id, on_success):
        self.popup = tk.Toplevel(parent)
        self.popup.title("Select Entry")
        self.popup.geometry("350x450")
        self.popup.configure(bg=COLORS['bg_main'])
        self.popup.grab_set()
        
        # Center the popup
        self.popup.update_idletasks()
        x = (self.popup.winfo_screenwidth() // 2) - (self.popup.winfo_width() // 2)
        y = (self.popup.winfo_screenheight() // 2) - (self.popup.winfo_height() // 2)
        self.popup.geometry(f"+{x}+{y}")

        tk.Label(self.popup, text=f"SELECT ENTRY FOR {participant_id}", 
                 font=FONTS['label_1'], bg=COLORS['bg_main'], fg="white").pack(pady=20)

        # The Listbox
        self.lb = tk.Listbox(self.popup, font=FONTS['label_1'], 
                             bg=COLORS['bg_raised'], fg="white", 
                             selectbackground=COLORS['success'], height=10)
        self.lb.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)

        # Load existing entries
        entries = data_manager.get_participant_entries(participant_id)
        for i in range(len(entries)):
            self.lb.insert(tk.END, f"Entry {i+1}")

        def confirm():
            selection = self.lb.curselection()
            if selection:
                idx = selection[0]
                self.popup.destroy()
                on_success(participant_id, idx)

        tk.Button(self.popup, text="CONFIRM", font=FONTS['button'],
                  bg=COLORS['success'], fg="white", command=confirm).pack(pady=20, fill=tk.X, padx=30)