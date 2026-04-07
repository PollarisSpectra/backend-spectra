import os.path

SECRET_KEY = "chave_secreta"
DEBUG = True

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DB_HOST = 'localhost'
DB_NAME = os.path.join(BASE_DIR, 'BANCO.FDB')

DB_USER = 'sysdba'
DB_PASSWORD = 'sysdba'

UPLOAD_FOLDER = os.path.abspath(os.path.dirname(__file__))