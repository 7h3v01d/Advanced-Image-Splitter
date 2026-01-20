# Advanced Image Splitter
A Python GUI tool to split large images into printable pages for posters or banners, with customizable grids, overlaps, and assembly guides.

⚠️ **LICENSE & USAGE NOTICE — READ FIRST**

This repository is **source-available for private technical evaluation and testing only**.

- ❌ No commercial use  
- ❌ No production use  
- ❌ No academic, institutional, or government use  
- ❌ No research, benchmarking, or publication  
- ❌ No redistribution, sublicensing, or derivative works  
- ❌ No independent development based on this code  

All rights remain exclusively with the author.  
Use of this software constitutes acceptance of the terms defined in **LICENSE.txt**.

---

## Overview
This application allows users to load an image and split it into multiple pages suitable for printing on standard paper sizes. It supports various page sizes, orientations, and output formats (PNG or PDF). The tool includes features like automatic scaling, overlap margins for easy assembly, cut marks, tile labels, and an optional assembly guide PDF.

## Features
- Page Size and Orientation: Choose from presets like A4, A3, Letter, Legal, Tabloid in Portrait or Landscape.
- Splitting Modes:
    - Grid-based (e.g., 2x2 pages).
    - Custom dimensions in mm.
- Image Handling:
    - Stretch to fit or maintain aspect ratio with centering.
    - Placeholder for AI upscaling to achieve 300 DPI.
- Enhancements:
    - Add borders with customizable width.
    - Include cut marks for precise trimming.
    - Add labels (e.g., "Row 1, Col 1") to each tile.
    - Overlap margins (default 10mm) for seamless assembly.
- Output:
    - PNG or PDF formats at 300 DPI.
    - Generates individual files per page in a dedicated output folder.
- Assembly Guide: Optional PDF with instructions, grid layout, and page details.
- Preview: Interactive image preview with zoom and grid overlay.
- Progress Tracking: Progress bar during processing.
- Multithreading: Uses QRunnable for non-blocking UI during splitting.

## Requirements
- Python 3.12+
- PyQt6
- Pillow (PIL)
- ReportLab

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/advanced-image-splitter.git
cd advanced-image-splitter
```
Install dependencies:
```bash
pip install pyqt6 pillow reportlab
```

## Usage
Run the application:
```bash
python image_splitter.py
```
2. Load an image using the "Load Image" button.
3. Configure settings:
- Select page size and orientation.
- Choose splitting mode (Grid or Custom).
- Enable options like stretch, borders, cut marks, etc.

4. Click "Split and Save" to process.
5. Output files will be saved in a subfolder named <image_name>_split in the same directory as the input image.

## Example

- Load a large poster image.
- Set to A4 Landscape, 3x2 grid, with cut marks and assembly guide.
- Output: 6 PDF pages + assembly_guide.pdf.

## Notes
- AI upscaling is a placeholder and uses Lanczos resampling; integrate a real AI library (e.g., via OpenCV or ESRGAN) for enhancement.
- Ensure "arial.ttf" font is available for labels (system-dependent).
- Cancel button available during processing.


