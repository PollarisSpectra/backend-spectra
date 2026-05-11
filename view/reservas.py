import jwt
from flask import Blueprint, jsonify, request
from database import con
from funcao import decodificar_token

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
    finally:
        if cur:
            cur.close()

# Rota de criação de reserva
# [-] TODO:
# - validar se o assento já está reservado para aquela sessão (busca por sessao)
@reservas_bp.route("/", methods=["POST"])
def criar_reserva():
    try:
        cookie = request.cookies.get('access_token', '')

        if not cookie:
            return jsonify({"error": "Token de autenticacao necessario"}), 401

        payload = decodificar_token(cookie)
        id_usuario = payload['id_usuario']

        data = request.json

        if not data:
            return jsonify({"error": "Payload necessario"}), 400

        id_sessao = int(data["id_sessao"])
        assentos = list(data["assentos"])

        if not id_sessao or not assentos:
            return jsonify({"error": "Insira todos os campos"}), 400

        cur = con.cursor()

        cur.execute("""
        SELECT * FROM RESERVA_ASSENTO ra
        LEFT JOIN RESERVA r ON r.ID_RESERVA = ra.ID_RESERVA
        WHERE r.ID_SESSAO = ?
        """, (id_sessao,))

        columns = [desc[0].lower() for desc in cur.description]
        assentos_sessao = [dict(zip(columns, assento)) for assento in cur.fetchall()]

        for reserva in assentos_sessao:
            if reserva['id_assento_sala'] in assentos:
                return jsonify({"error": f"Poltrona(s) ja reservada(s)"}), 400

        # obtendo o valor do assento para a sessão
        cur.execute("SELECT valor_assento FROM sessao WHERE id_sessao = ?", (id_sessao,))
        valor_assento = cur.fetchone()[0]

        # criando reserva com valor de assento
        cur.execute("""
        INSERT INTO reserva (id_promocao, id_usuario, id_sessao, valortotal, desconto, status, datareserva)
        VALUES (?, ?, ?, ?, 0, ?, CURRENT_TIMESTAMP)
        RETURNING id_reserva
        """, (None, id_usuario, id_sessao, (len(assentos) * valor_assento), 3))

        # conferindo se a reserva foi criada
        id_reserva_criada = cur.fetchone()[0]
        if not id_reserva_criada:
            raise Exception("Internal Server Error")

        dados = [
            (id_reserva_criada, id_assento)
            for id_assento in assentos
        ]

        # criando cada reserva_assento
        cur.executemany("""
        INSERT INTO reserva_assento (id_reserva, id_assento_sala)
        VALUES (?, ?)
        """, dados)

        con.commit()

        return jsonify({"message": "Reserva criada com sucesso"})
    except jwt.ExpiredSignatureError as e:
        return jsonify({"error": "Expired token"}), 401
    except jwt.InvalidTokenError as e:
        return jsonify({"error": "Invalid token"}), 401
    except ValueError:
        return jsonify({"error": "Verifique o tipo dos campos"}), 400
    except Exception as e:
        con.rollback()
        return jsonify({"error": "Internal Server Error"}), 500

# Rota de exclusão de reserva
@reservas_bp.route("/<int:id>", methods=["DELETE"])
def excluir_reserva(id):
    try:
        cur = con.cursor()
        cur.execute("SELECT 1 FROM reserva WHERE id_reserva = ?", (id,))

        if not cur.fetchone():
            return jsonify({"error": "Reserva nao encontrada"}), 404

        # falta validar se tem violação de FK aqui

        cur.execute("DELETE FROM reserva WHERE id_reserva = ?", (id,))
        con.commit()

        return jsonify({"message": "Reserva excluida com sucesso"})
    except Exception:
        con.rollback()
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        if cur:
            cur.close()