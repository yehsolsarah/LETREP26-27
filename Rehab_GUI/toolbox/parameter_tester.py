# Gilon Kraft
# LETREP26 - Software Subteam
# Date Started 02/05/2026

'''This program features a GUI that allows for the testing of the motors with changing the parameters'''

import tkinter as tk
from tkinter import ttk

def set_accel(accel):
    print(f"Acceleration Set to ", {accel})

def set_vel(vel):
    print(f"Velocity Set to ", {vel})
    
def set_angle(angle):
    print(f"Angular Displacement Set to ", {angle})
    
def run_motor():
    # ctypes.acceleration_velocity_set(int(accel.get()), int(vel.get()))
    # ctypes.moveDistance( parameters, int(angle.get()), targetIsAbsolute = False)


class Window:
    def __init__(self, master):
        self.master = master

        # Frame
        self.frame = tk.Frame(self.master, width = 300, height = 200)
        self.frame.pack()

        # Acceleration
        accel = tk.DoubleVar(self.master, value = 0)
        
        self.accel_label = tk.Label(self.frame, text = "Acceleration")
        self.accel_label.pack()
        
        self.accel_entry = tk.Entry(self.frame, textvariable = accel)
        self.accel_entry.pack()
        
        self.accel_button = tk.Button(
            self.master,
            text = "Set Acceleration",
            command = lambda: set_accel(accel.get())
        )
        self.accel_button.pack()

        # Velocity
        vel = tk.DoubleVar(self.master, value = 0)
        
        self.vel_label = tk.Label(self.frame, text = "Velocity")
        self.vel_label.pack()
        
        self.vel_entry = tk.Entry(self.frame, textvariable = vel)
        self.vel_entry.pack()
        
        self.vel_button = tk.Button(
            self.master,
            text = "Set Velocity",
            command = lambda: set_vel(vel.get())
        )
        self.vel_button.pack()
        
        # Angular Displacement
        angle = tk.DoubleVar(self.master, value = 0)
        
        self.angle_label = tk.Label(self.frame, text = "Angular Displacement")
        self.angle_label.pack()
        
        self.angle_entry = tk.Entry(self.frame, textvariable = angle)
        self.angle_entry.pack()
        
        self.angle_button = tk.Button(
            self.master,
            text = "Set Angle",
            command = lambda: set_angle(angle.get())
        )
        self.angle_button.pack()
        
        # Run Button
        self.run_button = tk.Button(
            self.master,
            text = "Run Motor",
            command = lambda: run_motor()
        )
        self.run_button.pack()

# Motor Initialization Function        
## ctypes.setup()

root = tk.Tk()
root.title("Motor Parameter Tetster")

window = Window(root)
root.mainloop()
