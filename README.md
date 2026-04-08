# Image Classifier Tool

Interactive desktop tool that labels images based on user prompts.

## Features

- Select individual image files or a folder of images.
- Enter a classification label
- Select an output folder for labeled images.
- Choose one of four placement modes:
  - Overlay at top
  - Overlay at bottom
  - Append at top
  - Append at bottom
- Text size scales with image size.
- Overlay text color is auto-selected for contrast against the local background.
- Appended labels use black text on a white background.

## Setup

### Option 1: Run with Python (requires [uv](https://docs.astral.sh/uv/#installation))

```powershell
uv sync
```

### Option 2: Build a standalone EXE (no dependencies required)

```powershell
.\build-exe.ps1
```

This script will:
- Check and install `uv` if needed
- Install all project dependencies
- Add PyInstaller to the dev dependencies
- Build a standalone `ImageClassifier.exe` in the `dist/` folder

## Run

### From source (with Python):

```powershell
uv run image-classifier
```

Or:

```powershell
uv run main.py
```

### From the built executable:

```powershell
.\dist\ImageClassifier.exe
```

## Output

Processed images are written to the selected output folder with `_labeled` added to the filename.
If that filename already exists, a numeric suffix is added (for example `_labeled_1`).