# Image-to-Latex-code
A Python desktop application that reads any raster image and converts it into a **fully self-contained LaTeX/TikZ source file** — no external image dependency required after conversion. The output `.tex` file reconstructs the image entirely from colored rectangles drawn with TikZ commands.

***

## Table of Contents

- [How It Works — Full Code Explanation](#how-it-works--full-code-explanation)
  - [1. Imports](#1-imports)
  - [2. The Conversion Core — `image_to_tikz()`](#2-the-conversion-core--image_to_tikz)
  - [3. The GUI — `App` class](#3-the-gui--app-class)
  - [4. Entry Point](#4-entry-point)
- [Where the Commands Come From](#where-the-commands-come-from)
- [Installation](#installation)
- [Usage](#usage)
- [Output Format](#output-format)
- [Resolution Guide](#resolution-guide)
- [Project Structure](#project-structure)
- [Requirements](#requirements)
- [License](#license)

***

## How It Works — Full Code Explanation

### 1. Imports

```python
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image
import os
import threading
```

| Import | Where it comes from | What it does |
|--------|---------------------|--------------|
| `tkinter` | Python standard library (built-in) | Creates native desktop GUI windows, buttons, labels, and entry fields |
| `tkinter.ttk` | Part of `tkinter` standard library | Provides themed (styled) widgets like `ttk.Button`, `ttk.Scale`, `ttk.Progressbar` |
| `tkinter.filedialog` | Part of `tkinter` standard library | Opens native OS file picker dialogs ("Browse…" buttons) |
| `tkinter.messagebox` | Part of `tkinter` standard library | Shows popup alert/info/error dialogs |
| `PIL.Image` | **Pillow** library — install with `pip install Pillow` | Opens and processes image files; resizes them; reads pixel RGB values |
| `os` | Python standard library (built-in) | Handles file paths, checks if files exist, extracts filenames |
| `threading` | Python standard library (built-in) | Runs the conversion in a background thread so the GUI doesn't freeze |

***

### 2. The Conversion Core — `image_to_tikz()`

This is the heart of the program. It takes an image file and returns a string of valid LaTeX code.

```python
def image_to_tikz(image_path, max_size=80, progress_cb=None):
```

**Parameters:**
- `image_path` — the path to the image file on disk
- `max_size` — the maximum number of pixels along the longest side after resizing (default: 80)
- `progress_cb` — an optional callback function that receives a percentage (0–100) for the progress bar

***

#### Step 1 — Open and normalize the image

```python
img = Image.open(image_path).convert("RGB")
```

- `Image.open()` comes from **Pillow**. It can open PNG, JPG, BMP, GIF, WEBP, TIFF, and more.
- `.convert("RGB")` ensures every pixel has exactly three color channels: Red, Green, Blue. This is necessary because some images have an alpha (transparency) channel (RGBA) or are grayscale. Converting to RGB makes pixel reading uniform regardless of the original format.

***

#### Step 2 — Resize while keeping the aspect ratio

```python
w, h = img.size
if w >= h:
    new_w = max_size
    new_h = max(1, round(h * max_size / w))
else:
    new_h = max_size
    new_w = max(1, round(w * max_size / h))

img = img.resize((new_w, new_h), Image.LANCZOS)
```

- `img.size` returns `(width, height)` as a tuple — this comes from **Pillow**.
- The `if/else` block calculates new dimensions so neither side exceeds `max_size`, preserving the original aspect ratio. `max(1, ...)` prevents a dimension of 0 for very thin images.
- `img.resize((new_w, new_h), Image.LANCZOS)` downscales the image. `Image.LANCZOS` is a high-quality resampling filter from **Pillow** that uses the Lanczos algorithm — it produces sharper results than simpler filters like `NEAREST` or `BILINEAR`.

***

#### Step 3 — Read pixel colors

```python
pixels = img.load()
```

- `img.load()` returns a **pixel access object** from **Pillow**. You can then read any pixel as `pixels[x, y]`, which returns a tuple `(R, G, B)` where each value is an integer from 0 to 255.

***

#### Step 4 — Generate TikZ rectangles for each pixel

```python
for y in range(new_h):
    for x in range(new_w):
        r, g, b = pixels[x, y]
        r_f = round(r / 255, 3)
        g_f = round(g / 255, 3)
        b_f = round(b / 255, 3)
        ty = new_h - 1 - y
        lines.append(
            f"  \\fill[fill={{rgb,1:red,{r_f};green,{g_f};blue,{b_f}}}] "
            f"({x},{ty}) rectangle ({x+1},{ty+1});"
        )
```

This is the core loop. For every pixel position `(x, y)`:

1. **Read RGB** — `pixels[x, y]` returns three integers (0–255).
2. **Normalize to 0–1 range** — LaTeX's TikZ `rgb` color model expects values between 0 and 1, not 0–255. So `r_f = r / 255`, etc. `round(..., 3)` keeps 3 decimal places to avoid bloated file sizes.
3. **Flip the Y axis** — `ty = new_h - 1 - y`  
   In standard image coordinates (Pillow), `y=0` is the **top** of the image. In TikZ coordinates, `y=0` is the **bottom**. Without this flip, the image would appear upside-down in LaTeX. By subtracting from `new_h - 1`, we mirror the row order.
4. **Write the TikZ command** — `\fill[fill={rgb,1:red,...;green,...;blue,...}] (x,ty) rectangle (x+1,ty+1);`  
   Each pixel becomes a 1×1 unit square at position `(x, ty)` to `(x+1, ty+1)`.

**The TikZ `\fill` command:**
- `\fill` is a TikZ drawing command that draws and fills a shape with no border stroke.
- `fill={rgb,1:red,R;green,G;blue,B}` is TikZ's syntax for specifying an RGB color inline. The `,1` means the scale goes from 0 to 1 (as opposed to 0–255).
- `(x,ty) rectangle (x+1,ty+1)` draws a filled rectangle from the bottom-left corner `(x, ty)` to the top-right corner `(x+1, ty+1)`.

***

#### Step 5 — Assemble the complete LaTeX document

```python
latex = rf"""\documentclass{{standalone}}
\usepackage{{tikz}}

\begin{{document}}
\begin{{tikzpicture}}[x=1pt, y=1pt, scale=1]
{tikz_body}
\end{{tikzpicture}}
\end{{document}}
"""
```

- `\documentclass{standalone}` — a minimal LaTeX class that crops the PDF to exactly the size of the content. No page margins or header/footer — just the picture.
- `\usepackage{tikz}` — loads the TikZ graphics package, which provides all the `\fill`, `\draw`, and coordinate commands.
- `\begin{tikzpicture}[x=1pt, y=1pt, scale=1]` — starts a TikZ drawing environment. `x=1pt, y=1pt` sets each coordinate unit to 1 typographic point (≈0.35 mm). This controls the physical size of the rendered image.
- `{tikz_body}` — all the `\fill` rectangle commands from Step 4 are inserted here.

The `rf"""..."""` is a Python **raw f-string**: the `r` prefix means backslashes are treated literally (not as escape sequences), and `f` allows `{variable}` interpolation.

***

### 3. The GUI — `App` class

The GUI is built with `tkinter` and `tkinter.ttk`. Here is a breakdown of every component:

#### `__init__` — initialization

```python
def __init__(self, root):
    self.root = root
    self.root.title("Image → TikZ LaTeX Generator")
    self.root.geometry("660x540")
    self.root.resizable(False, False)
    self.root.configure(bg="#f7f6f2")
```

- `root` is the main `tk.Tk()` window object passed in from the entry point.
- `.title()` sets the window title bar text.
- `.geometry("660x540")` sets a fixed window size in pixels (width × height).
- `.resizable(False, False)` prevents the user from resizing the window in both directions.
- `.configure(bg=...)` sets the background color of the window using a hex color code.

***

#### `_build_style()` — visual styling

```python
s = ttk.Style()
s.theme_use("clam")
s.configure("TLabel", background="#f7f6f2", font=("Segoe UI", 10))
```

- `ttk.Style()` is the theming engine for `ttk` widgets. It controls fonts, colors, and padding globally.
- `.theme_use("clam")` sets the base theme. `"clam"` is a cross-platform theme that allows custom colors (unlike the default `"vista"` or `"aqua"` themes which are OS-controlled).
- `.configure("TLabel", ...)` applies styles to all `ttk.Label` widgets. Custom styles like `"Head.TLabel"` or `"Primary.TButton"` are named variants you create and then reference with `style="Head.TLabel"` in any widget.
- `.map("Primary.TButton", background=[...])` sets **state-dependent** styles — here, the background color changes when the button is `active` (hovered/clicked) or `disabled`.

***

#### `_build_ui()` — widget layout

All widgets are placed using the `pack()` geometry manager, which stacks elements vertically (or horizontally with `side="left"`).

```python
ttk.Label(self.root, text="🎨  Image → TikZ LaTeX Generator", style="Head.TLabel").pack(anchor="w", padx=28, pady=(22, 2))
```

- `ttk.Label` creates a text label. `style="Head.TLabel"` applies the custom large bold style.
- `.pack(anchor="w")` aligns it to the left (`"w"` = west).
- `padx=28` adds 28px horizontal padding; `pady=(22, 2)` adds 22px top and 2px bottom padding.

```python
self.res_var = tk.IntVar(value=64)
slider = ttk.Scale(f3, from_=16, to=150, orient="horizontal", variable=self.res_var, command=self._update_res_label)
```

- `tk.IntVar()` is a special tkinter integer variable that widgets can bind to. When `slider` moves, `self.res_var` automatically updates, and vice versa.
- `ttk.Scale` creates a horizontal slider from 16 to 150. The `command=self._update_res_label` callback fires every time the slider moves to update the displayed pixel count label.

```python
self.progress = ttk.Progressbar(..., mode="determinate")
```

- `ttk.Progressbar` in `"determinate"` mode shows a bar that fills from 0 to 100. You set its value with `self.progress["value"] = pct`.

***

#### `_pick_image()` and `_pick_save()` — file dialogs

```python
path = filedialog.askopenfilename(
    title="Select an image",
    filetypes=[("Image files", "*.png *.jpg *.jpeg ..."), ("All files", "*.*")]
)
```

- `filedialog.askopenfilename()` opens the native OS "Open File" dialog. `filetypes` filters what files are visible. Returns the selected path as a string, or an empty string if cancelled.
- `filedialog.asksaveasfilename()` opens the native OS "Save As" dialog. `defaultextension=".tex"` auto-appends `.tex` if the user doesn't type an extension.

***

#### `_start_generation()` — threaded launch

```python
threading.Thread(target=self._run, args=(img, out, res), daemon=True).start()
```

- `threading.Thread` runs `self._run()` in a **background thread** so the GUI window stays responsive during conversion (which can take several seconds for large resolutions).
- `daemon=True` means the thread is automatically killed if the main window is closed.
- Input validation (empty fields, missing file, non-numeric width) is done before launching the thread.

***

#### `_run()` — background worker

```python
def _run(self, img, out, res):
    def progress_cb(pct):
        self.progress["value"] = pct
        self.status_var.set(f"Converting… {pct:.0f}%")
        self.root.update_idletasks()
    ...
    latex, w, h = image_to_tikz(img, max_size=res, progress_cb=progress_cb)
    with open(out, "w", encoding="utf-8") as f:
        f.write(latex)
    self.root.after(0, self._done, out, w, h)
```

- `progress_cb` is a nested function passed to `image_to_tikz()`. Every 200 pixels processed, it updates the progress bar and status label. `self.root.update_idletasks()` forces the GUI to repaint immediately.
- `self.root.after(0, self._done, ...)` schedules `_done()` to run on the **main thread** (required in tkinter — GUI updates must always happen on the main thread, never a background thread).
- `open(out, "w", encoding="utf-8")` writes the generated LaTeX string to disk.

***

### 4. Entry Point

```python
if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
```

- `tk.Tk()` creates the root window of the application.
- `App(root)` instantiates the application class, building all the UI.
- `root.mainloop()` starts the **tkinter event loop** — this is a loop that listens for user events (clicks, key presses, window close) and dispatches them to the appropriate handlers. The program stays running inside this loop until the window is closed.

***

## Where the Commands Come From

| Command / Concept | Source | Documentation |
|---|---|---|
| `Image.open()`, `.resize()`, `.load()`, `.convert()` | **Pillow** (PIL fork) — `pip install Pillow` | https://pillow.readthedocs.io |
| `Image.LANCZOS` | **Pillow** resampling filter | https://pillow.readthedocs.io/en/stable/reference/Image.html |
| `tk.Tk()`, `ttk.Label`, `ttk.Button`, etc. | **tkinter** — Python built-in GUI library | https://docs.python.org/3/library/tkinter.html |
| `ttk.Style`, `.configure()`, `.map()` | **tkinter.ttk** — themed widget extension | https://docs.python.org/3/library/tkinter.ttk.html |
| `filedialog.askopenfilename()` | **tkinter.filedialog** — built-in | https://docs.python.org/3/library/dialog.html |
| `tk.IntVar`, `tk.StringVar` | **tkinter** observable variables | https://docs.python.org/3/library/tkinter.html#tkinter-variables |
| `threading.Thread` | **threading** — Python built-in | https://docs.python.org/3/library/threading.html |
| `\fill[fill={rgb,1:...}]` | **TikZ** LaTeX package (`pgf/tikz`) | https://tikz.dev |
| `\documentclass{standalone}` | **LaTeX** document class | https://ctan.org/pkg/standalone |
| `\usepackage{tikz}` | **TikZ/PGF** LaTeX package | https://ctan.org/pkg/pgf |

***

## Installation

### Prerequisites

- Python 3.8 or higher
- A LaTeX distribution to compile the output (optional, only needed to produce the PDF):
  - **Windows**: [MiKTeX](https://miktex.org/) or [TeX Live](https://www.tug.org/texlive/)
  - **macOS**: [MacTeX](https://www.tug.org/mactex/)
  - **Linux**: `sudo apt install texlive-full` (Debian/Ubuntu) or equivalent

### Install Python dependency

```bash
pip install Pillow
```

> `tkinter` is included with Python on Windows and macOS. On Linux you may need:
> ```bash
> sudo apt install python3-tk
> ```

### Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/image-to-tikz.git
cd image-to-tikz
```

***

## Usage

### Run the application

```bash
python image_to_tikz.py
```

### Steps inside the GUI

1. Click **Browse…** next to *Image File* and select any PNG, JPG, BMP, GIF, WEBP, or TIFF image.
2. Click **Browse…** next to *Save .tex File As* and choose where to save the output. (Auto-fills based on the image path.)
3. Adjust the **Resolution slider** — this controls how many pixels the longest side is scaled to before conversion. See the [Resolution Guide](#resolution-guide) below.
4. Click **Generate TikZ File** and wait for the progress bar to complete.

### Compile the output to PDF

After generating, navigate to the output folder and run:

```bash
pdflatex your_file_tikz.tex
```

This produces a `your_file_tikz.pdf` — a fully vector PDF reconstruction of the image, with no external image file required.

***

## Output Format

The generated `.tex` file looks like this:

```latex
\documentclass{standalone}
\usepackage{tikz}

\begin{document}
\begin{tikzpicture}[x=1pt, y=1pt, scale=1]
% Auto-generated from: photo.jpg
% Resolution: 64x48 pixels
  \fill[fill={rgb,1:red,0.98;green,0.42;blue,0.2}] (0,47) rectangle (1,48);
  \fill[fill={rgb,1:red,0.97;green,0.41;blue,0.19}] (1,47) rectangle (2,48);
  ...
\end{tikzpicture}
\end{document}
```

Each line represents one pixel as a filled 1×1 unit rectangle with an exact RGB color. The total number of lines equals `width × height` pixels.

***

## Resolution Guide

| Slider | Approx. pixels | .tex file size | Compile time |
|--------|---------------|----------------|--------------|
| 32 px  | ~1,000        | ~100 KB        | Seconds      |
| 64 px  | ~4,000        | ~400 KB        | 10–30 sec    |
| 100 px | ~10,000       | ~1 MB          | 1–2 min      |
| 150 px | ~22,000       | ~2.2 MB        | Several min  |

**Recommendation:** Start at **64 px** for a good balance between visual quality and compile speed. The PDF output is vector-based and can be zoomed infinitely without loss of quality.

***

## Project Structure

```
image-to-tikz/
├── image_to_tikz.py   # Main application — all code in one file
├── README.md          # This documentation
└── examples/          # (Optional) sample input images and generated .tex files
```

***

## Requirements

```
Python >= 3.8
Pillow >= 9.0
```

No other third-party dependencies. `tkinter` and `threading` are part of the Python standard library.

***

## How the Y-Axis Flip Works

Pillow and TikZ use opposite coordinate systems:

```
Pillow (image):      TikZ (drawing):
y=0 ── top           y=0 ── bottom
y=h ── bottom        y=h ── top
```

Without correction the image renders upside-down. The fix is:

```python
ty = new_h - 1 - y
```

This maps Pillow row `0` → TikZ row `new_h - 1` (top), and Pillow row `new_h - 1` → TikZ row `0` (bottom), effectively mirroring the vertical axis.

***

## License

MIT License — free to use, modify, and distribute.

***

## Author

Generated with Python 3 · Pillow · tkinter · TikZ/LaTeX
