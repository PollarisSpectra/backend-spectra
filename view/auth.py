import secrets

import jwt

from funcao import validar_senha, enviando_email, encode_password, gerar_token, decodificar_token
from flask import Blueprint, jsonify, request, make_response, current_app
from flask_bcrypt import check_password_hash, generate_password_hash
import datetime
from database import con
import threading
import os.path
import random

auth_blueprint = Blueprint('auth', __name__, url_prefix='/auth')

@auth_blueprint.route('/login', methods=['POST'])
def login():
    cursor = con.cursor()
    try:
        dados = request.get_json()
        email = dados.get('email').lower()
        senha = dados.get('senha')

        if not email or not senha:
            return jsonify({'error': 'E-mail e senha são obrigatórios.'}), 400

        cursor.execute("""
            SELECT senha, id_usuario, nome, situacao, tentativas, tipo, email, email_confirmado
            FROM usuario
            WHERE email = ?
        """, (email,))
        usuario = cursor.fetchone()
        if not usuario:
            return jsonify({'error': 'Usuário não encontrado.'}), 404

        senha_hash = usuario[0]
        id_usuario = usuario[1]
        nome = usuario[2]
        situacao = usuario[3]
        tentativas = usuario[4]
        tipo = usuario[5]
        email_banco = usuario[6]
        email_confirmado = usuario[7]

        if email_confirmado == 0:
            return jsonify({'error': 'Usuário nao confirmou email. Contate o administrador.'}), 403

        if situacao == 1:
            return jsonify({'error': 'Usuário está inativo. Contate o administrador.'}), 403

        if check_password_hash(senha_hash, senha):
            if tipo != 0:
                cursor.execute("""
                               UPDATE usuario SET tentativas = 0 WHERE id_usuario = ?
                               """, (id_usuario,))
                con.commit()

            payload = {
                'id_usuario': id_usuario,
                'nome': nome,
                'email': email_banco,
                'tipo': tipo,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=60)
            }

            token = gerar_token(payload)

            resp = make_response(jsonify({
                'mensagem': 'Logado com sucesso',
                'usuario': {
                    'id_usuario': id_usuario,
                    'nome': nome,
                    'email': email_banco,
                    'tipo': tipo
                }
            }), 200)

            resp.set_cookie("access_token", token,
                                path='/',
                                httponly=True,
                                secure=False,
                                samesite='Lax'
                            )

            return resp

            # return jsonify({
            #     'message': 'Login realizado com sucesso.',
            #     'token': token,
            #     'usuario': {
            #         'id_usuario': id_usuario,
            #         'nome': nome,
            #         'email': email_banco,
            #         'tipo': tipo
            #     }
            # }), 200

            # enviado = enviar_codigo(id_usuario, email_banco)

            # if not enviado:
            #     return jsonify({'error': 'Erro ao enviar código'}), 500

            # return jsonify({
            #     'message': 'Código enviado para o email. Confirme para continuar.'
            # }), 200

        if tentativas < 2 and tipo != 0:
            cursor.execute("""
                UPDATE usuario
                SET tentativas = tentativas + 1
                WHERE id_usuario = ?
            """, (id_usuario,))
            con.commit()
            return jsonify({'error': 'E-mail ou senha incorretos. Tente novamente.'}), 401

        if tentativas == 2 and tipo != 0:
            cursor.execute("""
                UPDATE usuario
                SET tentativas = 3, situacao = 1
                WHERE id_usuario = ?
            """, (id_usuario,))
            con.commit()
            return jsonify({
                'error': 'Conta bloqueada após 3 tentativas. Contate o administrador.'
            }), 403

        return jsonify({'error': 'E-mail ou senha incorretos. Tente novamente.'}), 401

    except Exception as e:
        return jsonify({'error': f'Erro ao realizar login.'}), 500

    finally:
        cursor.close()

@auth_blueprint.route('/cadastro', methods=['POST'])
def cadastro():
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
            caminho_imagem_destino = os.path.join(current_app.config['UPLOAD_FOLDER'], "Usuarios")
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

@auth_blueprint.route('/validar_email', methods=['POST'])
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
        print(f"Erro ao validar email: {str(e)}")
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

@auth_blueprint.route('/recuperar_senha', methods=['POST'])
def recuperar_senha():
    cur = con.cursor()
    try:
        dados = request.get_json(silent=True) or {}

        email = (dados.get('email') or '').strip().lower()
        codigo = dados.get('codigo')
        nova_senha = dados.get('nova_senha')

        if not email:
            return jsonify({'error': 'Email é obrigatório'}), 400

        if not codigo and not nova_senha:
            cur.execute("""
                SELECT id_usuario
                FROM usuario
                WHERE email = ?
            """, (email,))
            if not cur.fetchone():
                return jsonify({'error': 'Usuário não encontrado'}), 404

            codigo = f"{secrets.randbelow(1000000):06d}"

            cur.execute("""
                UPDATE usuario
                SET codigo = ?
                WHERE email = ?
            """, (codigo, email))
            con.commit()

            threading.Thread(
                target=enviando_email,
                args=(email, "Recuperação de senha", f"Código: {codigo}"),
                daemon=True
            ).start()

            return jsonify({"mensagem": "Código enviado"}), 200

        if codigo and nova_senha:
            cur.execute("""
                SELECT id_usuario, senha, senha_um, senha_dois, senha_tres, codigo
                FROM usuario
                WHERE email = ?
            """, (email,))
            usuario = cur.fetchone()

            if not usuario:
                return jsonify({'error': 'Usuário não encontrado'}), 404

            id_usuario = usuario[0]
            senha_atual = usuario[1]
            senha_um = usuario[2]
            senha_dois = usuario[3]
            senha_tres = usuario[4]
            codigo_banco = usuario[5]

            if str(codigo_banco) != str(codigo):
                return jsonify({'error': 'Código inválido'}), 400

            if not validar_senha(nova_senha):
                return jsonify({"error": "A senha não segue nossos padrões de segurança"}), 400

            historico = [senha_atual, senha_um, senha_dois, senha_tres]
            for senha_hash in historico:
                if not senha_hash:
                    continue
                try:
                    if check_password_hash(senha_hash, nova_senha):
                        return jsonify({"error": "Não é permitido reutilizar as últimas 3 senhas"}), 400
                except ValueError:
                    continue

            nova_hash = generate_password_hash(nova_senha)

            cur.execute("""
                UPDATE usuario
                SET senha = ?,
                    senha_um = ?,
                    senha_dois = ?,
                    senha_tres = ?,
                    codigo = NULL
                WHERE id_usuario = ?
            """, (
                nova_hash,
                nova_hash,
                senha_um,
                senha_dois,
                id_usuario
            ))
            con.commit()

            return jsonify({"mensagem": "Senha redefinida com sucesso"}), 200

        return jsonify({'error': 'Dados inválidos'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        cur.close()

@auth_blueprint.route('/me', methods=['GET'])
def verificar():
    token = request.cookies.get("access_token")

    print(f"token: {token} tds os tokens: {request.cookies}")

    if not token:
        print(dict(request.headers))
        return jsonify({"error": "Token não enviado"}), 401

    try:
        payload = decodificar_token(token)

        return jsonify({
            'id_usuario': payload['id_usuario'],
            'nome': payload['nome'],
            'email': payload['email'],
            'tipo': payload['tipo']
        }), 200
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Expired token"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401