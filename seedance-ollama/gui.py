"""Desktop GUI for the Seedance Prompt Compiler.

Pick reference images, write a scene brief, choose models, generate a
Seedance 2.0 prompt via local Ollama models, and validate/save the result.
Run with: python gui.py
"""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import ollama

import seedance_ollama
import validate as validate_module

IMAGE_FILETYPES = [
    ("Images", "*.jpg *.jpeg *.png *.webp *.bmp"),
    ("All files", "*.*"),
]


def list_local_models():
    try:
        result = ollama.list()
        models = result.get("models", []) if isinstance(result, dict) else result.models
        names = []
        for m in models:
            name = m.get("model") if isinstance(m, dict) else getattr(m, "model", None)
            if name:
                names.append(name)
        return names
    except Exception:
        return []


class SeedanceGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Seedance Prompt Compiler")
        self.geometry("980x760")
        self.minsize(820, 600)

        self.image_paths = []
        self.guide_text = seedance_ollama.load_guide()

        self._build_layout()
        self._refresh_models()

    # ---------- UI construction ----------

    def _build_layout(self):
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(3, weight=1)

        # --- Left: images ---
        img_frame = ttk.LabelFrame(root, text="Reference Images (@image_1, @image_2, ...)")
        img_frame.grid(row=0, column=0, rowspan=3, sticky="nsew", padx=(0, 8), pady=(0, 8))
        img_frame.columnconfigure(0, weight=1)
        img_frame.rowconfigure(0, weight=1)

        self.image_listbox = tk.Listbox(img_frame, height=8, selectmode="extended")
        self.image_listbox.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        img_scroll = ttk.Scrollbar(img_frame, orient="vertical", command=self.image_listbox.yview)
        img_scroll.grid(row=0, column=1, sticky="ns", pady=6)
        self.image_listbox.configure(yscrollcommand=img_scroll.set)

        img_btns = ttk.Frame(img_frame)
        img_btns.grid(row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=(0, 6))
        ttk.Button(img_btns, text="Add...", command=self._add_images).pack(side="left")
        ttk.Button(img_btns, text="Remove Selected", command=self._remove_images).pack(side="left", padx=4)
        ttk.Button(img_btns, text="Move Up", command=lambda: self._move_image(-1)).pack(side="left", padx=4)
        ttk.Button(img_btns, text="Move Down", command=lambda: self._move_image(1)).pack(side="left", padx=4)

        # --- Right: settings ---
        settings = ttk.LabelFrame(root, text="Settings")
        settings.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 8))
        for c in range(2):
            settings.columnconfigure(c, weight=1)

        ttk.Label(settings, text="Duration (seconds):").grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.duration_var = tk.StringVar(value="15")
        ttk.Entry(settings, textvariable=self.duration_var, width=10).grid(row=0, column=1, sticky="w", padx=6, pady=4)

        self.single_model_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            settings, text="Single-model mode (skip two-stage pipeline)",
            variable=self.single_model_var, command=self._on_mode_toggle,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=6, pady=(4, 8))

        ttk.Label(settings, text="Vision model:").grid(row=2, column=0, sticky="w", padx=6, pady=4)
        self.vision_model_var = tk.StringVar(value=seedance_ollama.DEFAULT_VISION_MODEL)
        self.vision_combo = ttk.Combobox(settings, textvariable=self.vision_model_var, state="readonly")
        self.vision_combo.grid(row=2, column=1, sticky="ew", padx=6, pady=4)

        ttk.Label(settings, text="Writer model:").grid(row=3, column=0, sticky="w", padx=6, pady=4)
        self.writer_model_var = tk.StringVar(value=seedance_ollama.DEFAULT_WRITER_MODEL)
        self.writer_combo = ttk.Combobox(settings, textvariable=self.writer_model_var, state="readonly")
        self.writer_combo.grid(row=3, column=1, sticky="ew", padx=6, pady=4)

        ttk.Label(settings, text="Single model:").grid(row=4, column=0, sticky="w", padx=6, pady=4)
        self.single_model_name_var = tk.StringVar(value="")
        self.single_combo = ttk.Combobox(settings, textvariable=self.single_model_name_var, state="disabled")
        self.single_combo.grid(row=4, column=1, sticky="ew", padx=6, pady=4)

        ttk.Button(settings, text="Refresh model list", command=self._refresh_models).grid(
            row=5, column=0, columnspan=2, sticky="w", padx=6, pady=(4, 4)
        )

        # --- Brief ---
        brief_frame = ttk.LabelFrame(root, text="Scene Brief")
        brief_frame.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=(0, 8))
        brief_frame.columnconfigure(0, weight=1)
        brief_frame.rowconfigure(0, weight=1)
        self.brief_text = tk.Text(brief_frame, height=8, wrap="word")
        self.brief_text.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        # --- Actions ---
        actions = ttk.Frame(root)
        actions.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(0, 8))
        self.generate_btn = ttk.Button(actions, text="Generate Prompt", command=self._on_generate)
        self.generate_btn.pack(side="left")
        self.validate_btn = ttk.Button(actions, text="Validate", command=self._on_validate)
        self.validate_btn.pack(side="left", padx=6)
        ttk.Button(actions, text="Copy to Clipboard", command=self._on_copy).pack(side="left", padx=6)
        ttk.Button(actions, text="Save As...", command=self._on_save).pack(side="left", padx=6)

        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(actions, textvariable=self.status_var, foreground="#555").pack(side="left", padx=12)

        # --- Output ---
        out_frame = ttk.LabelFrame(root, text="Generated Prompt")
        out_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(0, 0))
        out_frame.columnconfigure(0, weight=1)
        out_frame.rowconfigure(0, weight=1)
        self.output_text = tk.Text(out_frame, wrap="word")
        self.output_text.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)
        out_scroll = ttk.Scrollbar(out_frame, orient="vertical", command=self.output_text.yview)
        out_scroll.grid(row=0, column=1, sticky="ns", pady=6)
        self.output_text.configure(yscrollcommand=out_scroll.set)

    # ---------- image list handling ----------

    def _add_images(self):
        paths = filedialog.askopenfilenames(title="Select reference images", filetypes=IMAGE_FILETYPES)
        for p in paths:
            self.image_paths.append(p)
        self._refresh_image_listbox()

    def _remove_images(self):
        selected = list(self.image_listbox.curselection())
        for i in reversed(selected):
            del self.image_paths[i]
        self._refresh_image_listbox()

    def _move_image(self, direction):
        selected = list(self.image_listbox.curselection())
        if len(selected) != 1:
            return
        i = selected[0]
        j = i + direction
        if 0 <= j < len(self.image_paths):
            self.image_paths[i], self.image_paths[j] = self.image_paths[j], self.image_paths[i]
            self._refresh_image_listbox()
            self.image_listbox.selection_set(j)

    def _refresh_image_listbox(self):
        self.image_listbox.delete(0, tk.END)
        for i, path in enumerate(self.image_paths, start=1):
            self.image_listbox.insert(tk.END, f"@image_{i}  {os.path.basename(path)}")

    # ---------- models ----------

    def _refresh_models(self):
        names = list_local_models()
        if not names:
            self.status_var.set("Could not reach Ollama, is it running?")
            return
        self.vision_combo["values"] = names
        self.writer_combo["values"] = names
        self.single_combo["values"] = names
        if self.vision_model_var.get() not in names and names:
            self.vision_model_var.set(names[0])
        if self.writer_model_var.get() not in names and names:
            self.writer_model_var.set(names[0])
        if not self.single_model_name_var.get() and names:
            self.single_model_name_var.set(names[0])
        self.status_var.set(f"Found {len(names)} local model(s).")

    def _on_mode_toggle(self):
        single = self.single_model_var.get()
        self.single_combo.configure(state="readonly" if single else "disabled")
        self.vision_combo.configure(state="disabled" if single else "readonly")
        self.writer_combo.configure(state="disabled" if single else "readonly")

    # ---------- generation ----------

    def _on_generate(self):
        brief = self.brief_text.get("1.0", tk.END).strip()
        if not brief:
            messagebox.showwarning("Missing brief", "Enter a scene brief first.")
            return
        try:
            duration = int(self.duration_var.get())
        except ValueError:
            messagebox.showwarning("Invalid duration", "Duration must be a whole number of seconds.")
            return

        self.generate_btn.configure(state="disabled")
        self.status_var.set("Generating... this can take a while on local models.")
        self.output_text.delete("1.0", tk.END)

        thread = threading.Thread(
            target=self._generate_worker,
            args=(list(self.image_paths), brief, duration),
            daemon=True,
        )
        thread.start()

    def _generate_worker(self, image_paths, brief, duration):
        try:
            single = self.single_model_var.get()
            if single:
                prompt = seedance_ollama.single_model_generate(
                    image_paths, brief, duration,
                    self.single_model_name_var.get(),
                    guide_text=self.guide_text,
                )
            else:
                descriptions = seedance_ollama.describe_images(
                    image_paths, vision_model=self.vision_model_var.get()
                )
                prompt = seedance_ollama.generate_prompt(
                    descriptions, brief, duration,
                    writer_model=self.writer_model_var.get(),
                    guide_text=self.guide_text,
                )
            self.after(0, self._on_generate_done, prompt, None)
        except Exception as exc:
            self.after(0, self._on_generate_done, None, exc)

    def _on_generate_done(self, prompt, error):
        self.generate_btn.configure(state="normal")
        if error is not None:
            self.status_var.set("Generation failed.")
            messagebox.showerror("Generation failed", str(error))
            return
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", prompt)
        self.status_var.set("Done.")

    # ---------- validate / copy / save ----------

    def _on_validate(self):
        prompt = self.output_text.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showinfo("Nothing to validate", "Generate a prompt first.")
            return
        try:
            duration = int(self.duration_var.get())
        except ValueError:
            duration = None
        issues = validate_module.validate(prompt, duration)
        if not issues:
            messagebox.showinfo("Validation", "OK: prompt passed all structural checks.")
        else:
            messagebox.showwarning(
                "Validation issues",
                f"{len(issues)} issue(s):\n\n" + "\n".join(f"- {i}" for i in issues),
            )

    def _on_copy(self):
        prompt = self.output_text.get("1.0", tk.END).strip()
        if not prompt:
            return
        self.clipboard_clear()
        self.clipboard_append(prompt)
        self.status_var.set("Copied to clipboard.")

    def _on_save(self):
        prompt = self.output_text.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showinfo("Nothing to save", "Generate a prompt first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(prompt)
        self.status_var.set(f"Saved to {path}")


def main():
    app = SeedanceGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
