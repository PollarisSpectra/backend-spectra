import secrets
import jwt
from funcao import validar_senha, enviando_email, encode_password, gerar_token, decodificar_token
from flask import Blueprint, jsonify, request, make_response, current_app, render_template

auth_blueprint = Blueprint('banner', __name__, url_prefix='/banner')

import os
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from database import con

banner_blueprint = Blueprint('banner', __name__, url_prefix='/banner')


@banner_blueprint.route('/cadastro', methods=['POST'])
def cadastro_banner():
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    cur = con.cursor()

    try:
        titulo = (request.form.get('titulo') or '').strip()
        texto = (request.form.get('texto') or '').strip()
        situacao = (request.form.get('situacao') or '').strip()

        imagem = request.files.get('imagem')

        if not titulo:
            return jsonify({"error": "O título do banner é obrigatório"}), 400

        if not situacao:
            return jsonify({"error": "A situação do banner é obrigatória"}), 400

        cur.execute("""
            INSERT INTO BANNER (
                TITULO,
                TEXTO,
                SITUACAO
            )
            VALUES (?, ?, ?)
            RETURNING ID_BANNER
        """, (
            titulo,
            texto,
            situacao
        ))

        id_banner = cur.fetchone()[0]
        con.commit()

        if imagem:
            nome_imagem = f"{id_banner}.jpg"
            pasta = os.path.join(current_app.config['UPLOAD_FOLDER'], "Banner")
            os.makedirs(pasta, exist_ok=True)

            caminho = os.path.join(pasta, nome_imagem)
            imagem.save(caminho)

        return jsonify({
            "message": "Banner cadastrado com sucesso!",
            "id_banner": id_banner
        }), 200

    except Exception as e:
        return jsonify({
            "error": f"Erro ao cadastrar banner: {str(e)}"
        }), 500

    finally:
        cur.close()


@banner_blueprint.route('/editar/<int:id>', methods=['PUT'])
def editar_banner(id):
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401


    cur = con.cursor()

    try:
        cur.execute("SELECT 1 FROM BANNER WHERE ID_BANNER = ?", (id,))

        if not cur.fetchone():
            return jsonify({"error": "Banner não encontrado"}), 404

        titulo = (request.form.get('titulo') or '').strip()
        texto = (request.form.get('texto') or '').strip()
        situacao = (request.form.get('situacao') or '').strip()

        imagem = request.files.get('imagem')

        if not titulo:
            return jsonify({"error": "O título do banner é obrigatório"}), 400

        if not situacao:
            return jsonify({"error": "A situação do banner é obrigatória"}), 400

        cur.execute("""
            UPDATE BANNER SET
                TITULO = ?,
                TEXTO = ?,
                SITUACAO = ?
            WHERE ID_BANNER = ?
        """, (
            titulo,
            texto,
            situacao,
            id
        ))

        con.commit()

        if imagem:
            nome_imagem = f"{id}.jpg"
            pasta = os.path.join(current_app.config['UPLOAD_FOLDER'], "Banner")
            os.makedirs(pasta, exist_ok=True)

            caminho = os.path.join(pasta, nome_imagem)
            imagem.save(caminho)

        return jsonify({
            "message": "Banner atualizado com sucesso!"
        }), 200

    except Exception as e:
        return jsonify({
            "error": f"Erro ao editar banner: {str(e)}"
        }), 500

    finally:
        cur.close()


@banner_blueprint.route('/excluir/<int:id>', methods=['DELETE'])
def excluir_banner(id):

    token = request.cookies.get('access_token')
    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    cur = con.cursor()

    try:
        cur.execute("SELECT 1 FROM BANNER WHERE ID_BANNER = ?", (id,))

        if not cur.fetchone():
            return jsonify({"error": "Banner não encontrado"}), 404

        cur.execute("DELETE FROM BANNER WHERE ID_BANNER = ?", (id,))
        con.commit()

        pasta = os.path.join(current_app.config['UPLOAD_FOLDER'], "Banner")
        caminho = os.path.join(pasta, f"{id}.jpg")

        if os.path.exists(caminho):
            os.remove(caminho)

        return jsonify({
            "message": "Banner excluído com sucesso!"
        }), 200

    except Exception as e:
        return jsonify({
            "error": f"Erro ao excluir banner: {str(e)}"
        }), 500

    finally:
        cur.close()


@banner_blueprint.route('/listar', methods=['GET'])
def listar_banners():

    cur = con.cursor()

    try:
        cur.execute("""
            SELECT
                ID_BANNER,
                TITULO,
                TEXTO,
                SITUACAO
            FROM BANNER
            WHERE SITUACAO = '1'
            ORDER BY ID_BANNER
        """)

        dados = cur.fetchall()

        banners = []

        for item in dados:
            banners.append({
                "id_banner": item[0],
                "titulo": item[1],
                "texto": item[2],
                "situacao": item[3],
                "imagem": f"/Banner/{item[0]}.jpg"
            })

        return jsonify({
            "banners": banners
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

    finally:
        cur.close()


@banner_blueprint.route('/imagem_banner/<path:filename>')
def servir_imagem_banner(filename):
    caminho = os.path.join(current_app.config['UPLOAD_FOLDER'], "Banner")
    return send_from_directory(caminho, filename)




@banner_blueprint.route('/<int:id>', methods=['GET'])
def buscar_banner(id):

    token = request.cookies.get('access_token')

    if not token:
        return jsonify({
            "error": "Token de autenticação necessário."
        }), 401

    cur = con.cursor()

    try:

        cur.execute("""
            SELECT
                ID_BANNER,
                TITULO,
                TEXTO,
                SITUACAO
            FROM BANNER
            WHERE ID_BANNER = ?
        """, (id,))

        banner = cur.fetchone()

        if not banner:
            return jsonify({
                "error": "Banner não encontrado"
            }), 404

        dados = {
            "id": banner[0],
            "titulo": banner[1],
            "texto": banner[2],
            "situacao": banner[3],
            "imagem": f"uploads/Banner/{banner[0]}.jpg"
        }

        return jsonify(dados), 200

    except Exception as e:
        return jsonify({
            "error": f"Erro ao buscar banner: {str(e)}"
        }), 500

    finally:
        cur.close()