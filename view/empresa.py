import fdb.fbcore
from flask import Blueprint, jsonify, request, current_app, send_from_directory
from funcao import decodificar_token
from database import con
import math
import jwt
import os

empresa_blueprint = Blueprint('empresa', __name__, url_prefix='/empresa')


@empresa_blueprint.route('/cadastro_empresa', methods=['POST'])
def cadastro_empresa():
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    cur = con.cursor()

    try:
        nome_fantasia = (request.form.get('nome_fantasia') or '').strip()
        if not nome_fantasia:
            return jsonify({"error": "O nome da empresa é obrigatório"}), 400

        razao_social = (request.form.get('razao_social') or '').strip()
        if not razao_social:
            return jsonify({"error": "Razão social é obrigatória"}), 400

        cnpj = (request.form.get('cnpj') or '').strip()
        cep = (request.form.get('cep') or '').strip()
        bairro = (request.form.get('bairro') or '').strip()
        rua = (request.form.get('rua') or '').strip()
        numero = (request.form.get('numero') or '').strip()
        cidade = (request.form.get('cidade') or '').strip()
        uf = (request.form.get('uf') or '').strip()

        chave_pix = (request.form.get('chave_pix') or '').strip()
        cor = (request.form.get('cor') or '').strip()

        imagem = request.files.get('imagem')

        if cnpj:
            cur.execute('SELECT 1 FROM EMPRESA WHERE CNPJ = ?', (cnpj,))
            if cur.fetchone():
                return jsonify({"error": "Empresa já cadastrada"}), 400

        cur.execute("""
            INSERT INTO EMPRESA (
                NOME_fantasia,
                RAZAO_SOCIAL,
                CNPJ,
                BAIRRO,
                RUA,
                NUMERO,
                CIDADE,
                CHAVE_PIX,
                COR
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING ID_EMPRESA
        """, (
            nome_fantasia,
            razao_social,
            cnpj,
            bairro,
            rua,
            numero,
            cidade,
            chave_pix,
            cor
        ))

        id_empresa = cur.fetchone()[0]
        con.commit()

        if imagem:
            nome_imagem = f"{id_empresa}.jpg"
            pasta = os.path.join(current_app.config['UPLOAD_FOLDER'], "Empresas")
            os.makedirs(pasta, exist_ok=True)

            caminho = os.path.join(pasta, nome_imagem)
            imagem.save(caminho)

        return jsonify({
            "message": "Empresa cadastrada com sucesso!",
            "id_empresa": id_empresa
        }), 200

    except Exception as e:
        return jsonify({
            "error": f"Erro ao cadastrar empresa: {str(e)}"
        }), 500

    finally:
        cur.close()


@empresa_blueprint.route('/listar_empresas', methods=['GET'])
def listar_empresas():
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    cur = con.cursor()

    try:
        cur.execute("""
            SELECT 
                ID_EMPRESA,
                NOME_FANTASIA,
                RAZAO_SOCIAL,
                CNPJ,
                BAIRRO,
                RUA,
                NUMERO,
                CIDADE,
                CHAVE_PIX,
                COR
            FROM EMPRESA
        """)

        empresas = cur.fetchall()

        resultado = []

        for i in empresas:
            resultado.append({
                "id_empresa": i[0],
                "nome_fantasia": i[1],
                "razao_social": i[2],
                "cnpj": i[3],
                "bairro": i[4],
                "rua": i[5],
                "numero": i[6],
                "cidade": i[7],
                "chave_pix": i[8],
                "telefone": i[9],
                "cor": i[9]
            })

        return jsonify({"empresas": resultado}), 200

    except Exception as e:
        return jsonify({"error": f"Erro ao listar empresas: {str(e)}"}), 500

    finally:
        cur.close()


@empresa_blueprint.route('/editar_empresa/<int:id>', methods=['PUT'])
def editar_empresa(id):
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    cur = con.cursor()

    try:
        cur.execute("SELECT 1 FROM EMPRESA WHERE ID_EMPRESA = ?", (id,))
        if not cur.fetchone():
            return jsonify({"error": "Empresa não encontrada"}), 404

        nome_fantasia = (request.form.get('nome_fantasia') or '').strip()
        razao_social = (request.form.get('razao_social') or '').strip()
        cnpj = (request.form.get('cnpj') or '').strip()
        bairro = (request.form.get('bairro') or '').strip()
        rua = (request.form.get('rua') or '').strip()
        numero = (request.form.get('numero') or '').strip()
        cidade = (request.form.get('cidade') or '').strip()
        uf = (request.form.get('uf') or '').strip()
        chave_pix = (request.form.get('chave_pix') or '').strip()
        cor = (request.form.get('cor') or '').strip()

        imagem = request.files.get('imagem')

        cur.execute("""
            UPDATE EMPRESA SET
                NOME_FANTASIA = ?,
                RAZAO_SOCIAL = ?,
                CNPJ = ?,
                BAIRRO = ?,
                RUA = ?,
                NUMERO = ?,
                CIDADE = ?,
                CHAVE_PIX = ?,
                COR = ?
            WHERE ID_EMPRESA = ?
        """, (
            nome_fantasia,
            razao_social,
            cnpj,
            bairro,
            rua,
            numero,
            cidade,
            chave_pix,
            cor,
            id
        ))

        con.commit()

        if imagem:
            nome_imagem = f"{id}.jpg"
            pasta = os.path.join(current_app.config['UPLOAD_FOLDER'], "Empresas")
            os.makedirs(pasta, exist_ok=True)

            caminho = os.path.join(pasta, nome_imagem)
            imagem.save(caminho)

        return jsonify({"message": "Empresa atualizada com sucesso!"}), 200

    except Exception as e:
        return jsonify({"error": f"Erro ao editar empresa: {str(e)}"}), 500

    finally:
        cur.close()