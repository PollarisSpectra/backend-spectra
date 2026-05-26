from datetime import datetime, timedelta
from fpdf import FPDF
import os
import jwt
from flask import Blueprint, jsonify, request, current_app, send_from_directory, send_file

from database import con
from funcao import decodificar_token, converter_horario

sessao_blueprint = Blueprint('sessao', __name__, url_prefix='/sessao')


class RelatorioPDF(FPDF):
    # ── PALETA CINZA CORPORATIVO ─────────────────────────────────────────────
    CINZA_900 = (26, 26, 31)  # header / footer
    CINZA_700 = (69, 70, 80)  # texto / cabeçalho tabela
    CINZA_400 = (143, 148, 153)  # texto médio
    CINZA_LINE = (222, 222, 227)  # bordas
    CINZA_100 = (242, 242, 245)  # zebra ímpar
    BRANCO = (255, 255, 255)

    def __init__(self, total_sessoes=0, maior_ocupacao="0.0%"):
        super().__init__()
        self.total_sessoes = total_sessoes
        self.maior_ocupacao = maior_ocupacao

    def header(self):
        # Fundo escuro (Aumentado para 42 para caber os KPIs horizontais da imagem)
        self.set_fill_color(*self.CINZA_900)
        self.rect(0, 0, 210, 42, 'F')

        # Linha fina de acento no topo da página
        self.set_fill_color(190, 190, 195)
        self.rect(0, 0, 210, 1, 'F')

        # Título
        self.set_font('Arial', 'B', 17)
        self.set_text_color(*self.BRANCO)
        self.set_xy(14, 7)
        self.cell(0, 7, 'RELATÓRIO DE OCUPAÇÃO', ln=True)

        # Subtítulo
        self.set_font('Arial', '', 8)
        self.set_text_color(158, 160, 168)
        self.set_x(14)
        self.cell(0, 4, 'Sessões com maior índice de ocupação de assentos', ln=True)

        # Data alinhada à direita no topo escuro
        self.set_font('Arial', '', 7)
        self.set_text_color(107, 109, 118)
        data_str = datetime.now().strftime('%d/%m/%Y  %H:%M')
        self.set_xy(14, 7)
        self.cell(183, 5, f'GERADO EM\n {data_str}', align='R', ln=True)

        # Divisor interno do header (Acima dos KPIs)
        self.set_draw_color(56, 56, 64)
        self.set_line_width(0.4)
        self.line(14, 25, 196, 25)

        # ── BLOCO DE MEIO (KPIs/Métricas do topo conforme a imagem) ──────────
        # Métrica 1: Total Sessões
        self.set_xy(14, 27)
        self.set_font('Arial', '', 6)
        self.set_text_color(107, 109, 118)
        self.cell(40, 3, "TOTAL SESSÕES", ln=True)
        self.set_x(14)
        self.set_font('Arial', 'B', 9)
        self.set_text_color(*self.BRANCO)
        self.cell(40, 4, str(self.total_sessoes), ln=True)

        # Métrica 2: Maior Ocupação
        self.set_xy(70, 27)
        self.set_font('Arial', '', 6)
        self.set_text_color(107, 109, 118)
        self.cell(40, 3, "MAIOR OCUPAÇÃO", ln=True)
        self.set_x(70)
        self.set_font('Arial', 'B', 9)
        self.set_text_color(*self.BRANCO)
        self.cell(40, 4, self.maior_ocupacao, ln=True)

        # Métrica 3: Período dinâmico baseado no mês atual
        self.set_xy(125, 27)
        self.set_font('Arial', '', 6)
        self.set_text_color(107, 109, 118)
        self.cell(40, 3, "PERÍODO", ln=True)
        self.set_x(125)
        self.set_font('Arial', 'B', 9)
        self.set_text_color(*self.BRANCO)
        # Exibe o mês/ano atual ex: "Mai 2026"
        meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        periodo_str = f"{meses[datetime.now().month - 1]} {datetime.now().year}"
        self.cell(40, 4, periodo_str, ln=True)

        # Linha separadora inferior do header completo
        self.set_draw_color(*self.CINZA_LINE)
        self.set_line_width(0.3)
        self.line(0, 42, 210, 42)
        self.set_xy(14, 47)

    def footer(self):
        self.set_y(-13)
        self.set_fill_color(*self.CINZA_900)
        self.rect(0, self.get_y() - 1, 210, 16, 'F')

        self.set_draw_color(56, 56, 64)
        self.set_line_width(0.4)
        self.line(0, self.get_y() - 1, 210, self.get_y() - 1)

        self.set_font('Arial', '', 7)
        self.set_text_color(128, 130, 138)
        data_str = datetime.now().strftime('%d/%m/%Y %H:%M')
        self.cell(130, 10, f'   Gerado em: {data_str}   |   Relatório Corporativo', align='L')

        self.set_font('Arial', 'B', 7)
        self.set_text_color(190, 190, 195)
        self.cell(0, 10, f'Página {self.page_no()}/{{nb}}', align='R')


# ==============================================================================
# ROTA: GERAR RELATÓRIO DE MAIOR OCUPAÇÃO EM PDF
# ==============================================================================
@sessao_blueprint.route('/relatorio_ocupacao', methods=['GET'])
def relatorio_ocupacao():
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

        cur = con.cursor()

        # Query SQL Corrigida para Firebird
        query = """
                SELECT s.id_sessao,
                       f.titulo                                                                                 AS filme_titulo,
                       sa.nome                                                                                  AS sala_nome,
                       s.data,
                       s.horario,
                       (sa.qtd_fileiras * sa.qtd_colunas)                                                       AS capacidade_total,
                       COUNT(r.id_reserva)                                                                      AS total_reservas,
                       ROUND((CAST(COUNT(r.id_reserva) AS REAL) / (sa.qtd_fileiras * sa.qtd_colunas)) * 100, \
                             2)                                                                                 AS percentual_ocupacao
                FROM sessao s
                         INNER JOIN filme f ON f.id_filme = s.id_filme
                         INNER JOIN sala sa ON sa.id_sala = s.id_sala
                         LEFT JOIN reserva r ON r.id_sessao = s.id_sessao
                GROUP BY s.id_sessao, f.titulo, sa.nome, s.data, s.horario, (sa.qtd_fileiras * sa.qtd_colunas)
                HAVING COUNT(r.id_reserva) > 0
                ORDER BY 8 DESC, 7 DESC
                """

        cur.execute(query)
        sessoes_ocupadas = cur.fetchall()

        if not sessoes_ocupadas:
            return jsonify({
                "error": "Não há dados de ocupação ou reservas registradas para gerar o relatório."
            }), 404

        # Cálculo dinâmico dos metadados para os KPI Cards
        total_sessoes_count = len(sessoes_ocupadas)
        max_pct = max([float(sessao[7]) for sessao in sessoes_ocupadas]) if sessoes_ocupadas else 0.0
        maior_ocupacao_str = f"{max_pct}%"

        # Inicialização do PDF Customizado passando os parâmetros calculados
        pdf = RelatorioPDF(total_sessoes=total_sessoes_count, maior_ocupacao=maior_ocupacao_str)
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # ── Introdução ───────────────────────────────────────────────────────
        pdf.set_font('Arial', '', 8)
        pdf.set_text_color(*RelatorioPDF.CINZA_400)
        texto_intro = (
            "Análise consolidada das sessões com maior índice de ocupação. "
            "Utilize estas informações para decisões de alocação de salas e programação de horários."
        )
        pdf.multi_cell(0, 5, texto_intro)
        pdf.ln(5)

        # ── Cabeçalho da tabela ──────────────────────────────────────────────
        col_larguras = [55, 30, 22, 18, 25, 20, 20]
        headers = ["FILME", "SALA", "DATA", "HORÁRIO", "CAPACIDADE", "RESERVAS", "OCUPAÇÃO"]

        pdf.set_fill_color(*RelatorioPDF.CINZA_700)
        pdf.set_text_color(*RelatorioPDF.BRANCO)
        pdf.set_font('Arial', 'B', 7)
        pdf.set_draw_color(*RelatorioPDF.CINZA_LINE)
        pdf.set_line_width(0.2)

        for i, h in enumerate(headers):
            align = 'L' if i < 2 else 'C'
            pdf.cell(col_larguras[i], 7, h, border=0, align=align, fill=True)
        pdf.ln()

        # ── Dados com zebra ──────────────────────────────────────────────────
        pdf.set_font('Arial', '', 8)
        cor_alternada = False

        for sessao in sessoes_ocupadas:
            filme = str(sessao[1])
            sala = str(sessao[2])
            data_str = str(sessao[3])
            try:
                data_obj = datetime.strptime(data_str, "%Y-%m-%d")
                data_str = data_obj.strftime("%d/%m/%Y")
            except:
                pass
            horario = str(sessao[4])
            capacidade = str(sessao[5])
            reservas = str(sessao[6])
            pct = float(sessao[7])
            ocupacao = f"{pct}%"

            if len(filme) > 28:
                filme = filme[:25] + "..."

            bg = RelatorioPDF.CINZA_100 if cor_alternada else RelatorioPDF.BRANCO
            pdf.set_fill_color(*bg)
            pdf.set_text_color(*RelatorioPDF.CINZA_700)

            pdf.cell(col_larguras[0], 7, filme, border='B', align='L', fill=True)
            pdf.cell(col_larguras[1], 7, sala, border='B', align='L', fill=True)
            pdf.cell(col_larguras[2], 7, data_str, border='B', align='C', fill=True)
            pdf.cell(col_larguras[3], 7, horario, border='B', align='C', fill=True)
            pdf.cell(col_larguras[4], 7, capacidade, border='B', align='C', fill=True)
            pdf.cell(col_larguras[5], 7, reservas, border='B', align='C', fill=True)

            # Badge monocromático por faixa conforme as regras visuais
            pdf.set_font('Arial', 'B', 7)
            if pct >= 90:
                pdf.set_text_color(*RelatorioPDF.BRANCO)
                pdf.set_fill_color(*RelatorioPDF.CINZA_900)
            elif pct >= 80:
                pdf.set_text_color(*RelatorioPDF.BRANCO)
                pdf.set_fill_color(*RelatorioPDF.CINZA_700)
            else:
                pdf.set_text_color(*RelatorioPDF.CINZA_700)
                pdf.set_fill_color(*RelatorioPDF.CINZA_LINE)

            pdf.cell(col_larguras[6], 7, ocupacao, border='B', align='C', fill=True)
            pdf.ln()

            pdf.set_font('Arial', '', 8)
            cor_alternada = not cor_alternada

        # ── Sumário ──────────────────────────────────────────────────────────
        pdf.ln(4)
        pdf.set_fill_color(*RelatorioPDF.CINZA_100)
        pdf.set_text_color(*RelatorioPDF.CINZA_700)
        pdf.set_font('Arial', 'B', 8)
        pdf.set_draw_color(*RelatorioPDF.CINZA_LINE)
        pdf.set_line_width(0.4)
        pdf.cell(0, 9, f"   Total de sessões mapeadas: {total_sessoes_count}",
                 border=1, ln=True, fill=True, align='L')

        pdf_path = "relatorio_sessoes_ocupacao.pdf"
        pdf.output(pdf_path)

        return send_file(pdf_path, as_attachment=True, mimetype='application/pdf')

    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expirado"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Token inválido"}), 401
    except Exception as e:
        if cur:
            con.rollback()
        print(str(e))
        return jsonify({"error": f"Erro interno ao gerar relatório: {str(e)}"}), 500
    finally:
        if cur:
            cur.close()


# ==============================================================================
# SEÇÃO SEGUINTE: CADASTROS / EXCLUSÕES / EDIÇÕES E LISTAGEM
# ==============================================================================
@sessao_blueprint.route('/cadastro_sessao', methods=['POST'])
def cadastro_sessao():
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401
    cur = None
    try:
        payload = decodificar_token(token)
        if payload['tipo'] == 1:
            return jsonify({"error": "Acesso negado"}), 403

        dados = request.get_json()
        if not dados:
            return jsonify({"error": "Payload necessário"}), 400

        id_filme = dados.get('id_filme')
        id_sala = dados.get('id_sala')
        data = dados.get('data')
        horario = dados.get('horario')
        valor = dados.get('valor_assento')

        if not id_filme or not id_sala or not data or not horario or valor is None:
            return jsonify({"error": "Dados obrigatórios não informados"}), 400

        cur = con.cursor()
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
            valor = float(str(valor).replace(',', '.'))
            if valor <= 0: raise ValueError
        except ValueError:
            return jsonify({"error": "Valor do assento inválido"}), 400

        inicio_novo = data_hora
        fim_novo = inicio_novo + timedelta(minutes=duracao)

        cur.execute(
            "SELECT s.horario, f.duracao FROM sessao s INNER JOIN filme f ON f.id_filme = s.id_filme WHERE s.id_sala = ? AND s.data = ?",
            (id_sala, data))
        sessoes = cur.fetchall()

        for sessao in sessoes:
            horario_existente = sessao[0]
            duracao_existente = sessao[1]
            inicio_existente = converter_horario(data, horario_existente)
            fim_existente = inicio_existente + timedelta(minutes=duracao_existente)

            if inicio_novo < fim_existente and fim_novo > inicio_existente:
                return jsonify({"error": "Conflito de horário com outra sessão nesta sala"}), 400

        cur.execute("SELECT 1 FROM sessao WHERE id_filme = ? AND id_sala = ? AND data = ? AND horario = ?",
                    (id_filme, id_sala, data, horario))
        if cur.fetchone():
            return jsonify({"error": "Essa sessão já está cadastrada"}), 400

        cur.execute(
            "INSERT INTO sessao (id_filme, id_sala, data, horario, valor_assento, status) VALUES (?, ?, ?, ?, ?, 1)",
            (id_filme, id_sala, data, horario, valor))
        con.commit()
        return jsonify({"message": "Sessão cadastrada com sucesso!"}), 201
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expirado"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Token inválido"}), 401
    except Exception as e:
        con.rollback()
        print(str(e))
        return jsonify({"error": "Erro interno do servidor"}), 500
    finally:
        if cur: cur.close()


@sessao_blueprint.route('/excluir_sessao/<int:id>', methods=['DELETE'])
def excluir_sessao(id):
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401
    cur = None
    try:
        payload = decodificar_token(token)
        if payload['tipo'] == 1:
            return jsonify(
                {"error": "Acesso negado", "mensagem": "Você não tem permissão para realizar esta ação."}), 403

        cur = con.cursor()
        cur.execute("SELECT data, horario FROM sessao WHERE id_sessao = ?", (id,))
        resultado = cur.fetchone()
        if not resultado:
            return jsonify({"error": "Sessão não encontrada"}), 404

        data_sessao, horario_sessao = resultado[0], resultado[1]
        data_hora_sessao = converter_horario(str(data_sessao), str(horario_sessao))

        if data_hora_sessao <= datetime.now():
            return jsonify({"error": "Sessão já aconteceu, não pode excluir"}), 400

        cur.execute("SELECT 1 FROM reserva WHERE id_sessao = ?", (id,))
        if cur.fetchone():
            return jsonify({"error": "Não é possível excluir sessão com reservas vinculadas"}), 400

        cur.execute("DELETE FROM sessao WHERE id_sessao = ?", (id,))
        con.commit()
        return jsonify({"message": "Sessão excluída com sucesso"}), 200
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expirado"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Token inválido"}), 401
    except Exception as e:
        con.rollback()
        print(str(e))
        return jsonify({"error": "Erro interno do servidor"}), 500
    finally:
        if cur: cur.close()


@sessao_blueprint.route('/editar_sessao/<int:id>', methods=['PUT'])
def editar_sessao(id):
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401
    cur = None
    try:
        payload = decodificar_token(token)
        if payload['tipo'] == 1:
            return jsonify({"error": "Acesso negado"}), 403

        dados = request.get_json()
        if not dados:
            return jsonify({"error": "Payload necessário"}), 400

        cur = con.cursor()
        cur.execute("SELECT id_filme, id_sala, data, horario, valor_assento, status FROM sessao WHERE id_sessao = ?",
                    (id,))
        sessao = cur.fetchone()
        if not sessao:
            return jsonify({"error": "Sessão não encontrada"}), 404

        id_filme = dados.get('id_filme', sessao[0])
        id_sala = dados.get('id_sala', sessao[1])
        data = dados.get('data', sessao[2])
        horario = dados.get('horario', sessao[3])
        valor = dados.get('valor_assento', sessao[4])
        status = dados.get('status', sessao[5])

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

        data_hora_antiga = converter_horario(str(sessao[2]), str(sessao[3]))
        if data_hora_antiga != data_hora and data_hora < datetime.now():
            return jsonify({"error": "Não é possível editar sessão para o passado"}), 400

        try:
            valor = float(str(valor).replace(',', '.'))
            if valor <= 0: raise ValueError
        except ValueError:
            return jsonify({"error": "Valor do assento inválido"}), 400

        inicio_novo = data_hora
        fim_novo = inicio_novo + timedelta(minutes=duracao)

        cur.execute(
            "SELECT s.horario, f.duracao FROM sessao s INNER JOIN filme f ON f.id_filme = s.id_filme WHERE s.id_sessao <> ? AND s.id_sala = ? AND s.data = ?",
            (id, id_sala, data))
        sessoes = cur.fetchall()

        for sessao_existente in sessoes:
            horario_existente = sessao_existente[0]
            duracao_existente = sessao_existente[1]
            inicio_existente = converter_horario(data, horario_existente)
            fim_existente = inicio_existente + timedelta(minutes=duracao_existente)

            if inicio_novo < fim_existente and fim_novo > inicio_existente:
                return jsonify({"error": "Conflito de horário com outra sessão nesta sala"}), 400

        cur.execute(
            "SELECT 1 FROM sessao WHERE id_sessao <> ? AND id_filme = ? AND id_sala = ? AND data = ? AND horario = ?",
            (id, id_filme, id_sala, data, horario))
        if cur.fetchone():
            return jsonify({"error": "Essa sessão já está cadastrada"}), 400

        cur.execute(
            "UPDATE sessao SET id_filme = ?, id_sala = ?, data = ?, horario = ?, valor_assento = ?, status = ? WHERE id_sessao = ?",
            (id_filme, id_sala, data, horario, valor, status, id))
        con.commit()

        return jsonify({
            "message": "Sessão atualizada com sucesso",
            "sessao": {"id_sessao": id, "id_sala": id_sala, "id_filme": id_filme, "data": str(data),
                       "horario": str(horario), "valor_assento": valor, "status": status}
        }), 200
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expirado"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Token inválido"}), 401
    except Exception as e:
        con.rollback()
        print(str(e))
        return jsonify({"error": "Erro interno do servidor"}), 500
    finally:
        if cur: cur.close()


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
                        SELECT sessao.ID_SESSAO,
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
                                 INNER JOIN filme ON filme.ID_FILME = sessao.ID_FILME
                                 INNER JOIN sala ON sala.ID_SALA = sessao.ID_SALA
                        WHERE sessao.ID_SESSAO = ?
                        """, (id_sessao,))
        else:
            cur.execute("""
                        SELECT sessao.ID_SESSAO,
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
                                 INNER JOIN filme ON filme.ID_FILME = sessao.ID_FILME
                                 INNER JOIN sala ON sala.ID_SALA = sessao.ID_SALA
                        WHERE UPPER(filme.TITULO) LIKE UPPER(?)
                          AND UPPER(sala.NOME) LIKE UPPER(?)
                          AND CAST(sessao.DATA AS VARCHAR(20)) LIKE ?
                          AND UPPER(filme.GENERO) LIKE UPPER(?)
                        """, (f"%{filme}%", f"%{sala}%", f"%{data}%", f"%{categoria}%"))

        resultado = cur.fetchall()
        if not resultado:
            return jsonify({"error": "Não há sessão relacionadas à sua busca"}), 404

        sessoes = []
        for linha in resultado:
            sessoes.append({
                "id_sessao": linha[0], "id_filme": linha[1], "id_sala": linha[2], "filme": linha[3], "sala": linha[4],
                "data": str(linha[5]), "horario": str(linha[6]), "valor_assento": linha[7], "status": linha[8],
                "genero": linha[9]
            })

        return jsonify(sessoes), 200
    except Exception as e:
        print(str(e))
        return jsonify({"error": "Erro interno do servidor ao listar sessões"}), 500
    finally:
        if cur:
            cur.close()

@sessao_blueprint.route('/listar_sessao_home', methods=['GET'])
def listar_sessao_home():

    cur = None

    try:

        cur = con.cursor()

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
                filme.GENERO,
                sala.QTD_FILEIRAS,
                sala.QTD_COLUNAS
            FROM sessao
            INNER JOIN filme
                ON filme.ID_FILME = sessao.ID_FILME
            INNER JOIN sala
                ON sala.ID_SALA = sessao.ID_SALA
            WHERE sessao.STATUS = '1'
            AND (
                sessao.DATA > CURRENT_DATE
                OR (
                    sessao.DATA = CURRENT_DATE
                    AND sessao.HORARIO > CURRENT_TIME
                )
            )
            ORDER BY sessao.DATA, sessao.HORARIO
        """)

        resultado = cur.fetchall()

        sessoes = []

        for linha in resultado:

            id_sessao = linha[0]

            qtd_fileiras = int(linha[10])
            qtd_colunas = int(linha[11])

            capacidade_total = qtd_fileiras * qtd_colunas

            # CONTA ASSENTOS RESERVADOS
            cur.execute("""
                SELECT COUNT(*)
                FROM RESERVA_ASSENTO ra
                INNER JOIN RESERVA r
                    ON r.ID_RESERVA = ra.ID_RESERVA
                WHERE r.ID_SESSAO = ?
            """, (id_sessao,))

            total_assentos = cur.fetchone()[0]

            # NÃO LISTA SESSÃO ESGOTADA
            if total_assentos >= capacidade_total:
                continue

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
                "genero": linha[9],
                "capacidade_total": capacidade_total,
                "assentos_reservados": total_assentos
            })

        return jsonify({
            "sessao": sessoes
        }), 200

    except Exception as e:

        print(str(e))

        return jsonify({
            "error": f"Erro ao listar sessões da home: {str(e)}"
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

@sessao_blueprint.route('/total_ativas', methods=['GET'])
def total_sessoes_ativas():
    cur = con.cursor()

    try:
        cur.execute("""
            SELECT COUNT(*)
            FROM SESSAO
            WHERE STATUS = '1'
        """)

        total = cur.fetchone()[0]

        return jsonify({"total": total}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()

        if cur: cur.close()

@sessao_blueprint.route('/buscar_sessao/<int:id>', methods=['GET'])
def buscar_sessao(id):

    cur = None

    try:

        cur = con.cursor()

        cur.execute("""
            SELECT
                ID_SESSAO,
                ID_FILME,
                ID_SALA,
                DATA,
                HORARIO,
                VALOR_ASSENTO,
                STATUS
            FROM sessao
            WHERE ID_SESSAO = ?
        """, (id,))

        resultado = cur.fetchone()

        if not resultado:
            return jsonify({
                "error": "Sessão não encontrada"
            }), 404

        return jsonify({
            "id_sessao": resultado[0],
            "id_filme": resultado[1],
            "id_sala": resultado[2],
            "data": str(resultado[3]),
            "horario": str(resultado[4]),
            "valor_assento": float(resultado[5]),
            "status": resultado[6]
        }), 200

    except Exception as e:

        print(str(e))

        return jsonify({
            "error": "Erro ao buscar sessão"
        }), 500

    finally:

        if cur:
            cur.close()