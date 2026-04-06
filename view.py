import os
import random
from pydoc import stripid

import jwt
from flask import Flask, jsonify, request, send_file, make_response, Response
from flask_bcrypt import generate_password_hash, check_password_hash
from funcao import *
from main import app, con
import threading
import datetime
import pygal

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

@app.route('/cadastro_usuario', methods=['POST'])
def cadastro_usuario():
    cur = con.cursor()
    try:
        nome = request.form.get('nome', '').strip().lower()
        if not nome or nome == '' :
            return jsonify({"error": "Nome é obrigatório"}), 400
        email = request.form.get('email').strip().lower()
        if not email or email == '' :
            return jsonify({"error": "Email é obrigatório"}), 400
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
        senha_hash = generate_password_hash(senha).decode('utf-8')

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
        # return jsonify({"message": "Erro ao cadastrar usuário", f'"erro: {e}"}), 500
        return jsonify({
            "message": f"Erro ao cadastrar usuário: {e}"
        }), 500
    finally:
        cur.close()


@app.route('/editar_usuario/<int:id>', methods=['PUT'])
def editar_usuario(id):
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401
    
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
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
            caminho_imagem_destino = os.path.join(app.config['UPLOAD_FOLDER'], "Usuarios")
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

@app.route('/desbloquear_usuario/<int:id>', methods=['PUT'])
def desbloquear_usuario(id):
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401
    
    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        id_usuario = payload['id_usuario']
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

        cur.execute("UPDATE usuario SET situacao = ?", (0,))

        con.commit()
    except Exception as e:
        return jsonify({"error": "Houve um erro ao desbloquear usuário."}), 500
    finally:
        cur.close()

    return jsonify({"mensagem": "Usuário desbloqueado com sucesso"}), 200

@app.route('/buscar_usuario', methods=['GET'])
def buscar_usuario():
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        id_usuario = payload['id_usuario']
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


@app.route('/listar_usuarios', methods=['GET'])
def listar_usuarios():
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        id_usuario = payload['id_usuario']
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
        cur.execute('SELECT * FROM usuario')
        usuarios = cur.fetchall()
        return jsonify({'usuarios': usuarios}), 200
    except Exception as e:
        return jsonify({"error": f"Erro ao listar usuários"}), 500
    finally:
        cur.close()

@app.route('/excluir_usuario/<int:id>', methods=['DELETE'])
def excluir_usuario(id):
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    try:
        payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        id_usuario = payload['id_usuario']
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

    cur = con.cursor()
    try:
        cur.execute('SELECT 1 FROM usuario WHERE id_usuario = ?', (id,))
        if not cur.fetchone():
            return jsonify({"error": "Usuário não encontrado"}), 404

        cur.execute('DELETE FROM usuario WHERE id_usuario = ?', (id,))
        con.commit()

        caminho_imagem = os.path.join(app.config['UPLOAD_FOLDER'], "Usuarios", f"{id}.jpg")
        if os.path.exists(caminho_imagem):
            os.remove(caminho_imagem)

        return jsonify({"message": "Usuário excluído com sucesso"}), 200

    except Exception as e:
        return jsonify({"error": f"Erro ao excluir usuário."}), 500

    finally:
        cur.close()

@app.route('/login', methods=['POST'])
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
                'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
            }

            token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

            resp = make_response(jsonify({
                "mensagem": "Logado com sucesso",
                "usuario": {
                    "id_usuario": id_usuario,
                    "nome": nome,
                }
            }), 200)
            resp.set_cookie("access_token", token,
                            httponly=True,
                            secure=False,
                            samesite="Lax",
                            path="/",
                            max_age=600
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

            enviado = enviar_codigo(id_usuario, email_banco)

            if not enviado:
                return jsonify({'error': 'Erro ao enviar código'}), 500

            return jsonify({
                'message': 'Código enviado para o email. Confirme para continuar.'
            }), 200


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

@app.route('/logout', methods=['POST'])
def logout():
    resp = make_response(jsonify({"mensagem": "Logout realizado com sucesso"}), 200)

    resp.set_cookie(
        "access_token",
        "",
        expires=0,
        max_age=0
    )

    return resp

@app.route('/validar_email', methods=['POST'])
def validar_email():
    cur = con.cursor()
    try:
        dados = request.get_json()
        email = dados.get('email').lower()
        codigo = dados.get('codigo')

        if not email or not codigo:
            return jsonify({'error': 'Email e código são obrigatórios.'}), 400

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

@app.route('/recuperar_senha', methods=['POST'])
def recuperar_senha():
    cur = con.cursor()
    try:
        dados = request.get_json()
        email = dados.get('email').lower()
        codigo = dados.get('codigo')
        nova_senha = dados.get('nova_senha')

        if not email:
            return jsonify({'error': 'Email é obrigatório'}), 400

        if not codigo and not nova_senha:
            cur.execute("SELECT id_usuario FROM usuario WHERE email = ?", (email,))
            if not cur.fetchone():
                return jsonify({'error': 'Usuário não encontrado'}), 404

            codigo = f"{random.randint(0, 999999):06d}"  # garante 6 dígitos

            cur.execute("UPDATE usuario SET codigo = ? WHERE email = ?", (codigo, email))
            con.commit()

            threading.Thread(
                target=enviando_email,
                args=(email, "Recuperação de senha", f"Código: {codigo}")
            ).start()

            return jsonify({"mensagem": "Código enviado"}), 200

        if codigo and nova_senha:
            cur.execute("""
                SELECT id_usuario, senha_um, senha_dois, senha_tres, codigo
                FROM usuario
                WHERE email = ?
            """, (email,))
            usuario = cur.fetchone()

            if not usuario:
                return jsonify({'error': 'Usuário não encontrado'}), 404

            id_usuario = usuario[0]
            ultimas_senhas = [usuario[1], usuario[2], usuario[3]]
            codigo_banco = usuario[4]

            # valida código
            if str(codigo_banco) != str(codigo):
                return jsonify({'error': 'Código inválido'}), 400

            # valida formato da nova senha
            if not validar_senha(nova_senha):
                return jsonify({"error": "A senha não segue nossos padrões de segurança"}), 400

            # valida contra últimas 3 senhas
            for s in ultimas_senhas:
                if s and check_password_hash(s, nova_senha):
                    return jsonify({"error": "Não é permitido reutilizar as últimas 3 senhas"}), 400

            # gera hash da nova senha
            senha_hash = generate_password_hash(nova_senha).decode('utf-8')

            # atualiza histórico das senhas
            senha_tres = usuario[2]  # antigo senha_dois
            senha_dois = usuario[1]   # antigo senha_um
            senha_um = senha_hash     # nova senha

            # atualiza banco
            cur.execute("""
                UPDATE usuario
                SET senha = ?,
                    senha_um = ?,
                    senha_dois = ?,
                    senha_tres = ?,
                    codigo = NULL
                WHERE id_usuario = ?
            """, (senha_hash, senha_um, senha_dois, senha_tres, id_usuario))
            con.commit()

            return jsonify({"mensagem": "Senha redefinida com sucesso"}), 200

        return jsonify({'error': 'Dados inválidos'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

    finally:
        cur.close()
