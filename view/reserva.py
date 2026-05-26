from flask import Blueprint, jsonify, request, send_file
from funcao import decodificar_token
from database import con
from fpdf import FPDF
from datetime import datetime
import os
import tempfile

reserva_blueprint = Blueprint('reserva', __name__, url_prefix='/reserva')


# ─────────────────────────────────────────────
#  CLASSE PDF CORPORATIVA
# ─────────────────────────────────────────────

class RelatorioPDF(FPDF):
    """
    Classe FPDF customizada com design corporativo minimalista escuro/cinza.
    Gerencia o cabeçalho principal com KPIs e o rodapé com paginação.
    """

    # Paleta de cores corporativas
    COR_HEADER_BG   = (26, 26, 31)      # Fundo escuro do topo
    COR_HEADER_TEXT = (255, 255, 255)   # Texto branco no header
    COR_ACCENT      = (90, 90, 105)     # Cinza médio (KPI border, badges)
    COR_KPI_BG      = (40, 40, 48)     # Fundo dos blocos KPI
    COR_KPI_TEXT    = (200, 200, 210)   # Texto secundário KPI
    COR_KPI_VALUE   = (255, 255, 255)   # Valor principal KPI
    COR_TABLE_HEAD  = (50, 50, 60)      # Cabeçalho da tabela
    COR_ZEBRA_DARK  = (245, 245, 248)   # Linha zebrada clara
    COR_ZEBRA_LIGHT = (255, 255, 255)   # Linha zebrada branca
    COR_FOOTER_TEXT = (140, 140, 155)   # Texto do rodapé
    COR_BODY_TEXT   = (30, 30, 40)      # Texto geral do corpo

    # Badge de status: (fundo, texto)
    STATUS_BADGE = {
        1: ((220, 220, 220), (50,  50,  50),  'Pago'),
        2: ((200, 200, 200), (80,  80,  80),  'Pendente'),
        3: ((160, 160, 160), (255, 255, 255), 'Cancelado'),
    }
    STATUS_DEFAULT = ((190, 190, 190), (50, 50, 50), 'Indefinido')

    def __init__(self, kpis: dict):
        """
        kpis: {
            'total_reservas': int,
            'faturamento_bruto': float,
            'total_descontos': float,
        }
        """
        super().__init__(orientation='L', unit='mm', format='A4')
        self.kpis = kpis
        self.gerado_em = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        self.set_auto_page_break(auto=True, margin=18)
        self.alias_nb_pages()

    # ── Header ────────────────────────────────
    def header(self):
        # Faixa escura superior
        self.set_fill_color(*self.COR_HEADER_BG)
        self.rect(0, 0, self.w, 22, 'F')

        # Título centralizado
        self.set_y(6)
        self.set_font('Helvetica', 'B', 13)
        self.set_text_color(*self.COR_HEADER_TEXT)
        self.cell(0, 10, 'RELATÓRIO DE RESERVAS REALIZADAS', align='C')

        # Subtítulo / data de geração (canto direito, menor)
        self.set_font('Helvetica', '', 7)
        self.set_text_color(*self.COR_FOOTER_TEXT)
        self.set_xy(self.w - 68, 14)
        self.cell(60, 5, f'Gerado em: {self.gerado_em}', align='R')

        # Blocos de KPI
        self._draw_kpis()

        # Espaço após o header antes do conteúdo
        self.set_y(50)

    def _draw_kpis(self):
        """Desenha os 3 blocos de KPI horizontais logo abaixo do título."""
        margem   = 10
        espaco   = 5
        largura  = (self.w - 2 * margem - 2 * espaco) / 3
        altura   = 20
        y_inicio = 24

        kpi_data = [
            ('TOTAL RESERVAS',  str(self.kpis['total_reservas'])),
            ('FATURAMENTO BRUTO', f"R$ {self.kpis['faturamento_bruto']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')),
            ('TOTAL DESCONTOS',   f"R$ {self.kpis['total_descontos']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')),
        ]

        for i, (label, valor) in enumerate(kpi_data):
            x = margem + i * (largura + espaco)

            # Fundo do bloco
            self.set_fill_color(*self.COR_KPI_BG)
            self.set_draw_color(*self.COR_ACCENT)
            self.set_line_width(0.3)
            self.rect(x, y_inicio, largura, altura, 'FD')

            # Rótulo (menor, cinza claro)
            self.set_xy(x, y_inicio + 3)
            self.set_font('Helvetica', '', 6.5)
            self.set_text_color(*self.COR_KPI_TEXT)
            self.cell(largura, 5, label, align='C')

            # Valor (maior, branco, negrito)
            self.set_xy(x, y_inicio + 9)
            self.set_font('Helvetica', 'B', 11)
            self.set_text_color(*self.COR_KPI_VALUE)
            self.cell(largura, 8, valor, align='C')

    # ── Footer ────────────────────────────────
    def footer(self):
        self.set_y(-12)
        self.set_draw_color(*self.COR_ACCENT)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), self.w - 10, self.get_y())

        self.set_y(-10)
        self.set_font('Helvetica', '', 7)
        self.set_text_color(*self.COR_FOOTER_TEXT)

        # Data à esquerda
        self.cell(0, 5, f'Gerado em: {self.gerado_em}', align='L')

        # Paginação à direita
        self.set_y(-10)
        self.cell(0, 5, f'Página {self.page_no()} de {{nb}}', align='R')

    # ── Tabela ────────────────────────────────
    def desenhar_cabecalho_tabela(self, colunas: list):
        """
        colunas: lista de tuplas (label, largura_mm, alinhamento)
        """
        self.set_fill_color(*self.COR_TABLE_HEAD)
        self.set_text_color(*self.COR_HEADER_TEXT)
        self.set_font('Helvetica', 'B', 8)
        self.set_draw_color(*self.COR_ACCENT)
        self.set_line_width(0.2)

        for label, larg, alinha in colunas:
            self.cell(larg, 8, label, border=1, align=alinha, fill=True)
        self.ln()

    def desenhar_linha_tabela(self, colunas: list, dados: list, num_linha: int):
        """
        colunas: lista de tuplas (label, largura_mm, alinhamento)
        dados:   valores correspondentes a cada coluna
        num_linha: índice da linha (para zebrado)
        """
        zebra = num_linha % 2 == 0
        cor_bg = self.COR_ZEBRA_DARK if zebra else self.COR_ZEBRA_LIGHT
        self.set_fill_color(*cor_bg)
        self.set_text_color(*self.COR_BODY_TEXT)
        self.set_font('Helvetica', '', 7.5)
        self.set_draw_color(210, 210, 218)
        self.set_line_width(0.1)

        altura_linha = 7
        x_inicio = self.get_x()
        y_inicio = self.get_y()

        # Verifica se precisamos de quebra de página antes de desenhar
        if y_inicio + altura_linha > self.page_break_trigger:
            self.add_page()
            self.desenhar_cabecalho_tabela(colunas)
            y_inicio = self.get_y()

        for idx, ((_, larg, alinha), valor) in enumerate(zip(colunas, dados)):
            # Coluna STATUS recebe badge especial
            if idx == len(colunas) - 1:
                self._desenhar_badge_status(larg, altura_linha, valor, cor_bg)
            else:
                self.cell(larg, altura_linha, str(valor), border='B', align=alinha, fill=True)

        self.ln()

    def _desenhar_badge_status(self, largura: float, altura: float, status_id, cor_bg):
        """Renderiza um badge monocromático para a coluna de status."""
        badge_info = self.STATUS_BADGE.get(status_id, self.STATUS_DEFAULT)
        cor_badge_bg, cor_badge_txt, texto = badge_info

        x = self.get_x()
        y = self.get_y()

        # Fundo da célula (zebrado)
        self.set_fill_color(*cor_bg)
        self.rect(x, y, largura, altura, 'F')

        # Badge interno (centralizado na célula)
        badge_w = largura - 6
        badge_h = altura - 2.5
        badge_x = x + (largura - badge_w) / 2
        badge_y = y + (altura - badge_h) / 2

        self.set_fill_color(*cor_badge_bg)
        self.set_draw_color(*self.COR_ACCENT)
        self.set_line_width(0.2)
        self.rect(badge_x, badge_y, badge_w, badge_h, 'F')

        # Texto do badge
        self.set_xy(badge_x, badge_y)
        self.set_font('Helvetica', 'B', 6.5)
        self.set_text_color(*cor_badge_txt)
        self.cell(badge_w, badge_h, texto, align='C')

        # Borda inferior da célula
        self.set_draw_color(210, 210, 218)
        self.set_line_width(0.1)
        self.line(x, y + altura, x + largura, y + altura)

        # Reposiciona o cursor para a próxima célula
        self.set_xy(x + largura, y)


# ─────────────────────────────────────────────
#  ROTA: /reserva/relatorio_reservas
# ─────────────────────────────────────────────

@reserva_blueprint.route('/relatorio_reservas', methods=['GET'])
def relatorio_reservas():
    """
    Gera e retorna um relatório PDF de reservas de cinema.

    Segurança:
        - Requer cookie 'access_token' válido.
        - Tipo 1 (cliente comum) não tem acesso (403).

    Retorno:
        - PDF enviado como attachment para download automático.
    """
    # ── 1. Autenticação ───────────────────────
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({'erro': 'Token de acesso ausente.'}), 401

    payload = decodificar_token(token)
    if not payload:
        return jsonify({'erro': 'Token inválido ou expirado.'}), 401

    if payload.get('tipo') == 1:
        return jsonify({'erro': 'Acesso negado. Permissão insuficiente.'}), 403

    # ── 2. Consulta ao banco de dados ─────────
    cursor = con.cursor()
    try:
        cursor.execute("""
            SELECT
                r.ID_RESERVA,
                u.NOME          AS CLIENTE,
                f.TITULO        AS FILME,
                r.DATARESERVA,
                r.VALORTOTAL,
                r.DESCONTO,
                r.STATUS
            FROM RESERVA r
            INNER JOIN USUARIO u ON u.ID_USUARIO = r.ID_USUARIO
            INNER JOIN SESSAO  s ON s.ID_SESSAO  = r.ID_SESSAO
            INNER JOIN FILME   f ON f.ID_FILME   = s.ID_FILME
            ORDER BY r.ID_RESERVA DESC
        """)
        registros = cursor.fetchall()

        # ── 3. Cálculo dos KPIs ───────────────
        total_reservas    = len(registros)
        faturamento_bruto = sum(float(row[4] or 0) for row in registros)
        total_descontos   = sum(float(row[5] or 0) for row in registros)

        # ── 4. Geração do PDF ─────────────────
        kpis = {
            'total_reservas':    total_reservas,
            'faturamento_bruto': faturamento_bruto,
            'total_descontos':   total_descontos,
        }
        pdf = RelatorioPDF(kpis=kpis)
        pdf.add_page()

        # Definição das colunas: (rótulo, largura mm, alinhamento)
        colunas = [
            ('CÓD.',    18,  'C'),
            ('CLIENTE', 72,  'L'),
            ('FILME',   72,  'L'),
            ('DATA',    30,  'C'),
            ('TOTAL',   32,  'R'),
            ('DESC.',   28,  'R'),
            ('STATUS',  35,  'C'),
        ]

        pdf.desenhar_cabecalho_tabela(colunas)

        for num_linha, row in enumerate(registros):
            id_reserva, cliente, filme, data_reserva, valor_total, desconto, status = row

            # Formata data
            if isinstance(data_reserva, datetime):
                data_fmt = data_reserva.strftime('%d/%m/%Y')
            elif data_reserva:
                data_fmt = str(data_reserva)[:10]
            else:
                data_fmt = '—'

            # Formata valores monetários em R$
            def fmt_brl(v):
                try:
                    return f"R$ {float(v):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                except (TypeError, ValueError):
                    return 'R$ 0,00'

            dados_linha = [
                str(id_reserva),
                str(cliente or '').strip()[:35],
                str(filme   or '').strip()[:35],
                data_fmt,
                fmt_brl(valor_total),
                fmt_brl(desconto),
                status,   # passado como int para o badge resolver
            ]

            pdf.desenhar_linha_tabela(colunas, dados_linha, num_linha)

        # Linha de totais (rodapé da tabela)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.set_fill_color(*RelatorioPDF.COR_TABLE_HEAD)
        pdf.set_text_color(*RelatorioPDF.COR_HEADER_TEXT)
        pdf.set_draw_color(*RelatorioPDF.COR_ACCENT)
        pdf.set_line_width(0.3)

        def fmt_brl(v):
            return f"R$ {float(v):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

        totais = [
            ('', 18), (f'{total_reservas} registro(s)', 72),
            ('', 72),  ('TOTAIS', 30),
            (fmt_brl(faturamento_bruto), 32),
            (fmt_brl(total_descontos),   28),
            ('', 35),
        ]
        for texto, larg in totais:
            alinha = 'R' if texto.startswith('R$') else ('C' if texto in ('', 'TOTAIS') else 'L')
            pdf.cell(larg, 8, texto, border=1, align=alinha, fill=True)
        pdf.ln()

        # ── 5. Salva e envia o arquivo ────────
        with tempfile.NamedTemporaryFile(
            suffix='.pdf',
            delete=False,
            prefix='relatorio_reservas_'
        ) as tmp:
            pdf_path = tmp.name

        pdf.output(pdf_path)

        nome_arquivo = f"relatorio_reservas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=nome_arquivo,
            mimetype='application/pdf'
        )

    except Exception as e:
        return jsonify({'erro': f'Erro ao gerar relatório: {str(e)}'}), 500

    finally:
        cursor.close()