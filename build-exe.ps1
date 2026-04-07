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

Write-Host "Image Classifier Tool - EXE Builder" -ForegroundColor Cyan
Write-Host "====================================`n" -ForegroundColor Cyan

# Check if uv is installed
Write-Host "Checking for uv package manager..." -ForegroundColor Yellow
$uvPath = & where.exe uv 2>$null
if (-not $uvPath) {
    Write-Host "uv not found. Installing uv..." -ForegroundColor Yellow
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    $uvPath = & where.exe uv 2>$null
    if (-not $uvPath) {
        Write-Host "Failed to install uv. Please install manually from https://astral.sh/uv" -ForegroundColor Red
        exit 1
    }
    Write-Host "uv installed successfully." -ForegroundColor Green
}
else {
    Write-Host "uv found at: $uvPath" -ForegroundColor Green
}

# Sync dependencies using uv
Write-Host "`nSyncing project dependencies..." -ForegroundColor Yellow
& uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to sync dependencies." -ForegroundColor Red
    exit 1
}
Write-Host "Dependencies synced successfully." -ForegroundColor Green

# Add PyInstaller to the project
Write-Host "`nAdding PyInstaller to project..." -ForegroundColor Yellow
& uv add --dev pyinstaller
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to add PyInstaller." -ForegroundColor Red
    exit 1
}
Write-Host "PyInstaller added successfully." -ForegroundColor Green

# Sync again to include PyInstaller
Write-Host "`nSyncing updated dependencies..." -ForegroundColor Yellow
& uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to sync updated dependencies." -ForegroundColor Red
    exit 1
}

# Create build output directory
$buildDir = ".\build"
if (Test-Path $buildDir) {
    Write-Host "`nCleaning previous build..." -ForegroundColor Yellow
    Remove-Item $buildDir -Recurse -Force
}

Write-Host "`nBuilding standalone executable..." -ForegroundColor Yellow
$specFile = @"
# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
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
    icon='icon.ico' if __import__('pathlib').Path('icon.ico').exists() else None,
)
"@

$specFile | Out-File -FilePath "build_spec.spec" -Encoding UTF8

# Run PyInstaller
& uv run pyinstaller --clean --noconfirm build_spec.spec

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to build executable." -ForegroundColor Red
    exit 1
}

Write-Host "`n✓ Build completed successfully!" -ForegroundColor Green

# Check if exe was created
$exePath = ".\dist\ImageClassifier.exe"
if (Test-Path $exePath) {
    $exeSize = (Get-Item $exePath).Length / 1MB
    Write-Host "Executable created: $exePath" -ForegroundColor Green
    Write-Host "Size: $([Math]::Round($exeSize, 2)) MB" -ForegroundColor Green
    Write-Host "`nYou can now distribute the exe file or the entire 'dist' folder." -ForegroundColor Cyan
}
else {
    Write-Host "Executable not found at expected path." -ForegroundColor Red
    exit 1
}

# Cleanup spec file
Remove-Item "build_spec.spec" -Force

Write-Host ""
Write-Host "Build complete! Run with: .\dist\ImageClassifier.exe" -ForegroundColor Green
