import fdb
from database import con

def seed_filmes():
    cur = con.cursor()

    # Lista com 20 registros para popular a tabela
    filmes = [
        (1, 'O Despertar do Amanhã', 'Um drama emocionante sobre superação e novos começos.', 'Drama', 120, '12',
         '2024-01-15', 'https://youtube.com/watch?v=tr1'),
        (2, 'Galáxia Perdida', 'Aventura espacial em busca de um novo lar para a humanidade.', 'Ficção Científica', 145,
         '10', '2023-11-20', 'https://youtube.com/watch?v=tr2'),
        (3, 'Rastro de Sangue', 'Um suspense policial tenso em uma cidade isolada pela neve.', 'Suspense', 110, '16',
         '2024-02-05', 'https://youtube.com/watch?v=tr3'),
        (4, 'A Herança de Avalon', 'Fantasias e mitos antigos se tornam realidade nos dias de hoje.', 'Fantasia', 135,
         'L', '2023-05-10', 'https://youtube.com/watch?v=tr4'),
        (5, 'Velocidade Máxima 5', 'Corridas clandestinas e perseguições em alta voltagem.', 'Ação', 105, '14',
         '2024-03-12', 'https://youtube.com/watch?v=tr5'),
        (6, 'Riso Eterno', 'Uma comédia sobre amizades de infância que se reencontram.', 'Comédia', 95, 'L',
         '2023-08-25', 'https://youtube.com/watch?v=tr6'),
        (7, 'O Código Oculto', 'Mistério envolvendo conspirações mundiais e enigmas milenares.', 'Mistério', 128, '12',
         '2024-04-01', 'https://youtube.com/watch?v=tr7'),
        (8, 'Sombras no Escuro', 'Terror psicológico ambientado em um asilo abandonado.', 'Terror', 102, '18',
         '2023-10-31', 'https://youtube.com/watch?v=tr8'),
        (9, 'Amor em Paris', 'Um romance clássico sob as luzes da Torre Eiffel.', 'Romance', 115, 'L', '2024-02-14',
         'https://youtube.com/watch?v=tr9'),
        (10, 'A Última Fronteira', 'Documentário detalhado sobre a vida selvagem no Ártico.', 'Documentário', 88, 'L',
         '2023-06-15', 'https://youtube.com/watch?v=tr10'),
        (11, 'Guerreiros de Metal', 'Batalhas épicas de robôs gigantes no futuro distópico.', 'Ação', 130, '12',
         '2024-05-20', 'https://youtube.com/watch?v=tr11'),
        (12, 'O Enigma do Tempo', 'Um cientista descobre como viajar poucos dias para o passado.', 'Ficção Científica',
         118, '10', '2023-12-12', 'https://youtube.com/watch?v=tr12'),
        (13, 'Coração de Leão', 'A biografia de um líder que mudou o destino de sua nação.', 'Biografia', 150, '12',
         '2023-09-07', 'https://youtube.com/watch?v=tr13'),
        (14, 'Noite Sem Fim', 'Vampiros dominam uma cidade durante os meses de escuridão.', 'Terror', 112, '16',
         '2024-01-20', 'https://youtube.com/watch?v=tr14'),
        (15, 'O Pequeno Explorador', 'Animação educativa sobre as maravilhas da natureza.', 'Animação', 85, 'L',
         '2023-07-01', 'https://youtube.com/watch?v=tr15'),
        (16, 'Missão Resgate', 'Operação militar secreta em território extremamente hostil.', 'Ação', 125, '14',
         '2024-03-30', 'https://youtube.com/watch?v=tr16'),
        (17, 'A Sinfonia do Caos', 'Thriller psicológico sobre a obsessão de um jovem maestro.', 'Suspense', 108, '14',
         '2023-11-11', 'https://youtube.com/watch?v=tr17'),
        (18, 'Deserto Vivo', 'A luta desesperada pela sobrevivência no coração do Saara.', 'Aventura', 122, '10',
         '2024-04-15', 'https://youtube.com/watch?v=tr18'),
        (19, 'Além do Horizonte', 'Exploração submarina revela segredos em fossas abissais.', 'Ficção Científica', 140,
         'L', '2023-04-22', 'https://youtube.com/watch?v=tr19'),
        (20, 'O Golpe Perfeito', 'Estrategistas planejam o maior assalto a banco da história.', 'Crime', 116, '14',
         '2024-06-01', 'https://youtube.com/watch?v=tr20')
    ]

    # Query em linha única para evitar erros de token no fdb
    sql = "INSERT INTO FILME (ID_FILME, TITULO, SINOPSE, GENERO, DURACAO, CLASSIFICACAO, DATA_LANCAMENTO, TRAILER) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"

    try:
        cur.execute("DELETE FROM SESSAO")
        cur.execute("DELETE FROM FILME")
        cur.executemany(sql, filmes)
        con.commit()
        print(f"Sucesso: {len(filmes)} filmes inseridos na tabela FILME.")
    except fdb.fbcore.DatabaseError as e:
        con.rollback()
        print(f"Erro de Banco de Dados: {e}")
    except Exception as e:
        con.rollback()
        print(f"Erro inesperado: {e}")
    finally:
        cur.close()


if __name__ == "__main__":
    seed_filmes()