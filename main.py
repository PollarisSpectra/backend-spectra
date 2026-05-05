from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=['http://localhost:5173', 'http://127.0.0.1:5173'])
app.config.from_pyfile('config.py')

from view.auth import auth_blueprint
from view.usuarios import usuarios_blueprint
from view.filmes import filmes_blueprint
from view.salas import salas_blueprint
from view.sessao import sessao_blueprint
from view.reservas import reservas_bp
from view.pix import pix_blueprint
from view.empresa import empresa_blueprint

app.register_blueprint(auth_blueprint)
app.register_blueprint(usuarios_blueprint)
app.register_blueprint(filmes_blueprint)
app.register_blueprint(salas_blueprint)
app.register_blueprint(sessao_blueprint)
app.register_blueprint(reservas_bp)
app.register_blueprint(pix_blueprint)
app.register_blueprint(empresa_blueprint)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)