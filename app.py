from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from appe.models import db, User
from routes import main
# app.py
from routes import main

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.secret_key = '1234567812345678'  # Required for session storage

# Initialize SQLAlchemy with the app
db.init_app(app)

with app.app_context():
    db.create_all()

app.register_blueprint(main)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)