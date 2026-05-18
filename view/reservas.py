import base64
import io

import jwt
import qrcode
from flask import Blueprint, jsonify, request
from database import con
from funcao import decodificar_token, gerar_payload_pix

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
    cur = None
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
        WHERE r.STATUS = '3' AND r.ID_SESSAO = ?
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
        """, (None, id_usuario, id_sessao, (len(assentos) * valor_assento), 1))

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

        return jsonify({"message": "Reserva criada com sucesso", "id_reserva": id_reserva_criada})
    except jwt.ExpiredSignatureError as e:
        return jsonify({"error": "Expired token"}), 401
    except jwt.InvalidTokenError as e:
        return jsonify({"error": "Invalid token"}), 401
    except ValueError:
        return jsonify({"error": "Verifique o tipo dos campos"}), 400
    except Exception as e:
        con.rollback()
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        if cur:
            cur.close()

@reservas_bp.route('/pagamento/<int:id>', methods=["POST"])
def pagamento(id):
    try:
        cookie = request.cookies.get('access_token')

        if not cookie:
            return jsonify({"error": "Token de autenticacao necessario"}), 401

        payload = decodificar_token(cookie)

        if not id:
            return jsonify({"error": "Insira o id da reserva"}), 400

        cur = con.cursor()
        cur.execute("""
        UPDATE RESERVA r
        SET r.STATUS = '0'
        WHERE r.ID_RESERVA = ?
        """, (id,))

        con.commit()

        return jsonify({"message": "Reserva confirmada com sucesso"})
    except jwt.ExpiredSignatureError as e:
        return jsonify({"error": "Expired token"}), 401
    except jwt.InvalidTokenError as e:
        return jsonify({"error": "Invalid token"}), 401
    except Exception:
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        if cur:
            cur.close()

@reservas_bp.route('/gerar_qrcode/<int:id>', methods=["GET"])
def gerar_qrcode_reserva(id):
    cur = None

    try:
        cur = con.cursor()

        cur.execute("""
            SELECT valortotal AS valor_total
            FROM RESERVA
            WHERE id_reserva = ?
        """, (id,))

        res = cur.fetchone()

        if not res:
            return jsonify({
                "error": "Reserva inexistente"
            }), 404

        reserva = dict(zip(
            [desc[0].lower() for desc in cur.description],
            res
        ))

        valor_total = float(reserva['valor_total'])

        payload = gerar_payload_pix(
            "41317641809",
            "PAULO HENRIQUE SOUZA CAVALLINI",
            "BIRIGUI",
            valor_total
        )

        img = qrcode.make(payload)

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        img_base64 = base64.b64encode(
            buffer.getvalue()
        ).decode("utf-8")

        return jsonify({
            "valor": valor_total,
            "payload": payload,
            "qrcode": img_base64
        }), 200

    except Exception as e:
        print(str(e))

        return jsonify({
            "error": "Internal Server Error"
        }), 500

# rota de assentos ocupados por reserva
@reservas_bp.route('/<int:id>/assentos_ocupados', methods=["GET"])
def obter_assentos_ocupados(id):
    cur = con.cursor()

    try:
        cur.execute("""
        SELECT assala.ASSENTO
        FROM RESERVA_ASSENTO ra
        LEFT JOIN RESERVA r ON r.ID_RESERVA = ra.ID_RESERVA
        INNER JOIN ASSENTO_SALA assala ON assala.ID_ASSENTO_SALA = ra.ID_ASSENTO_SALA
        WHERE r.ID_SESSAO = ?;
        """, (id,))

        assentos_ocupados = cur.fetchall()
        print(assentos_ocupados)

        if not assentos_ocupados:
            return jsonify({"error": "Sessao nao encontrada"}), 404

        return jsonify({ "message": "Assentos ocupados obtidos com sucesso", "assentos": [assento[0] for assento in assentos_ocupados] }), 200

    except Exception as e:
        print("Erro ao obter assentos ocupados: " + str(e))
        return jsonify({"message": "Internal Server Error"}), 500
    finally:
        if cur:
            cur.close()

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

# endpoint para obter reservas do usuario
@reservas_bp.route("/<int:id>/usuario", methods=["GET"])
def obter_reservas_usuario(id):
    cur = None
    try:
        cur = con.cursor()

        cur.execute("""
        SELECT r.*, f.* FROM RESERVA r
        INNER JOIN SESSAO s ON r.ID_SESSAO = s.ID_SESSAO 
        INNER JOIN FILME f ON f.ID_FILME = s.ID_FILME
        WHERE ID_USUARIO = ?
        """, (id,))

        res = cur.fetchall()

        colunas = [desc[0].lower() for desc in cur.description]
        resultado = [dict(zip(colunas, reserva)) for reserva in res]

        return jsonify({ "message": "Reservas obtidas com sucesso", "reservas": resultado})
    except Exception as e:
        print(str(e))
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        if cur:
            cur.close()


