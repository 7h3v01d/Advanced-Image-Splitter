import sys
import os
import math
from typing import Optional, Tuple, List
from concurrent.futures import ThreadPoolExecutor, Future

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QSpinBox, QMessageBox, QProgressBar,
    QDoubleSpinBox, QComboBox, QCheckBox, QLineEdit, QGroupBox, QSizePolicy
)
from PyQt6.QtGui import QPixmap, QImage, QPainter, QPen, QFont, QMouseEvent, QWheelEvent
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject, QRunnable, QThreadPool, QMetaObject, Q_ARG
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4, letter, legal
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import black, white

# Constants
DPI = 300
MM_TO_INCH = 0.0393701
MM_TO_PIXEL = MM_TO_INCH * DPI
A4_WIDTH_MM = 210
A4_HEIGHT_MM = 297
POINTS_PER_MM = MM_TO_INCH * 72  # Convert mm to points (1 inch = 72 points)

# Page size presets (in points for ReportLab, with mm equivalents for calculations)
PAGE_SIZES = {
    "A4": (A4[0], A4[1], 210, 297),  # (width_points, height_points, width_mm, height_mm)
    "A3": (842, 1191, 297, 420),     # A3 in points (297 mm × 420 mm)
    "Letter": (letter[0], letter[1], 215.9, 279.4),
    "Legal": (legal[0], legal[1], 215.9, 355.6),
    "Tabloid": (792, 1224, 279.4, 431.8)  # 11 × 17 inches = 792 × 1224 points
}

class ImageSplitterSignals(QObject):
    """Signals for image splitting thread"""
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    error = pyqtSignal(str)


class ImageSplitterWorker(QRunnable):
    """Worker thread for image splitting"""
    def __init__(self, parent, image_path, settings):
        super().__init__()
        self.parent = parent
        self.image_path = image_path
        self.settings = settings
        self.signals = ImageSplitterSignals()
        self.is_cancelled = False

    def run(self):
        try:
            self.split_image()
            if not self.is_cancelled:
                self.signals.finished.emit()
        except Exception as e:
            self.signals.error.emit(str(e))

    def cancel(self):
        self.is_cancelled = True

    def split_image(self):
        # Unpack settings
        orientation = self.settings['orientation']
        mode = self.settings['mode']
        grid_width = self.settings['grid_width']
        grid_height = self.settings['grid_height']
        custom_width = self.settings['custom_width']
        custom_height = self.settings['custom_height']
        stretch = self.settings['stretch']
        ai_upscale = self.settings['ai_upscale']
        cut_marks = self.settings['cut_marks']
        labels = self.settings['labels']
        guide = self.settings['guide']
        margin_mm = self.settings['margin_mm']
        output_format = self.settings['output_format']
        page_size_name = self.settings['page_size']
        border = self.settings['border']
        border_width = self.settings['border_width']
        
        # Page size in mm and points
        page_width_points, page_height_points, page_width_mm, page_height_mm = PAGE_SIZES[page_size_name]
        if orientation == "Landscape":
            page_width_mm, page_height_mm = page_height_mm, page_width_mm
            page_width_points, page_height_points = page_height_points, page_width_points
        
        # Calculate dimensions
        if mode == "Grid Size":
            h_splits = grid_width
            v_splits = grid_height
            target_width_mm = h_splits * page_width_mm
            target_height_mm = v_splits * page_height_mm
        else:
            target_width_mm = custom_width
            target_height_mm = custom_height
            h_splits = math.ceil(target_width_mm / page_width_mm)
            v_splits = math.ceil(target_height_mm / page_height_mm)
        
        # Convert to pixels
        page_width = int(page_width_mm * MM_TO_PIXEL)
        page_height = int(page_height_mm * MM_TO_PIXEL)
        margin_pixels = int(margin_mm * MM_TO_PIXEL)
        target_width = int(target_width_mm * MM_TO_PIXEL)
        target_height = int(target_height_mm * MM_TO_PIXEL)
        
        # Load image
        image = Image.open(self.image_path)
        img_width, img_height = image.size
        
        # AI upscaling (placeholder)
        if ai_upscale:
            # Calculate required scale factor to reach target DPI
            current_dpi_width = img_width / (target_width_mm * MM_TO_INCH)
            current_dpi_height = img_height / (target_height_mm * MM_TO_INCH)
            current_dpi = min(current_dpi_width, current_dpi_height)
            
            if current_dpi < DPI:
                scale_factor = DPI / current_dpi
                new_width = int(img_width * scale_factor)
                new_height = int(img_height * scale_factor)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                img_width, img_height = new_width, new_height
                self.signals.progress.emit(10)  # 10% progress for upscaling
        
        # Resize image
        if stretch:
            image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        else:
            scale_factor = min(target_width / img_width, target_height / img_height)
            new_width = int(img_width * scale_factor)
            new_height = int(img_height * scale_factor)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            canvas_img = Image.new('RGB', (target_width, target_height), (255, 255, 255))
            paste_x = (target_width - new_width) // 2
            paste_y = (target_height - new_height) // 2
            canvas_img.paste(image, (paste_x, paste_y))
            image = canvas_img
        
        img_width, img_height = image.size
        
        # Create output directory
        base_name = os.path.splitext(os.path.basename(self.image_path))[0]
        output_dir = os.path.join(os.path.dirname(self.image_path), f"{base_name}_split")
        os.makedirs(output_dir, exist_ok=True)
        
        # Prepare for splitting
        total_segments = h_splits * v_splits
        segment_count = 0
        font = ImageFont.truetype("arial.ttf", 24) if labels else None
        
        # Split image
        for i in range(v_splits):
            for j in range(h_splits):
                if self.is_cancelled:
                    return
                
                left = max(0, j * page_width - margin_pixels)
                upper = max(0, i * page_height - margin_pixels)
                right = min(img_width, (j + 1) * page_width + margin_pixels)
                lower = min(img_height, (i + 1) * page_height + margin_pixels)
                
                if right <= left or lower <= upper:
                    continue
                
                segment = image.crop((left, upper, right, lower))
                page_img = Image.new('RGB', (page_width, page_height), (255, 255, 255))
                paste_x = (page_width - segment.width) // 2
                paste_y = (page_height - segment.height) // 2
                page_img.paste(segment, (paste_x, paste_y))
                
                # Add border
                if border:
                    draw = ImageDraw.Draw(page_img)
                    draw.rectangle([0, 0, page_width-1, page_height-1], 
                                  outline='black', width=border_width)
                
                # Add cut marks
                if cut_marks:
                    draw = ImageDraw.Draw(page_img)
                    mark_length = 20
                    # Top-left
                    draw.line((0, 0, mark_length, 0), fill='black', width=2)
                    draw.line((0, 0, 0, mark_length), fill='black', width=2)
                    # Top-right
                    draw.line((page_width - mark_length, 0, page_width, 0), fill='black', width=2)
                    draw.line((page_width, 0, page_width, mark_length), fill='black', width=2)
                    # Bottom-left
                    draw.line((0, page_height - mark_length, 0, page_height), fill='black', width=2)
                    draw.line((0, page_height, mark_length, page_height), fill='black', width=2)
                    # Bottom-right
                    draw.line((page_width - mark_length, page_height, page_width, page_height), fill='black', width=2)
                    draw.line((page_width, page_height - mark_length, page_width, page_height), fill='black', width=2)
                
                # Add labels
                if labels:
                    draw = ImageDraw.Draw(page_img)
                    label_text = f"Row {i+1}, Col {j+1}"
                    # Add text with background for better visibility
                    bbox = draw.textbbox((0, 0), label_text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    draw.rectangle([10, 10, 15 + text_width, 15 + text_height], fill='white')
                    draw.text((12, 12), label_text, fill='black', font=font)
                
                # Save segment
                output_path = os.path.join(output_dir, f"{base_name}_row_{i+1}_col_{j+1}.{output_format.lower()}")
                
                if output_format == "PNG":
                    page_img.save(output_path, format='PNG', dpi=(DPI, DPI))
                else:  # PDF
                    pdf_path = output_path
                    c = canvas.Canvas(pdf_path, pagesize=(page_width_points, page_height_points))
                    # Convert PIL image to format ReportLab can use
                    img_temp_path = os.path.join(output_dir, f"temp_{i}_{j}.png")
                    page_img.save(img_temp_path, format='PNG')
                    c.drawImage(img_temp_path, 0, 0, page_width_points, page_height_points)
                    c.save()
                    os.remove(img_temp_path)
                
                segment_count += 1
                progress = int(10 + (segment_count / total_segments) * 85)  # 10-95% for splitting
                self.signals.progress.emit(progress)
        
        # Generate assembly guide
        if guide and not self.is_cancelled:
            self.generate_assembly_guide(output_dir, base_name, h_splits, v_splits, image, page_width_mm, page_height_mm)
            self.signals.progress.emit(100)
    
    def generate_assembly_guide(self, output_dir, base_name, h_splits, v_splits, full_image, page_width_mm, page_height_mm):
        """Generate a comprehensive assembly guide PDF"""
        pdf_path = os.path.join(output_dir, f"{base_name}_assembly_guide.pdf")
        c = canvas.Canvas(pdf_path, pagesize=A4)
        width, height = A4
        
        # Title page
        c.setFont("Helvetica-Bold", 24)
        c.drawString(72, height - 72, "Image Assembly Guide")
        c.setFont("Helvetica", 14)
        c.drawString(72, height - 100, f"For: {base_name}")
        c.drawString(72, height - 124, f"Grid: {h_splits} × {v_splits} pages")
        c.drawString(72, height - 148, f"Total pages: {h_splits * v_splits}")
        
        # Add miniature of the full image
        img_ratio = full_image.width / full_image.height
        img_width = 400
        img_height = img_width / img_ratio
        if img_height > 300:
            img_height = 300
            img_width = img_height * img_ratio
        
        # Save temporary image
        temp_img_path = os.path.join(output_dir, "temp_full_image.png")
        full_image.resize((int(img_width), int(img_height)), Image.Resampling.LANCZOS).save(temp_img_path)
        
        c.drawImage(temp_img_path, (width - img_width) / 2, height - 200 - img_height, 
                   width=img_width, height=img_height)
        os.remove(temp_img_path)
        
        c.showPage()
        
        # Assembly instructions
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, height - 72, "Assembly Instructions:")
        
        instructions = [
            "1. Print all pages at 100% scale (do not fit to page)",
            "2. Trim along the cut marks on each page",
            "3. Align pages using the row and column numbers",
            "4. Use the overlap areas to match adjacent pages",
            "5. Tape or glue pages together from behind",
            f"6. Final size: {page_width_mm * h_splits / 10:.1f} × {page_height_mm * v_splits / 10:.1f} cm"
        ]
        
        c.setFont("Helvetica", 12)
        y_pos = height - 100
        for instruction in instructions:
            c.drawString(72, y_pos, instruction)
            y_pos -= 24
        
        c showPage()
        
        # Grid layout page
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, height - 72, "Page Layout:")
        
        # Draw grid
        grid_width = 400
        grid_height = 400
        grid_x = (width - grid_width) / 2
        grid_y = height - 120 - grid_height
        
        cell_width = grid_width / h_splits
        cell_height = grid_height / v_splits
        
        for i in range(v_splits + 1):
            y = grid_y + i * cell_height
            c.line(grid_x, y, grid_x + grid_width, y)
        
        for j in range(h_splits + 1):
            x = grid_x + j * cell_width
            c.line(x, grid_y, x, grid_y + grid_height)
        
        # Add labels to cells
        c.setFont("Helvetica", 10)
        for i in range(v_splits):
            for j in range(h_splits):
                x = grid_x + j * cell_width + 5
                y = grid_y + (i + 1) * cell_height - 5
                c.drawString(x, y, f"Row {i+1}, Col {j+1}")
        
        c.showPage()
        
        # Page-by-page guide
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, height - 72, "Page Details:")
        
        y_pos = height - 100
        for i in range(v_splits):
            for j in range(h_splits):
                if y_pos < 100:
                    c.showPage()
                    y_pos = height - 72
                    c.setFont("Helvetica-Bold", 16)
                    c.drawString(72, y_pos, "Page Details (cont.):")
                    y_pos -= 28
                
                c.setFont("Helvetica-Bold", 12)
                c.drawString(72, y_pos, f"Page {i*h_splits + j + 1}: Row {i+1}, Col {j+1}")
                y_pos -= 20
                
                c.setFont("Helvetica", 10)
                c.drawString(90, y_pos, f"- Position: Top-left at ({j*page_width_mm/10:.1f} cm, {i*page_height_mm/10:.1f} cm)")
                y_pos -= 15
                c.drawString(90, y_pos, f"- Dimensions: {page_width_mm/10:.1f} × {page_height_mm/10:.1f} cm")
                y_pos -= 15
                c.drawString(90, y_pos, f"- File: {base_name}_row_{i+1}_col_{j+1}.pdf")
                y_pos -= 25
        
        c.save()


class ClickableLabel(QLabel):
    """QLabel that emits a signal when clicked"""
    clicked = pyqtSignal()
    
    def mousePressEvent(self, event: QMouseEvent):
        self.clicked.emit()
        super().mousePressEvent(event)


class ImageSplitter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Advanced Image Splitter for Printing")
        self.setGeometry(100, 100, 800, 700)
        self.image_path = None
        self.worker_thread = None
        self.worker = None
        self.init_ui()
        
        # Thread pool for background tasks
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(1)

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout()
        main_widget.setLayout(layout)

        # Image display with zoom capability
        image_group = QGroupBox("Image Preview")
        image_layout = QVBoxLayout()
        image_group.setLayout(image_layout)
        
        self.image_label = ClickableLabel("No image loaded")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(400, 300)
        self.image_label.setStyleSheet("border: 1px solid gray;")
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label.clicked.connect(self.reset_zoom)
        image_layout.addWidget(self.image_label)
        
        # Zoom controls
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QDoubleSpinBox()
        self.zoom_slider.setRange(0.1, 5.0)
        self.zoom_slider.setValue(1.0)
        self.zoom_slider.setSingleStep(0.1)
        self.zoom_slider.valueChanged.connect(self.update_preview)
        zoom_layout.addWidget(self.zoom_slider)
        zoom_layout.addWidget(QLabel("x"))
        zoom_layout.addStretch()
        image_layout.addLayout(zoom_layout)
        
        layout.addWidget(image_group)

        # Output settings
        settings_group = QGroupBox("Output Settings")
        settings_layout = QVBoxLayout()
        settings_group.setLayout(settings_layout)
        
        # Page size selection
        page_layout = QHBoxLayout()
        page_layout.addWidget(QLabel("Page Size:"))
        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(list(PAGE_SIZES.keys()))
        self.page_size_combo.setCurrentText("A4")
        self.page_size_combo.currentIndexChanged.connect(self.update_preview)
        page_layout.addWidget(self.page_size_combo)
        
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItems(["Portrait", "Landscape"])
        self.orientation_combo.currentIndexChanged.connect(self.update_preview)
        page_layout.addWidget(self.orientation_combo)
        settings_layout.addLayout(page_layout)

        # Output size selection
        size_group = QGroupBox("Output Size")
        size_layout = QVBoxLayout()
        size_group.setLayout(size_layout)

        grid_layout = QHBoxLayout()
        self.grid_width = QSpinBox()
        self.grid_width.setRange(1, 20)
        self.grid_width.setValue(2)
        self.grid_width.valueChanged.connect(self.update_preview)
        grid_layout.addWidget(QLabel("Grid Width (pages):"))
        grid_layout.addWidget(self.grid_width)

        self.grid_height = QSpinBox()
        self.grid_height.setRange(1, 20)
        self.grid_height.setValue(2)
        self.grid_height.valueChanged.connect(self.update_preview)
        grid_layout.addWidget(QLabel("Grid Height (pages):"))
        grid_layout.addWidget(self.grid_height)
        size_layout.addLayout(grid_layout)

        custom_layout = QHBoxLayout()
        self.custom_width = QLineEdit("1000")
        self.custom_width.setPlaceholderText("Width in mm")
        self.custom_width.textChanged.connect(self.update_preview)
        custom_layout.addWidget(QLabel("Custom Width (mm):"))
        custom_layout.addWidget(self.custom_width)

        self.custom_height = QLineEdit("500")
        self.custom_height.setPlaceholderText("Height in mm")
        self.custom_height.textChanged.connect(self.update_preview)
        custom_layout.addWidget(QLabel("Custom Height (mm):"))
        custom_layout.addWidget(self.custom_height)
        size_layout.addLayout(custom_layout)

        self.size_mode = QComboBox()
        self.size_mode.addItems(["Grid Size", "Custom Dimensions"])
        self.size_mode.currentIndexChanged.connect(self.toggle_size_mode)
        size_layout.addWidget(QLabel("Size Mode:"))
        size_layout.addWidget(self.size_mode)

        settings_layout.addWidget(size_group)

        # Additional options
        options_layout = QVBoxLayout()
        
        self.stretch_check = QCheckBox("Stretch to fit (non-proportional)")
        self.stretch_check.stateChanged.connect(self.update_preview)
        options_layout.addWidget(self.stretch_check)

        self.ai_upscale_check = QCheckBox("Enhance with AI Upscaling")
        options_layout.addWidget(self.ai_upscale_check)

        border_layout = QHBoxLayout()
        self.border_check = QCheckBox("Add Border")
        self.border_check.setChecked(True)
        border_layout.addWidget(self.border_check)
        
        border_layout.addWidget(QLabel("Border Width:"))
        self.border_width = QSpinBox()
        self.border_width.setRange(1, 20)
        self.border_width.setValue(2)
        border_layout.addWidget(self.border_width)
        border_layout.addStretch()
        options_layout.addLayout(border_layout)

        self.cut_marks_check = QCheckBox("Add Cut Marks")
        self.cut_marks_check.setChecked(True)
        options_layout.addWidget(self.cut_marks_check)

        self.labels_check = QCheckBox("Add Tile Labels")
        self.labels_check.setChecked(True)
        options_layout.addWidget(self.labels_check)

        self.guide_check = QCheckBox("Generate Assembly Guide PDF")
        self.guide_check.setChecked(True)
        options_layout.addWidget(self.guide_check)

        self.margin_spin = QDoubleSpinBox()
        self.margin_spin.setRange(0, 50)
        self.margin_spin.setValue(10)
        self.margin_spin.setSuffix(" mm")
        options_layout.addWidget(QLabel("Overlap Margin:"))
        options_layout.addWidget(self.margin_spin)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["PNG", "PDF"])
        options_layout.addWidget(QLabel("Output Format:"))
        options_layout.addWidget(self.format_combo)
        
        settings_layout.addLayout(options_layout)
        layout.addWidget(settings_group)

        # DPI feedback
        info_layout = QHBoxLayout()
        self.dpi_label = QLabel("DPI: N/A")
        info_layout.addWidget(self.dpi_label)
        
        self.dimensions_label = QLabel("Final Size: N/A")
        info_layout.addWidget(self.dimensions_label)
        
        self.pages_label = QLabel("Pages: N/A")
        info_layout.addWidget(self.pages_label)
        
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.load_button = QPushButton("Load Image")
        self.load_button.clicked.connect(self.load_image)
        button_layout.addWidget(self.load_button)

        self.split_button = QPushButton("Split and Save")
        self.split_button.clicked.connect(self.start_splitting)
        self.split_button.setEnabled(False)
        button_layout.addWidget(self.split_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.cancel_splitting)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Ready to load an image")
        layout.addWidget(self.status_label)

        self.toggle_size_mode()

    def toggle_size_mode(self):
        mode = self.size_mode.currentText()
        self.grid_width.setEnabled(mode == "Grid Size")
        self.grid_height.setEnabled(mode == "Grid Size")
        self.custom_width.setEnabled(mode == "Custom Dimensions")
        self.custom_height.setEnabled(mode == "Custom Dimensions")
        self.update_preview()

    def load_image(self):
        file_dialog = QFileDialog(self)
        file_path, _ = file_dialog.getOpenFileName(
            self, "Select Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.tiff)"
        )
        if file_path:
            self.image_path = file_path
            self.zoom_slider.setValue(1.0)  # Reset zoom
            self.update_preview()
            self.status_label.setText(f"Loaded: {os.path.basename(file_path)}")
            self.split_button.setEnabled(True)

    def reset_zoom(self):
        self.zoom_slider.setValue(1.0)

    def wheelEvent(self, event: QWheelEvent):
        """Zoom in/out with mouse wheel when holding Ctrl"""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_slider.setValue(self.zoom_slider.value() + 0.1)
            else:
                self.zoom_slider.setValue(max(0.1, self.zoom_slider.value() - 0.1))
            event.accept()
        else:
            super().wheelEvent(event)

    def update_preview(self):
        if not self.image_path:
            return
            
        try:
            pixmap = QPixmap(self.image_path)
            if pixmap.isNull():
                self.status_label.setText("Error: Unable to load image")
                return
                
            img_width, img_height = pixmap.width(), pixmap.height()

            # Calculate target dimensions
            mode = self.size_mode.currentText()
            page_size_name = self.page_size_combo.currentText()
            _, _, page_width_mm, page_height_mm = PAGE_SIZES[page_size_name]
            orientation = self.orientation_combo.currentText()
            
            if orientation == "Landscape":
                page_width_mm, page_height_mm = page_height_mm, page_width_mm

            if mode == "Grid Size":
                h_splits = self.grid_width.value()
                v_splits = self.grid_height.value()
                target_width_mm = h_splits * page_width_mm
                target_height_mm = v_splits * page_height_mm
            else:
                try:
                    target_width_mm = float(self.custom_width.text())
                    target_height_mm = float(self.custom_height.text())
                    h_splits = math.ceil(target_width_mm / page_width_mm)
                    v_splits = math.ceil(target_height_mm / page_height_mm)
                except ValueError:
                    return

            # Calculate DPI
            target_width_px = target_width_mm * MM_TO_PIXEL
            target_height_px = target_height_mm * MM_TO_PIXEL
            
            if self.stretch_check.isChecked():
                scale_factor_x = target_width_px / img_width
                scale_factor_y = target_height_px / img_height
                dpi_x = DPI * scale_factor_x
                dpi_y = DPI * scale_factor_y
                dpi = min(dpi_x, dpi_y)
            else:
                scale_factor = min(target_width_px / img_width, target_height_px / img_height)
                dpi = DPI * scale_factor
                
            # Update info labels
            self.dpi_label.setText(f"DPI: {int(dpi)}")
            self.dimensions_label.setText(f"Final Size: {target_width_mm/10:.1f} × {target_height_mm/10:.1f} cm")
            self.pages_label.setText(f"Pages: {h_splits} × {v_splits} = {h_splits * v_splits}")
            
            # Scale pixmap for preview
            zoom = self.zoom_slider.value()
            preview_width = int(500 * zoom)
            preview_height = int(300 * zoom)
            
            if self.stretch_check.isChecked():
                scaled_pixmap = pixmap.scaled(preview_width, preview_height, 
                                            Qt.AspectRatioMode.IgnoreAspectRatio)
            else:
                scaled_pixmap = pixmap.scaled(preview_width, preview_height, 
                                            Qt.AspectRatioMode.KeepAspectRatio)

            # Draw grid
            painter = QPainter(scaled_pixmap)
            pen = QPen(Qt.GlobalColor.red, 2)
            painter.setPen(pen)
            width = scaled_pixmap.width()
            height = scaled_pixmap.height()

            for i in range(1, h_splits):
                x = (width / h_splits) * i
                painter.drawLine(int(x), 0, int(x), height)
            for i in range(1, v_splits):
                y = (height / v_splits) * i
                painter.drawLine(0, int(y), width, int(y))
            painter.end()
            
            self.image_label.setPixmap(scaled_pixmap)
            
        except Exception as e:
            self.status_label.setText(f"Error updating preview: {str(e)}")

    def start_splitting(self):
        if not self.image_path:
            QMessageBox.warning(self, "Error", "Please load an image first!")
            return
            
        # Validate custom dimensions if in custom mode
        if self.size_mode.currentText() == "Custom Dimensions":
            try:
                width = float(self.custom_width.text())
                height = float(self.custom_height.text())
                if width <= 0 or height <= 0:
                    QMessageBox.warning(self, "Error", "Dimensions must be positive values!")
                    return
            except ValueError:
                QMessageBox.warning(self, "Error", "Please enter valid numbers for dimensions!")
                return

        # Prepare settings for the worker
        settings = {
            'orientation': self.orientation_combo.currentText(),
            'mode': self.size_mode.currentText(),
            'grid_width': self.grid_width.value(),
            'grid_height': self.grid_height.value(),
            'custom_width': float(self.custom_width.text()) if self.size_mode.currentText() == "Custom Dimensions" else 0,
            'custom_height': float(self.custom_height.text()) if self.size_mode.currentText() == "Custom Dimensions" else 0,
            'stretch': self.stretch_check.isChecked(),
            'ai_upscale': self.ai_upscale_check.isChecked(),
            'cut_marks': self.cut_marks_check.isChecked(),
            'labels': self.labels_check.isChecked(),
            'guide': self.guide_check.isChecked(),
            'margin_mm': self.margin_spin.value(),
            'output_format': self.format_combo.currentText(),
            'page_size': self.page_size_combo.currentText(),
            'border': self.border_check.isChecked(),
            'border_width': self.border_width.value()
        }

        # Disable UI during processing
        self.set_ui_enabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Processing...")

        # Create and start worker
        self.worker = ImageSplitterWorker(self, self.image_path, settings)
        self.worker.signals.progress.connect(self.progress_bar.setValue)
        self.worker.signals.finished.connect(self.splitting_finished)
        self.worker.signals.error.connect(self.splitting_error)
        
        self.thread_pool.start(self.worker)

    def cancel_splitting(self):
        if self.worker:
            self.worker.cancel()
        self.splitting_finished("Operation cancelled")

    def splitting_finished(self, message="Success"):
        self.set_ui_enabled(True)
        self.progress_bar.setVisible(False)
        
        if "cancelled" not in message.lower():
            QMessageBox.information(self, "Success", 
                                  f"Image processing completed successfully!\n{message}")
        
        self.status_label.setText(message)

    def splitting_error(self, error_message):
        self.set_ui_enabled(True)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Error", f"Failed to process image: {error_message}")
        self.status_label.setText(f"Error: {error_message}")

    def set_ui_enabled(self, enabled):
        """Enable or disable UI controls during processing"""
        self.load_button.setEnabled(enabled)
        self.split_button.setEnabled(enabled)
        self.cancel_button.setEnabled(not enabled)
        
        # Disable all settings controls during processing
        for child in self.findChildren((QSpinBox, QComboBox, QCheckBox, QLineEdit, QDoubleSpinBox)):
            child.setEnabled(enabled)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ImageSplitter()
    window.show()
    sys.exit(app.exec())