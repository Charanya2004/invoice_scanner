import os
import re
import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_path
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
from werkzeug.utils import secure_filename
from fpdf import FPDF
import pyttsx3
from model import db, Invoice, LineItem

# Set the path to the Tesseract executable (if needed)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Flask app
app = Flask(__name__)
app.secret_key = 'supersecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///invoices.db'  # Change to your preferred database
app.config['UPLOAD_FOLDER'] = 'uploads/'
app.config['PROCESSED_FOLDER'] = 'processed/'
app.config['OUTPUT_FOLDER'] = 'output/'

# Initialize the database
db.init_app(app)

# Ensure the necessary directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Create the database tables
with app.app_context():
    db.create_all()

# Noise removal function
def noise_removal(image):
    kernel = np.ones((1, 1), np.uint8)
    image = cv2.dilate(image, kernel, iterations=1)
    image = cv2.erode(image, kernel, iterations=1)
    image = cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel)
    image = cv2.medianBlur(image, 3)
    return image

# Perform OCR and return text
def extract_text_from_image(image_path, lang='eng'):
    img = cv2.imread(image_path)
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    processed_img = noise_removal(img_gray)
    text = pytesseract.image_to_string(processed_img, lang=lang)
    return text

# Convert PDF to images and extract text
def extract_text_from_pdf(pdf_path, lang='eng'):
    images = convert_from_path(pdf_path)
    full_text = ""
    for image in images:
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], "temp.jpg")
        image.save(image_path, 'JPEG')
        text = extract_text_from_image(image_path, lang)
        full_text += text + "\n\n"
    return full_text

# Parse invoice data from extracted text
def parse_invoice_data(extracted_text):
    lines = extracted_text.split('\n')
    invoice_data = {
        'invoice_number': '',
        'vendor_name': '',
        'date': '',
        'total_amount': 0.0,
        'line_items': []
    }

    # Patterns for invoice details
    invoice_number_pattern = r'Invoice No.\s*(\d+)'
    vendor_name_pattern = r'BILLED TO:\s*(.*)'
    date_pattern = r'(\d{1,2} \w+ \d{4})'
    total_amount_pattern = r'Total\s*\$?([\d,.]+)'
    
    for line in lines:
        # Match invoice number
        if re.search(invoice_number_pattern, line):
            invoice_data['invoice_number'] = re.search(invoice_number_pattern, line).group(1).strip()

        # Match vendor name
        elif re.search(vendor_name_pattern, line):
            invoice_data['vendor_name'] = re.search(vendor_name_pattern, line).group(1).strip()

        # Match date
        elif re.search(date_pattern, line):
            invoice_data['date'] = re.search(date_pattern, line).group(1).strip()

        # Match total amount
        elif re.search(total_amount_pattern, line):
            invoice_data['total_amount'] = float(re.search(total_amount_pattern, line).group(1).replace(',', '').strip())

        # Match line items
        else:
            parts = line.split()
            if len(parts) >= 4:  # Adjust based on your line item format
                description = " ".join(parts[:-3])  # Everything except last 3 parts
                quantity = parts[-3]
                price = parts[-2].replace('$', '').replace(',', '')

                # Try to convert quantity and price to numbers
                try:
                    quantity = int(quantity)
                    price = float(price)
                    invoice_data['line_items'].append({
                        'description': description,
                        'quantity': quantity,
                        'price': price
                    })
                except ValueError:
                    continue  # Skip lines that do not contain valid numbers

    return invoice_data

# Flask Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)

    file = request.files['file']
    
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)

    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Perform OCR (image or PDF)
        if filename.lower().endswith('.pdf'):
            extracted_text = extract_text_from_pdf(file_path)
        else:
            extracted_text = extract_text_from_image(file_path)

        # Parse the extracted text to get invoice data
        invoice_data = parse_invoice_data(extracted_text)

        # Save data to the database
        if invoice_data:
            invoice = Invoice(
                invoice_number=invoice_data['invoice_number'],
                vendor_name=invoice_data['vendor_name'],
                date=invoice_data['date'],
                total_amount=invoice_data['total_amount']
            )
            db.session.add(invoice)
            for item in invoice_data['line_items']:
                line_item = LineItem(
                    invoice=invoice,
                    description=item['description'],
                    quantity=item['quantity'],
                    price=item['price']
                )
                db.session.add(line_item)
            db.session.commit()

            return render_template('result.html', invoice=invoice, line_items=invoice_data['line_items'])

    return redirect(request.url)

@app.route('/output/<filename>')
def output_file(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

if __name__ == "__main__":
    app.run(debug=True)
