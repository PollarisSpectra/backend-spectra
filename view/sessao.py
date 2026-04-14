from datetime import datetime, timedelta
import os
from flask import Blueprint, jsonify, request, current_app
from funcao import decodificar_token, converter_horario
from database import con
import jwt

sessao_blueprint = Blueprint('sessao', __name__, url_prefix='/sessao')


@sessao_blueprint.route('/cadastro_sessao', methods=['POST'])
def cadastro_sessao():
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    cur = con.cursor()
    try:
        dados = request.get_json()

        id_filme = dados.get('id_filme')
        id_sala = dados.get('id_sala')
        data = dados.get('data')
        horario = dados.get('horario')
        valor = dados.get('valor_assento')

        print('peguei')

        # if not id_filme or not id_sala or not data or not horario:
        #      return jsonify({"error": "Dados obrigatórios não informados"}), 400

        cur.execute("SELECT duracao FROM filme WHERE id_filme = ?", (id_filme,))
        filme = cur.fetchone()


        if not filme:
            return jsonify({"error": "Filme não encontrado"}), 404

        duracao = filme[0]

        cur.execute("SELECT 1 FROM sala WHERE id_sala = ?", (id_sala,))
        if not cur.fetchone():
            return jsonify({"error": "Sala não encontrada"}), 404

        try:
            data_hora = converter_horario(data, horario)
        except ValueError:
            return jsonify({"error": "Formato de data ou horário inválido"}), 400

        if data_hora < datetime.now():
            return jsonify({"error": "Não é possível cadastrar sessão no passado"}), 400

        try:
            valor = float(valor.replace(',', '.'))

            print(valor)
        except:
            return jsonify({"error": "Valor do assento inválido"}), 400

        inicio_novo = data_hora
        fim_novo = inicio_novo + timedelta(minutes=duracao)

        cur.execute("""
            SELECT s.horario, f.duracao
            FROM sessao s
            JOIN filme f ON s.id_filme = f.id_filme
            WHERE s.id_sala = ? AND s.data = ?
        """, (id_sala, data))

        sessoes = cur.fetchall()

        for sessao in sessoes:
            horario_existente = sessao[0]
            duracao_existente = sessao[1]

            inicio_existente = converter_horario(data, horario_existente)

            # inicio_existente = datetime.strptime(
            #     f"{data} {horario_existente}",
            #     "%d/%m/%Y %H:%M"
            # )

            fim_existente = inicio_existente + timedelta(minutes=duracao_existente)


            if inicio_novo <= fim_existente and fim_novo >= inicio_existente:
                return jsonify({
                    "error": "Conflito de horário com outra sessão nesta sala"
                }), 400

        cur.execute("""
            SELECT 1 FROM sessao
            WHERE id_filme = ? AND id_sala = ? AND data = ? AND horario = ?
        """, (id_filme, id_sala, data, horario))

        if cur.fetchone():
            return jsonify({"error": "Essa sessão já está cadastrada"}), 400

        cur.execute("""
            INSERT INTO sessao (id_filme, id_sala, data, horario, valor_assento, status)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (id_filme, id_sala, data, horario, valor))

        con.commit()

        return jsonify({"message": "Sessão cadastrada com sucesso!"}), 200

    except Exception as e:
        return jsonify({"error": f"Erro ao cadastrar sessão: {e}"}), 500

    finally:
        cur.close()


@sessao_blueprint.route('/excluir_sessao/<int:id>', methods=['DELETE'])
def excluir_sessao(id):
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
        cur.execute('SELECT horario FROM sessao WHERE id_sessao = ?', (id,))
        resultado = cur.fetchone()

        if not resultado:
            return jsonify({"error": "Sessão não encontrada"}), 404

        hora_sessao = resultado[0]

        if hora_sessao <= datetime.now().time():
            return jsonify({"erro": "Sessão já aconteceu, não pode excluir"}), 400

        cur.execute('DELETE FROM sessao WHERE id_sessao = ?', (id,))
        con.commit()

        return jsonify({"message": "Sessão excluída com sucesso"}), 200

    except Exception as e:
        return jsonify({"error": f"Erro ao excluir sessão: {str(e)}"}), 500

    finally:
        cur.close()


@sessao_blueprint.route('/editar_sessao/<int:id>', methods=['PUT'])
def editar_sessao(id):
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    try:
        cur = con.cursor()
        cur.execute('SELECT id_filme, id_sala, data, horario, valor_assento FROM sessao WHERE id_sessao = ?', (id,))
        sessao = cur.fetchone()
        if not sessao:
            return jsonify({"error": "Sessão não encontrada"}), 404

        dados = request.get_json()

        id_filme = dados.get('id_filme', sessao[0])
        id_sala = dados.get('id_sala', sessao[1])
        data = dados.get('data', sessao[2])
        horario = dados.get('horario', sessao[3])
        valor = dados.get('valor_assento', sessao[4])

        cur.execute("SELECT duracao FROM filme WHERE id_filme = ?", (id_filme,))
        filme = cur.fetchone()

        if not filme:
            return jsonify({"error": "Filme não encontrado"}), 404

        duracao = filme[0]

        cur.execute("SELECT 1 FROM sala WHERE id_sala = ?", (id_sala,))
        if not cur.fetchone():
            return jsonify({"error": "Sala não encontrada"}), 404

        try:
            data_hora = converter_horario(data, horario)
        except ValueError:
            return jsonify({"error": "Formato de data ou horário inválido"}), 400

        if data_hora < datetime.now():
            return jsonify({"error": "Não é possível cadastrar sessão no passado"}), 400

        try:
            valor = float(valor.replace(',', '.'))

            print(valor)
        except:
            return jsonify({"error": "Valor do assento inválido"}), 400

        inicio_novo = data_hora
        fim_novo = inicio_novo + timedelta(minutes=duracao)

        cur.execute("""
                   SELECT s.horario, f.duracao
                   FROM sessao s
                   JOIN filme f ON s.id_filme = f.id_filme
                   WHERE s.id_sessao <> ? and  s.id_sala = ? AND s.data = ?
               """, (id, id_sala, data))

        sessoes = cur.fetchall()
        print(sessoes)

        for sessao in sessoes:
            print('entrei no for')
            horario_existente = sessao[0]
            duracao_existente = sessao[1]

            inicio_existente = converter_horario(data, horario_existente)
            fim_existente = inicio_existente + timedelta(minutes=duracao_existente)

            if inicio_novo <= fim_existente and fim_novo >= inicio_existente:
                return jsonify({
                    "error": "Conflito de horário com outra sessão nesta sala"
                }), 400

        cur.execute("""
                   SELECT 1 FROM sessao
                   WHERE id_sessao <> ? and  id_filme = ? AND id_sala = ? AND data = ? AND horario = ?
               """, (id, id_filme, id_sala, data, horario))

        if cur.fetchone():
            return jsonify({"error": "Essa sessão já está cadastrada"}), 400

        cur.execute("""
                    UPDATE sessao SET id_filme = ?, id_sala = ?, data = ?, horario = ?, valor_assento = ?
                    WHERE id_sessao = ? """, (id_filme, id_sala, data, horario, valor, id))
        con.commit()

        return jsonify({
            "message": "Sessão atualizada com sucesso",
            "sessao": {
                "id_sessao":id,
                "id_sala": id_sala,
                "id_filme": id_filme,
                "data": str(data),
                "horario": str(horario),
                "valor_assento": valor
            }
        }), 200

    except Exception as e:
        return jsonify({
            "message": f"Erro ao atualizar sessão.{e}"
        }), 500

    finally:
        cur.close()

@sessao_blueprint.route('/listar_sessao', methods=['GET'])
def listar_sessao():
    try:
        cur = con.cursor()

        filme = request.args.get('filme', '')
        sala = request.args.get('sala', '')
        data = request.args.get('data', '')

        cur.execute("""
           SELECT 
                sessao.ID_SESSAO, filme.TITULO, sala.NOME, sessao.DATA, sessao.HORARIO, sessao.VALOR_ASSENTO
           FROM sessao
           INNER JOIN filme ON filme.ID_FILME = sessao.ID_FILME
           INNER JOIN sala ON sala.ID_sala = sessao.ID_sala
           WHERE UPPER(filme.TITULO) LIKE UPPER(?)
             OR UPPER(sala.NOME) LIKE UPPER(?)
             OR CAST(sessao.DATA AS VARCHAR(20)) LIKE ?
        """, (
            f"%{filme}%",
            f"%{sala}%",
            f"%{data}%"
        ))

        resultado = cur.fetchall()

        sessoes = []
        for linha in resultado:
            sessoes.append({
                "id_sessao": linha[0],
                "filme": linha[1],
                "sala": linha[2],
                "data": str(linha[3]),
                "horario": str(linha[4]),
                "valor_assento": float(linha[5])
            })

        return jsonify({"sessao": sessoes}), 200

    except Exception as e:
        return jsonify({"error": f"Erro ao listar sessões: {str(e)}"}), 500

    finally:
        cur.close()