import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image
import os
import threading

# ── Conversion core ──────────────────────────────────────────────────────────

def image_to_tikz(image_path, max_size=80, progress_cb=None):
    img = Image.open(image_path).convert("RGB")

    # Resize keeping aspect ratio so width <= max_size
    w, h = img.size
    if w >= h:
        new_w = max_size
        new_h = max(1, round(h * max_size / w))
    else:
        new_h = max_size
        new_w = max(1, round(w * max_size / h))

    img = img.resize((new_w, new_h), Image.LANCZOS)
    pixels = img.load()

    total = new_w * new_h
    done = 0

    # Each pixel → 1×1 TikZ rectangle; y-axis flipped (TikZ grows upward)
    lines = []
    for y in range(new_h):
        for x in range(new_w):
            r, g, b = pixels[x, y]
            r_f = round(r / 255, 3)
            g_f = round(g / 255, 3)
            b_f = round(b / 255, 3)
            ty = new_h - 1 - y   # flip
            lines.append(
                f"  \\fill[fill={{rgb,1:red,{r_f};green,{g_f};blue,{b_f}}}] "
                f"({x},{ty}) rectangle ({x+1},{ty+1});"
            )
            done += 1
            if progress_cb and done % 200 == 0:
                progress_cb(done / total * 100)

    if progress_cb:
        progress_cb(100)

    tikz_body = "\n".join(lines)

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
    return latex, new_w, new_h


# ── GUI ───────────────────────────────────────────────────────────────────────

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Image → TikZ LaTeX Generator")
        self.root.geometry("660x540")
        self.root.resizable(False, False)
        self.root.configure(bg="#f7f6f2")

        self.image_path = tk.StringVar()
        self.save_path  = tk.StringVar()
        self.res_var    = tk.IntVar(value=64)

        self._build_style()
        self._build_ui()

    def _build_style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TLabel",      background="#f7f6f2", font=("Segoe UI", 10))
        s.configure("Sub.TLabel",  background="#f7f6f2", font=("Segoe UI", 9), foreground="#7a7974")
        s.configure("Head.TLabel", background="#f7f6f2", font=("Segoe UI", 14, "bold"), foreground="#01696f")
        s.configure("TEntry",      font=("Segoe UI", 10), padding=4)
        s.configure("TButton",     font=("Segoe UI", 10), padding=6)
        s.configure("TScale",      background="#f7f6f2")
        s.configure("Green.Horizontal.TProgressbar", troughcolor="#dcd9d5",
                    background="#01696f", thickness=10)
        s.configure("Primary.TButton", font=("Segoe UI", 11, "bold"),
                    foreground="white", background="#01696f")
        s.map("Primary.TButton", background=[("active", "#0c4e54"), ("disabled", "#bab9b4")])

    def _build_ui(self):
        P = dict(padx=28, pady=8)

        ttk.Label(self.root, text="🎨  Image → TikZ LaTeX Generator", style="Head.TLabel")\
            .pack(anchor="w", padx=28, pady=(22, 2))
        ttk.Label(self.root,
                  text="Converts any image to a self-contained .tex file using colored TikZ rectangles — no external image needed.",
                  style="Sub.TLabel", wraplength=600, justify="left")\
            .pack(anchor="w", padx=28, pady=(0, 14))

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=28)

        # Image path
        f1 = tk.Frame(self.root, bg="#f7f6f2"); f1.pack(fill="x", **P)
        ttk.Label(f1, text="Image File").pack(anchor="w")
        r1 = tk.Frame(f1, bg="#f7f6f2"); r1.pack(fill="x", pady=(4,0))
        ttk.Entry(r1, textvariable=self.image_path, width=54).pack(side="left", padx=(0,8))
        ttk.Button(r1, text="Browse…", command=self._pick_image).pack(side="left")

        # Save path
        f2 = tk.Frame(self.root, bg="#f7f6f2"); f2.pack(fill="x", **P)
        ttk.Label(f2, text="Save .tex File As").pack(anchor="w")
        r2 = tk.Frame(f2, bg="#f7f6f2"); r2.pack(fill="x", pady=(4,0))
        ttk.Entry(r2, textvariable=self.save_path, width=54).pack(side="left", padx=(0,8))
        ttk.Button(r2, text="Browse…", command=self._pick_save).pack(side="left")

        # Resolution slider
        f3 = tk.Frame(self.root, bg="#f7f6f2"); f3.pack(fill="x", **P)
        res_row = tk.Frame(f3, bg="#f7f6f2"); res_row.pack(fill="x")
        ttk.Label(res_row, text="Max Resolution (pixels along longest side)").pack(side="left")
        self.res_label = ttk.Label(res_row, text="64 px", style="Sub.TLabel")
        self.res_label.pack(side="right")

        slider = ttk.Scale(f3, from_=16, to=150, orient="horizontal",
                           variable=self.res_var, command=self._update_res_label)
        slider.pack(fill="x", pady=(6,0))

        # Quality warning
        self.warn_label = ttk.Label(f3,
            text="⚠  Higher values produce larger files and longer compile times.",
            style="Sub.TLabel")
        self.warn_label.pack(anchor="w", pady=(4,0))

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=28, pady=10)

        # Generate button
        self.gen_btn = ttk.Button(self.root, text="Generate TikZ File",
                                  style="Primary.TButton", command=self._start_generation)
        self.gen_btn.pack()

        # Progress bar
        self.progress = ttk.Progressbar(self.root, style="Green.Horizontal.TProgressbar",
                                        orient="horizontal", length=480, mode="determinate")
        self.progress.pack(pady=(14, 0))

        # Status bar
        self.status_var = tk.StringVar(value="Ready — select an image and output path.")
        tk.Label(self.root, textvariable=self.status_var,
                 bg="#e6e4df", fg="#28251d", font=("Segoe UI", 9),
                 anchor="w", padx=16, pady=6).pack(fill="x", side="bottom")

    def _update_res_label(self, _=None):
        v = self.res_var.get()
        self.res_label.config(text=f"{v} px")

    def _pick_image(self):
        path = filedialog.askopenfilename(
            title="Select an image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp"),
                       ("All files", "*.*")])
        if path:
            self.image_path.set(path)
            if not self.save_path.get():
                base = os.path.splitext(path)[0]
                self.save_path.set(base + "_tikz.tex")
            self.status_var.set(f"Image selected: {os.path.basename(path)}")

    def _pick_save(self):
        path = filedialog.asksaveasfilename(
            title="Save .tex file as",
            defaultextension=".tex",
            filetypes=[("LaTeX files", "*.tex"), ("All files", "*.*")])
        if path:
            self.save_path.set(path)
            self.status_var.set(f"Output path set: {os.path.basename(path)}")

    def _start_generation(self):
        img  = self.image_path.get().strip()
        out  = self.save_path.get().strip()
        res  = self.res_var.get()

        if not img:
            messagebox.showerror("Missing Input", "Please select an image file."); return
        if not os.path.isfile(img):
            messagebox.showerror("File Not Found", f"Image not found:\n{img}"); return
        if not out:
            messagebox.showerror("Missing Output", "Please specify a save path."); return

        self.gen_btn.state(["disabled"])
        self.progress["value"] = 0
        self.status_var.set("Converting… please wait.")
        threading.Thread(target=self._run, args=(img, out, res), daemon=True).start()

    def _run(self, img, out, res):
        def progress_cb(pct):
            self.progress["value"] = pct
            self.status_var.set(f"Converting… {pct:.0f}%")
            self.root.update_idletasks()

        try:
            latex, w, h = image_to_tikz(img, max_size=res, progress_cb=progress_cb)
            with open(out, "w", encoding="utf-8") as f:
                f.write(latex)

            self.root.after(0, self._done, out, w, h)
        except Exception as e:
            self.root.after(0, self._error, str(e))

    def _done(self, out, w, h):
        self.gen_btn.state(["!disabled"])
        self.progress["value"] = 100
        pixel_count = w * h
        self.status_var.set(f"✔  Done! {w}×{h} = {pixel_count:,} TikZ rectangles → {os.path.basename(out)}")
        messagebox.showinfo("Success! 🎉",
            f"TikZ file saved:\n{out}\n\n"
            f"Resolution used: {w}×{h} pixels ({pixel_count:,} colored rectangles)\n\n"
            "To compile to PDF run:\n"
            f"  pdflatex \"{os.path.basename(out)}\"\n\n"
            "⚠ Compile time grows with resolution.\n"
            "  64px is recommended for quick results.")

    def _error(self, msg):
        self.gen_btn.state(["!disabled"])
        self.status_var.set("Error during conversion.")
        messagebox.showerror("Conversion Error", f"Something went wrong:\n\n{msg}")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()