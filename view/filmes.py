import os
from flask import Blueprint, jsonify, request, current_app
from funcao import decodificar_token
from database import con
import jwt

filmes_blueprint = Blueprint('filmes', __name__, url_prefix='/filmes')


@filmes_blueprint.route('/cadastro_filme', methods=['POST'])
def cadastro_filme():
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    cur = con.cursor()
    try:
        titulo = (request.form.get('titulo') or '').strip().lower()
        if not titulo:
            return jsonify({"error": "Título é obrigatório"}), 400

        sinopse = (request.form.get('sinopse') or '').strip().lower()
        if not sinopse:
            return jsonify({"error": "Sinopse é obrigatória"}), 400

        genero = request.form.get('genero')
        duracao = request.form.get('duracao')
        classificacao = request.form.get('classificacao')
        data_lancamento = request.form.get('data_lancamento')
        trailer = request.form.get('trailer')
        imagem = request.files.get('imagem')

        # verifica duplicidade
        cur.execute('select 1 from filme where titulo = ?', (titulo,))
        if cur.fetchone():
            return jsonify({"error": "Filme já cadastrado"}), 400

        # insere primeiro
        cur.execute("""
                insert into filme(titulo, sinopse, genero, duracao, classificacao, data_lancamento, trailer)
                values(?, ?, ?, ?, ?, ?, ?)
                RETURNING id_filme
            """, (titulo, sinopse, genero, duracao, classificacao, data_lancamento, trailer))

        id_filme = cur.fetchone()[0]
        con.commit()

        # salva imagem depois
        caminho_imagem = None
        if imagem:
            nome_imagem = f"{id_filme}.jpg"
            caminho_imagem_destino = os.path.join(current_app.config['UPLOAD_FOLDER'], "Filmes")
            os.makedirs(caminho_imagem_destino, exist_ok=True)

            caminho_imagem = os.path.join(caminho_imagem_destino, nome_imagem)
            imagem.save(caminho_imagem)

        return jsonify({"message": "Filme cadastrado com sucesso!"}), 200

    except Exception as e:
        return jsonify({
            "message": f"Erro ao cadastrar filme: {e}"
        }), 500
    finally:
        cur.close()


@filmes_blueprint.route('/editar_filme/<int:id>', methods=['PUT'])
def editar_filme(id):
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        id_usuario = payload['id_usuario']
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Token invalid"}), 401

    cur = con.cursor()
    try:

        cur.execute('SELECT titulo, sinopse,genero,duracao, classificacao,data_lancamento, trailer  FROM filme WHERE id_filme = ?', (id,))
        filmes = cur.fetchone()
        if not filmes:
            return jsonify({"error": "Filme não encontrado"}), 404

        titulo = request.form.get('titulo', filmes[0])
        sinopse = request.form.get('sinopse', filmes[1])
        genero = request.form.get('genero', filmes[2])
        duracao = request.form.get('duracao', filmes[3])
        classificacao = request.form.get('classificacao', filmes[4])
        data_lancamento = request.form.get('data_lancamento', filmes[5])
        trailer = request.form.get('trailer', filmes[6])
        imagem = request.files.get('imagem')

        cur.execute('SELECT 1 FROM filme WHERE titulo = ? AND id_filme != ?', (titulo, id))
        if cur.fetchone():
            return jsonify({"error": "Filme já cadastrado"}), 400

        cur.execute("""
                UPDATE filme SET titulo = ?, sinopse = ?, genero = ?, duracao = ?, classificacao = ?, data_lancamento = ?, trailer = ?
                WHERE id_filme = ? """, (titulo, sinopse, genero, duracao, classificacao, data_lancamento, trailer, id))
        con.commit()

        if imagem:
            nome_imagem = f"{id}.jpg"
            caminho_imagem_destino = os.path.join(current_app.config['UPLOAD_FOLDER'], "Filmes")
            os.makedirs(caminho_imagem_destino, exist_ok=True)
            caminho_imagem = os.path.join(caminho_imagem_destino, nome_imagem)
            imagem.save(caminho_imagem)

        return jsonify({
            "message": "Filme atualizado com sucesso",
            "filme": {
                "id_filme": id,
                "titulo": titulo,
                "sinopse": sinopse,
                "genero": genero,
                "duracao": duracao,
                "classificacao": classificacao,
                "data_lancamento": data_lancamento,
                "trailer": trailer
            }
        }), 200

    except Exception as e:
        return jsonify({
            "message": f"Erro ao atualizar filme.{e}"
        }), 500

    finally:
        cur.close()


@filmes_blueprint.route('/excluir_filme/<int:id>', methods=['DELETE'])
def excluir_filme(id):
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
        cur.execute('SELECT 1 FROM filme WHERE id_filme = ?', (id,))
        if not cur.fetchone():
            return jsonify({"error": "Filme não encontrado"}), 404

        cur.execute('DELETE FROM filme WHERE id_filme = ?', (id,))
        con.commit()

        return jsonify({"message": "Filme excluído com sucesso"}), 200

    except Exception as e:
        return jsonify({"error": f"Erro ao excluir filme."}), 500

    finally:
        cur.close()



@filmes_blueprint.route('/listar_filme', methods=['GET'])
def listar_filme():
    try:
        cur = con.cursor()

        titulo = request.args.get('titulo', '')
        genero = request.args.get('genero', '')
        classificacao = request.args.get('classificacao', '')

        cur.execute("""
            SELECT * FROM filme
            WHERE UPPER(titulo) LIKE UPPER(?)
            AND UPPER(genero) LIKE UPPER(?)
            AND UPPER(classificacao) LIKE UPPER(?)
        """, (
            f"%{titulo}%",
            f"%{genero}%",
            f"%{classificacao}%"
        ))

        filmes = cur.fetchall()

        if not filmes:
            return jsonify({"error": "Não há resultados para sua busca"}), 404

        return jsonify({'filmes': filmes}), 200


    except Exception as e:
        return jsonify({"error": "Erro ao listar filmes"}), 500

    finally:
        cur.close()

