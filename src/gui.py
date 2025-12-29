import tkinter as tk
from tkinter import ttk
import asyncio

class TrafficControlPanel:
    def __init__(self, master, disruption_agent, tls_agents):
        self.master = master
        self.disruption_agent = disruption_agent
        self.tls_agents = {agent.tls_id: agent for agent in tls_agents}
        
        master.title("Manual Traffic Control Panel")
        master.geometry("600x600")

        self.create_widgets()
        self.controls_enabled = False
        self.disable_controls() # Start disabled until simulation runs

    def create_widgets(self):
        # --- Disruption Agent Section ---
        disruption_frame = ttk.LabelFrame(self.master, text="Disruption Agent (Block Lane)")
        disruption_frame.pack(pady=10,padx=10, fill="x")

        # Lane Selection
        ttk.Label(disruption_frame, text="Select Lane ID:").grid(row=0, column=0, padx=5, pady=5)
        
        # Get lanes from agent if possible, otherwise hardcode default list from file
        lane_options = getattr(self.disruption_agent, 'lane_list', [
            "E1_0", "E2_0" , "E3_0", "E4_0", "E5_0", "E6_0", 
            "E7_0", "E8_0", "E9_0", "E10_0", "E11_0", "E12_0",
            "E13_0", "E14_0", "E15_0", "E16_0"
        ])
        
        self.lane_var = tk.StringVar()
        self.lane_combo = ttk.Combobox(disruption_frame, textvariable=self.lane_var, values=lane_options)
        self.lane_combo.grid(row=0, column=1, padx=5, pady=5)
        if lane_options: self.lane_combo.current(0)

        # Duration
        ttk.Label(disruption_frame, text="Duration (s):").grid(row=1, column=0, padx=5, pady=5)
        self.duration_var = tk.StringVar(value="30")
        self.duration_entry = ttk.Entry(disruption_frame, textvariable=self.duration_var, width=10)
        self.duration_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # Activate Button
        self.btn_disruption = ttk.Button(disruption_frame, text="Activate Disruption", command=self.trigger_disruption)
        self.btn_disruption.grid(row=2, column=0, columnspan=2, pady=10)


        # --- Traffic Light Agent Section ---
        tls_frame = ttk.LabelFrame(self.master, text="Traffic Light Agent (Force Phase)")
        tls_frame.pack(pady=10, padx=10, fill="x")

        # TLS Selection
        ttk.Label(tls_frame, text="Select Junction:").grid(row=0, column=0, padx=5, pady=5)
        tls_ids = list(self.tls_agents.keys())
        self.tls_var = tk.StringVar()
        self.tls_combo = ttk.Combobox(tls_frame, textvariable=self.tls_var, values=tls_ids)
        self.tls_combo.grid(row=0, column=1, padx=5, pady=5)
        if tls_ids: self.tls_combo.current(0)

        # Phase Selection
        ttk.Label(tls_frame, text="Phase Index:").grid(row=1, column=0, padx=5, pady=5)
        # Assuming simple phases 0-3 for now, or we could fetch from agent dynamically if implemented
        self.phase_var = tk.StringVar()
        self.phase_combo = ttk.Combobox(tls_frame, textvariable=self.phase_var, values=[str(i) for i in range(10)])
        self.phase_combo.grid(row=1, column=1, padx=5, pady=5)
        self.phase_combo.current(0)

        # Set Phase Button
        self.btn_phase = ttk.Button(tls_frame, text="Set Phase", command=self.set_light_phase)
        self.btn_phase.grid(row=2, column=0, columnspan=2, pady=10)
        
        # Status Label
        self.status_label = ttk.Label(self.master, text="Status: Waiting for simulation...", foreground="blue")
        self.status_label.pack(side="bottom", pady=5)

    def enable_controls(self):
        self.controls_enabled = True
        self.btn_disruption.state(['!disabled'])
        self.btn_phase.state(['!disabled'])
        self.status_label.config(text="Status: Simulation Running. Controls Active.")

    def disable_controls(self):
        self.controls_enabled = False
        self.btn_disruption.state(['disabled'])
        self.btn_phase.state(['disabled'])

    def update(self):
        self.master.update()

    def trigger_disruption(self):
        if not self.controls_enabled: return
        lane_id = self.lane_var.get()
        try:
            duration = int(self.duration_var.get())
        except ValueError:
            print("Invalid duration")
            return
            
        print(f"[Panel] Requesting disruption on {lane_id} for {duration}s")
        # Call agent method
        if hasattr(self.disruption_agent, 'trigger_manual_disruption'):
             self.disruption_agent.trigger_manual_disruption(lane_id, duration)
        else:
            print("Error: DisruptionAgent does not have trigger_manual_disruption method.")

    def set_light_phase(self):
        if not self.controls_enabled: return
        tls_id = self.tls_var.get()
        try:
            phase_idx = int(self.phase_var.get())
        except ValueError:
             print("Invalid phase")
             return

        agent = self.tls_agents.get(tls_id)
        if agent:
             print(f"[Panel] Setting {tls_id} to phase {phase_idx}")
             if hasattr(agent, 'set_manual_phase'):
                 agent.set_manual_phase(phase_idx)
             else:
                 print("Error: TrafficLightAgent does not have set_manual_phase method.")
        else:
            print(f"Error: Agent for {tls_id} not found.")
