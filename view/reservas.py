import base64
import io
import math
import os
import threading

import jwt
import qrcode
from flask import Blueprint, jsonify, request, current_app
from database import con
from funcao import decodificar_token, gerar_payload_pix, enviando_email

reservas_bp = Blueprint('reservas', __name__, url_prefix='/reservas')

# Rota de consulta de reserva
@reservas_bp.route("/<int:id>")
def reservas(id):

    if not id:
        return jsonify({"error": "Campo 'id' necessario"}), 400

    try:
        cur = con.cursor()
        cur.execute("SELECT * FROM reserva WHERE id_reserva = ?", (id,))

        rawReserva = cur.fetchone()

        if not rawReserva:
            return jsonify({"error": "Reserva nao encontrada"}), 404

        columns = [desc[0].lower() for desc in cur.description]
        reserva = dict(zip(columns, rawReserva))

        return jsonify({ "message": "Sucesso ao consultar reserva", "reserva": reserva }), 200
    except Exception as e:
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        if cur:
            cur.close()

@reservas_bp.route('/<int:id_usuario>/usuario', methods=['GET'])
def listar_reservas_usuario(id_usuario):
    cur = None
    try:
        # Parâmetros de Filtro
        id_reserva_filtro = request.args.get('id_reserva', '')
        id_sessao_filtro = request.args.get('id_sessao', '')
        status_filtro = request.args.get('status', '')

        # Parâmetros de Paginação
        page_size = int(request.args.get('page_size', 10))
        page_number = int(request.args.get('page_number', 1))
        offset = (page_number - 1) * page_size

        cur = con.cursor()

        # 1. Query para contar o total de resultados com os filtros aplicados
        sql_count = """
            SELECT COUNT(*) FROM RESERVA
            WHERE ID_USUARIO = ?
            AND CAST(ID_RESERVA AS VARCHAR(20)) LIKE ?
            AND CAST(ID_SESSAO AS VARCHAR(20)) LIKE ?
            AND CAST(STATUS AS VARCHAR(20)) LIKE ?
        """
        params_count = (
            id_usuario,
            f"%{id_reserva_filtro}%",
            f"%{id_sessao_filtro}%",
            f"%{status_filtro}%"
        )
        cur.execute(sql_count, params_count)
        total_results = cur.fetchone()[0]

        # 2. Query Principal trazendo os dados da Reserva, ID_FILME e TITULO do Filme
        sql_main = """
            SELECT FIRST ? SKIP ?
                r.ID_RESERVA, r.ID_PROMOCAO, r.ID_USUARIO, r.ID_SESSAO,
                r.VALORTOTAL, r.DESCONTO, r.STATUS, r.DATARESERVA,
                s.ID_FILME, f.TITULO AS FILME_TITULO
            FROM RESERVA r
            INNER JOIN SESSAO s ON r.ID_SESSAO = s.ID_SESSAO
            INNER JOIN FILME f ON s.ID_FILME = f.ID_FILME
            WHERE r.ID_USUARIO = ?
            AND CAST(r.ID_RESERVA AS VARCHAR(20)) LIKE ?
            AND CAST(r.ID_SESSAO AS VARCHAR(20)) LIKE ?
            AND CAST(r.STATUS AS VARCHAR(20)) LIKE ?
            ORDER BY r.ID_RESERVA DESC
        """
        params_main = (
            page_size,
            offset,
            id_usuario,
            f"%{id_reserva_filtro}%",
            f"%{id_sessao_filtro}%",
            f"%{status_filtro}%"
        )
        cur.execute(sql_main, params_main)
        reservas = cur.fetchall()

        columns = [desc[0].lower() for desc in cur.description]
        resultados = [dict(zip(columns, row)) for row in reservas]

        # 3. Mapeia as imagens do respectivo Filme da Sessão
        for r in resultados:
            if r.get('datareserva'):
                r['datareserva'] = str(r['datareserva'])

            id_filme = r.get('id_filme')
            if id_filme:
                caminho = os.path.join(current_app.config['UPLOAD_FOLDER'], "Filmes", f"{id_filme}.jpg")
                if os.path.exists(caminho):
                    r['imagem_url'] = f"/imagem_filme/{id_filme}.jpg"
                else:
                    r['imagem_url'] = None
            else:
                r['imagem_url'] = None

        if not resultados and page_number == 1:
            return jsonify({"reservas": [], "total_pages": 0, "current_page": 1}), 200

        total_pages = math.ceil(total_results / page_size) if total_results > 0 else 0

        return jsonify({
            "total_results": total_results,
            "total_pages": total_pages,
            "current_page": page_number,
            "reservas": resultados
        }), 200

    except ValueError:
        return jsonify({"error": "page_size e page_number devem ser números inteiros"}), 400
    except Exception as e:
        print(f"Erro ao listar reservas: {str(e)}")
        return jsonify({"error": "Erro interno ao processar reservas"}), 500
    finally:
        if cur:
            cur.close()

# Rota de criação de reserva
@reservas_bp.route("/", methods=["POST"])
def criar_reserva():
    cur = None
    try:
        cookie = request.cookies.get('access_token', '')

        if not cookie:
            return jsonify({"error": "Token de autenticacao necessario"}), 401

        payload = decodificar_token(cookie)
        id_usuario = payload['id_usuario']

        data = request.json

        if not data:
            return jsonify({"error": "Payload necessario"}), 400

        id_sessao = int(data["id_sessao"])
        assentos = list(data["assentos"])

        if not id_sessao or not assentos:
            return jsonify({"error": "Insira todos os campos"}), 400

        cur = con.cursor()

        cur.execute("""
        SELECT * FROM RESERVA_ASSENTO ra
        LEFT JOIN RESERVA r ON r.ID_RESERVA = ra.ID_RESERVA
        WHERE r.STATUS = '1' AND r.ID_SESSAO = ?
        """, (id_sessao,))

        columns = [desc[0].lower() for desc in cur.description]
        assentos_sessao = [dict(zip(columns, assento)) for assento in cur.fetchall()]

        for reserva in assentos_sessao:
            if reserva['id_assento_sala'] in assentos:
                return jsonify({"error": f"Poltrona(s) ja reservada(s)"}), 400

        # obtendo o valor do assento para a sessão
        cur.execute("SELECT valor_assento FROM sessao WHERE id_sessao = ?", (id_sessao,))
        valor_assento = cur.fetchone()[0]

        # criando reserva com valor de assento
        cur.execute("""
        INSERT INTO reserva (id_promocao, id_usuario, id_sessao, valortotal, desconto, status, datareserva, expiracao)
        VALUES (?, ?, ?, ?, 0, ?, CURRENT_TIMESTAMP, DATEADD(10 MINUTE TO CURRENT_TIMESTAMP))
        RETURNING id_reserva
        """, (None, id_usuario, id_sessao, (len(assentos) * valor_assento), 3))

        # conferindo se a reserva foi criada
        id_reserva_criada = cur.fetchone()[0]
        if not id_reserva_criada:
            raise Exception("Internal Server Error")

        dados = [
            (id_reserva_criada, id_assento)
            for id_assento in assentos
        ]

        # criando cada reserva_assento
        cur.executemany("""
        INSERT INTO reserva_assento (id_reserva, id_assento_sala)
        VALUES (?, ?)
        """, dados)

        con.commit()

        return jsonify({"message": "Reserva criada com sucesso", "id_reserva": id_reserva_criada})
    except jwt.ExpiredSignatureError as e:
        return jsonify({"error": "Expired token"}), 401
    except jwt.InvalidTokenError as e:
        return jsonify({"error": "Invalid token"}), 401
    except ValueError:
        return jsonify({"error": "Verifique o tipo dos campos"}), 400
    except Exception as e:
        print(str(e))
        con.rollback()
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        if cur:
            cur.close()


@reservas_bp.route('/pagamento/<int:id>', methods=["POST"])
def pagamento(id):
    cur = None

    try:
        cookie = request.cookies.get('access_token')

        if not cookie:
            return jsonify({
                "error": "Token de autenticacao necessario"
            }), 401

        payload = decodificar_token(cookie)
        id_usuario = payload['id_usuario']

        if not id:
            return jsonify({
                "error": "Insira o id da reserva"
            }), 400

        cur = con.cursor()

        # confirma a reserva
        cur.execute("""
        UPDATE RESERVA r
        SET r.STATUS = '1'
        WHERE r.ID_RESERVA = ?
        """, (id,))

        con.commit()

        # busca dados gerais da reserva para o email
        cur.execute("""
            SELECT
                u.NOME,
                u.EMAIL,
                f.TITULO,
                r.VALORTOTAL,
                r.ID_RESERVA,
                s.DATA,
                s.HORARIO
            FROM RESERVA r
            INNER JOIN USUARIO u
                ON u.ID_USUARIO = r.ID_USUARIO
            INNER JOIN SESSAO s
                ON s.ID_SESSAO = r.ID_SESSAO
            INNER JOIN FILME f
                ON f.ID_FILME = s.ID_FILME
            WHERE r.ID_RESERVA = ?
        """, (id,))

        dados = cur.fetchone()

        print("DADOS DO EMAIL:", dados)

        if dados:
            nome, email, filme, valor_total, id_reserva, data_sessao, horario_sessao = dados

            # NOVA CONSULTA COM JOIN: Busca o nome do assento (A1, A2...) associado a esta reserva
            # Ajuste o nome da tabela 'ASSENTO_SALA' se no seu banco for diferente
            cur.execute("""
                SELECT ast.ASSENTO
                FROM RESERVA_ASSENTO ra
                INNER JOIN ASSENTO_SALA ast
                    ON ast.ID_ASSENTO_SALA = ra.ID_ASSENTO_SALA
                WHERE ra.ID_RESERVA = ?
                ORDER BY ast.ASSENTO
            """, (id,))

            assentos_linhas = cur.fetchall()

            # Formata os códigos dos assentos em uma lista (ex: "A1, A2, A3")
            lista_assentos = [linha[0] for linha in assentos_linhas]
            total_ingressos = len(lista_assentos)
            assentos_formatados = ", ".join(lista_assentos)

            # Formatação da Data para o padrão brasileiro (dd/mm/aaaa) se necessário
            if hasattr(data_sessao, 'strftime'):
                data_formatada = data_sessao.strftime('%d/%m/%Y')
            else:
                data_formatada = str(data_sessao)

            assunto = "Reserva confirmada - Cinema"

            # Mensagem do e-mail com os assentos corretos e formato padrão de cinema
            mensagem = f"""
                    Olá, {nome}!

                    Sua reserva foi confirmada com sucesso
                    Obrigado por comprar conosco.

                    Segue os dados dos seus ingressos:

                    Número da reserva: # {id_reserva}
                    Filme: {filme}
                    Data: {data_formatada} às {horario_sessao}
                    Qtd. Ingressos: {total_ingressos}
                    Assento(s): {assentos_formatados}

                    ----------------------------------------
                    Valor Total: R$ {valor_total}
                    ----------------------------------------

                    Apresente o número da reserva ou este e-mail na bilheteria/totem para retirar seus ingressos físicos ou entrar na sala.

                    Bom filme!
                    """

            thread = threading.Thread(
                target=enviando_email,
                args=(email, assunto, mensagem)
            )

            thread.start()

        return jsonify({
            "message": "Reserva confirmada com sucesso"
        }), 200

    except jwt.ExpiredSignatureError:
        return jsonify({
            "error": "Expired token"
        }), 401

    except jwt.InvalidTokenError:
        return jsonify({
            "error": "Invalid token"
        }), 401

    except Exception as e:
        print(str(e))

        con.rollback()

        return jsonify({
            "error": "Internal Server Error"
        }), 500

    finally:
        if cur:
            cur.close()

@reservas_bp.route('/gerar_qrcode/<int:id>', methods=["GET"])
def gerar_qrcode_reserva(id):
    cur = None

    try:
        cur = con.cursor()

        cur.execute("""
            SELECT valortotal AS valor_total
            FROM RESERVA
            WHERE id_reserva = ?
        """, (id,))

        res = cur.fetchone()

        if not res:
            return jsonify({
                "error": "Reserva inexistente"
            }), 404

        reserva = dict(zip(
            [desc[0].lower() for desc in cur.description],
            res
        ))

        cur.execute("""
        SELECT cidade, chave_pix, cnpj, razao_social
        FROM EMPRESA e
        ORDER BY ID_EMPRESA ASC
        FETCH FIRST 1 ROW ONLY
        """)

        resultado = cur.fetchone()

        dados = { "cidade": "BIRIGUI", "chave_pix": "41317641809", "razao_social": "PAULO HENRIQUE SOUZA CAVALLINI" }

        if resultado:
            dados = dict(zip([desc[0].lower() for desc in cur.description], resultado))

        valor_total = float(reserva['valor_total'])

        payload = gerar_payload_pix(
            dados["chave_pix"],
            dados["razao_social"],
            dados["cidade"],
            valor_total
        )

        img = qrcode.make(payload)

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        img_base64 = base64.b64encode(
            buffer.getvalue()
        ).decode("utf-8")

        return jsonify({
            "valor": valor_total,
            "payload": payload,
            "qrcode": img_base64
        }), 200

    except Exception as e:
        print(str(e))

        return jsonify({
            "error": "Internal Server Error"
        }), 500

# rota de assentos ocupados por reserva
@reservas_bp.route('/<int:id>/assentos_ocupados', methods=["GET"])
def obter_assentos_ocupados(id):
    cur = con.cursor()

    try:
        cur.execute("""
        SELECT assala.ASSENTO
        FROM RESERVA_ASSENTO ra
        LEFT JOIN RESERVA r ON r.ID_RESERVA = ra.ID_RESERVA
        INNER JOIN ASSENTO_SALA assala ON assala.ID_ASSENTO_SALA = ra.ID_ASSENTO_SALA
        WHERE r.ID_SESSAO = ?
        AND (r.STATUS = '1' OR (r.STATUS = '3' AND r.EXPIRACAO > CURRENT_TIMESTAMP))
        """, (id,))

        assentos_ocupados = cur.fetchall()

        if not assentos_ocupados:
            return jsonify({"error": "Sessao nao encontrada"}), 404

        return jsonify({ "message": "Assentos ocupados obtidos com sucesso", "assentos": [assento[0] for assento in assentos_ocupados] }), 200

    except Exception as e:
        print("Erro ao obter assentos ocupados: " + str(e))
        return jsonify({"message": "Internal Server Error"}), 500
    finally:
        if cur:
            cur.close()

# Rota de exclusão de reserva
@reservas_bp.route("/<int:id>", methods=["DELETE"])
def excluir_reserva(id):
    try:
        cur = con.cursor()
        cur.execute("SELECT 1 FROM reserva WHERE id_reserva = ?", (id,))

        if not cur.fetchone():
            return jsonify({"error": "Reserva nao encontrada"}), 404

        # falta validar se tem violação de FK aqui

        cur.execute("DELETE FROM reserva WHERE id_reserva = ?", (id,))
        con.commit()

        return jsonify({"message": "Reserva excluida com sucesso"})
    except Exception:
        con.rollback()
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        if cur:
            cur.close()

# endpoint para obter reservas do usuario
@reservas_bp.route("/<int:id>/usuario", methods=["GET"])
def obter_reservas_usuario(id):
    cur = None
    try:
        cur = con.cursor()

        cur.execute("""
        SELECT r.*, f.* FROM RESERVA r
        INNER JOIN SESSAO s ON r.ID_SESSAO = s.ID_SESSAO
        INNER JOIN FILME f ON f.ID_FILME = s.ID_FILME
        WHERE ID_USUARIO = ?
        """, (id,))

        res = cur.fetchall()

        colunas = [desc[0].lower() for desc in cur.description]
        resultado = [dict(zip(colunas, reserva)) for reserva in res]

        return jsonify({ "message": "Reservas obtidas com sucesso", "reservas": resultado})
    except Exception as e:
        print(str(e))
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        if cur:
            cur.close()

