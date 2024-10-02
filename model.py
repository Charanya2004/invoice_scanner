from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Invoice(db.Model):
    __tablename__ = 'invoices'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), nullable=False)
    vendor_name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(20), nullable=False)  # Change to Date if needed
    total_amount = db.Column(db.Float, nullable=False)

    line_items = db.relationship('LineItem', backref='invoice', lazy=True)

class LineItem(db.Model):
    __tablename__ = 'line_items'
    
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey('invoices.id'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
