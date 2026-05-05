from flask import Blueprint, jsonify, request
from database import con

reservas_bp = Blueprint('reservas', __name__, url_prefix='/reservas')

# Rota de consulta de reserva
@reservas_bp.route("/<int:id>")
def reservas(id):

    if not id:
        return jsonify({"error": "Campo 'id' necessario"}), 400

    try:
        cur = con.cursor()
        cur.execute("SELECT * FROM reserva WHERE id_reserva = ?", (id,))

        rawReserva = cur.fetchone()

        if not rawReserva:
            return jsonify({"error": "Reserva nao encontrada"}), 404

        columns = [desc[0].lower() for desc in cur.description]
        reserva = dict(zip(columns, rawReserva))

        return jsonify({ "message": "Sucesso ao consultar reserva", "reserva": reserva }), 200
    except Exception as e:
        return jsonify({"error": "Internal Server Error"}), 500

# Rota de criação de reserva
@reservas_bp.route("/", methods=["POST"])
def criar_reserva():
    try:
        data = request.json()
        return jsonify({"message": data})
    except Exception:
        return jsonify({"error": "Internal Server Error"}), 500

# Rota de exclusão de reserva
@reservas_bp.route("/", methods=["DELETE"])
def excluir_reserva(id):
    try:
        pass
    except Exception:
        return jsonify({"error": "Internal Server Error"}), 500