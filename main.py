from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from PIL import Image, ImageDraw, ImageFont, ImageStat

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".bmp",
    ".gif",
    ".tif",
    ".tiff",
    ".webp",
}


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size=size)
    except OSError:
        return ImageFont.load_default()


def text_size(
    text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont
) -> tuple[int, int]:
    probe = Image.new("RGB", (10, 10), "white")
    draw = ImageDraw.Draw(probe)
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def pick_contrasting_text_color(
    img: Image.Image, x: int, y: int, w: int, h: int, pad: int
) -> tuple[int, int, int]:
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(img.width, x + w + pad)
    y1 = min(img.height, y + h + pad)
    region = img.crop((x0, y0, x1, y1))
    mean = ImageStat.Stat(region).mean
    r, g, b = mean[:3]
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return (0, 0, 0) if luminance > 140 else (255, 255, 255)


def collect_images_from_folder(folder: Path) -> list[Path]:
    return sorted(
        [
            p
            for p in folder.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
    )


def output_path_for(source_path: Path, output_dir: Path) -> Path:
    base = output_dir / f"{source_path.stem}_labeled{source_path.suffix}"
    if not base.exists():
        return base

    index = 1
    while True:
        candidate = output_dir / (
            f"{source_path.stem}_labeled_{index}{source_path.suffix}"
        )
        if not candidate.exists():
            return candidate
        index += 1


def draw_labeled_image(img: Image.Image, label: str, placement: str) -> Image.Image:
    working = img.convert("RGB")
    padding = max(8, int(working.height * 0.015))

    font_size = max(14, int(min(working.width, working.height) * 0.06))
    font = load_font(font_size)
    label_w, label_h = text_size(label, font)

    max_text_width = max(1, working.width - (padding * 2))
    while label_w > max_text_width and font_size > 10:
        font_size -= 2
        font = load_font(font_size)
        label_w, label_h = text_size(label, font)

    x = max(padding, (working.width - label_w) // 2)

    if placement == "overlay_top":
        y = padding
        color = pick_contrasting_text_color(working, x, y, label_w, label_h, padding)
        outline = (0, 0, 0) if color == (255, 255, 255) else (255, 255, 255)
        stroke_width = max(1, font_size // 14)
        draw = ImageDraw.Draw(working)
        draw.text(
            (x, y),
            label,
            fill=color,
            font=font,
            stroke_width=stroke_width,
            stroke_fill=outline,
        )
        return working

    if placement == "overlay_bottom":
        y = max(padding, working.height - label_h - padding)
        color = pick_contrasting_text_color(working, x, y, label_w, label_h, padding)
        outline = (0, 0, 0) if color == (255, 255, 255) else (255, 255, 255)
        stroke_width = max(1, font_size // 14)
        draw = ImageDraw.Draw(working)
        draw.text(
            (x, y),
            label,
            fill=color,
            font=font,
            stroke_width=stroke_width,
            stroke_fill=outline,
        )
        return working

    label_band_h = label_h + (padding * 2)
    result = Image.new("RGB", (working.width, working.height + label_band_h), "white")
    draw = ImageDraw.Draw(result)

    if placement == "append_top":
        result.paste(working, (0, label_band_h))
        draw.text((x, padding), label, fill="black", font=font)
        return result

    if placement == "append_bottom":
        result.paste(working, (0, 0))
        draw.text((x, working.height + padding), label, fill="black", font=font)
        return result

    raise ValueError(f"Unsupported placement: {placement}")


def process_image(path: Path, label: str, placement: str, output_dir: Path) -> Path:
    with Image.open(path) as img:
        rendered = draw_labeled_image(img, label, placement)
        output = output_path_for(path, output_dir)
        save_kwargs = (
            {"quality": 95} if path.suffix.lower() in {".jpg", ".jpeg"} else {}
        )
        rendered.save(output, **save_kwargs)
    return output


class ImageClassifierApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Image Classifier Tool")
        self.root.geometry("500x400")
        self.root.resizable(False, False)

        self.image_paths: list[Path] = []
        self.label_text: str = ""
        self.placement: str = ""
        self.output_dir: Path | None = None

        self.state = "select_images"
        self.draw_ui()

    def clear_ui(self) -> None:
        for widget in self.root.winfo_children():
            widget.destroy()

    def draw_ui(self) -> None:
        self.clear_ui()

        if self.state == "select_images":
            self.draw_select_images()
        elif self.state == "enter_label":
            self.draw_enter_label()
        elif self.state == "choose_placement":
            self.draw_choose_placement()
        elif self.state == "choose_output":
            self.draw_choose_output()
        elif self.state == "processing":
            self.draw_processing()

    def draw_select_images(self) -> None:
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame, text="Step 1: Choose Image Source", font=("Arial", 14, "bold")
        ).pack(anchor="w", pady=(0, 16))

        tk.Button(
            frame,
            text="Select image files",
            width=40,
            height=2,
            command=self.on_select_files,
        ).pack(fill="x", pady=8)

        tk.Button(
            frame,
            text="Select folder of images",
            width=40,
            height=2,
            command=self.on_select_folder,
        ).pack(fill="x", pady=8)

        tk.Button(
            frame, text="Exit", width=40, height=2, command=self.root.destroy
        ).pack(fill="x", pady=8)

    def on_select_files(self) -> None:
        files = filedialog.askopenfilenames(
            title="Select Image Files",
            filetypes=[
                ("Image Files", "*.jpg *.jpeg *.png *.bmp *.gif *.tif *.tiff *.webp")
            ],
        )
        if files:
            self.image_paths = [Path(f) for f in files]
            self.state = "enter_label"
            self.draw_ui()

    def on_select_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select Folder of Images")
        if folder:
            self.image_paths = collect_images_from_folder(Path(folder))
            if not self.image_paths:
                messagebox.showwarning(
                    "No Images", "No image files found in selected folder."
                )
                return
            self.state = "enter_label"
            self.draw_ui()

    def draw_enter_label(self) -> None:
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame,
            text=f"Step 2: Enter Classification Label\n({len(self.image_paths)} image(s) selected)",
            font=("Arial", 14, "bold"),
        ).pack(anchor="w", pady=(0, 16))

        tk.Label(frame, text="Label:").pack(anchor="w")
        entry = tk.Entry(frame, font=("Arial", 12), width=40)
        entry.pack(fill="x", pady=(4, 16))
        entry.focus()

        def on_next() -> None:
            text = entry.get().strip()
            if not text:
                messagebox.showwarning("Empty Label", "Please enter a label.")
                return
            self.label_text = text
            self.state = "choose_placement"
            self.draw_ui()

        tk.Button(
            frame,
            text="Next",
            width=40,
            height=2,
            command=on_next,
        ).pack(fill="x", pady=8)

        tk.Button(frame, text="Back", width=40, height=2, command=self.go_back).pack(
            fill="x", pady=8
        )

    def draw_choose_placement(self) -> None:
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame, text="Step 3: Choose Label Placement", font=("Arial", 14, "bold")
        ).pack(anchor="w", pady=(0, 16))

        def set_placement(p: str) -> None:
            self.placement = p
            self.state = "choose_output"
            self.draw_ui()

        tk.Button(
            frame,
            text="Overlay at top",
            width=40,
            height=2,
            command=lambda: set_placement("overlay_top"),
        ).pack(fill="x", pady=4)

        tk.Button(
            frame,
            text="Overlay at bottom",
            width=40,
            height=2,
            command=lambda: set_placement("overlay_bottom"),
        ).pack(fill="x", pady=4)

        tk.Button(
            frame,
            text="Append at top",
            width=40,
            height=2,
            command=lambda: set_placement("append_top"),
        ).pack(fill="x", pady=4)

        tk.Button(
            frame,
            text="Append at bottom",
            width=40,
            height=2,
            command=lambda: set_placement("append_bottom"),
        ).pack(fill="x", pady=4)

        tk.Button(frame, text="Back", width=40, height=1, command=self.go_back).pack(
            fill="x", pady=8
        )

    def draw_choose_output(self) -> None:
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame, text="Step 4: Choose Output Folder", font=("Arial", 14, "bold")
        ).pack(anchor="w", pady=(0, 16))

        if self.output_dir:
            tk.Label(frame, text=f"Selected: {self.output_dir}", wraplength=400).pack(
                anchor="w", pady=(0, 16)
            )

        def on_browse() -> None:
            folder = filedialog.askdirectory(
                title="Select Output Folder",
                initialdir=str(self.image_paths[0].parent) if self.image_paths else "",
            )
            if folder:
                self.output_dir = Path(folder)
                self.clear_ui()
                self.draw_choose_output()

        tk.Button(frame, text="Browse", width=40, height=2, command=on_browse).pack(
            fill="x", pady=8
        )

        tk.Button(
            frame,
            text="Process Images",
            width=40,
            height=2,
            state="disabled" if not self.output_dir else "normal",
            command=self.on_process,
        ).pack(fill="x", pady=8)

        tk.Button(frame, text="Back", width=40, height=1, command=self.go_back).pack(
            fill="x", pady=8
        )

    def on_process(self) -> None:
        self.state = "processing"
        self.draw_ui()
        self.root.update()

        success = 0
        failures: list[str] = []

        for path in self.image_paths:
            try:
                process_image(path, self.label_text, self.placement, self.output_dir)
                success += 1
            except Exception as exc:
                failures.append(f"{path.name}: {exc}")

        summary_lines = [f"Processed: {success}/{len(self.image_paths)} image(s)"]
        summary_lines.append(f"Output folder: {self.output_dir}")
        if failures:
            summary_lines.append("\nFailed:")
            summary_lines.extend(failures)
        summary = "\n".join(summary_lines)

        messagebox.showinfo("Complete", summary)
        self.state = "select_images"
        self.image_paths = []
        self.label_text = ""
        self.placement = ""
        self.output_dir = None
        self.draw_ui()

    def draw_processing(self) -> None:
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame,
            text="Processing images...\nPlease wait.",
            font=("Arial", 14),
            justify="center",
        ).pack(expand=True)

    def go_back(self) -> None:
        if self.state == "enter_label":
            self.state = "select_images"
        elif self.state == "choose_placement":
            self.state = "enter_label"
        elif self.state == "choose_output":
            self.state = "choose_placement"
        self.draw_ui()


def main() -> None:
    root = tk.Tk()
    app = ImageClassifierApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
