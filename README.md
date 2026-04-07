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

### Option 1: Run with Python (requires Python 3.13+)

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

The exe can be shared and run on any Windows machine without requiring Python or any other dependencies.

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

## Windows Defender & Code Signing

The built EXE is unsigned (no code signing certificate). If Windows Defender flags it on first run:

1. Click **More info** → **Run anyway**
2. Or add the application to your antivirus exclusion list
3. Or run `build-exe.ps1` yourself to verify the source code

Since you're building locally from source, the exe is safe and you can verify the source code before building.
