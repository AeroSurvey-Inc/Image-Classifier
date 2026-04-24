# Image Classifier Tool

[![Latest Release](https://img.shields.io/github/v/release/AeroSurvey-Inc/Image-Classifier)](https://github.com/AeroSurvey-Inc/Image-Classifier/releases/latest)

Interactive desktop tool that labels images based on user prompts.

## Features

- Select individual image files or a folder of images.
- Enter a classification label
- Optionally add a timestamp after the classifier label is applied.
- Use the image EXIF timestamp or type a manual timestamp.
- Choose whether the timestamp is overlaid on the image or appended below it.
- Select an output folder for labeled images.
- Choose one of four placement modes:
  - Overlay at top
  - Overlay at bottom
  - Append at top
  - Append at bottom
- Text size scales with image size.
- Overlay text color is auto-selected for contrast against the local background.
- Appended labels use black text on a white background.
- Timestamp overlays are automatically placed in a corner that avoids the classifier label area.

## Setup

### Run with Python (requires [uv](https://docs.astral.sh/uv/#installation))

```powershell
uv sync
```

## Build

Requires [uv](https://docs.astral.sh/uv/#installation). PyInstaller is included as a dev dependency.

```powershell
uv sync
uv run pyinstaller --onefile --windowed --name ImageClassifier --icon aerosurvey-mark-8-icon.ico main.py
```

The output executable will be at `dist\ImageClassifier.exe`. It can be run on any Windows machine without Python installed.

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