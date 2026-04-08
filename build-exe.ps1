#Requires -Version 5.0
<#
.SYNOPSIS
    Build the Image Classifier Tool into a standalone Windows executable.

.DESCRIPTION
    This script ensures all dependencies are installed and creates a standalone
    exe file using PyInstaller. The exe can be distributed without requiring
    Python or uv to be installed.

.EXAMPLE
    .\build-exe.ps1
#>

$ErrorActionPreference = "Stop"

Write-Host -ForegroundColor Cyan "Image Classifier Tool - EXE Builder"
Write-Host -ForegroundColor Cyan "===================================="
Write-Host ""

# Check if uv is installed
Write-Host -ForegroundColor Yellow "Checking for uv package manager..."
$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCommand) {
    Write-Host -ForegroundColor Yellow "uv not found. Installing uv..."
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    
    # Add uv installation directory to PATH
    $uvPath = "$env:USERPROFILE\.local\bin"
    if (Test-Path $uvPath) {
        $env:Path = "$uvPath;$env:Path"
    }
    
    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uvCommand) {
        Write-Host -ForegroundColor Red "Failed to install uv. Please install manually from https://astral.sh/uv"
        exit 1
    }
    Write-Host -ForegroundColor Green "uv installed successfully."
}
else {
    Write-Host -ForegroundColor Green ("uv found at: " + $uvCommand.Source)
}

# Sync dependencies using uv
Write-Host ""
Write-Host -ForegroundColor Yellow "Syncing project dependencies..."
& uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Host -ForegroundColor Red "Failed to sync dependencies."
    exit 1
}
Write-Host -ForegroundColor Green "Dependencies synced successfully."

# Add PyInstaller to the project
Write-Host ""
Write-Host -ForegroundColor Yellow "Adding PyInstaller to project..."
& uv add --dev pyinstaller
if ($LASTEXITCODE -ne 0) {
    Write-Host -ForegroundColor Red "Failed to add PyInstaller."
    exit 1
}
Write-Host -ForegroundColor Green "PyInstaller added successfully."

# Sync again to include PyInstaller
Write-Host ""
Write-Host -ForegroundColor Yellow "Syncing updated dependencies..."
& uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Host -ForegroundColor Red "Failed to sync updated dependencies."
    exit 1
}

# Create build output directory
$buildDir = '.\build'
if (Test-Path $buildDir) {
    Write-Host ""
    Write-Host -ForegroundColor Yellow "Cleaning previous build..."
    Remove-Item $buildDir -Recurse -Force
}

Write-Host ""
Write-Host -ForegroundColor Yellow "Building standalone executable..."

# Create PyInstaller spec file
$specContent = @'
# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('aerosurvey-mark-8-icon.ico', '.')],
    hiddenimports=['PIL'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ImageClassifier',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='aerosurvey-mark-8-icon.ico' if __import__('pathlib').Path('aerosurvey-mark-8-icon.ico').exists() else None,
)
'@

$specContent | Out-File -FilePath 'build_spec.spec' -Encoding UTF8

# Run PyInstaller
& uv run pyinstaller --clean --noconfirm 'build_spec.spec'

if ($LASTEXITCODE -ne 0) {
    Write-Host -ForegroundColor Red "Failed to build executable."
    exit 1
}

Write-Host ""
Write-Host -ForegroundColor Green "Build completed successfully!"

# Check if exe was created
$exePath = '.\dist\ImageClassifier.exe'
if (Test-Path $exePath) {
    $exeSize = (Get-Item $exePath).Length / 1MB
    Write-Host -ForegroundColor Green ('Executable created: ' + $exePath)
    Write-Host -ForegroundColor Green ('Size: ' + [Math]::Round($exeSize, 2) + ' MB')
    Write-Host ""
    Write-Host -ForegroundColor Cyan "You can now distribute the exe file or the entire dist folder."
}
else {
    Write-Host -ForegroundColor Red "Executable not found at expected path."
    exit 1
}

# Cleanup spec file
Remove-Item 'build_spec.spec' -Force

Write-Host ""
Write-Host -ForegroundColor Green "Build complete! Run with: .\dist\ImageClassifier.exe"
