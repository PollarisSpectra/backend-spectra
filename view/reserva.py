from flask import Blueprint, jsonify, request, current_app
from flask_bcrypt import generate_password_hash
from funcao import validar_senha
from funcao import decodificar_token
from database import con
import os.path
import jwt

reserva_blueprint = Blueprint('reserva', __name__, url_prefix='/reserva')

@reserva_blueprint.route('/selecionar_assentos', methods=['POST'])
def selecionar_assentos():
    cur = None

    try:
        cur = con.cursor()
        dados = request.get_json() or {}

        id_sessao = dados.get("id_sessao")
        assentos = dados.get("assentos", [])

        if not id_sessao:
            return jsonify({"error": "Sessão é obrigatória"}), 400

        if not assentos:
            return jsonify({"error": "Selecione pelo menos um assento"}), 400

        # 🔹 pegar sala da sessão
        cur.execute("""
            SELECT ID_SALA
            FROM SESSAO
            WHERE ID_SESSAO = ?
        """, (id_sessao,))

        resultado = cur.fetchone()

        if not resultado:
            return jsonify({"error": "Sessão não encontrada"}), 404

        id_sala = resultado[0]

        # 🔹 criar reserva
        cur.execute("""
            INSERT INTO RESERVA (ID_SESSAO)
            VALUES (?)
            RETURNING ID_RESERVA
        """, (id_sessao,))

        id_reserva = cur.fetchone()[0]

        # 🔹 inserir assentos
        for codigo in assentos:
            fileira = codigo[0]
            numero = int(codigo[1:])

            # 🔴 verificar se já está reservado
            cur.execute("""
                SELECT 1
                FROM RESERVA_ASSENTO ra
                INNER JOIN ASSENTO_SALA a 
                    ON a.ID_ASSENTO_SALA = ra.ID_ASSENTO_SALA
                INNER JOIN RESERVA r 
                    ON r.ID_RESERVA = ra.ID_RESERVA
                WHERE r.ID_SESSAO = ?
                AND a.FILEIRA = ?
                AND a.NUMERO = ?
            """, (id_sessao, fileira, numero))

            if cur.fetchone():
                con.rollback()
                return jsonify({
                    "error": f"O assento {codigo} já está reservado"
                }), 400

            # 🔹 pegar id_assento_sala
            cur.execute("""
                SELECT ID_ASSENTO_SALA
                FROM ASSENTO_SALA
                WHERE ID_SALA = ?
                AND FILEIRA = ?
                AND NUMERO = ?
            """, (id_sala, fileira, numero))

            resultado_assento = cur.fetchone()

            if not resultado_assento:
                con.rollback()
                return jsonify({
                    "error": f"Assento {codigo} não encontrado"
                }), 404

            id_assento_sala = resultado_assento[0]

            # 🔹 INSERT correto
            cur.execute("""
                INSERT INTO RESERVA_ASSENTO (ID_RESERVA, ID_ASSENTO_SALA)
                VALUES (?, ?)
            """, (id_reserva, id_assento_sala))

        con.commit()

        return jsonify({
            "message": "Assentos reservados com sucesso!",
            "id_reserva": id_reserva
        }), 201

    except Exception as e:
        con.rollback()
        return jsonify({
            "error": f"Erro ao selecionar assentos: {str(e)}"
        }), 500

    finally:
        if cur:
            cur.close()