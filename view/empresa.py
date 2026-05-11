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

        chave_pix = (request.form.get('chave_pix') or '').strip()
        cor = (request.form.get('cor') or '').strip()
        telefone = (request.form.get('telefone') or '').strip()

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
                COR,
                TELEFONE
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            cor,
            telefone
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
        chave_pix = (request.form.get('chave_pix') or '').strip()
        cor = (request.form.get('cor') or '').strip()
        telefone = (request.form.get('telefone') or '').strip()

        imagem = request.files.get('imagem')

        if cnpj:
            cur.execute("""
                SELECT 1 
                FROM EMPRESA 
                WHERE CNPJ = ? AND ID_EMPRESA != ?
            """, (cnpj, id))

            if cur.fetchone():
                return jsonify({"error": "CNPJ já pertence a outra empresa"}), 400

        if nome_fantasia:
            cur.execute("""
                SELECT 1 
                FROM EMPRESA 
                WHERE NOME_FANTASIA = ? AND ID_EMPRESA != ?
            """, (nome_fantasia, id))

            if cur.fetchone():
                return jsonify({"error": "Nome fantasia já existe"}), 400

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
                COR = ?,
                TELEFONE = ?
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
            telefone,
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


@empresa_blueprint.route('/cadastro_cores', methods=['POST'])
def cadastro_cores():
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    cur = con.cursor()

    try:
        cor_botao = (request.form.get('cor_botao') or '').strip()
        cor_principal = (request.form.get('cor_principal') or '').strip()
        cor_alerta = (request.form.get('cor_alerta') or '').strip()
        cor_fundo = (request.form.get('cor_fundo') or '').strip()
        cor_secundaria = (request.form.get('cor_secundaria') or '').strip()
        cor_texto = (request.form.get('cor_texto') or '').strip()
        cor_destaque_texto = (request.form.get('cor_destaque_texto') or '').strip()
        cor_hover = (request.form.get('cor_hover') or '').strip()
        cor_texto_destaque = (request.form.get('cor_texto_destaque') or '').strip()
        cor_card = (request.form.get('cor_card') or '').strip()
        cor_formulario = (request.form.get('cor_formulario') or '').strip()
        cor_linha = (request.form.get('cor_linha') or '').strip()
        cor_modal = (request.form.get('cor_modal') or '').strip()
        cor_icone = (request.form.get('cor_icone') or '').strip()
        cor_texto_formulario = (request.form.get('cor_texto_formulario') or '').strip()

        cur.execute("""
            INSERT INTO CORES (
                COR_BOTAO,
                COR_PRINCIPAL,
                COR_ALERTA,
                COR_FUNDO,
                COR_SECUNDARIA,
                COR_TEXTO,
                COR_DESTAQUE_TEXTO,
                COR_HOVER,
                COR_TEXTO_DESTAQUE,
                COR_CARD,
                COR_FORMULARIO,
                COR_LINHA,
                COR_MODAL,
                COR_ICONE, 
                COR_TEXTO_FORMULARIO,
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cor_botao,
            cor_principal,
            cor_alerta,
            cor_fundo,
            cor_secundaria,
            cor_texto,
            cor_destaque_texto,
            cor_hover,
            cor_texto_destaque,
            cor_card,
            cor_formulario,
            cor_linha,
            cor_modal,
            cor_icone,
            cor_texto_formulario,
        ))

        con.commit()

        return jsonify({
            "message": "Cores cadastradas com sucesso!"
        }), 200

    except Exception as e:
        con.rollback()
        return jsonify({
            "error": f"Erro ao cadastrar cores: {str(e)}"
        }), 500

    finally:
        cur.close()

@empresa_blueprint.route('/editar_cores/<int:id_empresa>', methods=['PUT'])
def editar_cores(id_empresa):
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    cur = con.cursor()

    try:
        cor_botao = (request.form.get('cor_botao') or '').strip()
        cor_principal = (request.form.get('cor_principal') or '').strip()
        cor_alerta = (request.form.get('cor_alerta') or '').strip()
        cor_fundo = (request.form.get('cor_fundo') or '').strip()
        cor_secundaria = (request.form.get('cor_secundaria') or '').strip()
        cor_texto = (request.form.get('cor_texto') or '').strip()
        cor_destaque_texto = (request.form.get('cor_destaque_texto') or '').strip()
        cor_hover = (request.form.get('cor_hover') or '').strip()
        cor_texto_destaque = (request.form.get('cor_texto_destaque') or '').strip()
        cor_card = (request.form.get('cor_card') or '').strip()
        cor_formulario = (request.form.get('cor_formulario') or '').strip()
        cor_linha = (request.form.get('cor_linha') or '').strip()
        cor_modal = (request.form.get('cor_modal') or '').strip()
        cor_icone = (request.form.get('cor_icone') or '').strip()
        cor_texto_formulario = (request.form.get('cor_texto_formulario') or '').strip()

        cur.execute("""
            UPDATE CORES
            SET
                COR_BOTAO = ?,
                COR_PRINCIPAL = ?,
                COR_ALERTA = ?,
                COR_FUNDO = ?,
                COR_SECUNDARIA = ?,
                COR_TEXTO = ?,
                COR_DESTAQUE_TEXTO = ?,
                COR_HOVER = ?,
                COR_TEXTO_DESTAQUE = ?,
                COR_CARD = ?,
                COR_FORMULARIO = ?,
                COR_LINHA = ?,
                COR_MODAL = ?,
                COR_ICONE = ?,
                COR_TEXTO_FORMULARIO = ?,
            WHERE ID_EMPRESA = ?
        """, (
            cor_botao,
            cor_principal,
            cor_alerta,
            cor_fundo,
            cor_secundaria,
            cor_texto,
            cor_destaque_texto,
            cor_hover,
            cor_texto_destaque,
            cor_card,
            cor_formulario,
            cor_linha,
            cor_modal,
            cor_icone,
            cor_texto_formulario,
            id_empresa
        ))

        con.commit()

        return jsonify({
            "message": "Cores atualizadas com sucesso!"
        }), 200

    except Exception as e:
        con.rollback()
        return jsonify({
            "error": f"Erro ao atualizar cores: {str(e)}"
        }), 500

    finally:
        cur.close()
