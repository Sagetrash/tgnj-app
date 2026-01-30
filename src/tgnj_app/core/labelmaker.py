from reportlab.lib.pagesizes import A4
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm, cm
from reportlab.lib.utils import ImageReader
import os


# Avery L7651 specs
LABEL_WIDTH = 38.1 * mm
LABEL_HEIGHT = 21.2 * mm

PAGE_WIDTH, PAGE_HEIGHT = A4

LEFT_MARGIN = 0.47 * cm
TOP_MARGIN = 1.0 * cm
HORIZONTAL_PITCH = 4.06 * cm
VERTICAL_PITCH = 2.12 * cm

COLUMNS = 5
ROWS = 13


def draw_label(c, x, y, product_id, weight, size, logo):
    # c.rect(x, y, LABEL_WIDTH, LABEL_HEIGHT, stroke=1, fill=0)
    text_x = x + 7 * mm
    text_y = y + LABEL_HEIGHT - 7 * mm


    img_x = 18 * mm #measurements for image
    img_y = 7 * mm
    n = 30# size nxn
    c.setFont("Helvetica", 11)
    c.drawString(text_x, text_y, f"{product_id}")
    c.drawImage(logo,text_x + img_x,text_y - img_y,width=n,height=n)
    c.drawString(text_x, text_y - 14, f"{weight:.2f}")
    c.drawString(text_x, text_y - 28, f"{size}")

def create_pdf(data:dict,logo_path):
    logo = ImageReader(logo_path)

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    
    labels_per_page = COLUMNS * ROWS
    label_count = 0
    
    for row in data:
        col = label_count % COLUMNS
        row_num = (label_count // COLUMNS) % ROWS
        
        x = LEFT_MARGIN + col * HORIZONTAL_PITCH
        y = PAGE_HEIGHT - TOP_MARGIN - (row_num + 1) * VERTICAL_PITCH + (VERTICAL_PITCH - LABEL_HEIGHT)
        
        draw_label(c, x, y, f"{row['sku_group']}-{row['sku_id']:03d}", row['weight'], f"{row["length"]}x{row["width"]}x{row["depth"]}",logo)
        label_count += 1
        
        if label_count % labels_per_page == 0:
            c.showPage()
    
    c.save()
    buffer.seek(0)
    print(f"PDF labels saved")
    return buffer

#csv_ = "csv/test.csv"
#out = "print_these/test.pdf"
#create_pdf(csv_,out)