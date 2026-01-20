"""
Interactive crop area selection tool for OCR region selection.
"""
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk, ImageDraw
from typing import Optional, Tuple
import config


class CropSelectorDialog:
    """Dialog window for selecting crop area on a screenshot."""
    
    def __init__(self, parent, screenshot: Image.Image):
        """
        Initialize the crop selector dialog.
        
        Args:
            parent: Parent tkinter window
            screenshot: PIL Image of the window to crop
        """
        self.result = None  # Will store (left, top, right, bottom)
        self.screenshot = screenshot
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Crop Area")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Calculate display size (scale down if image is too large)
        max_width = parent.winfo_screenwidth() - 100
        max_height = parent.winfo_screenheight() - 200
        
        img_width, img_height = screenshot.size
        scale_x = min(1.0, max_width / img_width)
        scale_y = min(1.0, max_height / img_height)
        self.scale = min(scale_x, scale_y)
        
        self.display_width = int(img_width * self.scale)
        self.display_height = int(img_height * self.scale)
        
        # Resize image for display
        self.display_image = screenshot.resize(
            (self.display_width, self.display_height),
            Image.Resampling.LANCZOS
        )
        
        # Instructions
        instructions = tk.Label(
            self.dialog,
            text="Click and drag to select the text area to read. Avoid headers, page numbers, and images.",
            wraplength=self.display_width,
            pady=10
        )
        instructions.pack()
        
        # Canvas for image and rectangle drawing
        self.canvas = tk.Canvas(
            self.dialog,
            width=self.display_width,
            height=self.display_height,
            cursor="cross"
        )
        self.canvas.pack()
        
        # Convert PIL image to PhotoImage
        self.photo = ImageTk.PhotoImage(self.display_image)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        
        # Rectangle drawing state
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.current_rect = None
        
        # Bind mouse events
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        
        # Buttons
        button_frame = tk.Frame(self.dialog)
        button_frame.pack(pady=10)
        
        tk.Button(
            button_frame,
            text="Accept",
            command=self._accept,
            width=12
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="Reset",
            command=self._reset,
            width=12
        ).pack(side=tk.LEFT, padx=5)
        
        tk.Button(
            button_frame,
            text="Cancel",
            command=self._cancel,
            width=12
        ).pack(side=tk.LEFT, padx=5)
        
        # Center dialog on parent
        self.dialog.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.dialog.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")
    
    def _on_press(self, event):
        """Handle mouse button press."""
        self.start_x = event.x
        self.start_y = event.y
        
        # Remove old rectangle if exists
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        
        # Create new rectangle
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline='red', width=2
        )
    
    def _on_drag(self, event):
        """Handle mouse drag."""
        if self.rect_id:
            # Clamp coordinates to canvas bounds
            cur_x = max(0, min(event.x, self.display_width))
            cur_y = max(0, min(event.y, self.display_height))
            
            # Update rectangle
            self.canvas.coords(
                self.rect_id,
                self.start_x, self.start_y,
                cur_x, cur_y
            )
    
    def _on_release(self, event):
        """Handle mouse button release."""
        if self.rect_id:
            # Clamp coordinates to canvas bounds
            end_x = max(0, min(event.x, self.display_width))
            end_y = max(0, min(event.y, self.display_height))
            
            # Ensure start is top-left, end is bottom-right
            x1 = min(self.start_x, end_x)
            y1 = min(self.start_y, end_y)
            x2 = max(self.start_x, end_x)
            y2 = max(self.start_y, end_y)
            
            # Store the rectangle in display coordinates
            self.current_rect = (x1, y1, x2, y2)
            
            # Update rectangle to be neat
            self.canvas.coords(self.rect_id, x1, y1, x2, y2)
    
    def _reset(self):
        """Reset the selection."""
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
        self.current_rect = None
        self.start_x = None
        self.start_y = None
    
    def _accept(self):
        """Accept the current selection."""
        if not self.current_rect:
            messagebox.showwarning(
                "No Selection",
                "Please draw a rectangle around the text area first.",
                parent=self.dialog
            )
            return
        
        x1, y1, x2, y2 = self.current_rect
        
        # Validate selection size
        if (x2 - x1) < 50 or (y2 - y1) < 50:
            messagebox.showwarning(
                "Selection Too Small",
                "Please select a larger area.",
                parent=self.dialog
            )
            return
        
        # Convert display coordinates back to original image coordinates
        orig_x1 = int(x1 / self.scale)
        orig_y1 = int(y1 / self.scale)
        orig_x2 = int(x2 / self.scale)
        orig_y2 = int(y2 / self.scale)
        
        # Convert to crop format (left, top, right, bottom margins)
        img_width, img_height = self.screenshot.size
        crop_left = orig_x1
        crop_top = orig_y1
        crop_right = img_width - orig_x2
        crop_bottom = img_height - orig_y2
        
        self.result = (crop_left, crop_top, crop_right, crop_bottom)
        self.dialog.destroy()
    
    def _cancel(self):
        """Cancel the dialog."""
        self.result = None
        self.dialog.destroy()
    
    def show(self) -> Optional[Tuple[int, int, int, int]]:
        """
        Show the dialog and wait for user input.
        
        Returns:
            Tuple of (left, top, right, bottom) crop margins, or None if cancelled
        """
        self.dialog.wait_window()
        return self.result


def select_crop_area(parent, screenshot: Image.Image) -> Optional[Tuple[int, int, int, int]]:
    """
    Show crop area selection dialog.
    
    Args:
        parent: Parent tkinter window
        screenshot: PIL Image to select crop area from
    
    Returns:
        Tuple of (left, top, right, bottom) crop margins, or None if cancelled
    """
    dialog = CropSelectorDialog(parent, screenshot)
    return dialog.show()
