"""
QR Code Generation Utilities for Asset Management App

This module provides functions to generate QR codes for assets:
- Single QR code as PNG
- QR code with label as PNG
- Bulk QR codes as printable PDF
"""

from io import BytesIO
from typing import List, Dict, Any
import qrcode
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, mm
from reportlab.pdfgen import canvas


def generate_asset_qr(serial_number: str, size: int = 200) -> BytesIO:
    """
    Generate a simple QR code containing the serial number.

    Args:
        serial_number: The asset serial number to encode
        size: Size of the QR code in pixels (default 200)

    Returns:
        BytesIO buffer containing the PNG image
    """
    # Create QR code instance
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )

    # Add data
    qr.add_data(serial_number)
    qr.make(fit=True)

    # Create image
    img = qr.make_image(fill_color="black", back_color="white")

    # Resize to specified size
    img = img.resize((size, size), Image.Resampling.LANCZOS)

    # Save to BytesIO
    output = BytesIO()
    img.save(output, format='PNG')
    output.seek(0)

    return output


def generate_asset_label_image(asset_data: Dict[str, Any], qr_size: int = 150) -> BytesIO:
    """
    Generate a QR code with asset information label below.

    Args:
        asset_data: Dictionary containing asset info (serial_number, asset_type, brand, model)
        qr_size: Size of the QR code in pixels (default 150)

    Returns:
        BytesIO buffer containing the PNG image with label
    """
    serial = asset_data.get('Serial Number', asset_data.get('serial_number', 'Unknown'))
    asset_type = asset_data.get('Asset Type', asset_data.get('asset_type', ''))
    brand = asset_data.get('Brand', asset_data.get('brand', ''))
    model = asset_data.get('Model', asset_data.get('model', ''))

    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(serial)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

    # Create label image with padding
    padding = 20
    label_height = 60
    total_width = qr_size + (padding * 2)
    total_height = qr_size + label_height + (padding * 2)

    # Create white background
    label_img = Image.new('RGB', (total_width, total_height), 'white')

    # Paste QR code centered
    qr_x = (total_width - qr_size) // 2
    label_img.paste(qr_img, (qr_x, padding))

    # Add text
    draw = ImageDraw.Draw(label_img)

    # Try to use a nice font, fall back to default
    try:
        font_large = ImageFont.truetype("arial.ttf", 14)
        font_small = ImageFont.truetype("arial.ttf", 11)
    except:
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        except:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

    # Draw serial number (bold/large)
    text_y = padding + qr_size + 8
    serial_text = f"S/N: {serial}"
    bbox = draw.textbbox((0, 0), serial_text, font=font_large)
    text_width = bbox[2] - bbox[0]
    text_x = (total_width - text_width) // 2
    draw.text((text_x, text_y), serial_text, fill='black', font=font_large)

    # Draw type and brand
    text_y += 20
    info_text = f"{asset_type}"
    if brand:
        info_text += f" - {brand}"
    if model:
        info_text += f" {model}"

    # Truncate if too long
    if len(info_text) > 25:
        info_text = info_text[:22] + "..."

    bbox = draw.textbbox((0, 0), info_text, font=font_small)
    text_width = bbox[2] - bbox[0]
    text_x = (total_width - text_width) // 2
    draw.text((text_x, text_y), info_text, fill='#666666', font=font_small)

    # Save to BytesIO
    output = BytesIO()
    label_img.save(output, format='PNG')
    output.seek(0)

    return output


def generate_bulk_qr_pdf(assets: List[Dict[str, Any]], labels_per_row: int = 3) -> BytesIO:
    """
    Generate a PDF with multiple QR code labels for printing.

    Args:
        assets: List of asset dictionaries
        labels_per_row: Number of labels per row (default 3)

    Returns:
        BytesIO buffer containing the PDF
    """
    output = BytesIO()

    # Create PDF with A4 page size
    c = canvas.Canvas(output, pagesize=A4)
    page_width, page_height = A4

    # Label dimensions
    label_width = 2 * inch
    label_height = 2.2 * inch
    qr_size = int(1.3 * inch)

    # Calculate margins for centering
    total_labels_width = labels_per_row * label_width
    margin_left = (page_width - total_labels_width) / 2
    margin_top = 0.5 * inch

    # Calculate how many rows fit per page
    rows_per_page = int((page_height - margin_top) / label_height)

    current_row = 0
    current_col = 0

    for i, asset in enumerate(assets):
        # Calculate position
        x = margin_left + (current_col * label_width)
        y = page_height - margin_top - ((current_row + 1) * label_height)

        # Get asset info
        serial = asset.get('Serial Number', asset.get('serial_number', 'Unknown'))
        asset_type = asset.get('Asset Type', asset.get('asset_type', ''))
        brand = asset.get('Brand', asset.get('brand', ''))
        model = asset.get('Model', asset.get('model', ''))

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(serial)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_img = qr_img.resize((qr_size, qr_size), Image.Resampling.LANCZOS)

        # Save QR to temporary BytesIO
        qr_buffer = BytesIO()
        qr_img.save(qr_buffer, format='PNG')
        qr_buffer.seek(0)

        # Draw border rectangle
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.setLineWidth(0.5)
        c.rect(x + 5, y + 5, label_width - 10, label_height - 10)

        # Draw QR code
        qr_x = x + (label_width - qr_size) / 2
        qr_y = y + label_height - qr_size - 15

        # Create a temporary image from the buffer
        from reportlab.lib.utils import ImageReader
        qr_buffer.seek(0)
        c.drawImage(ImageReader(qr_buffer), qr_x, qr_y, width=qr_size, height=qr_size)

        # Draw text
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica-Bold", 10)

        # Serial number
        serial_text = f"S/N: {serial}"
        text_width = c.stringWidth(serial_text, "Helvetica-Bold", 10)
        text_x = x + (label_width - text_width) / 2
        c.drawString(text_x, y + 35, serial_text)

        # Asset type and brand
        c.setFont("Helvetica", 8)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        info_text = f"{asset_type}"
        if brand:
            info_text += f" - {brand}"
        if len(info_text) > 30:
            info_text = info_text[:27] + "..."
        text_width = c.stringWidth(info_text, "Helvetica", 8)
        text_x = x + (label_width - text_width) / 2
        c.drawString(text_x, y + 20, info_text)

        # Move to next position
        current_col += 1
        if current_col >= labels_per_row:
            current_col = 0
            current_row += 1

            # Check if we need a new page
            if current_row >= rows_per_page:
                c.showPage()
                current_row = 0

    c.save()
    output.seek(0)

    return output
