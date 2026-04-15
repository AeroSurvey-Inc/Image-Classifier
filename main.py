"""Tkinter-based image classification labeler with configurable placement options."""

from __future__ import annotations

import sys
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox

from PIL import ExifTags, Image, ImageDraw, ImageFont, ImageStat

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

PRESET_LABELS = [
    "CUI",
    "FOUO PROPRIETARY",
    "PROPRIETARY",
    "UNCLASSIFIED",
    "UNCLASSIFIED FOUO",
    "UNCLASSIFIED PROPRIETARY",
]

APP_ICON_FILE = "aerosurvey-mark-8-icon.ico"
EXIF_TIMESTAMP_TAGS = [
    tag
    for tag, name in ExifTags.TAGS.items()
    if name in {"DateTimeOriginal", "DateTimeDigitized", "DateTime"}
]


@dataclass(slots=True)
class TimestampOptions:
    """User-selected configuration for optional timestamp rendering."""

    enabled: bool = False
    source: str = "exif"
    placement_mode: str = "overlay"
    manual_text: str = ""


def resource_path(relative_name: str) -> Path:
    """Return an absolute path for a bundled resource.

    Args:
        relative_name: Resource path relative to the application root.

    Returns:
        Absolute path to the requested resource in source or bundled mode.
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_name
    return Path(__file__).resolve().parent / relative_name


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a font for drawing text on output images.

    Args:
        size: Requested font size in pixels.

    Returns:
        Loaded Arial font when available, otherwise Pillow's default font.
    """
    try:
        return ImageFont.truetype("arial.ttf", size=size)
    except OSError:
        return ImageFont.load_default()


def text_size(
    text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont
) -> tuple[int, int]:
    """Measure rendered text dimensions for a font.

    Args:
        text: Text to measure.
        font: Font used to render the text.

    Returns:
        Tuple of rendered width and height in pixels.
    """
    probe = Image.new("RGB", (10, 10), "white")
    draw = ImageDraw.Draw(probe)
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def pick_contrasting_text_color(
    img: Image.Image, x: int, y: int, w: int, h: int, pad: int
) -> tuple[int, int, int]:
    """Choose black or white text based on nearby image luminance.

    Args:
        img: Source image containing the target draw region.
        x: Left coordinate of the text region.
        y: Top coordinate of the text region.
        w: Width of the text region.
        h: Height of the text region.
        pad: Extra padding around the text region used for sampling.

    Returns:
        RGB color tuple for black or white text.
    """
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(img.width, x + w + pad)
    y1 = min(img.height, y + h + pad)
    region = img.crop((x0, y0, x1, y1))
    mean = ImageStat.Stat(region).mean
    r, g, b = mean[:3]
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return (0, 0, 0) if luminance > 140 else (255, 255, 255)


def fit_text(
    img: Image.Image,
    text: str,
    *,
    scale: float,
    min_size: int = 10,
    max_width: int | None = None,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, int, int, int]:
    """Fit text within the available width for an image.

    Args:
        img: Image that determines scaling and width limits.
        text: Text to fit.
        scale: Relative font scale based on the image dimensions.
        min_size: Smallest font size allowed during shrink-to-fit.
        max_width: Optional explicit maximum text width in pixels.

    Returns:
        Tuple containing the fitted font, text width, text height, and font size.
    """
    padding = max(8, int(img.height * 0.015))
    available_width = max_width or max(1, img.width - (padding * 2))
    font_size = max(min_size, int(min(img.width, img.height) * scale))
    font = load_font(font_size)
    text_w, text_h = text_size(text, font)

    while text_w > available_width and font_size > min_size:
        font_size -= 2
        font = load_font(font_size)
        text_w, text_h = text_size(text, font)

    return font, text_w, text_h, font_size


def rects_overlap(
    first: tuple[int, int, int, int],
    second: tuple[int, int, int, int],
    margin: int = 6,
) -> bool:
    """Check whether two rectangles overlap after adding margin.

    Args:
        first: First rectangle as x, y, width, height.
        second: Second rectangle as x, y, width, height.
        margin: Extra separation margin to treat as overlap.

    Returns:
        True when the rectangles overlap within the requested margin.
    """
    first_x, first_y, first_w, first_h = first
    second_x, second_y, second_w, second_h = second
    return not (
        first_x + first_w + margin <= second_x
        or second_x + second_w + margin <= first_x
        or first_y + first_h + margin <= second_y
        or second_y + second_h + margin <= first_y
    )


def format_exif_timestamp(raw_value: str) -> str:
    """Normalize an EXIF timestamp string for display.

    Args:
        raw_value: Raw EXIF timestamp string.

    Returns:
        Normalized timestamp string when the EXIF format is recognized.
    """
    if len(raw_value) >= 19 and raw_value[4] == ":" and raw_value[7] == ":":
        return raw_value[:10].replace(":", "-") + raw_value[10:]
    return raw_value


def read_exif_timestamp(img: Image.Image) -> str | None:
    """Read the first supported EXIF timestamp field from an image.

    Args:
        img: Source image to inspect for EXIF metadata.

    Returns:
        Normalized timestamp string when EXIF data is available, otherwise None.
    """
    exif = img.getexif()
    if not exif:
        return None

    for tag in EXIF_TIMESTAMP_TAGS:
        value = exif.get(tag)
        if not value:
            continue
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="ignore")
        timestamp = str(value).strip()
        if timestamp:
            return format_exif_timestamp(timestamp)
    return None


def resolve_timestamp_text(
    img: Image.Image, source_path: Path, options: TimestampOptions
) -> str | None:
    """Resolve the timestamp text to render for an image.

    Args:
        img: Source image used when reading EXIF timestamps.
        source_path: Original image path used in error messages.
        options: User-selected timestamp configuration.

    Returns:
        Timestamp text to render, or None when timestamping is disabled.

    Raises:
        ValueError: If EXIF timestamp mode is enabled and no supported EXIF
            timestamp is found.
    """
    if not options.enabled:
        return None
    if options.source == "manual":
        text = options.manual_text.strip()
        return text or None

    timestamp = read_exif_timestamp(img)
    if timestamp:
        return timestamp
    raise ValueError(f"No EXIF timestamp found for {source_path.name}")


def overlay_text_y(
    img_height: int, text_height: int, padding: int, placement: str, font_size: int
) -> int:
    """Return the vertical draw position for overlay text.

    Args:
        img_height: Height of the image being drawn on.
        text_height: Measured text height in pixels.
        padding: Base edge padding.
        placement: Overlay position identifier.
        font_size: Effective font size used for drawing.

    Returns:
        Vertical pixel coordinate for the text baseline region.

    Raises:
        ValueError: If the placement is not a supported overlay mode.
    """
    if placement == "overlay_top":
        return padding
    if placement == "overlay_bottom":
        bottom_inset = padding + max(4, font_size // 6)
        return max(padding, img_height - text_height - bottom_inset)
    raise ValueError(f"Unsupported overlay placement: {placement}")


def draw_text_with_placement(
    img: Image.Image,
    text: str,
    placement: str,
    *,
    scale: float,
    horizontal_align: str = "center",
) -> tuple[Image.Image, tuple[int, int, int, int], int]:
    """Draw text onto an image using a named placement mode.

    Args:
        img: Source image to draw onto.
        text: Text to render.
        placement: Placement mode such as overlay or append.
        scale: Relative font scale based on the image dimensions.
        horizontal_align: Horizontal alignment for the rendered text.

    Returns:
        Tuple containing the rendered image, occupied text bounds, and vertical
        shift applied to previously tracked regions when a band is appended above
        the image.

    Raises:
        ValueError: If the placement or horizontal alignment is unsupported.
    """
    working = img.convert("RGB")
    padding = max(8, int(working.height * 0.015))
    font, text_w, text_h, font_size = fit_text(working, text, scale=scale)

    if horizontal_align == "center":
        x = max(padding, (working.width - text_w) // 2)
    elif horizontal_align == "right":
        x = max(padding, working.width - text_w - padding)
    elif horizontal_align == "left":
        x = padding
    else:
        raise ValueError(f"Unsupported horizontal alignment: {horizontal_align}")

    if placement == "overlay_top":
        y = overlay_text_y(working.height, text_h, padding, placement, font_size)
        color = pick_contrasting_text_color(working, x, y, text_w, text_h, padding)
        outline = (0, 0, 0) if color == (255, 255, 255) else (255, 255, 255)
        stroke_width = max(1, font_size // 14)
        draw = ImageDraw.Draw(working)
        draw.text(
            (x, y),
            text,
            fill=color,
            font=font,
            stroke_width=stroke_width,
            stroke_fill=outline,
        )
        return working, (x, y, text_w, text_h), 0

    if placement == "overlay_bottom":
        y = overlay_text_y(working.height, text_h, padding, placement, font_size)
        color = pick_contrasting_text_color(working, x, y, text_w, text_h, padding)
        outline = (0, 0, 0) if color == (255, 255, 255) else (255, 255, 255)
        stroke_width = max(1, font_size // 14)
        draw = ImageDraw.Draw(working)
        draw.text(
            (x, y),
            text,
            fill=color,
            font=font,
            stroke_width=stroke_width,
            stroke_fill=outline,
        )
        return working, (x, y, text_w, text_h), 0

    band_h = text_h + (padding * 2)
    result = Image.new("RGB", (working.width, working.height + band_h), "white")
    draw = ImageDraw.Draw(result)

    if placement == "append_top":
        result.paste(working, (0, band_h))
        y = padding
        draw.text((x, y), text, fill="black", font=font)
        return result, (x, y, text_w, text_h), band_h

    if placement == "append_bottom":
        result.paste(working, (0, 0))
        y = working.height + padding
        draw.text((x, y), text, fill="black", font=font)
        return result, (x, y, text_w, text_h), 0

    raise ValueError(f"Unsupported placement: {placement}")


def collect_images_from_folder(folder: Path) -> list[Path]:
    """Recursively collect supported image files from a folder.

    Args:
        folder: Root folder to scan.

    Returns:
        Sorted list of supported image paths.
    """
    return sorted(
        [
            p
            for p in folder.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
    )


def output_path_for(source_path: Path, output_dir: Path) -> Path:
    """Build a non-conflicting output path in the target directory.

    Args:
        source_path: Original source image path.
        output_dir: Destination directory for processed images.

    Returns:
        First available output path using the labeled filename pattern.
    """
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


def choose_timestamp_overlay_placement(
    img: Image.Image,
    timestamp: str,
    occupied_regions: list[tuple[int, int, int, int]],
) -> tuple[str, str]:
    """Choose an overlay position for the timestamp that avoids label bounds.

    Args:
        img: Image that will receive the timestamp.
        timestamp: Timestamp text that needs placement.
        occupied_regions: Existing text regions to avoid.

    Returns:
        Tuple of placement mode and horizontal alignment.
    """
    padding = max(8, int(img.height * 0.015))
    _, text_w, text_h, _ = fit_text(img, timestamp, scale=0.035, min_size=10)
    candidates = [
        ("overlay_bottom", "right"),
        ("overlay_top", "right"),
        ("overlay_bottom", "left"),
        ("overlay_top", "left"),
    ]

    for placement, align in candidates:
        x = padding if align == "left" else max(padding, img.width - text_w - padding)
        font_size = max(10, int(min(img.width, img.height) * 0.035))
        y = overlay_text_y(img.height, text_h, padding, placement, font_size)
        candidate_box = (x, y, text_w, text_h)
        if not any(rects_overlap(candidate_box, box) for box in occupied_regions):
            return placement, align

    return candidates[0]


def process_image(
    path: Path,
    label: str,
    placements: list[str],
    output_dir: Path,
    timestamp_options: TimestampOptions,
) -> Path:
    """Process one image and save the labeled result.

    Args:
        path: Source image path.
        label: Classification label text.
        placements: Ordered list of label placement modes to apply.
        output_dir: Destination directory for the processed image.
        timestamp_options: Timestamp rendering configuration.

    Returns:
        Output path for the saved image.

    Raises:
        ValueError: If timestamp EXIF mode is enabled but no EXIF timestamp is
            available, or if a placement helper receives an unsupported mode.
        OSError: If Pillow cannot read or save the image.
    """
    with Image.open(path) as img:
        rendered = img.convert("RGB")
        occupied_regions: list[tuple[int, int, int, int]] = []
        for placement in placements:
            rendered, bounds, shift = draw_text_with_placement(
                rendered,
                label,
                placement,
                scale=0.06,
            )
            if shift:
                occupied_regions = [
                    (x, y + shift, w, h) for x, y, w, h in occupied_regions
                ]
            occupied_regions.append(bounds)

        timestamp_text = resolve_timestamp_text(img, path, timestamp_options)
        if timestamp_text:
            if timestamp_options.placement_mode == "append":
                rendered, _, _ = draw_text_with_placement(
                    rendered,
                    timestamp_text,
                    "append_bottom",
                    scale=0.035,
                    horizontal_align="right",
                )
            else:
                placement, align = choose_timestamp_overlay_placement(
                    rendered,
                    timestamp_text,
                    occupied_regions,
                )
                rendered, _, _ = draw_text_with_placement(
                    rendered,
                    timestamp_text,
                    placement,
                    scale=0.035,
                    horizontal_align=align,
                )

        output = output_path_for(path, output_dir)
        save_kwargs = (
            {"quality": 95} if path.suffix.lower() in {".jpg", ".jpeg"} else {}
        )
        rendered.save(output, **save_kwargs)
    return output


class ImageClassifierApp:
    """State-driven Tkinter UI for selecting images, labels, and output settings."""

    def __init__(self, root: tk.Tk):
        """Initialize the application window and state.

        Args:
            root: Tk root window for the application.

        Returns:
            None.
        """
        self.root = root
        self.root.title("Image Classifier Tool")
        self.root.geometry("560x640")
        self.root.resizable(False, False)

        icon_path = resource_path(APP_ICON_FILE)
        if icon_path.exists():
            try:
                self.root.iconbitmap(default=str(icon_path))
            except tk.TclError:
                pass

        self.image_paths: list[Path] = []
        self.label_text: str = ""
        self.placements: list[str] = []
        self.output_dir: Path | None = None
        self.timestamp_options = TimestampOptions()

        self.state = "select_images"
        self.draw_ui()

    def clear_ui(self) -> None:
        """Remove all widgets from the root window.

        Returns:
            None.
        """
        for widget in self.root.winfo_children():
            widget.destroy()

    def draw_ui(self) -> None:
        """Render the screen for the current application state.

        Returns:
            None.
        """
        self.clear_ui()

        if self.state == "select_images":
            self.draw_select_images()
        elif self.state == "enter_label":
            self.draw_enter_label()
        elif self.state == "choose_placement":
            self.draw_choose_placement()
        elif self.state == "choose_timestamp":
            self.draw_choose_timestamp()
        elif self.state == "choose_output":
            self.draw_choose_output()
        elif self.state == "processing":
            self.draw_processing()

    def draw_select_images(self) -> None:
        """Render the image source selection screen.

        Returns:
            None.
        """
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
        """Handle file selection and advance to label entry.

        Returns:
            None.
        """
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
        """Handle folder selection and collect supported images.

        Returns:
            None.
        """
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
        """Render the classification label entry screen.

        Returns:
            None.
        """
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame,
            text=f"Step 2: Enter Classification Label\n({len(self.image_paths)} image(s) selected)",
            font=("Arial", 14, "bold"),
        ).pack(anchor="w", pady=(0, 16))

        tk.Label(frame, text="Preset labels:").pack(anchor="w")

        preset_frame = tk.Frame(frame)
        preset_frame.pack(fill="x", pady=(4, 12))

        tk.Label(frame, text="Label:").pack(anchor="w")
        entry = tk.Entry(frame, font=("Arial", 12), width=40)
        entry.pack(fill="x", pady=(4, 16))
        if self.label_text:
            entry.insert(0, self.label_text)
        entry.focus()

        def use_preset(label: str) -> None:
            """Populate the label entry field with a preset value.

            Args:
                label: Preset label text to insert into the entry widget.

            Returns:
                None.
            """
            entry.delete(0, tk.END)
            entry.insert(0, label)
            entry.focus()

        for index, label in enumerate(PRESET_LABELS):
            tk.Button(
                preset_frame,
                text=label,
                width=24,
                command=lambda value=label: use_preset(value),
            ).grid(row=index // 2, column=index % 2, padx=4, pady=4, sticky="ew")

        preset_frame.grid_columnconfigure(0, weight=1)
        preset_frame.grid_columnconfigure(1, weight=1)

        def on_next() -> None:
            """Validate the label and advance to placement selection.

            Returns:
                None.
            """
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
        """Render the label placement selection screen.

        Returns:
            None.
        """
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame,
            text="Step 3: Choose Label Placement(s)",
            font=("Arial", 14, "bold"),
        ).pack(anchor="w", pady=(0, 16))

        placement_options = [
            ("overlay_top", "Overlay at top"),
            ("overlay_bottom", "Overlay at bottom"),
            ("append_top", "Append at top"),
            ("append_bottom", "Append at bottom"),
        ]

        selected_vars: dict[str, tk.BooleanVar] = {}
        selected_set = set(self.placements)

        for key, label in placement_options:
            var = tk.BooleanVar(value=key in selected_set)
            selected_vars[key] = var
            tk.Checkbutton(
                frame,
                text=label,
                variable=var,
                anchor="w",
                font=("Arial", 11),
            ).pack(fill="x", pady=2)

        def on_next() -> None:
            """Validate placement selection and advance to timestamp options.

            Returns:
                None.
            """
            chosen = [key for key, _ in placement_options if selected_vars[key].get()]
            if not chosen:
                messagebox.showwarning(
                    "No Placement Selected",
                    "Please select at least one placement option.",
                )
                return
            self.placements = chosen
            self.state = "choose_timestamp"
            self.draw_ui()

        tk.Button(
            frame,
            text="Next",
            width=40,
            height=2,
            command=on_next,
        ).pack(fill="x", pady=8)

        tk.Button(frame, text="Back", width=40, height=1, command=self.go_back).pack(
            fill="x", pady=8
        )

    def draw_choose_timestamp(self) -> None:
        """Render the optional timestamp configuration screen.

        Returns:
            None.
        """
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame,
            text="Step 4: Timestamp Options",
            font=("Arial", 14, "bold"),
        ).pack(anchor="w", pady=(0, 16))

        enabled_var = tk.BooleanVar(value=self.timestamp_options.enabled)
        source_var = tk.StringVar(value=self.timestamp_options.source)
        placement_var = tk.StringVar(value=self.timestamp_options.placement_mode)

        tk.Checkbutton(
            frame,
            text="Add timestamp after classifier label(s)",
            variable=enabled_var,
            anchor="w",
            font=("Arial", 11),
        ).pack(fill="x", pady=(0, 12))

        source_frame = tk.LabelFrame(frame, text="Timestamp source", padx=12, pady=12)
        source_frame.pack(fill="x", pady=(0, 12))

        tk.Radiobutton(
            source_frame,
            text="Use EXIF timestamp",
            variable=source_var,
            value="exif",
            anchor="w",
        ).pack(fill="x", pady=2)
        tk.Radiobutton(
            source_frame,
            text="Type timestamp manually",
            variable=source_var,
            value="manual",
            anchor="w",
        ).pack(fill="x", pady=2)

        tk.Label(source_frame, text="Manual timestamp:").pack(anchor="w", pady=(8, 0))
        manual_entry = tk.Entry(frame, font=("Arial", 12), width=40)
        manual_entry.pack(fill="x", pady=(4, 12))
        if self.timestamp_options.manual_text:
            manual_entry.insert(0, self.timestamp_options.manual_text)

        placement_frame = tk.LabelFrame(
            frame,
            text="Timestamp rendering",
            padx=12,
            pady=12,
        )
        placement_frame.pack(fill="x", pady=(0, 12))

        tk.Radiobutton(
            placement_frame,
            text="Overlay on image",
            variable=placement_var,
            value="overlay",
            anchor="w",
        ).pack(fill="x", pady=2)
        tk.Radiobutton(
            placement_frame,
            text="Append below image",
            variable=placement_var,
            value="append",
            anchor="w",
        ).pack(fill="x", pady=2)

        help_text = (
            "Overlay timestamps are placed in a corner that avoids the classifier label. "
            "Appended timestamps are added below the labeled image."
        )
        tk.Label(frame, text=help_text, justify="left", wraplength=460).pack(
            anchor="w", pady=(0, 16)
        )

        def refresh_controls() -> None:
            """Update timestamp control enabled states.

            Returns:
                None.
            """
            enabled = enabled_var.get()
            source_state = "normal" if enabled else "disabled"
            placement_state = "normal" if enabled else "disabled"
            manual_state = (
                "normal" if enabled and source_var.get() == "manual" else "disabled"
            )

            for widget in source_frame.winfo_children():
                widget.configure(state=source_state)
            for widget in placement_frame.winfo_children():
                widget.configure(state=placement_state)
            manual_entry.configure(state=manual_state)

        enabled_var.trace_add("write", lambda *_: refresh_controls())
        source_var.trace_add("write", lambda *_: refresh_controls())
        refresh_controls()

        def on_next() -> None:
            """Validate timestamp settings and advance to output selection.

            Returns:
                None.
            """
            manual_text = manual_entry.get().strip()
            if enabled_var.get() and source_var.get() == "manual" and not manual_text:
                messagebox.showwarning(
                    "Missing Timestamp",
                    "Please enter a manual timestamp or disable timestamping.",
                )
                return

            self.timestamp_options = TimestampOptions(
                enabled=enabled_var.get(),
                source=source_var.get(),
                placement_mode=placement_var.get(),
                manual_text=manual_text,
            )
            self.state = "choose_output"
            self.draw_ui()

        tk.Button(
            frame,
            text="Next",
            width=40,
            height=2,
            command=on_next,
        ).pack(fill="x", pady=8)

        tk.Button(frame, text="Back", width=40, height=1, command=self.go_back).pack(
            fill="x", pady=8
        )

    def draw_choose_output(self) -> None:
        """Render the output folder selection screen.

        Returns:
            None.
        """
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame, text="Step 5: Choose Output Folder", font=("Arial", 14, "bold")
        ).pack(anchor="w", pady=(0, 16))

        if self.output_dir:
            tk.Label(frame, text=f"Selected: {self.output_dir}", wraplength=400).pack(
                anchor="w", pady=(0, 16)
            )

        def on_browse() -> None:
            """Open the folder picker and store the chosen output directory.

            Returns:
                None.
            """
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
        """Process selected images and show a completion summary.

        Returns:
            None.
        """
        self.state = "processing"
        self.draw_ui()
        self.root.update()

        success = 0
        failures: list[str] = []

        for path in self.image_paths:
            try:
                process_image(
                    path,
                    self.label_text,
                    self.placements,
                    self.output_dir,
                    self.timestamp_options,
                )
                success += 1
            except Exception as exc:
                failures.append(f"{path.name}: {exc}")

        summary_lines = [f"Processed: {success}/{len(self.image_paths)} image(s)"]
        summary_lines.append(f"Placements per image: {len(self.placements)}")
        if self.timestamp_options.enabled:
            source_label = (
                "EXIF" if self.timestamp_options.source == "exif" else "Manual"
            )
            mode_label = self.timestamp_options.placement_mode.capitalize()
            summary_lines.append(f"Timestamp: {source_label} ({mode_label})")
        summary_lines.append(f"Outputs created: {success}")
        summary_lines.append(f"Output folder: {self.output_dir}")
        if failures:
            summary_lines.append("\nFailed:")
            summary_lines.extend(failures)
        summary = "\n".join(summary_lines)

        messagebox.showinfo("Complete", summary)
        self.state = "select_images"
        self.image_paths = []
        self.label_text = ""
        self.placements = []
        self.output_dir = None
        self.timestamp_options = TimestampOptions()
        self.draw_ui()

    def draw_processing(self) -> None:
        """Render the processing progress screen.

        Returns:
            None.
        """
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(fill="both", expand=True)

        tk.Label(
            frame,
            text="Processing images...\nPlease wait.",
            font=("Arial", 14),
            justify="center",
        ).pack(expand=True)

    def go_back(self) -> None:
        """Navigate to the previous screen in the workflow.

        Returns:
            None.
        """
        if self.state == "enter_label":
            self.state = "select_images"
        elif self.state == "choose_placement":
            self.state = "enter_label"
        elif self.state == "choose_timestamp":
            self.state = "choose_placement"
        elif self.state == "choose_output":
            self.state = "choose_timestamp"
        self.draw_ui()


def main() -> None:
    """Start the Tkinter application.

    Returns:
        None.
    """
    root = tk.Tk()
    ImageClassifierApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
