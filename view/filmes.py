import fdb.fbcore
import math
import os
import jwt
import tempfile
from flask import Blueprint, jsonify, request, current_app, send_from_directory, send_file
from fpdf import FPDF
from datetime import datetime
from funcao import decodificar_token
from database import con

filmes_blueprint = Blueprint('filmes', __name__, url_prefix='/filmes')


# ==============================================================================
# UTILITÁRIO
# ==============================================================================

def _truncar(texto: str, limite: int) -> str:
    """Trunca texto e adiciona '...' se ultrapassar o limite."""
    texto = str(texto or '').strip()
    return texto[:limite - 3] + '...' if len(texto) > limite else texto


# ==============================================================================
# CLASSE PDF — RELATÓRIO DE FILMES MAIS ASSISTIDOS
# ==============================================================================

class FilmesPDF(FPDF):
    """PDF corporativo cinza para o relatório de filmes mais assistidos."""

    # Paleta cinza corporativo
    CINZA_900 = (26, 26, 31)  # header / footer
    CINZA_700 = (69, 70, 80)  # cabeçalho da tabela
    CINZA_400 = (143, 148, 153)  # texto secundário
    CINZA_LINE = (222, 222, 227)  # bordas
    CINZA_100 = (242, 242, 245)  # zebra ímpar
    BRANCO = (255, 255, 255)

    def __init__(self, total_filmes: int = 0, total_sessoes: int = 0, total_reservas: int = 0):
        super().__init__()
        self.total_filmes = total_filmes
        self.total_sessoes = total_sessoes
        self.total_reservas = total_reservas
        self.gerado_em = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    # ── Header ────────────────────────────────────────────────────────────────
    def header(self):
        # Faixa escura — 42 mm para acomodar KPIs
        self.set_fill_color(*self.CINZA_900)
        self.rect(0, 0, 210, 42, 'F')

        # Acento superior
        self.set_fill_color(190, 190, 195)
        self.rect(0, 0, 210, 1, 'F')

        # Título
        self.set_font('Arial', 'B', 17)
        self.set_text_color(*self.BRANCO)
        self.set_xy(14, 7)
        self.cell(0, 7, 'RELATÓRIO DE FILMES MAIS ASSISTIDOS', ln=True)

        # Subtítulo
        self.set_font('Arial', '', 8)
        self.set_text_color(158, 160, 168)
        self.set_x(14)
        self.cell(0, 4, 'Filmes ordenados pelo total de reservas realizadas', ln=True)

        # Data — alinhada à direita
        self.set_font('Arial', '', 7)
        self.set_text_color(107, 109, 118)
        self.set_xy(14, 7)
        self.cell(183, 5, f"GERADO EM  {self.gerado_em}", align='R', ln=True)

        # Divisor acima dos KPIs
        self.set_draw_color(56, 56, 64)
        self.set_line_width(0.4)
        self.line(14, 25, 196, 25)

        # ── KPI 1: Filmes no relatório ────────────────────────────────────────
        self.set_xy(14, 27)
        self.set_font('Arial', '', 6)
        self.set_text_color(107, 109, 118)
        self.cell(40, 3, "FILMES LISTADOS", ln=True)
        self.set_x(14)
        self.set_font('Arial', 'B', 9)
        self.set_text_color(*self.BRANCO)
        self.cell(40, 4, str(self.total_filmes), ln=True)

        # ── KPI 2: Total sessões ──────────────────────────────────────────────
        self.set_xy(70, 27)
        self.set_font('Arial', '', 6)
        self.set_text_color(107, 109, 118)
        self.cell(40, 3, "SESSÕES REALIZADAS", ln=True)
        self.set_x(70)
        self.set_font('Arial', 'B', 9)
        self.set_text_color(*self.BRANCO)
        self.cell(40, 4, str(self.total_sessoes), ln=True)

        # ── KPI 3: Total reservas ─────────────────────────────────────────────
        self.set_xy(125, 27)
        self.set_font('Arial', '', 6)
        self.set_text_color(107, 109, 118)
        self.cell(40, 3, "RESERVAS TOTAIS", ln=True)
        self.set_x(125)
        self.set_font('Arial', 'B', 9)
        self.set_text_color(*self.BRANCO)
        self.cell(40, 4, str(self.total_reservas), ln=True)

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
            f"   Gerado em: {self.gerado_em}   |   Relatório Corporativo",
            align='L'
        )

        self.set_font('Arial', 'B', 7)
        self.set_text_color(190, 190, 195)
        self.cell(0, 10, f'Página {self.page_no()}/{{nb}}', align='R')


# ==============================================================================
# ROTA: RELATÓRIO DE FILMES MAIS ASSISTIDOS
# ==============================================================================

@filmes_blueprint.route('/relatorio_filmes', methods=['GET'])
def relatorio_filmes():
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    cur = None
    try:
        payload = decodificar_token(token)
        if payload['tipo'] == 1:
            return jsonify({"error": "Acesso negado"}), 403

        cur = con.cursor()

        # Filmes ordenados pelo número de reservas (mais assistidos primeiro)
        cur.execute("""
                    SELECT f.id_filme,
                           f.titulo,
                           f.genero,
                           f.classificacao,
                           f.duracao,
                           COUNT(DISTINCT s.id_sessao) AS total_sessoes,
                           COUNT(r.id_reserva)         AS total_reservas
                    FROM filme f
                             LEFT JOIN sessao s ON s.id_filme = f.id_filme
                             LEFT JOIN reserva r ON r.id_sessao = s.id_sessao
                    GROUP BY f.id_filme, f.titulo, f.genero, f.classificacao, f.duracao
                    ORDER BY total_reservas DESC, total_sessoes DESC
                    """)
        filmes = cur.fetchall()

        if not filmes:
            return jsonify({"error": "Nenhum filme encontrado para gerar o relatório."}), 404

        total_filmes_count = len(filmes)
        total_sessoes_count = sum(int(f[5]) for f in filmes)
        total_reservas_count = sum(int(f[6]) for f in filmes)

        # ── Instância e configuração do PDF ──────────────────────────────────
        pdf = FilmesPDF(
            total_filmes=total_filmes_count,
            total_sessoes=total_sessoes_count,
            total_reservas=total_reservas_count,
        )
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # ── Texto de introdução ───────────────────────────────────────────────
        pdf.set_font('Arial', '', 8)
        pdf.set_text_color(*FilmesPDF.CINZA_400)
        pdf.multi_cell(0, 5, (
            "Ranking consolidado de filmes ordenados pelo volume de reservas realizadas. "
            "Utilize estas informações para decisões de programação e negociação de títulos."
        ))
        pdf.ln(5)

        # ── Cabeçalho da tabela ───────────────────────────────────────────────
        #   Colunas: Pos | Título | Gênero | Classificação | Duração | Sessões | Reservas | Rank
        col_larg = [10, 60, 30, 28, 20, 20, 20, 22]
        col_heads = ["#", "TÍTULO", "GÊNERO", "CLASSIF.", "MIN", "SESSÕES", "RESERVAS", "DESTAQUE"]

        pdf.set_fill_color(*FilmesPDF.CINZA_700)
        pdf.set_text_color(*FilmesPDF.BRANCO)
        pdf.set_font('Arial', 'B', 7)
        pdf.set_draw_color(*FilmesPDF.CINZA_LINE)
        pdf.set_line_width(0.2)

        alinhamentos = ['C', 'L', 'L', 'C', 'C', 'C', 'C', 'C']
        for i, h in enumerate(col_heads):
            pdf.cell(col_larg[i], 7, h, border=0, align=alinhamentos[i], fill=True)
        pdf.ln()

        # ── Linhas de dados com zebra e badge de destaque ─────────────────────
        cor_alternada = False
        max_reservas = int(filmes[0][6]) if filmes else 1  # para calcular badge relativo

        for pos, filme in enumerate(filmes, start=1):
            id_filme = filme[0]
            titulo = _truncar(filme[1], 32)
            genero = _truncar(filme[2] or '—', 16)
            classificacao = str(filme[3] or '—')
            duracao = str(filme[4] or '—')
            qtd_sessoes = int(filme[5])
            qtd_reservas = int(filme[6])

            bg = FilmesPDF.CINZA_100 if cor_alternada else FilmesPDF.BRANCO
            pdf.set_fill_color(*bg)
            pdf.set_text_color(*FilmesPDF.CINZA_700)
            pdf.set_font('Arial', '', 8)

            # Número de posição em negrito
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(col_larg[0], 7, str(pos), border='B', align='C', fill=True)
            pdf.set_font('Arial', '', 8)
            pdf.cell(col_larg[1], 7, titulo, border='B', align='L', fill=True)
            pdf.cell(col_larg[2], 7, genero, border='B', align='L', fill=True)
            pdf.cell(col_larg[3], 7, classificacao, border='B', align='C', fill=True)
            pdf.cell(col_larg[4], 7, duracao, border='B', align='C', fill=True)
            pdf.cell(col_larg[5], 7, str(qtd_sessoes), border='B', align='C', fill=True)

            # Reservas em negrito
            pdf.set_font('Arial', 'B', 8)
            pdf.cell(col_larg[6], 7, str(qtd_reservas), border='B', align='C', fill=True)

            # Badge de destaque por posição no ranking
            pdf.set_font('Arial', 'B', 7)
            if pos == 1:
                badge_txt = '1º LUGAR'
                pdf.set_text_color(*FilmesPDF.BRANCO)
                pdf.set_fill_color(*FilmesPDF.CINZA_900)
            elif pos == 2:
                badge_txt = '2º LUGAR'
                pdf.set_text_color(*FilmesPDF.BRANCO)
                pdf.set_fill_color(*FilmesPDF.CINZA_700)
            elif pos == 3:
                badge_txt = '3º LUGAR'
                pdf.set_text_color(*FilmesPDF.CINZA_700)
                pdf.set_fill_color(*FilmesPDF.CINZA_LINE)
            elif qtd_reservas == 0:
                badge_txt = 'SEM RESERVAS'
                pdf.set_text_color(*FilmesPDF.CINZA_400)
                pdf.set_fill_color(*bg)
            else:
                badge_txt = ''
                pdf.set_fill_color(*bg)

            pdf.cell(col_larg[7], 7, badge_txt, border='B', align='C', fill=True)
            pdf.ln()

            cor_alternada = not cor_alternada

        # ── Rodapé da tabela — totais ─────────────────────────────────────────
        pdf.ln(4)
        pdf.set_fill_color(*FilmesPDF.CINZA_100)
        pdf.set_text_color(*FilmesPDF.CINZA_700)
        pdf.set_font('Arial', 'B', 8)
        pdf.set_draw_color(*FilmesPDF.CINZA_LINE)
        pdf.set_line_width(0.4)
        pdf.cell(
            0, 9,
            f"   {total_filmes_count} filmes  |  {total_sessoes_count} sessões realizadas  |  {total_reservas_count} reservas no total",
            border=1, ln=True, fill=True, align='L'
        )

        # ── Salva em arquivo temporário e envia ───────────────────────────────
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False, prefix='relatorio_filmes_') as tmp:
            pdf_path = tmp.name

        pdf.output(pdf_path)

        nome_arquivo = f"relatorio_filmes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
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
        print(str(e))
        return jsonify({"error": f"Erro interno ao gerar relatório: {str(e)}"}), 500
    finally:
        if cur:
            cur.close()


# ==============================================================================
# DEMAIS ROTAS DE FILMES (inalteradas, apenas organizadas)
# ==============================================================================

@filmes_blueprint.route('/cadastro_filme', methods=['POST'])
def cadastro_filme():
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    cur = con.cursor()
    try:
        titulo = (request.form.get('titulo') or '').strip()
        if not titulo:
            return jsonify({"error": "Título é obrigatório"}), 400

        sinopse = (request.form.get('sinopse') or '').strip()
        if not sinopse:
            return jsonify({"error": "Sinopse é obrigatória"}), 400

        genero = request.form.get('genero')
        duracao = request.form.get('duracao')
        classificacao = request.form.get('classificacao')
        data_lancamento = request.form.get('data_lancamento')
        trailer = request.form.get('trailer')
        imagem = request.files.get('imagem')

        cur.execute('SELECT 1 FROM filme WHERE titulo = ?', (titulo,))
        if cur.fetchone():
            return jsonify({"error": "Filme já cadastrado"}), 400

        cur.execute("""
                    INSERT INTO filme(titulo, sinopse, genero, duracao, classificacao, data_lancamento, trailer)
                    VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id_filme
                    """, (titulo, sinopse, genero, duracao, classificacao, data_lancamento, trailer))

        id_filme = cur.fetchone()[0]
        con.commit()

        if imagem:
            caminho_destino = os.path.join(current_app.config['UPLOAD_FOLDER'], "Filmes")
            os.makedirs(caminho_destino, exist_ok=True)
            imagem.save(os.path.join(caminho_destino, f"{id_filme}.jpg"))

        return jsonify({"message": "Filme cadastrado com sucesso!"}), 200

    except Exception as e:
        return jsonify({"message": f"Erro ao cadastrar filme: {e}"}), 500
    finally:
        cur.close()


@filmes_blueprint.route('/editar_filme/<int:id>', methods=['PUT'])
def editar_filme(id):
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Token invalid"}), 401

    cur = con.cursor()
    try:
        cur.execute(
            'SELECT titulo, sinopse, genero, duracao, classificacao, data_lancamento, trailer FROM filme WHERE id_filme = ?',
            (id,)
        )
        filme_db = cur.fetchone()
        if not filme_db:
            return jsonify({"error": "Filme não encontrado"}), 404

        titulo = request.form.get('titulo', filme_db[0])
        sinopse = request.form.get('sinopse', filme_db[1])
        genero = request.form.get('genero', filme_db[2])
        duracao = request.form.get('duracao', filme_db[3])
        classificacao = request.form.get('classificacao', filme_db[4])
        data_lancamento = request.form.get('data_lancamento', filme_db[5])
        trailer = request.form.get('trailer', filme_db[6])
        imagem = request.files.get('imagem')

        cur.execute('SELECT 1 FROM filme WHERE titulo = ? AND id_filme != ?', (titulo, id))
        if cur.fetchone():
            return jsonify({"error": "Filme já cadastrado"}), 400

        cur.execute("""
                    UPDATE filme
                    SET titulo          = ?,
                        sinopse         = ?,
                        genero          = ?,
                        duracao         = ?,
                        classificacao   = ?,
                        data_lancamento = ?,
                        trailer         = ?
                    WHERE id_filme = ?
                    """, (titulo, sinopse, genero, duracao, classificacao, data_lancamento, trailer, id))
        con.commit()

        if imagem:
            caminho_destino = os.path.join(current_app.config['UPLOAD_FOLDER'], "Filmes")
            os.makedirs(caminho_destino, exist_ok=True)
            imagem.save(os.path.join(caminho_destino, f"{id}.jpg"))

        return jsonify({
            "message": "Filme atualizado com sucesso",
            "filme": {
                "id_filme": id, "titulo": titulo, "sinopse": sinopse,
                "genero": genero, "duracao": duracao, "classificacao": classificacao,
                "data_lancamento": data_lancamento, "trailer": trailer
            }
        }), 200

    except Exception as e:
        return jsonify({"message": f"Erro ao atualizar filme. {e}"}), 500
    finally:
        cur.close()


@filmes_blueprint.route('/excluir_filme/<int:id>', methods=['DELETE'])
def excluir_filme(id):
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({"error": "Token de autenticação necessário."}), 401

    try:
        payload = decodificar_token(token)
        if payload['tipo'] == 1:
            return jsonify({
                "error": "Acesso negado",
                "mensagem": "Você não tem permissão para realizar esta ação."
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
        print("Erro ao excluir filme: ", str(e))
        return jsonify({"error": "Erro ao excluir filme."}), 500
    finally:
        cur.close()


@filmes_blueprint.route('/listar_filme', methods=['GET'])
def listar_filme():
    cur = None
    try:
        cur = con.cursor()
        titulo = request.args.get('titulo', '')
        genero = request.args.get('genero', '')
        classificacao = request.args.get('classificacao', '')

        cur.execute("""
                    SELECT *
                    FROM filme
                    WHERE UPPER(titulo) LIKE UPPER(?)
                      AND UPPER(genero) LIKE UPPER(?)
                      AND UPPER(classificacao) LIKE UPPER(?)
                    """, (f"%{titulo}%", f"%{genero}%", f"%{classificacao}%"))

        filmes = cur.fetchall()
        if not filmes:
            return jsonify({"error": "Não há resultados para sua busca"}), 404

        return jsonify({'filmes': filmes}), 200

    except Exception as e:
        return jsonify({"error": "Erro ao listar filmes"}), 500
    finally:
        if cur:
            cur.close()


@filmes_blueprint.route('/filme', methods=['GET'])
def listar_e_buscar_filmes():
    cur = None
    try:
        titulo = request.args.get('titulo', '')
        genero = request.args.get('genero', '')
        classificacao = request.args.get('classificacao', '')
        page_size = int(request.args.get('page_size', 10))
        page_number = int(request.args.get('page_number', 1))
        offset = (page_number - 1) * page_size

        cur = con.cursor()
        params = (f"%{titulo}%", f"%{genero}%", f"%{classificacao}%")

        cur.execute("""
                    SELECT COUNT(*)
                    FROM FILME
                    WHERE UPPER(titulo) LIKE UPPER(?)
                      AND UPPER(genero) LIKE UPPER(?)
                      AND UPPER(classificacao) LIKE UPPER(?)
                    """, params)
        total_results = cur.fetchone()[0]

        cur.execute("""
                    SELECT FIRST ? SKIP ? *
                    FROM FILME
                    WHERE UPPER (titulo) LIKE UPPER (?)
                      AND UPPER (genero) LIKE UPPER (?)
                      AND UPPER (classificacao) LIKE UPPER (?)
                    ORDER BY ID_FILME
                    """, (page_size, offset, f"%{titulo}%", f"%{genero}%", f"%{classificacao}%"))
        filmes = cur.fetchall()

        columns = [desc[0].lower() for desc in cur.description]
        resultados = [dict(zip(columns, row)) for row in filmes]

        for filme in resultados:
            id_filme = filme.get('id_filme')
            caminho = os.path.join(current_app.config['UPLOAD_FOLDER'], "Filmes", f"{id_filme}.jpg")
            filme['imagem_url'] = f"/imagem_filme/{id_filme}.jpg" if os.path.exists(caminho) else None

        if not resultados and page_number == 1:
            return jsonify({"error": "Não há resultados para sua busca"}), 404

        return jsonify({
            "total_results": total_results,
            "total_pages": math.ceil(total_results / page_size) if total_results > 0 else 0,
            "current_page": page_number,
            "filmes": resultados,
        }), 200

    except ValueError:
        return jsonify({"error": "page_size e page_number devem ser números inteiros"}), 400
    except Exception as e:
        print(f"Erro: {str(e)}")
        return jsonify({"error": "Erro interno ao processar filmes"}), 500
    finally:
        if cur:
            cur.close()


@filmes_blueprint.route('/<int:id>', methods=['GET'])
def buscar_filme(id):
    token = request.cookies.get('access_token')
    if not token:
        return jsonify({"error": "Token não enviado"}), 401

    cur = None
    try:
        payload = decodificar_token(token)

        cur = con.cursor()
        cur.execute("SELECT * FROM FILME WHERE id_filme = ?", (id,))
        resultado = cur.fetchone()

        if not resultado:
            return jsonify({"error": "Filme não encontrado"}), 404

        columns = [desc[0].lower() for desc in cur.description]
        return jsonify({"filme": dict(zip(columns, resultado))}), 200

    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Expired token"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401
    except Exception as e:
        return jsonify({"error": "Erro interno no servidor"}), 500
    finally:
        if cur:
            cur.close()


@filmes_blueprint.route('/imagem_filme/<path:filename>')
def servir_imagem_filme(filename):
    caminho = os.path.join(current_app.config['UPLOAD_FOLDER'], "Filmes")
    return send_from_directory(caminho, filename)


@filmes_blueprint.route('/total_cartaz', methods=['GET'])
def total_filmes_cartaz():
    cur = con.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM FILME")
        return jsonify({"total": cur.fetchone()[0]}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()