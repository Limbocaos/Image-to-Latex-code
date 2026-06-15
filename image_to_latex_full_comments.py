# -----------------------------
# Imports
# -----------------------------

# tkinter is Python's built-in GUI library.
# It import it as "tk" because that is the common convention.
import tkinter as tk

# ttk contains themed widgets (better-looking buttons, labels, sliders, etc.)
# filedialog opens native OS dialogs to choose files
# messagebox shows popup messages like errors and success alerts
from tkinter import ttk, filedialog, messagebox

# Pillow (PIL fork) is used to open images, resize them, and read pixels.
# Install with: pip install Pillow
from PIL import Image

# os helps us work with file paths and filenames.
import os

# threading lets us run the heavy conversion in the background
# so the GUI window does not freeze while processing.
import threading


# ============================================================
# Conversion function
# ============================================================
def image_to_tikz(image_path, max_size=80, progress_cb=None):
    """
    Convert an image into a LaTeX/TikZ document.

    Parameters
    ----------
    image_path : str
        Path to the input image.
    max_size : int
        Maximum size of the longest side after resizing.
        Example:
            if the original image is 1200x800 and max_size=80,
            the resized image becomes 80x53.
    progress_cb : function or None
        Optional callback function used to report progress to the GUI.
        The callback receives one number: the percentage completed.

    Returns
    -------
    latex : str
        Complete LaTeX document as a string.
    new_w : int
        Width of resized image in pixels.
    new_h : int
        Height of resized image in pixels.
    """

    # --------------------------------------------------------
    # Step 1: Open the image and force it into RGB format
    # --------------------------------------------------------
    # Some images may be RGBA (with transparency), grayscale, palette-based, etc.
    # Converting to RGB guarantees that every pixel gives us (R, G, B).
    img = Image.open(image_path).convert("RGB") #This line read the input image

    # --------------------------------------------------------
    # Step 2: Read original dimensions
    # --------------------------------------------------------
    w, h = img.size  # Pillow returns (width, height)

    # --------------------------------------------------------
    # Step 3: Resize while keeping aspect ratio
    # --------------------------------------------------------
    # It want the longest side to become max_size.
    # This keeps file size manageable because every pixel becomes one TikZ rectangle.

    if w >= h:
        # Landscape or square image:
        # set new width to max_size and scale height proportionally
        new_w = max_size
        new_h = max(1, round(h * max_size / w))
    else:
        # Portrait image:
        # set new height to max_size and scale width proportionally
        new_h = max_size
        new_w = max(1, round(w * max_size / h))

    # Resize using a high-quality filter.
    # LANCZOS is one of Pillow's best downsampling filters.
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # --------------------------------------------------------
    # Step 4: Prepare direct pixel access
    # --------------------------------------------------------
    # "pixels[x, y]" will return the RGB tuple for that location.
    pixels = img.load()

    # Total number of pixels after resizing.
    # This will also be the number of TikZ rectangles generate.
    total = new_w * new_h
    done = 0  # counts how many pixels have processed so far

    # This list will store every generated TikZ line.
    # Later that join the list into one big string.
    lines = []

    # --------------------------------------------------------
    # Step 5: Convert every pixel into a TikZ rectangle
    # --------------------------------------------------------
    # Outer loop = rows
    for y in range(new_h):
        # Inner loop = columns
        for x in range(new_w):

            # Read the pixel color from the resized image
            r, g, b = pixels[x, y]

            # TikZ rgb,1 color syntax expects values from 0.0 to 1.0,
            # while Pillow gives 0 to 255.
            # So normalize the values.
            r_f = round(r / 255, 3)
            g_f = round(g / 255, 3)
            b_f = round(b / 255, 3)

            # IMPORTANT:
            # Image coordinates and TikZ coordinates grow in opposite directions on Y.
            #
            # Pillow image:
            #   y = 0 at the TOP
            #   y increases downward
            #
            # TikZ:
            #   y = 0 at the BOTTOM
            #   y increases upward
            #
            # So we flip the row index to avoid upside-down output.
            ty = new_h - 1 - y

            # Build one TikZ command for one pixel.

            tikz_line = (
                f"  \\fill[fill={{rgb,1:red,{r_f};green,{g_f};blue,{b_f}}}] "
                f"({x},{ty}) rectangle ({x+1},{ty+1});"
            )

            # Store this line in our list
            lines.append(tikz_line)

            # Update progress tracking
            done += 1

            # If a progress callback exists, report progress every 200 pixels
            # so the GUI bar can update without too much overhead.
            if progress_cb and done % 200 == 0:
                progress_cb(done / total * 100)

    # Make sure the progress finishes at 100%
    if progress_cb:
        progress_cb(100)

    # Join all TikZ commands into one large block of text
    tikz_body = "\n".join(lines)

    # --------------------------------------------------------
    # Step 6: Wrap the TikZ commands in a complete LaTeX file
    # --------------------------------------------------------
    # Documentclass "standalone" so the output PDF is tightly cropped.
    # tikzpicture is the environment where all drawing commands live.

    latex = rf"""\documentclass{{standalone}}
\usepackage{{tikz}}

\begin{{document}}
\begin{{tikzpicture}}[x=1pt, y=1pt, scale=1]
% Auto-generated from: {os.path.basename(image_path)}
% Resolution: {new_w}x{new_h} pixels
{tikz_body}
\end{{tikzpicture}}
\end{{document}}
"""

    # Return the final LaTeX plus the resized dimensions
    return latex, new_w, new_h


# ============================================================
# GUI application class
# ============================================================
class App:
    """
    Main desktop application window.

    This class creates the interface, reacts to button clicks,
    and calls the conversion function in a background thread.
    """

    def __init__(self, root):
        # Save the Tk root window so we can modify it later
        self.root = root

        # Set basic window properties
        self.root.title("Image -> TikZ LaTeX Generator")
        self.root.geometry("660x540") #Size of the window
        self.root.resizable(False, False)
        self.root.configure(bg="#f7f6f2")

        # ----------------------------------------------------
        # Tkinter variables
        # ----------------------------------------------------
        # StringVar and IntVar are tkinter "special variables".
        # Widgets can bind to them and update automatically.

        self.image_path = tk.StringVar()     # selected input image path
        self.save_path = tk.StringVar()      # output .tex path
        self.res_var = tk.IntVar(value=64)   # slider value, default 64 medium value

        # Build the visual style and then place the widgets
        self._build_style()
        self._build_ui()

    def _build_style(self):
        """
        Create visual styles for labels, buttons, progress bars, etc.
        """
        s = ttk.Style()

        # "clam" is a cross-platform ttk theme that is easy to customize
        s.theme_use("clam")

        # Default label style
        s.configure("TLabel", background="#f7f6f2", font=("Segoe UI", 10))

        # Subtext style
        s.configure("Sub.TLabel",
                    background="#f7f6f2",
                    font=("Segoe UI", 9),
                    foreground="#7a7974")

        # Header style
        s.configure("Head.TLabel",
                    background="#f7f6f2",
                    font=("Segoe UI", 14, "bold"),
                    foreground="#01696f")

        # Entry boxes
        s.configure("TEntry", font=("Segoe UI", 10), padding=4)

        # Normal buttons
        s.configure("TButton", font=("Segoe UI", 10), padding=6)

        # Slider background
        s.configure("TScale", background="#f7f6f2")

        # Progress bar style
        s.configure("Green.Horizontal.TProgressbar",
                    troughcolor="#dcd9d5",
                    background="#01696f",
                    thickness=10)

        # Main action button style
        s.configure("Primary.TButton",
                    font=("Segoe UI", 11, "bold"),
                    foreground="white",
                    background="#01696f")

        # State-specific colors for the primary button
        s.map("Primary.TButton",
              background=[("active", "#0c4e54"), ("disabled", "#bab9b4")])

    def _build_ui(self):
        """
        Create and place all GUI widgets.
        """
        P = dict(padx=28, pady=8)

        # Title label
        ttk.Label(
            self.root,
            text="🎨  Image -> TikZ LaTeX Generator",
            style="Head.TLabel"
        ).pack(anchor="w", padx=28, pady=(22, 2))

        # Description text
        ttk.Label(
            self.root,
            text="Converts an image into a self-contained .tex file using TikZ rectangles.",
            style="Sub.TLabel",
            wraplength=600,
            justify="left"
        ).pack(anchor="w", padx=28, pady=(0, 14))

        # Horizontal separator line
        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=28)

        # -------------------------
        # Image file selection row
        # -------------------------
        f1 = tk.Frame(self.root, bg="#f7f6f2")
        f1.pack(fill="x", **P)

        ttk.Label(f1, text="Image File").pack(anchor="w")

        r1 = tk.Frame(f1, bg="#f7f6f2")
        r1.pack(fill="x", pady=(4, 0))

        # Entry linked to self.image_path
        ttk.Entry(r1, textvariable=self.image_path, width=54).pack(side="left", padx=(0, 8))

        # Browse button
        ttk.Button(r1, text="Browse...", command=self._pick_image).pack(side="left")

        # -------------------------
        # Save file selection row
        # -------------------------
        f2 = tk.Frame(self.root, bg="#f7f6f2")
        f2.pack(fill="x", **P)

        ttk.Label(f2, text="Save .tex File As").pack(anchor="w")

        r2 = tk.Frame(f2, bg="#f7f6f2")
        r2.pack(fill="x", pady=(4, 0))

        ttk.Entry(r2, textvariable=self.save_path, width=54).pack(side="left", padx=(0, 8))
        ttk.Button(r2, text="Browse...", command=self._pick_save).pack(side="left")

        # -------------------------
        # Resolution slider row
        # -------------------------
        f3 = tk.Frame(self.root, bg="#f7f6f2")
        f3.pack(fill="x", **P)

        res_row = tk.Frame(f3, bg="#f7f6f2")
        res_row.pack(fill="x")

        ttk.Label(res_row, text="Max Resolution (longest side)").pack(side="left")

        # Label that shows the current slider value
        self.res_label = ttk.Label(res_row, text="64 px", style="Sub.TLabel")
        self.res_label.pack(side="right")

        slider = ttk.Scale(
            f3,
            from_=16,
            to=150,
            orient="horizontal",
            variable=self.res_var,
            command=self._update_res_label
        )
        slider.pack(fill="x", pady=(6, 0))

        ttk.Label(
            f3,
            text="Higher values create larger .tex files and longer LaTeX compile times.",
            style="Sub.TLabel"
        ).pack(anchor="w", pady=(4, 0))

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=28, pady=10)

        # Main generate button
        self.gen_btn = ttk.Button(
            self.root,
            text="Generate TikZ File",
            style="Primary.TButton",
            command=self._start_generation
        )
        self.gen_btn.pack()

        # Progress bar
        self.progress = ttk.Progressbar(
            self.root,
            style="Green.Horizontal.TProgressbar",
            orient="horizontal",
            length=480,
            mode="determinate"
        )
        self.progress.pack(pady=(14, 0))

        # Status bar at the bottom
        self.status_var = tk.StringVar(value="Ready - select an image and output path.")
        tk.Label(
            self.root,
            textvariable=self.status_var,
            bg="#e6e4df",
            fg="#28251d",
            font=("Segoe UI", 9),
            anchor="w",
            padx=16,
            pady=6
        ).pack(fill="x", side="bottom")

    def _update_res_label(self, _=None):
        """
        Update the little text at the right of the slider.
        """
        v = self.res_var.get()
        self.res_label.config(text=f"{v} px")

    def _pick_image(self):
        """
        Open a file dialog so the user can choose an image.
        """
        path = filedialog.askopenfilename(
            title="Select an image",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp"),
                ("All files", "*.*")
            ]
        )

        # If the user selected something (and did not cancel)
        if path:
            self.image_path.set(path)

            # If no output path has been chosen yet, auto-suggest one
            if not self.save_path.get():
                base = os.path.splitext(path)[0]
                self.save_path.set(base + "_tikz.tex")

            self.status_var.set(f"Image selected: {os.path.basename(path)}")

    def _pick_save(self):
        """
        Open a save dialog so the user can choose where to save the .tex file.
        """
        path = filedialog.asksaveasfilename(
            title="Save .tex file as",
            defaultextension=".tex",
            filetypes=[("LaTeX files", "*.tex"), ("All files", "*.*")]
        )

        if path:
            self.save_path.set(path)
            self.status_var.set(f"Output path set: {os.path.basename(path)}")

    def _start_generation(self):
        """
        Validate inputs and start conversion in a background thread.
        """
        img = self.image_path.get().strip()
        out = self.save_path.get().strip()
        res = self.res_var.get()

        # Basic validation
        if not img:
            messagebox.showerror("Missing Input", "Please select an image file.")
            return

        if not os.path.isfile(img):
            messagebox.showerror("File Not Found", f"Image not found:\n{img}")
            return

        if not out:
            messagebox.showerror("Missing Output", "Please specify a save path.")
            return

        # Disable the button to prevent duplicate clicks during processing
        self.gen_btn.state(["disabled"])

        # Reset progress
        self.progress["value"] = 0
        self.status_var.set("Converting... please wait.")

        # Run the heavy work in a separate thread
        threading.Thread(
            target=self._run,
            args=(img, out, res),
            daemon=True
        ).start()

    def _run(self, img, out, res):
        """
        Background worker function.
        This runs outside the main GUI thread.
        """
        def progress_cb(pct):
            # Update progress bar and status text
            self.progress["value"] = pct
            self.status_var.set(f"Converting... {pct:.0f}%")
            self.root.update_idletasks()

        try:
            # Generate LaTeX code from the image
            latex, w, h = image_to_tikz(img, max_size=res, progress_cb=progress_cb)

            # Save to file
            with open(out, "w", encoding="utf-8") as f:
                f.write(latex)

            # Schedule GUI-safe success handler on main thread
            self.root.after(0, self._done, out, w, h)

        except Exception as e:
            # Schedule GUI-safe error handler on main thread
            self.root.after(0, self._error, str(e))

    def _done(self, out, w, h):
        """
        Called when conversion finishes successfully.
        """
        self.gen_btn.state(["!disabled"])
        self.progress["value"] = 100

        pixel_count = w * h
        self.status_var.set(
            f"Done! {w}x{h} = {pixel_count:,} TikZ rectangles -> {os.path.basename(out)}"
        )

        messagebox.showinfo(
            "Success!",
            f"TikZ file saved:\n{out}\n\n"
            f"Resolution used: {w}x{h} pixels ({pixel_count:,} rectangles)\n\n"
            f"Compile with:\n  pdflatex \"{os.path.basename(out)}\""
        )

    def _error(self, msg):
        """
        Called if something fails during conversion.
        """
        self.gen_btn.state(["!disabled"])
        self.status_var.set("Error during conversion.")
        messagebox.showerror("Conversion Error", f"Something went wrong:\n\n{msg}")


# ============================================================
# Program entry point
# ============================================================
# This block runs only when the file is executed directly.
if __name__ == "__main__":
    root = tk.Tk()   # create the main window
    App(root)        # build the application inside that window
    root.mainloop()  # start Tkinter's event loop