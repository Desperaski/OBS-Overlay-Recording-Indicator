import obspython as obs
import tkinter as tk
import ctypes
import threading
import queue
import os

STATUS = {"record": False, "buffer": False, "paused": False}
SETTINGS = {
    "corner": "top-left",
    "margin": 5,
    "f_size": 25,
    "opacity": 0.6
}

WINDOW_SIZE = 150
UPDATE_MS = 100
REPLAY_BUFFER_PAUSE = 5

SYMBOLS = {"record": "●", "pause": "■", "buffer": "⟳"}
COLORS = {"record": "#FF0000", "pause": "#FFA500", "buffer": "#00FFFF"}

cmd_queue = queue.Queue()
overlay_instance = None

def set_clickthrough(hwnd):
    if os.name != 'nt': return
    try:
        styles = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        styles |= 0x80000 | 0x20 | 0x80
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, styles)
        ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, 255, 1)
    except:
        pass

class Overlay:
    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.config(bg="black")
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "black")
        
        self.label = tk.Label(
            self.root, text="", font=("Arial", SETTINGS["f_size"], "bold"),
            fg="white", bg="black"
        )
        self.label.pack(expand=True)
        
        set_clickthrough(self.root.winfo_id())
        self._apply_settings()
        self._loop()

    def _apply_settings(self):
        self.root.attributes("-alpha", SETTINGS["opacity"])
        self.label.config(font=("Arial", SETTINGS["f_size"], "bold"))
        
        if SETTINGS["corner"] == "off":
            self.root.withdraw()
            return
        
        self.root.deiconify()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        m = SETTINGS["margin"]
        s = WINDOW_SIZE
        
        pos = {
            "top-left": (m, m),
            "top-right": (sw - s - m, m),
            "bottom-left": (m, sh - s - m),
            "bottom-right": (sw - s - m, sh - s - m)
        }
        x, y = pos.get(SETTINGS["corner"], (m, m))
        self.root.geometry(f"{s}x{s}+{x}+{y}")

    def _loop(self):
        try:
            while True:
                cmd = cmd_queue.get_nowait()
                if cmd == "update": 
                    self._apply_settings()
                elif cmd == "exit": 
                    self.root.destroy()
                    return
        except queue.Empty:
            pass

        if SETTINGS["corner"] != "off":
            if STATUS["record"]:
                char = SYMBOLS["pause"] if STATUS["paused"] else SYMBOLS["record"]
                col = COLORS["pause"] if STATUS["paused"] else COLORS["record"]
                self.label.config(text=char, fg=col)
            elif STATUS["buffer"]:
                self.label.config(text=SYMBOLS["buffer"], fg=COLORS["buffer"])
            else:
                self.label.config(text="")
        else:
            self.label.config(text="")
        
        self.root.after(UPDATE_MS, self._loop)

def event_handler(event):
    if event == obs.OBS_FRONTEND_EVENT_RECORDING_STARTED:
        STATUS["record"] = True
    elif event == obs.OBS_FRONTEND_EVENT_RECORDING_STOPPED:
        STATUS["record"] = False
        STATUS["paused"] = False
    elif event == obs.OBS_FRONTEND_EVENT_RECORDING_PAUSED:
        STATUS["paused"] = True
    elif event == obs.OBS_FRONTEND_EVENT_RECORDING_UNPAUSED:
        STATUS["paused"] = False
    elif event == obs.OBS_FRONTEND_EVENT_REPLAY_BUFFER_SAVED:
        STATUS["buffer"] = True
        threading.Timer(REPLAY_BUFFER_PAUSE, lambda: STATUS.update({"buffer": False})).start()

def script_description():
    return "OBS Overlay Recording Indicator\n\n● Record | ■ Pause | ⟳ Buffer"

def script_properties():
    props = obs.obs_properties_create()
    p = obs.obs_properties_add_list(props, "corner", "Position", obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
    for v, d in [("top-left", "Top-left"), ("top-right", "Top-right"), ("bottom-left", "Bottom-left"), ("bottom-right", "Bottom-right"), ("off", "Off")]:
        obs.obs_property_list_add_string(p, d, v)
    obs.obs_properties_add_int_slider(props, "margin", "Margin", 1, 300, 1)
    obs.obs_properties_add_int_slider(props, "f_size", "Size", 10, 150, 1)
    obs.obs_properties_add_float_slider(props, "opacity", "Opacity", 0.1, 1.0, 0.1)
    return props

def script_update(settings):
    SETTINGS["corner"] = obs.obs_data_get_string(settings, "corner") or "top-left"
    SETTINGS["margin"] = obs.obs_data_get_int(settings, "margin")
    SETTINGS["f_size"] = obs.obs_data_get_int(settings, "f_size") or 25
    SETTINGS["opacity"] = obs.obs_data_get_double(settings, "opacity") or 0.6
    cmd_queue.put("update")

def start_overlay():
    global overlay_instance
    if overlay_instance is None:
        overlay_instance = Overlay()
        overlay_instance.root.mainloop()
        overlay_instance = None

def script_load(settings):
    obs.obs_frontend_add_event_callback(event_handler)
    thread = threading.Thread(target=start_overlay, daemon=True)
    thread.start()

def script_unload():
    cmd_queue.put("exit")
