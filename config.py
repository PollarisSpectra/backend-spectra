import os.path

SECRET_KEY = "chave_secreta"
DEBUG = True

DB_HOST = 'localhost'
DB_NAME = r'C:\Users\Aluno\Documents\GitHub\backend-spectra\BANCO\BANCO.FDB'


DB_USER = 'sysdba'
DB_PASSWORD = 'sysdba'

UPLOAD_FOLDER = os.path.abspath(os.path.dirname(__file__))