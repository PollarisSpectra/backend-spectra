import fdb.fbcore
from flask import Blueprint, jsonify, request, current_app, send_from_directory, send_file
from funcao import decodificar_token
from database import con
import math
import jwt
import os

empresa_blueprint = Blueprint('empresa', __name__, url_prefix='/empresa')


@empresa_blueprint.route('/cadastro_empresa', methods=['POST'])
def cadastro_empresa():
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


        cur.execute("SELECT COUNT(*) FROM EMPRESA")

        total = cur.fetchone()[0]

        if total > 0:
            return jsonify({
                "error": "Empresa já cadastrada"
            }), 400

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
    cur = con.cursor()

    try:
        cor_botao = (request.form.get('COR_BOTAO') or '').strip()
        cor_principal = (request.form.get('COR_PRINCIPAL') or '').strip()
        cor_alerta = (request.form.get('COR_ALERTA') or '').strip()
        cor_fundo = (request.form.get('COR_FUNDO') or '').strip()
        cor_secundaria = (request.form.get('COR_SECUNDARIA') or '').strip()
        cor_texto = (request.form.get('COR_TEXTO') or '').strip()
        cor_destaque_texto = (request.form.get('COR_DESTAQUE_TEXTO') or '').strip()
        cor_hover = (request.form.get('COR_HOVER') or '').strip()
        cor_texto_destaque = (request.form.get('COR_TEXTO_DESTAQUE') or '').strip()
        cor_card = (request.form.get('COR_CARD') or '').strip()
        cor_formulario = (request.form.get('COR_FORMULARIO') or '').strip()
        cor_linha = (request.form.get('COR_LINHA') or '').strip()
        cor_modal = (request.form.get('COR_MODAL') or '').strip()
        cor_icone = (request.form.get('COR_ICONE') or '').strip()
        cor_texto_formulario = (request.form.get('COR_TEXTO_FORMULARIO') or '').strip()

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
                COR_TEXTO_FORMULARIO
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
        return jsonify({
            "error": "Token de autenticação necessário."
        }), 401

    cur = con.cursor()

    try:

        cor_botao = (request.form.get('COR_BOTAO') or '').strip()
        cor_principal = (request.form.get('COR_PRINCIPAL') or '').strip()
        cor_alerta = (request.form.get('COR_ALERTA') or '').strip()
        cor_fundo = (request.form.get('COR_FUNDO') or '').strip()
        cor_secundaria = (request.form.get('COR_SECUNDARIA') or '').strip()
        cor_texto = (request.form.get('COR_TEXTO') or '').strip()
        cor_destaque_texto = (request.form.get('COR_DESTAQUE_TEXTO') or '').strip()
        cor_hover = (request.form.get('COR_HOVER') or '').strip()
        cor_texto_destaque = (request.form.get('COR_TEXTO_DESTAQUE') or '').strip()
        cor_card = (request.form.get('COR_CARD') or '').strip()
        cor_formulario = (request.form.get('COR_FORMULARIO') or '').strip()
        cor_linha = (request.form.get('COR_LINHA') or '').strip()
        cor_modal = (request.form.get('COR_MODAL') or '').strip()
        cor_icone = (request.form.get('COR_ICONE') or '').strip()
        cor_texto_formulario = (request.form.get('COR_TEXTO_FORMULARIO') or '').strip()

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
                COR_TEXTO_FORMULARIO = ?
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
@empresa_blueprint.route('/buscar_cores', methods=['GET'])
def buscar_cores():

    cur = con.cursor()

    try:

        cur.execute("""
            SELECT
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
                COR_TEXTO_FORMULARIO
            FROM CORES
            ROWS 1
        """)

        cores = cur.fetchone()

        print(cores)

        if not cores:
            return jsonify({
                "error": "Nenhuma cor encontrada"
            }), 404

        return jsonify({
            "COR_BOTAO": cores[0],
            "COR_PRINCIPAL": cores[1],
            "COR_ALERTA": cores[2],
            "COR_FUNDO": cores[3],
            "COR_SECUNDARIA": cores[4],
            "COR_TEXTO": cores[5],
            "COR_DESTAQUE_TEXTO": cores[6],
            "COR_HOVER": cores[7],
            "COR_TEXTO_DESTAQUE": cores[8],
            "COR_CARD": cores[9],
            "COR_FORMULARIO": cores[10],
            "COR_LINHA": cores[11],
            "COR_MODAL": cores[12],
            "COR_ICONE": cores[13],
            "COR_TEXTO_FORMULARIO": cores[14]
        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500

    finally:
        cur.close()
        
@empresa_blueprint.route('/verificar_empresa', methods=['GET'])
def verificar_empresa():

    cur = con.cursor()

    try:

        cur.execute("""
            SELECT FIRST 1
                ID_EMPRESA,
                NOME_FANTASIA,
                TELEFONE,
                RUA,
                NUMERO,
                BAIRRO,
                CIDADE
            FROM EMPRESA
        """)

        empresa = cur.fetchone()

        if not empresa:

            return jsonify({
                "tem_empresa": False
            })

        endereco = (
            f"{empresa[3]}, "
            f"{empresa[4]} - "
            f"{empresa[5]}, "
            f"{empresa[6]}"
        )

        return jsonify({
            "tem_empresa": True,
            "id_empresa": int(empresa[0]),
            "nome_fantasia": empresa[1],
            "telefone": empresa[2],
            "endereco": endereco
        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500

    finally:
        cur.close()

@empresa_blueprint.route('/logo/<int:id>')
def obter_logo_empresa(id):


    caminho = os.path.join(
        current_app.config['UPLOAD_FOLDER'],
        "Empresas",
        f"{id}.jpg"
    )

    return send_file(caminho, mimetype='image/jpeg')

@empresa_blueprint.route('/buscar_empresa', methods=['GET'])
def buscar_empresa():

    cur = con.cursor()

    try:

        cur.execute("""
            SELECT FIRST 1
                ID_EMPRESA,
                NOME_FANTASIA,
                RAZAO_SOCIAL,
                CNPJ,
                BAIRRO,
                RUA,
                NUMERO,
                CIDADE,
                CHAVE_PIX,
                COR,
                TELEFONE
            FROM EMPRESA
        """)

        empresa = cur.fetchone()

        if not empresa:
            return jsonify({
                "error": "Empresa não encontrada"
            }), 404

        return jsonify({
            "id_empresa": empresa[0],
            "nome_fantasia": empresa[1],
            "razao_social": empresa[2],
            "cnpj": empresa[3],
            "bairro": empresa[4],
            "rua": empresa[5],
            "numero": empresa[6],
            "cidade": empresa[7],
            "chave_pix": empresa[8],
            "cor": empresa[9],
            "telefone": empresa[10]
        }), 200

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500

    finally:
        cur.close()