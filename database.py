import os.path
import fdb

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def get_database():
    try:
        con = fdb.connect(
            host='localhost',
            user='sysdba',
            database=os.path.join(BASE_DIR, 'BANCO.FDB'),
            password='sysdba',
        )
        return con
    except Exception as e:
        print(f"Houve um erro ao conectar: {str(e)}")

con = get_database()