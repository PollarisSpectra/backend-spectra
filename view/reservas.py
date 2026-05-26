import base64
import io
import math
import os
import tempfile
import threading

import jwt
import qrcode
from flask import Blueprint, jsonify, request, current_app, send_file
from fpdf import FPDF
from datetime import datetime

from database import con
from funcao import decodificar_token, gerar_payload_pix, enviando_email

reservas_bp = Blueprint('reservas', __name__, url_prefix='/reservas')


# ==============================================================================
# UTILITÁRIO
# ==============================================================================

def fmt_brl(v) -> str:
    """Formata valor numérico para moeda BRL: R$ 1.234,56"""
    try:
        return f"R$ {float(v):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (TypeError, ValueError):
        return 'R$ 0,00'


# ==============================================================================
# CLASSE PDF — RELATÓRIO DE RESERVAS
# ==============================================================================

class ReservaPDF(FPDF):
    """PDF corporativo cinza para o relatório de reservas realizadas."""

    COR_HEADER_BG = (26, 26, 31)
    COR_HEADER_TEXT = (255, 255, 255)
    COR_ACCENT = (90, 90, 105)
    COR_KPI_BG = (40, 40, 48)
    COR_KPI_TEXT = (200, 200, 210)
    COR_KPI_VALUE = (255, 255, 255)
    COR_TABLE_HEAD = (50, 50, 60)
    COR_ZEBRA_DARK = (245, 245, 248)
    COR_ZEBRA_LIGHT = (255, 255, 255)
    COR_FOOTER_TEXT = (140, 140, 155)
    COR_BODY_TEXT = (30, 30, 40)

    STATUS_BADGE = {
        1: ((220, 220, 220), (50, 50, 50), 'Pago'),
        2: ((200, 200, 200), (80, 80, 80), 'Pendente'),
        3: ((160, 160, 160), (255, 255, 255), 'Cancelado'),
    }
    STATUS_DEFAULT = ((190, 190, 190), (50, 50, 50), 'Indefinido')

    def __init__(self, kpis: dict):
        super().__init__(orientation='L', unit='mm', format='A4')
        self.kpis = kpis
        self.gerado_em = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        self.set_auto_page_break(auto=True, margin=18)
        self.alias_nb_pages()

    def header(self):
        self.set_fill_color(*self.COR_HEADER_BG)
        self.rect(0, 0, self.w, 22, 'F')

        self.set_y(6)
        self.set_font('Helvetica', 'B', 13)
        self.set_text_color(*self.COR_HEADER_TEXT)
        self.cell(0, 10, 'RELATÓRIO DE RESERVAS REALIZADAS', align='C')

        self.set_font('Helvetica', '', 7)
        self.set_text_color(*self.COR_FOOTER_TEXT)
        self.set_xy(self.w - 68, 14)
        self.cell(60, 5, f'Gerado em: {self.gerado_em}', align='R')

        self._draw_kpis()
        self.set_y(50)

    def _draw_kpis(self):
        margem = 10
        espaco = 5
        largura = (self.w - 2 * margem - 2 * espaco) / 3
        altura = 20
        y_ini = 24

        kpi_data = [
            ('TOTAL RESERVAS', str(self.kpis['total_reservas'])),
            ('FATURAMENTO BRUTO', fmt_brl(self.kpis['faturamento_bruto'])),
            ('TOTAL DESCONTOS', fmt_brl(self.kpis['total_descontos'])),
        ]

        for i, (label, valor) in enumerate(kpi_data):
            x = margem + i * (largura + espaco)

            self.set_fill_color(*self.COR_KPI_BG)
            self.set_draw_color(*self.COR_ACCENT)
            self.set_line_width(0.3)
            self.rect(x, y_ini, largura, altura, 'FD')

            self.set_xy(x, y_ini + 3)
            self.set_font('Helvetica', '', 6.5)
            self.set_text_color(*self.COR_KPI_TEXT)
            self.cell(largura, 5, label, align='C')

            self.set_xy(x, y_ini + 9)
            self.set_font('Helvetica', 'B', 11)
            self.set_text_color(*self.COR_KPI_VALUE)
            self.cell(largura, 8, valor, align='C')

    def footer(self):
        self.set_y(-12)
        self.set_draw_color(*self.COR_ACCENT)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), self.w - 10, self.get_y())

        self.set_y(-10)
        self.set_font('Helvetica', '', 7)
        self.set_text_color(*self.COR_FOOTER_TEXT)
        self.cell(0, 5, f'Gerado em: {self.gerado_em}', align='L')
        self.set_y(-10)
        self.cell(0, 5, f'Página {self.page_no()} de {{nb}}', align='R')

    def desenhar_cabecalho_tabela(self, colunas: list):
        self.set_fill_color(*self.COR_TABLE_HEAD)
        self.set_text_color(*self.COR_HEADER_TEXT)
        self.set_font('Helvetica', 'B', 8)
        self.set_draw_color(*self.COR_ACCENT)
        self.set_line_width(0.2)
        for label, larg, alinha in colunas:
            self.cell(larg, 8, label, border=1, align=alinha, fill=True)
        self.ln()

    def desenhar_linha_tabela(self, colunas: list, dados: list, num_linha: int):
        zebra = num_linha % 2 == 0
        cor_bg = self.COR_ZEBRA_DARK if zebra else self.COR_ZEBRA_LIGHT
        self.set_fill_color(*cor_bg)
        self.set_text_color(*self.COR_BODY_TEXT)
        self.set_font('Helvetica', '', 7.5)
        self.set_draw_color(210, 210, 218)
        self.set_line_width(0.1)

        altura_linha = 7
        if self.get_y() + altura_linha > self.page_break_trigger:
            self.add_page()
            self.desenhar_cabecalho_tabela(colunas)

        for idx, ((_, larg, alinha), valor) in enumerate(zip(colunas, dados)):
            if idx == len(colunas) - 1:
                self._desenhar_badge_status(larg, altura_linha, valor, cor_bg)
            else:
                self.cell(larg, altura_linha, str(valor), border='B', align=alinha, fill=True)
        self.ln()

    def _desenhar_badge_status(self, largura: float, altura: float, status_id, cor_bg):
        badge_info = self.STATUS_BADGE.get(status_id, self.STATUS_DEFAULT)
        cor_badge_bg, cor_badge_txt, texto = badge_info

        x = self.get_x()
        y = self.get_y()

        self.set_fill_color(*cor_bg)
        self.rect(x, y, largura, altura, 'F')

        badge_w = largura - 6
        badge_h = altura - 2.5
        badge_x = x + (largura - badge_w) / 2
        badge_y = y + (altura - badge_h) / 2

        self.set_fill_color(*cor_badge_bg)
        self.set_draw_color(*self.COR_ACCENT)
        self.set_line_width(0.2)
        self.rect(badge_x, badge_y, badge_w, badge_h, 'F')

        self.set_xy(badge_x, badge_y)
        self.set_font('Helvetica', 'B', 6.5)
        self.set_text_color(*cor_badge_txt)
        self.cell(badge_w, badge_h, texto, align='C')

        self.set_draw_color(210, 210, 218)
        self.set_line_width(0.1)
        self.line(x, y + altura, x + largura, y + altura)
        self.set_xy(x + largura, y)


# ==============================================================================
# ROTA: RELATÓRIO DE RESERVAS REALIZADAS
# ==============================================================================

@reservas_bp.route('/relatorio_reservas', methods=['GET'])
def relatorio_reservas():
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({'erro': 'Token de acesso ausente.'}), 401

    payload = decodificar_token(token)
    if not payload:
        return jsonify({'erro': 'Token inválido ou expirado.'}), 401

    if payload.get('tipo') == 1:
        return jsonify({'erro': 'Acesso negado. Permissão insuficiente.'}), 403

    cursor = con.cursor()
    try:
        cursor.execute("""
                       SELECT r.ID_RESERVA,
                              u.NOME   AS CLIENTE,
                              f.TITULO AS FILME,
                              r.DATARESERVA,
                              r.VALORTOTAL,
                              r.DESCONTO,
                              r.STATUS
                       FROM RESERVA r
                                INNER JOIN USUARIO u ON u.ID_USUARIO = r.ID_USUARIO
                                INNER JOIN SESSAO s ON s.ID_SESSAO = r.ID_SESSAO
                                INNER JOIN FILME f ON f.ID_FILME = s.ID_FILME
                       ORDER BY r.ID_RESERVA DESC
                       """)
        registros = cursor.fetchall()

        total_reservas = len(registros)
        faturamento_bruto = sum(float(row[4] or 0) for row in registros)
        total_descontos = sum(float(row[5] or 0) for row in registros)

        pdf = ReservaPDF(kpis={
            'total_reservas': total_reservas,
            'faturamento_bruto': faturamento_bruto,
            'total_descontos': total_descontos,
        })
        pdf.add_page()

        colunas = [
            ('CÓD.', 18, 'C'),
            ('CLIENTE', 72, 'L'),
            ('FILME', 72, 'L'),
            ('DATA', 30, 'C'),
            ('TOTAL', 32, 'R'),
            ('DESC.', 28, 'R'),
            ('STATUS', 35, 'C'),
        ]
        pdf.desenhar_cabecalho_tabela(colunas)

        for num_linha, row in enumerate(registros):
            id_reserva, cliente, filme, data_reserva, valor_total, desconto, status = row

            if isinstance(data_reserva, datetime):
                data_fmt = data_reserva.strftime('%d/%m/%Y')
            elif data_reserva:
                data_fmt = str(data_reserva)[:10]
            else:
                data_fmt = '—'

            pdf.desenhar_linha_tabela(
                colunas,
                [
                    str(id_reserva),
                    str(cliente or '').strip()[:35],
                    str(filme or '').strip()[:35],
                    data_fmt,
                    fmt_brl(valor_total),
                    fmt_brl(desconto),
                    status,
                ],
                num_linha
            )

        # Linha de totais
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_fill_color(*ReservaPDF.COR_TABLE_HEAD)
        pdf.set_text_color(*ReservaPDF.COR_HEADER_TEXT)
        pdf.set_draw_color(*ReservaPDF.COR_ACCENT)
        pdf.set_line_width(0.3)

        totais = [
            ('', 18),
            (f'{total_reservas} registro(s)', 72),
            ('', 72),
            ('TOTAIS', 30),
            (fmt_brl(faturamento_bruto), 32),
            (fmt_brl(total_descontos), 28),
            ('', 35),
        ]
        for texto, larg in totais:
            alinha = 'R' if texto.startswith('R$') else ('C' if texto in ('', 'TOTAIS') else 'L')
            pdf.cell(larg, 8, texto, border=1, align=alinha, fill=True)
        pdf.ln()

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False, prefix='relatorio_reservas_') as tmp:
            pdf_path = tmp.name

        pdf.output(pdf_path)

        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"relatorio_reservas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            mimetype='application/pdf'
        )

    except Exception as e:
        return jsonify({'erro': f'Erro ao gerar relatório: {str(e)}'}), 500
    finally:
        cursor.close()


# ==============================================================================
# ROTA: CONSULTAR RESERVA POR ID
# CORRIGIDO: indentação perdida — corpo estava no nível do módulo
# ==============================================================================

@reservas_bp.route("/<int:id>")
def reservas(id):
    if not id:
        return jsonify({"error": "Campo 'id' necessario"}), 400

    cur = None
    try:
        cur = con.cursor()
        cur.execute("SELECT * FROM reserva WHERE id_reserva = ?", (id,))

        rawReserva = cur.fetchone()
        if not rawReserva:
            return jsonify({"error": "Reserva nao encontrada"}), 404

        columns = [desc[0].lower() for desc in cur.description]
        reserva = dict(zip(columns, rawReserva))

        return jsonify({"message": "Sucesso ao consultar reserva", "reserva": reserva}), 200

    except Exception as e:
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        if cur:
            cur.close()


# ==============================================================================
# ROTA: LISTAR RESERVAS DE UM USUÁRIO (paginado + filtros)
# CORRIGIDO: SELECT FIRST ? SKIP ? duplicado no sql_main
# ==============================================================================

@reservas_bp.route('/<int:id_usuario>/usuario', methods=['GET'])
def listar_reservas_usuario(id_usuario):
    cur = None
    try:
        id_reserva_filtro = request.args.get('id_reserva', '')
        id_sessao_filtro = request.args.get('id_sessao', '')
        status_filtro = request.args.get('status', '')

        page_size = int(request.args.get('page_size', 10))
        page_number = int(request.args.get('page_number', 1))
        offset = (page_number - 1) * page_size

        cur = con.cursor()

        # Contagem total com filtros
        cur.execute("""
                    SELECT COUNT(*)
                    FROM RESERVA
                    WHERE ID_USUARIO = ?
                      AND CAST(ID_RESERVA AS VARCHAR(20)) LIKE ?
                      AND CAST(ID_SESSAO AS VARCHAR(20)) LIKE ?
                      AND CAST(STATUS AS VARCHAR(20)) LIKE ?
                    """, (
                        id_usuario,
                        f"%{id_reserva_filtro}%",
                        f"%{id_sessao_filtro}%",
                        f"%{status_filtro}%",
                    ))
        total_results = cur.fetchone()[0]

        # Query principal — SELECT FIRST/SKIP aparecia duplicado; corrigido
        cur.execute("""
                    SELECT FIRST ? SKIP ?
                        r.ID_RESERVA, r.ID_PROMOCAO, r.ID_USUARIO, r.ID_SESSAO, r.VALORTOTAL, r.DESCONTO, r.STATUS, r.DATARESERVA, s.ID_FILME, f.TITULO AS FILME_TITULO
                    FROM RESERVA r
                        INNER JOIN SESSAO s
                    ON r.ID_SESSAO = s.ID_SESSAO
                        INNER JOIN FILME f ON s.ID_FILME = f.ID_FILME
                    WHERE r.ID_USUARIO = ?
                      AND CAST (r.ID_RESERVA AS VARCHAR (20)) LIKE ?
                      AND CAST (r.ID_SESSAO AS VARCHAR (20)) LIKE ?
                      AND CAST (r.STATUS AS VARCHAR (20)) LIKE ?
                    ORDER BY r.ID_RESERVA DESC
                    """, (
                        page_size,
                        offset,
                        id_usuario,
                        f"%{id_reserva_filtro}%",
                        f"%{id_sessao_filtro}%",
                        f"%{status_filtro}%",
                    ))

        reservas = cur.fetchall()
        columns = [desc[0].lower() for desc in cur.description]
        resultados = [dict(zip(columns, row)) for row in reservas]

        for r in resultados:
            if r.get('datareserva'):
                r['datareserva'] = str(r['datareserva'])

            id_filme = r.get('id_filme')
            if id_filme:
                caminho = os.path.join(current_app.config['UPLOAD_FOLDER'], "Filmes", f"{id_filme}.jpg")
                r['imagem_url'] = f"/imagem_filme/{id_filme}.jpg" if os.path.exists(caminho) else None
            else:
                r['imagem_url'] = None

        if not resultados and page_number == 1:
            return jsonify({"reservas": [], "total_pages": 0, "current_page": 1}), 200

        total_pages = math.ceil(total_results / page_size) if total_results > 0 else 0

        return jsonify({
            "total_results": total_results,
            "total_pages": total_pages,
            "current_page": page_number,
            "reservas": resultados,
        }), 200

    except ValueError:
        return jsonify({"error": "page_size e page_number devem ser números inteiros"}), 400
    except Exception as e:
        print(f"Erro ao listar reservas: {str(e)}")
        return jsonify({"error": "Erro interno ao processar reservas"}), 500
    finally:
        if cur:
            cur.close()


# ==============================================================================
# ROTA: CRIAR RESERVA
# ==============================================================================

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

        # Verifica assentos já ocupados
        cur.execute("""
                    SELECT ra.ID_ASSENTO_SALA
                    FROM RESERVA_ASSENTO ra
                             LEFT JOIN RESERVA r ON r.ID_RESERVA = ra.ID_RESERVA
                    WHERE r.STATUS = '1'
                      AND r.ID_SESSAO = ?
                    """, (id_sessao,))

        columns = [desc[0].lower() for desc in cur.description]
        assentos_sessao = [dict(zip(columns, row)) for row in cur.fetchall()]

        for reserva in assentos_sessao:
            if reserva['id_assento_sala'] in assentos:
                return jsonify({"error": "Poltrona(s) ja reservada(s)"}), 400

        # Valor do assento
        cur.execute("SELECT valor_assento FROM sessao WHERE id_sessao = ?", (id_sessao,))
        valor_assento = cur.fetchone()[0]

        # Cria a reserva
        cur.execute("""
                    INSERT INTO reserva (id_promocao, id_usuario, id_sessao, valortotal, desconto, status, datareserva,
                                         expiracao)
                    VALUES (?, ?, ?, ?, 0, ?, CURRENT_TIMESTAMP,
                            DATEADD(10 MINUTE TO CURRENT_TIMESTAMP)) RETURNING id_reserva
                    """, (None, id_usuario, id_sessao, len(assentos) * valor_assento, 3))

        id_reserva_criada = cur.fetchone()[0]
        if not id_reserva_criada:
            raise Exception("Internal Server Error")

        # Cria os registros de assento vinculados
        cur.executemany("""
                        INSERT INTO reserva_assento (id_reserva, id_assento_sala)
                        VALUES (?, ?)
                        """, [(id_reserva_criada, id_assento) for id_assento in assentos])

        con.commit()

        return jsonify({"message": "Reserva criada com sucesso", "id_reserva": id_reserva_criada})

    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Expired token"}), 401
    except jwt.InvalidTokenError:
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


# ==============================================================================
# ROTA: CONFIRMAR PAGAMENTO DE RESERVA
# CORRIGIDO: SELECT ast.ASSENTO duplicado na query de assentos
# ==============================================================================

@reservas_bp.route('/pagamento/<int:id>', methods=["POST"])
def pagamento(id):
    cur = None
    try:
        cookie = request.cookies.get('access_token')
        if not cookie:
            return jsonify({"error": "Token de autenticacao necessario"}), 401

        payload = decodificar_token(cookie)
        id_usuario = payload['id_usuario']

        if not id:
            return jsonify({"error": "Insira o id da reserva"}), 400

        cur = con.cursor()

        # Confirma o pagamento
        cur.execute("""
                    UPDATE RESERVA r
                    SET r.STATUS = '1'
                    WHERE r.ID_RESERVA = ?
                    """, (id,))
        con.commit()

        # Dados gerais para o e-mail
        cur.execute("""
                    SELECT u.NOME,
                           u.EMAIL,
                           f.TITULO,
                           r.VALORTOTAL,
                           r.ID_RESERVA,
                           s.DATA,
                           s.HORARIO
                    FROM RESERVA r
                             INNER JOIN USUARIO u ON u.ID_USUARIO = r.ID_USUARIO
                             INNER JOIN SESSAO s ON s.ID_SESSAO = r.ID_SESSAO
                             INNER JOIN FILME f ON f.ID_FILME = s.ID_FILME
                    WHERE r.ID_RESERVA = ?
                    """, (id,))

        dados = cur.fetchone()

        if dados:
            nome, email, filme, valor_total, id_reserva, data_sessao, horario_sessao = dados

            # Busca os assentos desta reserva — SELECT duplicado removido
            cur.execute("""
                        SELECT ast.ASSENTO
                        FROM RESERVA_ASSENTO ra
                                 INNER JOIN ASSENTO_SALA ast ON ast.ID_ASSENTO_SALA = ra.ID_ASSENTO_SALA
                        WHERE ra.ID_RESERVA = ?
                        ORDER BY ast.ASSENTO
                        """, (id,))

            lista_assentos = [linha[0] for linha in cur.fetchall()]
            total_ingressos = len(lista_assentos)
            assentos_formatados = ", ".join(lista_assentos)

            data_formatada = (
                data_sessao.strftime('%d/%m/%Y')
                if hasattr(data_sessao, 'strftime')
                else str(data_sessao)
            )

            mensagem = f"""
Olá, {nome}!

Sua reserva foi confirmada com sucesso.
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
                args=(email, "Reserva confirmada - Cinema", mensagem)
            )
            thread.start()

        return jsonify({"message": "Reserva confirmada com sucesso"}), 200

    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Expired token"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401
    except Exception as e:
        print(str(e))
        con.rollback()
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        if cur:
            cur.close()


# ==============================================================================
# ROTA: GERAR QR CODE PIX PARA PAGAMENTO
# CORRIGIDO: cur.fetchone() chamado duas vezes sobre o mesmo resultado;
#            linha com [0] extra que causaria TypeError foi removida
# ==============================================================================

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
            return jsonify({"error": "Reserva inexistente"}), 404

        columns = [desc[0].lower() for desc in cur.description]
        reserva = dict(zip(columns, res))

        cur.execute("""
                    SELECT cidade, chave_pix, cnpj, razao_social
                    FROM EMPRESA e
                    ORDER BY ID_EMPRESA ASC
                        FETCH FIRST 1 ROW ONLY
                    """)

        # Fallback com dados padrão caso a empresa não esteja cadastrada
        dados = {
            "cidade": "BIRIGUI",
            "chave_pix": "41317641809",
            "razao_social": "PAULO HENRIQUE SOUZA CAVALLINI",
        }

        # CORRIGIDO: era cur.fetchone()[0] (TypeError) seguido de sobrescrita;
        # agora um único fetchone() com leitura correta
        resultado = cur.fetchone()
        if resultado:
            dados = dict(zip([desc[0].lower() for desc in cur.description], resultado))

        valor_total = float(reserva['valor_total'])

        payload = gerar_payload_pix(
            dados["chave_pix"],
            dados["razao_social"],
            dados["cidade"],
            valor_total,
        )

        img = qrcode.make(payload)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return jsonify({
            "valor": valor_total,
            "payload": payload,
            "qrcode": img_base64,
        }), 200

    except Exception as e:
        print(str(e))
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        if cur:
            cur.close()


# ==============================================================================
# ROTA: ASSENTOS OCUPADOS DE UMA SESSÃO
# CORRIGIDO: LEFT JOIN RESERVA duplicado — SQL inválido no Firebird
# ==============================================================================

@reservas_bp.route('/<int:id>/assentos_ocupados', methods=["GET"])
def obter_assentos_ocupados(id):
    cur = None
    try:

        cur.execute("SELECT 1 FROM SESSAO where ID_SESSAO = ?", (id,))
        if not cur.fetchone():
            return jsonify({"error": "Sessao nao encontrada"}), 404

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
            assentos_ocupados = []

        return jsonify({
            "message": "Assentos ocupados obtidos com sucesso",
            "assentos": [assento[0] for assento in assentos_ocupados],
        }), 200

    except Exception as e:
        print("Erro ao obter assentos ocupados: " + str(e))
        return jsonify({"message": "Internal Server Error"}), 500
    finally:
        if cur:
            cur.close()


# ==============================================================================
# ROTA: EXCLUIR RESERVA
# CORRIGIDO: cur declarado dentro do try — NameError no finally caso falhasse
# ==============================================================================

@reservas_bp.route("/<int:id>", methods=["DELETE"])
def excluir_reserva(id):
    cur = None
    try:
        cur = con.cursor()
        cur.execute("SELECT 1 FROM reserva WHERE id_reserva = ?", (id,))

        if not cur.fetchone():
            return jsonify({"error": "Reserva nao encontrada"}), 404

        cur.execute("DELETE FROM reserva WHERE id_reserva = ?", (id,))
        con.commit()

        return jsonify({"message": "Reserva excluida com sucesso"})

    except Exception:
        con.rollback()
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        if cur:
            cur.close()


# ==============================================================================
# ROTA: OBTER RESERVAS DE UM USUÁRIO (endpoint legado)
# CORRIGIDO: INNER JOIN SESSAO duplicado — SQL inválido no Firebird
# ==============================================================================

@reservas_bp.route("/<int:id>/usuario", methods=["GET"])
def obter_reservas_usuario(id):
    cur = None
    try:
        cur = con.cursor()

        cur.execute("""
                    SELECT r.*, f.*
                    FROM RESERVA r
                             INNER JOIN SESSAO s ON r.ID_SESSAO = s.ID_SESSAO
                             INNER JOIN FILME f ON f.ID_FILME = s.ID_FILME
                    WHERE r.ID_USUARIO = ?
                    """, (id,))

        res = cur.fetchall()
        colunas = [desc[0].lower() for desc in cur.description]
        resultado = [dict(zip(colunas, reserva)) for reserva in res]

        return jsonify({"message": "Reservas obtidas com sucesso", "reservas": resultado})

    except Exception as e:
        print(str(e))
        return jsonify({"error": "Internal Server Error"}), 500
    finally:
        if cur:
            cur.close()

@reservas_bp.route('/total_ingressos', methods=['GET'])
def total_ingressos_vendidos():
    cur = con.cursor()

    try:
        cur.execute("""
            SELECT COUNT(*)
            FROM RESERVA
        """)

        total = cur.fetchone()[0]

        return jsonify({"total": total}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cur.close()

@reservas_bp.route('/relatorio_publico', methods=['GET'])
def relatorio_publico():
    cur = con.cursor()

    try:
        cur.execute("""
        SELECT COUNT(*) AS publico,
        r.DATARESERVA AS data_reserva
        FROM RESERVA r
        INNER JOIN RESERVA_ASSENTO ra 
        ON ra.ID_RESERVA = r.ID_RESERVA
        WHERE r.DATARESERVA >= DATEADD(-1 MONTH TO CURRENT_DATE)
        GROUP BY r.DATARESERVA
        ORDER BY r.DATARESERVA;
        """)

        resultados = cur.fetchall()
        colunas = [desc[0].lower() for desc in cur.description]
        dados = [dict(zip(colunas, row)) for row in resultados]

        return jsonify({ "message": "Relatorio obtido com sucesso", "dados": dados}), 200
    except Exception as e:
        print(str(e))
        return jsonify({"error": "Internal Server Error"}), 500
