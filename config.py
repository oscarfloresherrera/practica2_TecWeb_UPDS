import os

class Config:
    SQLALCHEMY_DATABASE_URI = "postgresql://postgres:1379@localhost/practica1"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "tu_clave_secreta_estatica"  # Cambia esto por una clave segura, fija y privada.
    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 7  # 7 días
