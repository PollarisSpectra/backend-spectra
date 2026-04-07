from funcao import validar_senha, enviando_email, encode_password
from flask import Blueprint, jsonify, request, make_response
from flask_bcrypt import check_password_hash
from database import con
import threading
import os.path
import random

auth_blueprint = Blueprint('auth', __name__, url_prefix='/auth')

@auth_blueprint.route('/login', methods=["POST"])
def login():
    try:
        data = request.get_json()
        print(data)
        email = data.get('email')
        senha = data.get('senha')

        if not data:
            return jsonify({"error": "Payload json faltando"}), 400

        if not email or not senha:
            return jsonify({"error": "Email e senha obrigatórios"}), 400

        cursor = con.cursor()
        cursor.execute("SELECT senha, id_usuario, nome, tipo FROM usuario WHERE email = ?", (email,))

        usuario = cursor.fetchone()

        if not usuario:
            return jsonify({"error": "Usuário não encontrado"}), 404

        if not check_password_hash(usuario[0], senha):
            return jsonify({"error": "Email ou senha incorretos"}), 401

        response = make_response(jsonify({
            'mensagem': 'Logado com sucesso',
            'usuario': {
                'id_usuario': usuario[1],
                'nome': usuario[2],
                'tipo': usuario[3]
            }
        }), 200)

        return response
    except Exception as e:
        print(f"Houve um erro: {e}")
        return jsonify({"error": "Internal server error"}), 500

@auth_blueprint.route('/register', methods=['POST'])
def cadastro_usuario():
    cur = con.cursor()
    try:
        nome = request.form.get('nome')
        email = request.form.get('email')

        if (not nome or nome == '') or (not email or email == ''):
            return jsonify({"error": "Nome e email são obrigatórios"}), 400

        nome = nome.strip()
        email = email.strip().lower()

        data_nascimento = request.form.get('data_nascimento')
        senha = request.form.get('senha')
        imagem = request.files.get('imagem')

        validado = validar_senha(senha)

        if not validado:
            return jsonify({"error": "A senha não segue nossos padrões de segurança"}), 400

        cur.execute('select 1 from usuario where email = ?', (email,))
        if cur.fetchone():
            return jsonify({"error": "Email já cadastrado"}), 400

        codigo = random.randint(000000, 999999)
        senha_hash = encode_password(senha)
        cur.execute("""
                    insert into usuario(nome, email, data_nascimento, senha, tipo,email_confirmado, codigo)
                       values(?, ?, ?, ?, ?, ?, ?) RETURNING id_usuario
                    """, (nome, email, data_nascimento, senha_hash,1,  0, codigo))

        id_usuario = cur.fetchone()[0]
        con.commit()
        caminho_imagem = None

        if imagem:
            nome_imagem = f"{id_usuario}.jpg"
            caminho_imagem_destino = os.path.join(app.config['UPLOAD_FOLDER'], "Usuarios")
            os.makedirs(caminho_imagem_destino, exist_ok=True)
            caminho_imagem = os.path.join(caminho_imagem_destino, nome_imagem)
            imagem.save(caminho_imagem)
        try:
            assunto = 'Confirmação de Email'
            mensagem = f'Confirme aqui seu email: {codigo}'
            thread = threading.Thread(target=enviando_email,
                                      args=(email, assunto, mensagem))
            thread.start()
            return jsonify({"mensagem": "Email enviado com sucesso!"}), 200
        except Exception as e:
            return jsonify({"mensagem": f"Erro ao enviar email {e}!"}), 200
    except Exception as e:
        print(f"Houve um erro: {e}")
        return jsonify({"error": "Internal server error"}), 500
    finally:
        cur.close()

@auth_blueprint.route('/email', methods=['POST'])
def validar_email():
    cur = con.cursor()
    try:
        dados = request.get_json()
        email = dados.get('email')
        codigo = dados.get('codigo')

        if not email or not codigo:
            return jsonify({'error': 'Email e código são obrigatórios.'}), 400

        email = email.replace(' ', '').lower()

        cur.execute("""
            SELECT id_usuario, codigo
            FROM usuario
            WHERE email = ?
        """, (email,))
        usuario = cur.fetchone()

        if not usuario:
            return jsonify({'error': 'Usuário não encontrado.'}), 404

        id_usuario = usuario[0]
        codigo_banco = usuario[1]

        if int(codigo) != int(codigo_banco):
            return jsonify({'error': 'Código inválido.'}), 400

        cur.execute("""
            UPDATE usuario
            SET email_confirmado = 1,
                codigo = NULL
            WHERE id_usuario = ?
        """, (id_usuario,))
        con.commit()

        return jsonify({'message': 'Email validado com sucesso.'}), 200

    except Exception as e:
        return jsonify({'error': f'Erro ao validar email.'}), 500

    finally:
        cur.close()

@auth_blueprint.route('/logout', methods=['POST'])
def logout():
    resp = make_response(jsonify({"mensagem": "Logout realizado com sucesso"}), 200)

    resp.set_cookie(
        "access_token",
        "",
        expires=0,
        max_age=0
    )

    return resp

