import customtkinter as ctk
import logging
import sys 
from pathlib import Path 

logger = logging.getLogger(__name__) # Will be child of "py_pixel_bot"

class RegionSelectorWindow(ctk.CTkToplevel):
    def __init__(self, master=None, initial_region_name=""):
        super().__init__(master)
        logger.info("Initializing RegionSelectorWindow (Phase 2 - Refined)...")

        self.start_x = None
        self.start_y = None
        self.current_rect_item = None 
        self.final_selected_coords = None 
        self.confirmed_region_data = None # This attribute will store the result

        # --- Window Configuration ---
        self.title("Region Selector")
        try:
            # Fullscreen can sometimes be problematic or vary by OS/WM with Tkinter underlyingly
            self.attributes('-fullscreen', True) 
            self.attributes('-topmost', True) 
            self.attributes('-alpha', 0.35) # Slightly less transparent for better rectangle visibility
        except Exception as e_attr:
            logger.warning(f"Could not set all window attributes (fullscreen/topmost/alpha): {e_attr}. Using defaults.")
            # Fallback to a large window if fullscreen fails
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            self.geometry(f"{screen_width}x{screen_height}+0+0")


        # --- Canvas for Drawing ---
        self.canvas = ctk.CTkCanvas(self, highlightthickness=0, bg="gray15") # Slightly lighter than pure black
        self.canvas.pack(fill="both", expand=True)

        # --- Mouse Bindings for Drawing ---
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)
        self.bind("<Escape>", self.cancel_and_close_event) # Ensure it takes event arg

        # --- Instruction Label (initially visible) ---
        self.instruction_frame = ctk.CTkFrame(self.canvas, fg_color=("gray10", "gray90"), corner_radius=6)
        self.instruction_label = ctk.CTkLabel(self.instruction_frame, 
                                             text="Click and drag to select a region.\nRelease mouse to see confirmation options. Press ESC to cancel.",
                                             font=("Arial", 16), text_color=("white","black"), padx=10, pady=5)
        self.instruction_label.pack(padx=5, pady=5)
        self.instruction_frame.place(relx=0.5, rely=0.05, anchor="n")

        # --- Confirmation Widgets (initially not placed) ---
        self.confirm_frame = ctk.CTkFrame(self.canvas, fg_color=("gray90", "gray25"), corner_radius=6) # Opaque frame
        
        ctk.CTkLabel(self.confirm_frame, text="Region Name:", font=("Arial", 14)).grid(row=0, column=0, padx=10, pady=(10,5), sticky="w")
        self.region_name_entry = ctk.CTkEntry(self.confirm_frame, font=("Arial", 14), width=250)
        self.region_name_entry.insert(0, initial_region_name or "MyRegion")
        self.region_name_entry.grid(row=0, column=1, padx=10, pady=(10,5), sticky="ew")
        
        self.coords_label = ctk.CTkLabel(self.confirm_frame, text="Coords: (x,y,w,h)", font=("Arial", 12))
        self.coords_label.grid(row=1, column=0, columnspan=2, padx=10, pady=2, sticky="w")

        button_frame = ctk.CTkFrame(self.confirm_frame, fg_color="transparent") # Frame for buttons
        button_frame.grid(row=2, column=0, columnspan=2, pady=(5,10))

        self.confirm_button = ctk.CTkButton(button_frame, text="Confirm Region", command=self.on_confirm, font=("Arial", 14))
        self.confirm_button.pack(side="left", padx=10)
        
        self.cancel_button = ctk.CTkButton(button_frame, text="Redraw / Cancel", command=self.on_cancel_selection, fg_color="gray50", hover_color="gray40", font=("Arial", 14))
        self.cancel_button.pack(side="left", padx=10)
        
        logger.info("RegionSelectorWindow UI elements configured.")
        self.grab_set() 
        self.focus_force()
        logger.debug("RegionSelectorWindow grab_set and focus_force called.")


    def on_mouse_press(self, event):
        self.confirm_frame.place_forget()
        self.instruction_frame.place(relx=0.5, rely=0.05, anchor="n") 

        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        logger.debug(f"Mouse press at canvas ({self.start_x:.0f}, {self.start_y:.0f})")

        if self.current_rect_item:
            self.canvas.delete(self.current_rect_item)
        self.current_rect_item = None
        self.final_selected_coords = None
        # self.confirmed_region_data = None # Reset only on explicit cancel or new successful confirm

    def on_mouse_drag(self, event):
        if self.start_x is None or self.start_y is None:
            return

        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)

        if self.current_rect_item:
            self.canvas.delete(self.current_rect_item)
        
        self.current_rect_item = self.canvas.create_rectangle(
            self.start_x, self.start_y, cur_x, cur_y, 
            outline="cyan", width=2, fill="#00FFFF", stipple="gray12" # Cyan, slightly more visible fill
        )
        # Using a lower level log for drag events as they are very frequent
        # logger.log(logging.DEBUG - 5, f"Drag to ({cur_x:.0f}, {cur_y:.0f})")

    def on_mouse_release(self, event):
        if self.start_x is None or self.start_y is None:
            logger.debug("Mouse release ignored, no corresponding press.")
            return 

        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)
        logger.debug(f"Mouse release at canvas ({end_x:.0f}, {end_y:.0f})")

        # Normalize coordinates (x1 < x2, y1 < y2)
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)

        width = x2 - x1
        height = y2 - y1

        # Define a minimum size for a valid region
        min_dimension = 5 
        if width >= min_dimension and height >= min_dimension:
            self.final_selected_coords = (int(x1), int(y1), int(width), int(height))
            logger.info(f"Region drawn: x={int(x1)}, y={int(y1)}, w={int(width)}, h={int(height)}")
            
            if self.current_rect_item: 
                self.canvas.itemconfig(self.current_rect_item, outline="lime green", fill="green", stipple="gray25")

            self.instruction_frame.place_forget() 
            self.coords_label.configure(text=f"Coords: (X:{int(x1)}, Y:{int(y1)}, W:{int(width)}, H:{int(height)})")
            self.confirm_frame.place(relx=0.5, rely=0.15, anchor="n") # Place slightly lower
            self.region_name_entry.focus_set() 
            self.region_name_entry.configure(border_color=ctk.ThemeManager.theme["CTkEntry"]["border_color"]) # Reset border color
        else:
            logger.warning(f"Selected region too small (w:{width:.0f}, h:{height:.0f}). Selection ignored.")
            if self.current_rect_item:
                self.canvas.delete(self.current_rect_item)
            self.current_rect_item = None
            self.final_selected_coords = None
        
        # Reset start_x/y to prevent issues if user clicks again without dragging before a new press
        self.start_x = None
        self.start_y = None


    def on_confirm(self):
        logger.debug("Confirm button clicked.")
        if self.final_selected_coords:
            region_name = self.region_name_entry.get().strip()
            if not region_name:
                logger.warning("Region name cannot be empty. Please enter a name.")
                self.region_name_entry.focus_set()
                self.region_name_entry.configure(border_color="red")
                return

            self.confirmed_region_data = { # This is the data that will be returned
                "name": region_name,
                "coords": self.final_selected_coords
            }
            logger.info(f"Region selection CONFIRMED: Name='{self.confirmed_region_data['name']}', Coords={self.confirmed_region_data['coords']}")
            # This print is helpful for immediate user feedback if running script directly
            print(f"SUCCESS (GUI Event): Region Confirmed -> Name: {self.confirmed_region_data['name']}, Coords: {self.confirmed_region_data['coords']}")
            self.destroy() # Close the Toplevel window
        else:
            logger.warning("Confirm button clicked, but no valid region (self.final_selected_coords) is set.")

    def on_cancel_selection(self): # "Redraw / Cancel" button
        logger.info("Selection cancelled by 'Redraw / Cancel' button. Clearing current selection.")
        if self.current_rect_item:
            self.canvas.delete(self.current_rect_item)
        self.current_rect_item = None
        self.final_selected_coords = None
        self.confirmed_region_data = None # Ensure no data if cancelled this way
        self.confirm_frame.place_forget()
        self.instruction_frame.place(relx=0.5, rely=0.05, anchor="n") # Show instructions again
        logger.debug("Ready for new region selection.")

    def cancel_and_close_event(self, event=None): # Bound to ESC
        logger.info("RegionSelectorWindow closing due to ESC or programmatic call.")
        self.confirmed_region_data = None # Explicitly ensure no data is returned on cancel
        self.destroy()

    # This method is not strictly needed if launch_region_selector_interactive directly accesses confirmed_region_data
    # but keeping it for API consistency if called from elsewhere.
    def get_confirmed_region(self): 
        logger.debug(f"get_confirmed_region called, returning: {self.confirmed_region_data}")
        return self.confirmed_region_data


def launch_region_selector_interactive(initial_name=""):
    """
    Launches the modal region selector GUI and waits for it to close.
    Returns the confirmed region data (dict: {"name": str, "coords": tuple}) or None if cancelled.
    """
    logger.info(f"Launching interactive region selector. Initial proposed name: '{initial_name}'")
    root_for_selector = None
    selector_window_instance = None
    returned_data = None

    try:
        # Attempt to create a minimal, hidden root window for the Toplevel.
        # This helps CustomTkinter manage its lifecycle, especially if run standalone.
        root_for_selector = ctk.CTk()
        root_for_selector.withdraw() # Hide the root window.

        selector_window_instance = RegionSelectorWindow(master=root_for_selector, initial_region_name=initial_name)
        logger.debug(f"RegionSelectorWindow instance created: {selector_window_instance}. Making it modal and waiting...")
        
        # wait_window makes the Toplevel modal and blocks until it's destroyed.
        selector_window_instance.wait_window() 
        logger.debug("wait_window() returned. RegionSelectorWindow should be destroyed.")

        # After the window is destroyed, its attributes can still be accessed if the instance reference exists.
        if selector_window_instance: # Check if instance was created
            # The data is stored in an attribute of the (now destroyed) window instance
            returned_data = selector_window_instance.confirmed_region_data 
            if returned_data:
                 logger.info(f"Data retrieved from closed selector instance: Name='{returned_data.get('name')}', Coords={returned_data.get('coords')}")
            else:
                 logger.info("Selector instance closed, and confirmed_region_data is None (selection likely cancelled or no valid selection made).")
        else:
            logger.warning("Selector window instance was not created properly.")
            
        return returned_data

    except Exception as e:
        logger.error(f"Error during launch_region_selector_interactive: {e}", exc_info=True)
        return None
    finally:
        # Ensure the dummy root window is destroyed if it was created by this function and still exists.
        if root_for_selector and hasattr(root_for_selector, 'winfo_exists') and root_for_selector.winfo_exists():
            logger.debug("Destroying temporary root window from launch_region_selector_interactive.")
            root_for_selector.destroy()
        logger.debug("launch_region_selector_interactive finished.")


if __name__ == '__main__':
    current_script_path = Path(__file__).resolve()
    project_src_dir = current_script_path.parent.parent.parent.parent 
    if str(project_src_dir) not in sys.path:
        sys.path.insert(0, str(project_src_dir))

    from py_pixel_bot.core.config_manager import load_environment_variables
    load_environment_variables() 
    from py_pixel_bot.core.logging_setup import setup_logging
    setup_logging() 

    test_logger_gui = logging.getLogger(__name__ + "_test_main") # More specific logger
    test_logger_gui.info("--- RegionSelector Test Start (Phase 2 - Refined) ---")
    
    # It's good practice to set appearance mode and theme once at the start if your app uses CTk.
    # If this is called from a larger CTk app, that app would handle this.
    try:
        ctk.set_appearance_mode(os.getenv("CTkAppearanceMode", "System")) 
        ctk.set_default_color_theme(os.getenv("CTkColorTheme", "blue")) 
    except Exception as e_theme:
        test_logger_gui.warning(f"Could not set CTk theme in test: {e_theme}")


    test_logger_gui.info("Launching RegionSelectorWindow via helper function...")
    
    selected_data_from_launch = launch_region_selector_interactive(initial_name="TestRegionFromMain")
    
    if selected_data_from_launch:
        test_logger_gui.info(f"Test completed. Confirmed Region -> Name: '{selected_data_from_launch.get('name')}', Coords: {selected_data_from_launch.get('coords')}")
    else:
        test_logger_gui.info("Test completed. No region was confirmed or window was cancelled by user.")
        
    test_logger_gui.info("--- RegionSelector Test End (Phase 2 - Refined) ---")