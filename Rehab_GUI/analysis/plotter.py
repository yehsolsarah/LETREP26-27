# matplotlib functions for plotting data in the main GUI
import matplotlib
matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from toolbox.theme import COLORS

class LivePlotter:
    def __init__(self, canvas_frame):
        """
        Initialize figure once, and prepare it for live updates
        """
        # Create Figure and axis
        self.fig, self.ax = plt.subplots(figsize=(5, 3), dpi=100)
        self.canvas_frame = canvas_frame

        # Apply theme form toolbox.theme
        self.fig.patch.set_facecolor(COLORS.get('bg_frame', '#121212'))
        self.ax.set_facecolor(COLORS.get('bg_main', '#1e1e1e'))

        # Initialize empty plot elements
        self.line, = self.ax.plot([], [], color=COLORS.get('text_secondary','#888888'),
                                  linestyle='-', alpha=0.5, zorder=1)
        
        self.scatter = self.ax.scatter([], [], s=30, zorder=2)
        
        # initialize threshold line ( stays invisible until threshold exists)
        self.threshold_line = self.ax.axhline(0, color=COLORS.get('danger', '#f44336'),
                                              linestyle='--', linewidth=1.5, alpha=0)
        
        self.fill = None # placeholder for the green success zone

        # Final styling
        self.ax.set_title("EMG Maximum Voltages", color=COLORS.get('text_primary', '#ffffff'), fontsize=10)
        self.ax.set_xlabel("Trial Number", color=COLORS.get('text_secondary', '#aaaaaa'), fontsize=8)
        self.ax.set_ylabel("Max EMG (mV)", color=COLORS.get('text_secondary', '#aaaaaa'), fontsize=8)

        self.ax.tick_params(colors=COLORS.get('text_secondary', '#aaaaaa'), labelsize=8)
        for spine in self.ax.spines.values():
            spine.set_color(COLORS.get('text_secondary', '#aaaaaa'))

        plt.tight_layout()

    def update(self, all_maxes, threshold=None):
        """
        Updates the existing plot without rebuilding figure
        """
        if not all_maxes:
            return
        
        trials = np.arange(1, len(all_maxes) + 1)

        # update the line and scatter positions
        self.line.set_data(trials, all_maxes) #fix in a bit
        self.scatter.set_offsets(np.column_stack((trials, all_maxes)))

        # update logic and colors if threshold exists
        if threshold is not None and threshold > 0:
            # show and move threshold line
            self.threshold_line.set_ydata([threshold, threshold])
            self.threshold_line.set_alpha(1)

            # color points 
            point_colors = [COLORS.get('success', '#4caf50') if val < threshold
                      else COLORS.get('danger', '#f44336') for val in all_maxes]
            self.scatter.set_facecolor(point_colors) #fix later too

            # update success Zone
            if self.fill:
                self.fill.remove()
            self.fill = self.ax.fill_between(trials, 0, threshold,
                                             color=COLORS.get('success', '#4caf50'), alpha=0.1)
            
        # rescale view to fitnew data
        self.ax.relim()
        self.ax.autoscale_view()

        # redraw only the canvas
        self.fig.canvas.draw_idle()

def session_summary(all_emg_max, all_force_max, final_threshold):
    #creates a popup at the end of the session comparing force and EMG for all trials preformed
    # Create plot
    plt.figure(figsize=(8,6))

    # Convert to numpy arrays
    emg = np.array(all_emg_max)
    force = np.array(all_force_max)
    trials = np.arange(1, len(emg)+1)

    # Separate success and fail for coloring
    success_mask = emg < final_threshold

    # 1. Plot the "Success" trials (Green)
    plt.scatter(force[success_mask], emg[success_mask], 
            color='#4caf50', s=60, label='Successful Trials', edgecolors='black', alpha=0.8)

    # 2. Plot the "Failed" trials (Red)
    plt.scatter(force[~success_mask], emg[~success_mask], 
            color='#f44336', s=60, label='Above Threshold', edgecolors='black', alpha=0.8)

    # 3. Add the Threshold Line
    plt.axhline(y=final_threshold, color='#f44336', linestyle='--', linewidth=2, label='Final Threshold')

    # 4. Success Zone Shading
    plt.fill_between([min(force)*0.9, max(force)*1.1], 0, final_threshold, 
                    color='#4caf50', alpha=0.1)
    
    # Labeling
    plt.title(f"Session Summary ({len(emg)} Trials)", fontsize=14)
    plt.xlabel("Maximum Force Peak (V)", fontsize=12)
    plt.ylabel("Maximum EMG (mV)", fontsize=12)
    plt.legend()
    plt.grid(True, linestyle=":", alpha=0.6)

    # add trial numbers next to the points
    for i, txt in enumerate(trials):
        plt.annotate (txt, (force[i], emg[i]),textcoords="offset points", xytext=(0,5), ha='center', fontsize=8)
    
    # Save with a timestamp to avoid overwriting
    plt.savefig(f"debug_plots/session_{int(time.time())}.png")
    plt.close(fig) # Critical: close the figure to free up memory