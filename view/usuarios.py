from flask import Blueprint, jsonify, request, current_app
from flask_bcrypt import generate_password_hash
from funcao import validar_senha
from funcao import decodificar_token
from database import con
import os.path
import jwt

usuarios_blueprint = Blueprint('usuarios', __name__, url_prefix='/usuarios')

@usuarios_blueprint.route('/', methods=['GET'])
def todos_usuarios():
    try:
        token = request.cookies.get('access_token')
        
        if not token:
            return jsonify({"error": "Token necessário"}), 400
        
        payload = decodificar_token(token)

        if payload['tipo'] != 0:
            return jsonify({
                "error": "Acesso negado",
                "mensagem": "Você não tem permissão para realizar esta ação. Apenas administradores podem acessar este recurso."
            }), 403

        cursor = con.cursor()

        cursor.execute("select * from usuario")
        usuarios = cursor.fetchall()

        return jsonify({"message": "Usuários obtidos com sucesso", "usuarios": usuarios}) 
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expirado"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Token inválido"}), 401
    except Exception as e:
        print(str(e))
        return jsonify({"message": "Internal Server Error"}), 500

# Atualiza usuário
@usuarios_blueprint.route('/<int:id>', methods=['PUT'])
def editar_usuario(id):
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    try:
        payload = decodificar_token(token)
        id_usuario = payload['id_usuario']
        tipo = payload['tipo']

        if id_usuario != id and tipo != 0: # os ids são diferentes e não é administrador
            return jsonify({"error": "Você não pode editar outro usuário, apenas administradores."}), 401

    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Token invalid"}), 401

    cur = con.cursor()
    try:
        cur.execute('SELECT 1 FROM usuario WHERE id_usuario = ?', (id,))
        if not cur.fetchone():
            return jsonify({"error": "Usuário não encontrado"}), 404

        nome = request.form.get('nome')
        email = request.form.get('email')

        if not nome or not email:
            return jsonify({"error": "Nome e email são obrigatórios."}), 400

        email = request.form.get('email').strip().lower()
        senha = request.form.get('senha')
        data_nascimento = request.form.get('data_nascimento')
        imagem = request.files.get('imagem')

        cur.execute('SELECT 1 FROM usuario WHERE email = ? AND id_usuario != ?', (email, id))
        if cur.fetchone():
            return jsonify({"error": "Email já cadastrado"}), 400

        if not validar_senha(senha):
            return jsonify({"error": "Senha inválida"}), 400

        senha_hash = generate_password_hash(senha).decode('utf-8')

        cur.execute("""
            UPDATE usuario SET nome = ?, email = ?, data_nascimento = ?, senha = ?
            WHERE id_usuario = ? """, (nome, email, data_nascimento, senha_hash, id))
        con.commit()

        if imagem:
            nome_imagem = f"{id}.jpg"
            caminho_imagem_destino = os.path.join(current_app.config['UPLOAD_FOLDER'], "Usuarios")
            os.makedirs(caminho_imagem_destino, exist_ok=True)
            caminho_imagem = os.path.join(caminho_imagem_destino, nome_imagem)
            imagem.save(caminho_imagem)

        return jsonify({
            "message": "Usuário atualizado com sucesso",
            "usuario": {
                "id_usuario": id,
                "nome": nome,
                "email": email,
                "data_nascimento": data_nascimento
            }
        }), 200

    except Exception as e:
        return jsonify({
            "message": f"Erro ao atualizar usuário.{e}"
        }), 500

    finally:
        cur.close()

@usuarios_blueprint.route('/<int:id>', methods=["DELETE"])
def excluir(id):
    try:
        token = request.cookies.get('access_token')

        if not token:
            return jsonify({"error": "Token necessário"}), 400
        
        payload = decodificar_token(token)

        if payload['tipo'] != 0:
            return jsonify({
                "error": "Acesso negado",
                "mensagem": "Você não tem permissão para realizar esta ação. Apenas administradores podem acessar este recurso."
            }), 403

        cursor = con.cursor()

        cursor.execute("SELECT 1 FROM usuario WHERE id_usuario = ?", (id,))
        if not cursor.fetchone():
            return jsonify({"error": "Usuário não encontrado"}), 404

        cursor.execute("DELETE FROM usuario WHERE id_usuario = ?", (id,))
        con.commit()

        return jsonify({"message": "Usuário deletado com sucesso"}) 
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Token invalid"}), 401
    except Exception as e:
        print(str(e))
        con.rollback()
        return jsonify({"message": "Internal Server Error"}), 500
    
@usuarios_blueprint.route('/buscar_usuario', methods=['GET'])
def buscar_usuario():
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    try:
        payload = decodificar_token(token)
        # id_usuario = payload['id_usuario']
        tipo = payload['tipo']

        if tipo == 1:  # indica que o usuário não é administrador
            return jsonify({
                "error": "Acesso negado",
                "mensagem": "Você não tem permissão para realizar esta ação. Apenas administradores podem acessar este recurso."
            }), 403
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Token invalid"}), 401

    nome = request.args.get('nome')

    if not nome:
        return jsonify({"error": "Informe o nome do usuário"}), 400

    try:
        cur = con.cursor()

       # cur.execute('SELECT * FROM usuario WHERE nome = ?', (nome,))
        cur.execute('SELECT * FROM usuario WHERE lower(nome) LIKE ?', (f"%{nome.lower()}%",))
        usuarios = cur.fetchall()

        return jsonify({'usuarios': usuarios}), 200
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar usuário"}), 500
    finally:
        cur.close()

@usuarios_blueprint.route('/desbloquear_usuario/<int:id>', methods=['PUT'])
def desbloquear_usuario(id):
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    try:
        payload = decodificar_token(token)
        tipo = payload['tipo']

        if tipo == 1: # indica que o usuário não é administrador
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
        cur.execute("SELECT 1 FROM usuario WHERE id_usuario = ?", (id,))

        if not cur.fetchone():
            return jsonify({"error": "Usuário não encontrado."}), 404

        cur.execute("UPDATE usuario SET situacao = 0, tentativas = 0 WHERE id_usuario = ?", (id,))

        con.commit()
    except Exception as e:
        return jsonify({"error": "Houve um erro ao desbloquear usuário."}), 500
    finally:
        cur.close()

    return jsonify({"mensagem": "Usuário desbloqueado com sucesso"}), 200