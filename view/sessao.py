from datetime import datetime, timedelta
import os

import jwt
from flask import Blueprint, jsonify, request, current_app, send_from_directory

from database import con
from funcao import decodificar_token, converter_horario

sessao_blueprint = Blueprint(
    'sessao',
    __name__,
    url_prefix='/sessao'
)


@sessao_blueprint.route('/cadastro_sessao', methods=['POST'])
def cadastro_sessao():
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({
            "error": "Token de autenticação necessário."
        }), 401

    cur = None

    try:
        payload = decodificar_token(token)

        if payload['tipo'] == 1:
            return jsonify({
                "error": "Acesso negado"
            }), 403

        dados = request.get_json()

        if not dados:
            return jsonify({
                "error": "Payload necessário"
            }), 400

        id_filme = dados.get('id_filme')
        id_sala = dados.get('id_sala')
        data = dados.get('data')
        horario = dados.get('horario')
        valor = dados.get('valor_assento')

        if (
            not id_filme or
            not id_sala or
            not data or
            not horario or
            valor is None
        ):
            return jsonify({
                "error": "Dados obrigatórios não informados"
            }), 400

        cur = con.cursor()

        # valida filme
        cur.execute(
            "SELECT duracao FROM filme WHERE id_filme = ?",
            (id_filme,)
        )

        filme = cur.fetchone()

        if not filme:
            return jsonify({
                "error": "Filme não encontrado"
            }), 404

        duracao = filme[0]

        # valida sala
        cur.execute(
            "SELECT 1 FROM sala WHERE id_sala = ?",
            (id_sala,)
        )

        if not cur.fetchone():
            return jsonify({
                "error": "Sala não encontrada"
            }), 404

        # valida data/hora
        try:
            data_hora = converter_horario(data, horario)
        except ValueError:
            return jsonify({
                "error": "Formato de data ou horário inválido"
            }), 400

        if data_hora < datetime.now():
            return jsonify({
                "error": "Não é possível cadastrar sessão no passado"
            }), 400

        # valida valor
        try:
            valor = float(str(valor).replace(',', '.'))

            if valor <= 0:
                raise ValueError

        except ValueError:
            return jsonify({
                "error": "Valor do assento inválido"
            }), 400

        inicio_novo = data_hora
        fim_novo = inicio_novo + timedelta(minutes=duracao)

        # verifica conflito de horário
        cur.execute("""
            SELECT
                s.horario,
                f.duracao
            FROM sessao s
            INNER JOIN filme f
                ON f.id_filme = s.id_filme
            WHERE s.id_sala = ?
            AND s.data = ?
        """, (id_sala, data))

        sessoes = cur.fetchall()

        for sessao in sessoes:
            horario_existente = sessao[0]
            duracao_existente = sessao[1]

            inicio_existente = converter_horario(
                data,
                horario_existente
            )

            fim_existente = (
                inicio_existente +
                timedelta(minutes=duracao_existente)
            )

            # conflito
            if (
                inicio_novo < fim_existente and
                fim_novo > inicio_existente
            ):
                return jsonify({
                    "error": "Conflito de horário com outra sessão nesta sala"
                }), 400

        # verifica duplicidade exata
        cur.execute("""
            SELECT 1
            FROM sessao
            WHERE id_filme = ?
            AND id_sala = ?
            AND data = ?
            AND horario = ?
        """, (
            id_filme,
            id_sala,
            data,
            horario
        ))

        if cur.fetchone():
            return jsonify({
                "error": "Essa sessão já está cadastrada"
            }), 400

        cur.execute("""
            INSERT INTO sessao (
                id_filme,
                id_sala,
                data,
                horario,
                valor_assento,
                status
            )
            VALUES (?, ?, ?, ?, ?, 1)
        """, (
            id_filme,
            id_sala,
            data,
            horario,
            valor
        ))

        con.commit()

        return jsonify({
            "message": "Sessão cadastrada com sucesso!"
        }), 201

    except jwt.ExpiredSignatureError:
        return jsonify({
            "error": "Token expirado"
        }), 401

    except jwt.InvalidTokenError:
        return jsonify({
            "error": "Token inválido"
        }), 401

    except Exception as e:
        con.rollback()

        print(str(e))

        return jsonify({
            "error": "Erro interno do servidor"
        }), 500

    finally:
        if cur:
            cur.close()


@sessao_blueprint.route('/excluir_sessao/<int:id>', methods=['DELETE'])
def excluir_sessao(id):
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({
            "error": "Token de autenticação necessário."
        }), 401

    cur = None

    try:
        payload = decodificar_token(token)

        if payload['tipo'] == 1:
            return jsonify({
                "error": "Acesso negado",
                "mensagem": (
                    "Você não tem permissão para realizar esta ação."
                )
            }), 403

        cur = con.cursor()

        cur.execute("""
            SELECT
                data,
                horario
            FROM sessao
            WHERE id_sessao = ?
        """, (id,))

        resultado = cur.fetchone()

        if not resultado:
            return jsonify({
                "error": "Sessão não encontrada"
            }), 404

        data_sessao = resultado[0]
        horario_sessao = resultado[1]

        data_hora_sessao = converter_horario(
            str(data_sessao),
            str(horario_sessao)
        )

        if data_hora_sessao <= datetime.now():
            return jsonify({
                "error": "Sessão já aconteceu, não pode excluir"
            }), 400

        # impede exclusão se houver reservas
        cur.execute("""
            SELECT 1
            FROM reserva
            WHERE id_sessao = ?
        """, (id,))

        if cur.fetchone():
            return jsonify({
                "error": (
                    "Não é possível excluir sessão com reservas vinculadas"
                )
            }), 400

        cur.execute("""
            DELETE FROM sessao
            WHERE id_sessao = ?
        """, (id,))

        con.commit()

        return jsonify({
            "message": "Sessão excluída com sucesso"
        }), 200

    except jwt.ExpiredSignatureError:
        return jsonify({
            "error": "Token expirado"
        }), 401

    except jwt.InvalidTokenError:
        return jsonify({
            "error": "Token inválido"
        }), 401

    except Exception as e:
        con.rollback()

        print(str(e))

        return jsonify({
            "error": "Erro interno do servidor"
        }), 500

    finally:
        if cur:
            cur.close()


@sessao_blueprint.route('/editar_sessao/<int:id>', methods=['PUT'])
def editar_sessao(id):
    token = request.cookies.get('access_token')

    if not token:
        return jsonify({
            "error": "Token de autenticação necessário."
        }), 401

    cur = None

    try:
        payload = decodificar_token(token)

        if payload['tipo'] == 1:
            return jsonify({
                "error": "Acesso negado"
            }), 403

        dados = request.get_json()

        if not dados:
            return jsonify({
                "error": "Payload necessário"
            }), 400

        cur = con.cursor()

        cur.execute("""
            SELECT
                id_filme,
                id_sala,
                data,
                horario,
                valor_assento,
                status
            FROM sessao
            WHERE id_sessao = ?
        """, (id,))

        sessao = cur.fetchone()

        if not sessao:
            return jsonify({
                "error": "Sessão não encontrada"
            }), 404

        id_filme = dados.get('id_filme', sessao[0])
        id_sala = dados.get('id_sala', sessao[1])
        data = dados.get('data', sessao[2])
        horario = dados.get('horario', sessao[3])
        valor = dados.get('valor_assento', sessao[4])
        status = dados.get('status', sessao[5])

        # valida filme
        cur.execute("""
            SELECT duracao
            FROM filme
            WHERE id_filme = ?
        """, (id_filme,))

        filme = cur.fetchone()

        if not filme:
            return jsonify({
                "error": "Filme não encontrado"
            }), 404

        duracao = filme[0]

        # valida sala
        cur.execute("""
            SELECT 1
            FROM sala
            WHERE id_sala = ?
        """, (id_sala,))

        if not cur.fetchone():
            return jsonify({
                "error": "Sala não encontrada"
            }), 404

        # valida data/hora
        try:
            data_hora = converter_horario(data, horario)
        except ValueError:
            return jsonify({
                "error": "Formato de data ou horário inválido"
            }), 400

        data_hora_antiga = converter_horario(
            str(sessao[2]),
            str(sessao[3])
        )

        if (
            data_hora_antiga != data_hora and
            data_hora < datetime.now()
        ):
            return jsonify({
                "error": "Não é possível editar sessão para o passado"
            }), 400

        # valida valor
        try:
            valor = float(str(valor).replace(',', '.'))

            if valor <= 0:
                raise ValueError

        except ValueError:
            return jsonify({
                "error": "Valor do assento inválido"
            }), 400

        inicio_novo = data_hora
        fim_novo = inicio_novo + timedelta(minutes=duracao)

        # conflito horário
        cur.execute("""
            SELECT
                s.horario,
                f.duracao
            FROM sessao s
            INNER JOIN filme f
                ON f.id_filme = s.id_filme
            WHERE s.id_sessao <> ?
            AND s.id_sala = ?
            AND s.data = ?
        """, (
            id,
            id_sala,
            data
        ))

        sessoes = cur.fetchall()

        for sessao_existente in sessoes:
            horario_existente = sessao_existente[0]
            duracao_existente = sessao_existente[1]

            inicio_existente = converter_horario(
                data,
                horario_existente
            )

            fim_existente = (
                inicio_existente +
                timedelta(minutes=duracao_existente)
            )

            if (
                inicio_novo < fim_existente and
                fim_novo > inicio_existente
            ):
                return jsonify({
                    "error": (
                        "Conflito de horário com outra sessão nesta sala"
                    )
                }), 400

        # duplicidade
        cur.execute("""
            SELECT 1
            FROM sessao
            WHERE id_sessao <> ?
            AND id_filme = ?
            AND id_sala = ?
            AND data = ?
            AND horario = ?
        """, (
            id,
            id_filme,
            id_sala,
            data,
            horario
        ))

        if cur.fetchone():
            return jsonify({
                "error": "Essa sessão já está cadastrada"
            }), 400

        cur.execute("""
            UPDATE sessao
            SET
                id_filme = ?,
                id_sala = ?,
                data = ?,
                horario = ?,
                valor_assento = ?,
                status = ?
            WHERE id_sessao = ?
        """, (
            id_filme,
            id_sala,
            data,
            horario,
            valor,
            status,
            id
        ))

        con.commit()

        return jsonify({
            "message": "Sessão atualizada com sucesso",
            "sessao": {
                "id_sessao": id,
                "id_sala": id_sala,
                "id_filme": id_filme,
                "data": str(data),
                "horario": str(horario),
                "valor_assento": valor,
                "status": status
            }
        }), 200

    except jwt.ExpiredSignatureError:
        return jsonify({
            "error": "Token expirado"
        }), 401

    except jwt.InvalidTokenError:
        return jsonify({
            "error": "Token inválido"
        }), 401

    except Exception as e:
        con.rollback()

        print(str(e))

        return jsonify({
            "error": "Erro interno do servidor"
        }), 500

    finally:
        if cur:
            cur.close()


@sessao_blueprint.route('/listar_sessao', methods=['GET'])
def listar_sessao():
    cur = None

    try:
        cur = con.cursor()

        id_sessao = request.args.get('id_sessao')
        filme = request.args.get('filme', '')
        sala = request.args.get('sala', '')
        data = request.args.get('data', '')
        categoria = request.args.get('categoria', '')

        if id_sessao:
            cur.execute("""
                SELECT
                    sessao.ID_SESSAO,
                    sessao.ID_FILME,
                    sessao.ID_SALA,
                    filme.TITULO,
                    sala.NOME,
                    sessao.DATA,
                    sessao.HORARIO,
                    sessao.VALOR_ASSENTO,
                    sessao.STATUS,
                    filme.GENERO
                FROM sessao
                INNER JOIN filme
                    ON filme.ID_FILME = sessao.ID_FILME
                INNER JOIN sala
                    ON sala.ID_SALA = sessao.ID_SALA
                WHERE sessao.ID_SESSAO = ?
            """, (id_sessao,))
        else:
            cur.execute("""
                SELECT
                    sessao.ID_SESSAO,
                    sessao.ID_FILME,
                    sessao.ID_SALA,
                    filme.TITULO,
                    sala.NOME,
                    sessao.DATA,
                    sessao.HORARIO,
                    sessao.VALOR_ASSENTO,
                    sessao.STATUS,
                    filme.GENERO
                FROM sessao
                INNER JOIN filme
                    ON filme.ID_FILME = sessao.ID_FILME
                INNER JOIN sala
                    ON sala.ID_SALA = sessao.ID_SALA
                WHERE UPPER(filme.TITULO) LIKE UPPER(?)
                AND UPPER(sala.NOME) LIKE UPPER(?)
                AND CAST(sessao.DATA AS VARCHAR(20)) LIKE ?
                AND UPPER(filme.GENERO) LIKE UPPER(?)
            """, (
                f"%{filme}%",
                f"%{sala}%",
                f"%{data}%",
                f"%{categoria}%"
            ))

        resultado = cur.fetchall()

        if not resultado:
            return jsonify({
                "error": "Não há sessões relacionadas à sua busca"
            }), 404

        sessoes = []

        for linha in resultado:
            sessoes.append({
                "id_sessao": linha[0],
                "id_filme": linha[1],
                "id_sala": linha[2],
                "filme": linha[3],
                "sala": linha[4],
                "data": str(linha[5]),
                "horario": str(linha[6]),
                "valor_assento": float(linha[7]),
                "status": linha[8],
                "categoria": linha[9]
            })

        return jsonify({
            "sessao": sessoes
        }), 200

    except Exception as e:
        print(str(e))

        return jsonify({
            "error": f"Erro ao listar sessões: {str(e)}"
        }), 500

    finally:
        if cur:
            cur.close()


@sessao_blueprint.route('/imagem_filme/<path:filename>')
def servir_imagem_filme(filename):
    caminho = os.path.join(
        current_app.config['UPLOAD_FOLDER'],
        "Filmes"
    )

    return send_from_directory(caminho, filename)


@sessao_blueprint.route('/sala_sessao/<int:id_sessao>', methods=['GET'])
def sala_sessao(id_sessao):
    cur = None

    try:
        cur = con.cursor()

        cur.execute("""
            SELECT
                sessao.ID_SESSAO,
                sessao.DATA,
                sessao.HORARIO,
                filme.ID_FILME,
                filme.TITULO,
                filme.GENERO,
                filme.DURACAO,
                filme.SINOPSE,
                sala.ID_SALA,
                sala.NOME,
                sala.QTD_FILEIRAS,
                sala.QTD_COLUNAS
            FROM sessao
            INNER JOIN filme
                ON filme.ID_FILME = sessao.ID_FILME
            INNER JOIN sala
                ON sala.ID_SALA = sessao.ID_SALA
            WHERE sessao.ID_SESSAO = ?
        """, (id_sessao,))

        resultado = cur.fetchone()

        if not resultado:
            return jsonify({
                "error": "Sessão não encontrada"
            }), 404

        id_filme = resultado[3]
        id_sala = resultado[8]

        qtd_fileiras = int(resultado[10])
        qtd_colunas = int(resultado[11])

        return jsonify({
            "filme": {
                "id_filme": id_filme,
                "titulo": resultado[4],
                "genero": resultado[5],
                "duracao": resultado[6],
                "sinopse": resultado[7],
                "imagem_url": f"/sessao/imagem_filme/{id_filme}.jpg",
                "data": str(resultado[1]),
                "horario": str(resultado[2])
            },
            "sala": {
                "id_sala": id_sala,
                "nome": resultado[9],
                "qtd_fileiras": qtd_fileiras,
                "qtd_colunas": qtd_colunas
            }
        }), 200

    except Exception as e:
        print(str(e))

        return jsonify({
            "error": (
                f"Erro ao buscar sala da sessão: {str(e)}"
            )
        }), 500

    finally:
        if cur:
            cur.close()