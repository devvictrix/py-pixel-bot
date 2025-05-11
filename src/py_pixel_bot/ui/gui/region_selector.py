import customtkinter as ctk
import logging
import sys 
from pathlib import Path 

logger = logging.getLogger(__name__)

class RegionSelectorWindow(ctk.CTkToplevel):
    def __init__(self, master=None, initial_region_name=""):
        super().__init__(master)
        logger.info("Initializing RegionSelectorWindow (Phase 2)...")
        self.start_x = None; self.start_y = None
        self.current_rect_item = None 
        self.final_selected_coords = None 
        self.confirmed_region_data = None 
        self.title("Region Selector"); self.attributes('-fullscreen', True); self.attributes('-topmost', True); self.attributes('-alpha', 0.3) 
        self.canvas = ctk.CTkCanvas(self, highlightthickness=0, bg="gray20"); self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press); self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release); self.bind("<Escape>", self.cancel_and_close)
        self.instruction_frame = ctk.CTkFrame(self.canvas, fg_color=("gray10", "gray90"))
        self.instruction_label = ctk.CTkLabel(self.instruction_frame, text="Click and drag to select a region.\nRelease mouse for options. Press ESC to cancel.", font=("Arial", 16), text_color=("white","black"), padx=10, pady=5)
        self.instruction_label.pack(); self.instruction_frame.place(relx=0.5, rely=0.05, anchor="n")
        self.confirm_frame = ctk.CTkFrame(self.canvas, fg_color=("gray85", "gray20"))
        ctk.CTkLabel(self.confirm_frame, text="Region Name:", font=("Arial", 14)).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.region_name_entry = ctk.CTkEntry(self.confirm_frame, font=("Arial", 14), width=200)
        self.region_name_entry.insert(0, initial_region_name or "MyRegion"); self.region_name_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.coords_label = ctk.CTkLabel(self.confirm_frame, text="Coords: (x,y,w,h)", font=("Arial", 12))
        self.coords_label.grid(row=1, column=0, columnspan=2, padx=5, pady=2, sticky="w")
        self.confirm_button = ctk.CTkButton(self.confirm_frame, text="Confirm Region", command=self.on_confirm, font=("Arial", 14))
        self.confirm_button.grid(row=2, column=0, padx=5, pady=10)
        self.cancel_button = ctk.CTkButton(self.confirm_frame, text="Redraw / Cancel", command=self.on_cancel_selection, fg_color="gray50", hover_color="gray40", font=("Arial", 14))
        self.cancel_button.grid(row=2, column=1, padx=5, pady=10)
        logger.info("RegionSelectorWindow configured."); self.grab_set(); self.focus_force()

    def on_mouse_press(self, event):
        self.confirm_frame.place_forget(); self.instruction_frame.place(relx=0.5, rely=0.05, anchor="n")
        self.start_x = self.canvas.canvasx(event.x); self.start_y = self.canvas.canvasy(event.y)
        logger.debug(f"Mouse press at canvas ({self.start_x}, {self.start_y})")
        if self.current_rect_item: self.canvas.delete(self.current_rect_item)
        self.current_rect_item = None; self.final_selected_coords = None; self.confirmed_region_data = None

    def on_mouse_drag(self, event):
        if self.start_x is None or self.start_y is None: return
        cur_x = self.canvas.canvasx(event.x); cur_y = self.canvas.canvasy(event.y)
        if self.current_rect_item: self.canvas.delete(self.current_rect_item)
        self.current_rect_item = self.canvas.create_rectangle(self.start_x, self.start_y, cur_x, cur_y, outline="red", width=2, fill="blue", stipple="gray25")

    def on_mouse_release(self, event):
        if self.start_x is None or self.start_y is None: return 
        end_x = self.canvas.canvasx(event.x); end_y = self.canvas.canvasy(event.y)
        logger.debug(f"Mouse release at canvas ({end_x}, {end_y})")
        x1=min(self.start_x,end_x); y1=min(self.start_y,end_y); x2=max(self.start_x,end_x); y2=max(self.start_y,end_y)
        width = x2-x1; height = y2-y1
        if width > 5 and height > 5:
            self.final_selected_coords = (int(x1),int(y1),int(width),int(height))
            logger.info(f"Region drawn: x={int(x1)}, y={int(y1)}, w={int(width)}, h={int(height)}")
            if self.current_rect_item: self.canvas.itemconfig(self.current_rect_item, outline="green", fill="green", stipple="gray50")
            self.instruction_frame.place_forget()
            self.coords_label.configure(text=f"Coords: (X:{int(x1)}, Y:{int(y1)}, W:{int(width)}, H:{int(height)})")
            self.confirm_frame.place(relx=0.5, rely=0.05, anchor="n"); self.region_name_entry.focus_set()
        else:
            logger.warning("Selected region too small. Ignored."); 
            if self.current_rect_item: self.canvas.delete(self.current_rect_item)
            self.current_rect_item = None; self.final_selected_coords = None

    def on_confirm(self):
        if self.final_selected_coords:
            region_name = self.region_name_entry.get().strip()
            if not region_name: logger.warning("Region name empty."); self.region_name_entry.focus_set(); self.region_name_entry.configure(border_color="red"); return
            self.confirmed_region_data = {"name": region_name, "coords": self.final_selected_coords}
            logger.info(f"Region confirmed: Name='{region_name}', Coords={self.final_selected_coords}")
            print(f"SUCCESS: Region Confirmed -> Name: {region_name}, Coords: {self.final_selected_coords}")
            self.cancel_and_close() # Use cancel_and_close to ensure destroy
        else: logger.warning("Confirm clicked, no region selected.")

    def on_cancel_selection(self):
        logger.info("Selection cancelled by Redraw/Cancel button.")
        if self.current_rect_item: self.canvas.delete(self.current_rect_item)
        self.current_rect_item = None; self.final_selected_coords = None
        self.confirm_frame.place_forget(); self.instruction_frame.place(relx=0.5, rely=0.05, anchor="n")

    def cancel_and_close(self, event=None):
        logger.info("RegionSelectorWindow closing."); self.confirmed_region_data = None; self.destroy()

    def get_confirmed_region(self): return self.confirmed_region_data

def launch_region_selector_interactive(initial_name=""):
    root = None; selector = None
    try:
        try: # Attempt to manage root window for standalone test
            app_root = ctk.CTk(); root = app_root
            if app_root.winfo_exists() and len(app_root.winfo_children())==0 : root.withdraw()
            else: root = ctk.CTk(); root.withdraw() # Default to new hidden root
        except Exception: root = ctk.CTk(); root.withdraw()
        selector = RegionSelectorWindow(master=root, initial_region_name=initial_name)
        logger.debug("RegionSelectorWindow created. Waiting for window..."); selector.wait_window()
        confirmed_data = selector.get_confirmed_region() if hasattr(selector, 'get_confirmed_region') else None
        if confirmed_data: logger.info(f"Selector returned: {confirmed_data}"); return confirmed_data
        else: logger.info("Selector closed without confirmation."); return None
    except Exception as e: logger.error(f"Error in launch_region_selector: {e}", exc_info=True); return None
    finally:
        if root and hasattr(root, 'winfo_exists') and root.winfo_exists():
             if not (selector and hasattr(selector, 'winfo_exists') and selector.winfo_exists()):
                 logger.debug("Destroying dummy root from launch_region_selector."); root.destroy()

if __name__ == '__main__':
    current_script_path = Path(__file__).resolve()
    project_src_dir = current_script_path.parent.parent.parent.parent 
    if str(project_src_dir) not in sys.path: sys.path.insert(0, str(project_src_dir))
    from py_pixel_bot.core.config_manager import load_environment_variables
    load_environment_variables() 
    from py_pixel_bot.core.logging_setup import setup_logging
    setup_logging() 
    test_logger_gui = logging.getLogger(__name__ + "_test")
    test_logger_gui.info("--- RegionSelector Test Start (Phase 2) ---")
    ctk.set_appearance_mode("System"); ctk.set_default_color_theme("blue")
    test_logger_gui.info("Launching RegionSelectorWindow...")
    selected_data = launch_region_selector_interactive(initial_name="DefaultGUIRegion")
    if selected_data: test_logger_gui.info(f"Test completed. Confirmed: Name='{selected_data['name']}', Coords={selected_data['coords']}")
    else: test_logger_gui.info("Test completed. No region confirmed.")
    test_logger_gui.info("--- RegionSelector Test End (Phase 2) ---")