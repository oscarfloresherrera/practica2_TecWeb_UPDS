# models/__init__.py
from flask_sqlalchemy import SQLAlchemy

# Inicialización de la base de datos
db = SQLAlchemy()

# Importa los modelos definidos en models.py
from .models import db, Client, Product, Category, Detail, Bill, PaymentMethod, User
