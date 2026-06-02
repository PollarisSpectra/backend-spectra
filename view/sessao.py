import math
from datetime import datetime, timedelta
from fpdf import FPDF
import os
import jwt
import tempfile
from flask import Blueprint, jsonify, request, current_app, send_from_directory, send_file

from database import con
from funcao import decodificar_token, converter_horario

sessao_blueprint = Blueprint('sessao', __name__, url_prefix='/sessao')


# ==============================================================================
# CLASSE PDF — RELATÓRIO DE OCUPAÇÃO
# ==============================================================================

class OcupacaoPDF(FPDF):
    """PDF corporativo cinza para o relatório de sessões com maior ocupação."""

    # ── Paleta cinza corporativo ─────────────────────────────────────────────
    CINZA_900 = (26, 26, 31)  # header / footer
    CINZA_700 = (69, 70, 80)  # cabeçalho da tabela / texto principal
    CINZA_400 = (143, 148, 153)  # texto secundário / intro
    CINZA_LINE = (222, 222, 227)  # bordas
    CINZA_100 = (242, 242, 245)  # zebra ímpar
    BRANCO = (255, 255, 255)

    def __init__(self, total_sessoes: int = 0, maior_ocupacao: str = "0.00%"):
        super().__init__()
        self.total_sessoes = total_sessoes
        self.maior_ocupacao = maior_ocupacao

    # ── Header ────────────────────────────────────────────────────────────────
    def header(self):
        # Faixa escura — altura 42 para acomodar KPIs
        self.set_fill_color(*self.CINZA_900)
        self.rect(0, 0, 210, 42, 'F')

        # Acento superior
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

        # Data — alinhada à direita
        self.set_font('Arial', '', 7)
        self.set_text_color(107, 109, 118)
        self.set_xy(14, 7)
        self.cell(183, 5, f"GERADO EM  {datetime.now().strftime('%d/%m/%Y  %H:%M')}", align='R', ln=True)

        # Divisor acima dos KPIs
        self.set_draw_color(56, 56, 64)
        self.set_line_width(0.4)
        self.line(14, 25, 196, 25)

        # ── KPI 1: Total Sessões ──────────────────────────────────────────────
        self.set_xy(14, 27)
        self.set_font('Arial', '', 6)
        self.set_text_color(107, 109, 118)
        self.cell(40, 3, "TOTAL SESSÕES", ln=True)
        self.set_x(14)
        self.set_font('Arial', 'B', 9)
        self.set_text_color(*self.BRANCO)
        self.cell(40, 4, str(self.total_sessoes), ln=True)

        # ── KPI 2: Maior Ocupação ─────────────────────────────────────────────
        self.set_xy(70, 27)
        self.set_font('Arial', '', 6)
        self.set_text_color(107, 109, 118)
        self.cell(40, 3, "MAIOR OCUPAÇÃO", ln=True)
        self.set_x(70)
        self.set_font('Arial', 'B', 9)
        self.set_text_color(*self.BRANCO)
        self.cell(40, 4, self.maior_ocupacao, ln=True)

        # ── KPI 3: Período ────────────────────────────────────────────────────
        meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
        periodo_str = f"{meses[datetime.now().month - 1]} {datetime.now().year}"
        self.set_xy(125, 27)
        self.set_font('Arial', '', 6)
        self.set_text_color(107, 109, 118)
        self.cell(40, 3, "PERÍODO", ln=True)
        self.set_x(125)
        self.set_font('Arial', 'B', 9)
        self.set_text_color(*self.BRANCO)
        self.cell(40, 4, periodo_str, ln=True)

        # Divisor inferior do header
        self.set_draw_color(*self.CINZA_LINE)
        self.set_line_width(0.3)
        self.line(0, 42, 210, 42)
        self.set_xy(14, 47)

    # ── Footer ────────────────────────────────────────────────────────────────
    def footer(self):
        self.set_y(-13)
        self.set_fill_color(*self.CINZA_900)
        self.rect(0, self.get_y() - 1, 210, 16, 'F')

        self.set_draw_color(56, 56, 64)
        self.set_line_width(0.4)
        self.line(0, self.get_y() - 1, 210, self.get_y() - 1)

        self.set_font('Arial', '', 7)
        self.set_text_color(128, 130, 138)
        self.cell(
            130, 10,
            f"   Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}   |   Relatório Corporativo",
            align='L'
        )

        self.set_font('Arial', 'B', 7)
        self.set_text_color(190, 190, 195)
        self.cell(0, 10, f'Página {self.page_no()}/{{nb}}', align='R')


# ==============================================================================
# ROTA: RELATÓRIO DE SESSÕES COM MAIOR OCUPAÇÃO
# ==============================================================================

@sessao_blueprint.route('/relatorio_ocupacao', methods=['GET'])
def relatorio_ocupacao():
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    cur = None
    try:
        payload = decodificar_token(token)
        if payload['tipo'] == 1:
            return jsonify({"error": "Acesso negado"}), 403

        cur = con.cursor()

        cur.execute("""
            SELECT
                s.id_sessao,
                f.titulo AS filme_titulo,
                sa.nome AS sala_nome,
                s.data,
                s.horario,
                (sa.qtd_fileiras * sa.qtd_colunas) AS capacidade_total,
                COUNT(ra.id_assento_sala) AS total_assentos_vendidos,
                CAST(
                    (
                        (CAST(COUNT(ra.id_assento_sala) AS REAL) /
                        (sa.qtd_fileiras * sa.qtd_colunas)) * 100
                    ) AS NUMERIC(15, 2)
                ) AS percentual_ocupacao
            FROM sessao s
            INNER JOIN filme f 
                ON f.id_filme = s.id_filme
            INNER JOIN sala sa 
                ON sa.id_sala = s.id_sala
            LEFT JOIN reserva r 
                ON r.id_sessao = s.id_sessao
            LEFT JOIN reserva_assento ra 
                ON ra.id_reserva = r.id_reserva
            GROUP BY
                s.id_sessao,
                f.titulo,
                sa.nome,
                s.data,
                s.horario,
                (sa.qtd_fileiras * sa.qtd_colunas)
            HAVING COUNT(ra.id_assento_sala) > 0
            ORDER BY 8 DESC, 7 DESC
                    """)
        sessoes = cur.fetchall()

        if not sessoes:
            return jsonify({"error": "Não há dados de ocupação para gerar o relatório."}), 404

        total_sessoes_count = len(sessoes)
        max_pct = max(float(s[7]) for s in sessoes)
        maior_ocupacao_str = f"{max_pct:.2f}%"

        # ── Instância e configuração do PDF ──────────────────────────────────
        pdf = OcupacaoPDF(total_sessoes=total_sessoes_count, maior_ocupacao=maior_ocupacao_str)
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # ── Texto de introdução ───────────────────────────────────────────────
        pdf.set_font('Arial', '', 8)
        pdf.set_text_color(*OcupacaoPDF.CINZA_400)
        pdf.multi_cell(0, 5, (
            "Análise consolidada das sessões com maior índice de ocupação. "
            "Utilize estas informações para decisões de alocação de salas e programação de horários."
        ))
        pdf.ln(5)

        # ── Cabeçalho da tabela ───────────────────────────────────────────────
        col_larg = [55, 30, 22, 18, 25, 20, 20]
        col_heads = ["FILME", "SALA", "DATA", "HORÁRIO", "CAPACIDADE", "RESERVAS", "OCUPAÇÃO"]

        pdf.set_fill_color(*OcupacaoPDF.CINZA_700)
        pdf.set_text_color(*OcupacaoPDF.BRANCO)
        pdf.set_font('Arial', 'B', 7)
        pdf.set_draw_color(*OcupacaoPDF.CINZA_LINE)
        pdf.set_line_width(0.2)

        for i, h in enumerate(col_heads):
            pdf.cell(col_larg[i], 7, h, border=0, align='L' if i < 2 else 'C', fill=True)
        pdf.ln()

        # ── Linhas de dados com zebra ─────────────────────────────────────────
        pdf.set_font('Arial', '', 8)
        cor_alternada = False

        for sessao in sessoes:
            filme = str(sessao[1])
            sala = str(sessao[2])
            data_str = str(sessao[3])
            try:
                data_str = datetime.strptime(data_str, "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                pass
            horario = str(sessao[4])
            cap = str(sessao[5])
            reservas = str(sessao[6])
            pct = float(sessao[7])
            ocupacao = f"{pct:.2f}%"

            if len(filme) > 28:
                filme = filme[:25] + "..."

            bg = OcupacaoPDF.CINZA_100 if cor_alternada else OcupacaoPDF.BRANCO
            pdf.set_fill_color(*bg)
            pdf.set_text_color(*OcupacaoPDF.CINZA_700)
            pdf.set_font('Arial', '', 8)

            pdf.cell(col_larg[0], 7, filme, border='B', align='L', fill=True)
            pdf.cell(col_larg[1], 7, sala, border='B', align='L', fill=True)
            pdf.cell(col_larg[2], 7, data_str, border='B', align='C', fill=True)
            pdf.cell(col_larg[3], 7, horario, border='B', align='C', fill=True)
            pdf.cell(col_larg[4], 7, cap, border='B', align='C', fill=True)
            pdf.cell(col_larg[5], 7, reservas, border='B', align='C', fill=True)

            # Coluna de ocupação com badge de cor por intensidade
            pdf.set_font('Arial', 'B', 7)
            if pct >= 90:
                pdf.set_text_color(*OcupacaoPDF.BRANCO)
                pdf.set_fill_color(*OcupacaoPDF.CINZA_900)
            elif pct >= 80:
                pdf.set_text_color(*OcupacaoPDF.BRANCO)
                pdf.set_fill_color(*OcupacaoPDF.CINZA_700)
            else:
                pdf.set_text_color(*OcupacaoPDF.CINZA_700)
                pdf.set_fill_color(*OcupacaoPDF.CINZA_LINE)

            pdf.cell(col_larg[6], 7, ocupacao, border='B', align='C', fill=True)
            pdf.ln()

            cor_alternada = not cor_alternada

        # ── Rodapé da tabela — total ──────────────────────────────────────────
        pdf.ln(4)
        pdf.set_fill_color(*OcupacaoPDF.CINZA_100)
        pdf.set_text_color(*OcupacaoPDF.CINZA_700)
        pdf.set_font('Arial', 'B', 8)
        pdf.set_draw_color(*OcupacaoPDF.CINZA_LINE)
        pdf.set_line_width(0.4)
        pdf.cell(
            0, 9,
            f"   Total de sessões mapeadas: {total_sessoes_count}",
            border=1, ln=True, fill=True, align='L'
        )

        # ── Salva em arquivo temporário e envia ───────────────────────────────
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False, prefix='relatorio_ocupacao_') as tmp:
            pdf_path = tmp.name

        pdf.output(pdf_path)

        nome_arquivo = f"relatorio_ocupacao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=nome_arquivo,
            mimetype='application/pdf'
        )

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
# CADASTRO / EDIÇÃO / EXCLUSÃO / LISTAGEM DE SESSÕES
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
            if valor <= 0:
                raise ValueError
        except ValueError:
            return jsonify({"error": "Valor do assento inválido"}), 400

        inicio_novo = data_hora
        fim_novo = inicio_novo + timedelta(minutes=duracao)

        cur.execute(
            "SELECT s.horario, f.duracao FROM sessao s "
            "INNER JOIN filme f ON f.id_filme = s.id_filme "
            "WHERE s.id_sala = ? AND s.data = ?",
            (id_sala, data)
        )
        for sessao in cur.fetchall():
            inicio_ex = converter_horario(data, sessao[0])
            fim_ex = inicio_ex + timedelta(minutes=sessao[1])
            if inicio_novo < fim_ex and fim_novo > inicio_ex:
                return jsonify({"error": "Conflito de horário com outra sessão nesta sala"}), 400

        cur.execute(
            "SELECT 1 FROM sessao WHERE id_filme = ? AND id_sala = ? AND data = ? AND horario = ?",
            (id_filme, id_sala, data, horario)
        )
        if cur.fetchone():
            return jsonify({"error": "Essa sessão já está cadastrada"}), 400

        cur.execute(
            "INSERT INTO sessao (id_filme, id_sala, data, horario, valor_assento, status) VALUES (?, ?, ?, ?, ?, 1)",
            (id_filme, id_sala, data, horario, valor)
        )
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
        if cur:
            cur.close()


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

        data_hora_sessao = converter_horario(str(resultado[0]), str(resultado[1]))
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
        if cur:
            cur.close()


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
        cur.execute(
            "SELECT id_filme, id_sala, data, horario, valor_assento, status FROM sessao WHERE id_sessao = ?",
            (id,)
        )
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
            if valor <= 0:
                raise ValueError
        except ValueError:
            return jsonify({"error": "Valor do assento inválido"}), 400

        inicio_novo = data_hora
        fim_novo = inicio_novo + timedelta(minutes=duracao)

        cur.execute(
            "SELECT s.horario, f.duracao FROM sessao s "
            "INNER JOIN filme f ON f.id_filme = s.id_filme "
            "WHERE s.id_sessao <> ? AND s.id_sala = ? AND s.data = ?",
            (id, id_sala, data)
        )
        for s_ex in cur.fetchall():
            inicio_ex = converter_horario(data, s_ex[0])
            fim_ex = inicio_ex + timedelta(minutes=s_ex[1])
            if inicio_novo < fim_ex and fim_novo > inicio_ex:
                return jsonify({"error": "Conflito de horário com outra sessão nesta sala"}), 400

        cur.execute(
            "SELECT 1 FROM sessao WHERE id_sessao <> ? AND id_filme = ? AND id_sala = ? AND data = ? AND horario = ?",
            (id, id_filme, id_sala, data, horario)
        )
        if cur.fetchone():
            return jsonify({"error": "Essa sessão já está cadastrada"}), 400

        cur.execute(
            "UPDATE sessao SET id_filme = ?, id_sala = ?, data = ?, horario = ?, valor_assento = ?, status = ? WHERE id_sessao = ?",
            (id_filme, id_sala, data, horario, valor, status, id)
        )
        con.commit()

        return jsonify({
            "message": "Sessão atualizada com sucesso",
            "sessao": {
                "id_sessao": id, "id_sala": id_sala, "id_filme": id_filme,
                "data": str(data), "horario": str(horario),
                "valor_assento": valor, "status": status
            }
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
            return jsonify({"error": "Não há sessões relacionadas à sua busca"}), 404

        sessoes = []
        for linha in resultado:
            sessoes.append({
                "id_sessao": linha[0],
                "id_filme": linha[1],
                "id_sala": linha[2],
                "filme": linha[3],  # CORRIGIDO: era [3] if 'inline' in locals() else linha[3]
                "sala": linha[4],
                "data": str(linha[5]),
                "horario": str(linha[6]),
                "valor_assento": linha[7],
                "status": linha[8],
                "genero": linha[9],
            })

        return jsonify(sessoes), 200

    except Exception as e:
        print(str(e))
        return jsonify({"error": "Erro interno do servidor ao listar sessões"}), 500
    finally:
        if cur:
            cur.close()

@sessao_blueprint.route('/listar_sessao_paginacao', methods=['GET'])
def listar_sessao_paginacao():
    cur = None
    try:
        cur = con.cursor()
        id_sessao = request.args.get('id_sessao')
        filme = request.args.get('filme', '')
        sala = request.args.get('sala', '')
        data = request.args.get('data', '')
        categoria = request.args.get('categoria', '')
        page_size = int(request.args.get('page_size', 10))
        page_number = int(request.args.get('page_number', 1))
        offset = (page_number - 1) * page_size

        base_query = """
            FROM sessao
                     INNER JOIN filme ON filme.ID_FILME = sessao.ID_FILME
                     INNER JOIN sala ON sala.ID_SALA = sessao.ID_SALA
        """

        if id_sessao:
            cur.execute(f"""
                        SELECT COUNT(*)
                        {base_query}
                        WHERE sessao.ID_SESSAO = ?
                        """, (id_sessao,))
            total_results = cur.fetchone()[0]

            cur.execute(f"""
                        SELECT FIRST ? SKIP ?
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
                        {base_query}
                        WHERE sessao.ID_SESSAO = ?
                        ORDER BY sessao.ID_SESSAO
                        """, (page_size, offset, id_sessao))
        else:
            params = (f"%{filme}%", f"%{sala}%", f"%{data}%", f"%{categoria}%")
            filters = """
                WHERE UPPER(filme.TITULO) LIKE UPPER(?)
                  AND UPPER(sala.NOME) LIKE UPPER(?)
                  AND CAST(sessao.DATA AS VARCHAR(20)) LIKE ?
                  AND UPPER(filme.GENERO) LIKE UPPER(?)
            """

            cur.execute(f"SELECT COUNT(*) {base_query} {filters}", params)
            total_results = cur.fetchone()[0]

            cur.execute(f"""
                        SELECT FIRST ? SKIP ?
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
                        {base_query}
                        {filters}
                        ORDER BY sessao.ID_SESSAO
                        """, (page_size, offset, *params))

        resultado = cur.fetchall()

        if not resultado and page_number == 1:
            return jsonify({"error": "Não há sessões relacionadas à sua busca"}), 404

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
                "valor_assento": linha[7],
                "status": linha[8],
                "genero": linha[9],
            })

        return jsonify({
            "total_results": total_results,
            "total_pages": math.ceil(total_results / page_size) if total_results > 0 else 0,
            "current_page": page_number,
            "sessoes": sessoes,
        }), 200

    except ValueError:
        return jsonify({"error": "page_size e page_number devem ser números inteiros"}), 400
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

        id_sessao = request.args.get('id_sessao')

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
                    filme.GENERO,
                    sala.QTD_FILEIRAS,
                    sala.QTD_COLUNAS
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
            id_sessao_linha = linha[0]

            qtd_fileiras = int(linha[10])
            qtd_colunas = int(linha[11])
            capacidade_total = qtd_fileiras * qtd_colunas

            cur.execute("""
                SELECT COUNT(*)
                FROM RESERVA_ASSENTO ra
                INNER JOIN RESERVA r
                    ON r.ID_RESERVA = ra.ID_RESERVA
                WHERE r.ID_SESSAO = ?
            """, (id_sessao_linha,))

            total_assentos = cur.fetchone()[0]

            if not id_sessao and total_assentos >= capacidade_total:
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
    caminho = os.path.join(current_app.config['UPLOAD_FOLDER'], "Filmes")
    return send_from_directory(caminho, filename)


@sessao_blueprint.route('/sala_sessao/<int:id_sessao>', methods=['GET'])
def sala_sessao(id_sessao):
    cur = None
    try:
        cur = con.cursor()
        cur.execute("""
                    SELECT sessao.ID_SESSAO,
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
                             INNER JOIN filme ON filme.ID_FILME = sessao.ID_FILME
                             INNER JOIN sala ON sala.ID_SALA = sessao.ID_SALA
                    WHERE sessao.ID_SESSAO = ?
                    """, (id_sessao,))

        resultado = cur.fetchone()
        if not resultado:
            return jsonify({"error": "Sessão não encontrada"}), 404

        return jsonify({
            "filme": {
                "id_filme": resultado[3],
                "titulo": resultado[4],
                "genero": resultado[5],
                "duracao": resultado[6],
                "sinopse": resultado[7],
                "imagem_url": f"/sessao/imagem_filme/{resultado[3]}.jpg",
                "data": str(resultado[1]),
                "horario": str(resultado[2]),
            },
            "sala": {
                "id_sala": resultado[8],
                "nome": resultado[9],
                "qtd_fileiras": int(resultado[10]),
                "qtd_colunas": int(resultado[11]),
            }
        }), 200

    except Exception as e:
        print(str(e))
        return jsonify({"error": f"Erro ao buscar sala da sessão: {str(e)}"}), 500
    finally:
        if cur:
            cur.close()


@sessao_blueprint.route('/total_ativas', methods=['GET'])
def total_sessoes_ativas():
    cur = con.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM SESSAO WHERE STATUS = '1'")
        total = cur.fetchone()[0]
        return jsonify({"total": total}), 200  # CORRIGIDO: era dict puro sem jsonify
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cur:
            cur.close()

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