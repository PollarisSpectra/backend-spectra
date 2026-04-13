from flask import Blueprint, jsonify, request
from funcao import decodificar_token
from database import con
import jwt

salas_blueprint = Blueprint('salas', __name__, url_prefix='/salas')

@salas_blueprint.route('/cadastro_sala', methods=['POST'])
def cadastro_sala():
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    cur = con.cursor()

    try:
        data = request.get_json() or {}

        nome = data.get('nome', '').strip()
        if not nome or nome == '':
            return jsonify({"error": "Nome é obrigatório"}), 400

        qtd_fileiras = data.get('qtd_fileiras')
        if not qtd_fileiras or qtd_fileiras == '':
            return jsonify({"error": "Quantidade de fileiras é obrigatória"}), 400

        qtd_colunas = data.get('qtd_colunas')
        if not qtd_colunas or qtd_colunas == '':
            return jsonify({"error": "Quantidade de colunas é obrigatória"}), 400

        print(qtd_fileiras)
        print(qtd_colunas)
        print(nome)

        cur.execute('SELECT 1 FROM sala WHERE nome = ?', (nome,))
        if cur.fetchone():
            return jsonify({"error": "Nome da sala já está cadastrado"}), 400

        print(qtd_fileiras)
        print(qtd_colunas)
        print(nome)

        cur.execute("""
            INSERT INTO sala(nome, qtd_fileiras, qtd_colunas)
            VALUES(?, ?, ?)
        """, (nome.lower(), qtd_fileiras, qtd_colunas))

        con.commit()

        return jsonify({"message": "Sala cadastrada com sucesso!"}), 200

    except Exception as e:
        con.rollback()
        return jsonify({
            "message": f"Erro ao cadastrar sala: {e}"
        }), 500

    finally:
        cur.close()

@salas_blueprint.route('/editar_sala/<int:id>', methods=['PUT'])
def editar_sala(id):
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    try:
        cur = con.cursor()
        cur.execute('SELECT 1 FROM sala WHERE id_sala = ?', (id,))
        if not cur.fetchone():
            return jsonify({"error": "Sala não encontrada"}), 404


        dados = request.get_json()

        nome = dados.get('nome')
        qtd_fileiras = dados.get('qtd_fileiras')
        qtd_colunas = dados.get('qtd_colunas')

        cur.execute('SELECT 1 FROM sala WHERE nome = ? AND id_sala != ?', (nome.lower(), id))
        if cur.fetchone():
            return jsonify({"error": "Nome da sala já está cadastrado"}), 400


        print(nome)
        print(qtd_fileiras)
        print(qtd_colunas)
        print(id)

        cur.execute("""
                    UPDATE sala SET nome = ?, qtd_fileiras = ?, qtd_colunas = ?
                    WHERE id_sala = ? """, (nome, qtd_fileiras, qtd_colunas, id))
        con.commit()

        return jsonify({
            "message": "Sala atualizada com sucesso",
            "sala": {
                "id_sala": id,
                "nome": nome,
                "qtd_fileiras": qtd_fileiras,
                "qtd_colunas": qtd_colunas
            }
        }), 200

    except Exception as e:
        return jsonify({
            "message": f"Erro ao atualizar sala.{e}"
        }), 500

    finally:
        cur.close()


@salas_blueprint.route('/excluir_sala/<int:id>', methods=['DELETE'])
def excluir_sala(id):
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    try:
        payload = decodificar_token(token)
        id_usuario = payload['id_usuario']
        tipo = payload['tipo']

        if tipo == 1:
            return jsonify({
                "error": "Acesso negado",
                "mensagem": "Você não tem permissão para realizar esta ação. Apenas administradores podem acessar este recurso."
            }), 403
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Token invalid"}), 401

    cur = con.cursor()
    try:
        cur.execute('SELECT 1 FROM sala WHERE id_sala = ?', (id,))
        if not cur.fetchone():
            return jsonify({"error": "Sala não encontrada"}), 404

        cur.execute('SELECT 1 FROM sessao WHERE id_sala = ?', (id,))
        if cur.fetchone():
            return jsonify({"error": "Não é possível excluir a sala com sessões vinculadas"}), 400

        cur.execute('DELETE FROM ASSENTO_SALA WHERE ID_SALA = ?', (id,))
        cur.execute('DELETE FROM SALA WHERE ID_SALA = ?', (id,))
        con.commit()

        return jsonify({"message": "Sala excluída com sucesso"}), 200

    except Exception as e:
        return jsonify({"error": f"Erro ao excluir sala."}), 500

    finally:
        cur.close()


@salas_blueprint.route('/listar_sala', methods=['GET'])
def listar_sala():
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    try:
        payload = decodificar_token(token)
        id_usuario = payload['id_usuario']
        tipo = payload['tipo']

        if tipo == 1:
            return jsonify({
                "error": "Acesso negado",
                "mensagem": "Você não tem permissão para realizar esta ação. Apenas administradores podem acessar este recurso."
            }), 403
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Token invalid"}), 401

    try:
        cur = con.cursor()
        cur.execute('SELECT * FROM sala')
        salas = cur.fetchall()
        return jsonify({'salas': salas}), 200
    except Exception as e:
        return jsonify({"error": f"Erro ao listar salas"}), 500
    finally:
        cur.close()