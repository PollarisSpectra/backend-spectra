from datetime import datetime, timedelta
import random
from database import get_database

con = get_database()
cur = con.cursor()

id_sala = 1
status = 1
hoje = datetime.now()

print("-- Iniciando SEED Aleatório...")
print("-- Gerando volume realista de sessões, reservas e assentos por dia...\n")

try:
    for i in range(1, 31):
        # Calcula a data do dia corrente no laço
        data_calculada = hoje - timedelta(days=i)
        data_str = data_calculada.strftime('%Y-%m-%d')

        # 1. QUANTIDADE DE SESSÕES NO DIA: Sorteia entre 1 e 3 sessões para hoje
        qtd_sessoes_dia = random.randint(1, 3)

        for _ in range(qtd_sessoes_dia):
            id_filme = random.choice([1, 3, 6, 20])
            horario_str = random.choice(['10:00:00', '13:30:00', '16:00:00', '19:15:00', '21:45:00'])
            valor_assento = round(random.uniform(15.0, 35.0), 2)

            # Insere a sessão
            query_sessao = """
                INSERT INTO sessao (id_filme, id_sala, status, data, horario, valor_assento) 
                VALUES (?, ?, ?, ?, ?, ?)
                RETURNING id_sessao
            """
            cur.execute(query_sessao, (id_filme, id_sala, status, data_str, horario_str, valor_assento))
            id_sessao_criada = cur.fetchone()[0]

            # 2. QUANTIDADE DE RESERVAS NA SESSÃO: Sorteia de 1 a 5 compras/reservas diferentes
            qtd_reservas_sessao = random.randint(1, 5)

            # Conjunto para garantir que não vamos duplicar assento na mesma sessão
            assentos_ocupados_na_sessao = set()

            for _ in range(qtd_reservas_sessao):
                # Cria a reserva daquela compra
                query_nova_reserva = """
                    INSERT INTO reserva (id_sessao, datareserva) 
                    VALUES (?, ?)
                    RETURNING id_reserva
                """
                cur.execute(query_nova_reserva, (id_sessao_criada, data_str))
                id_reserva_nova = cur.fetchone()[0]

                # 3. QUANTIDADE DE ASSENTOS POR RESERVA: Sorteia de 1 a 4 ingressos por pessoa
                qtd_assentos_por_reserva = random.randint(1, 4)

                for _ in range(qtd_assentos_por_reserva):
                    # Garante um assento único de 1 a 150 que ainda não foi pego nesta sessão
                    id_assento_sala = random.randint(1, 150)
                    while id_assento_sala in assentos_ocupados_na_sessao:
                        id_assento_sala = random.randint(1, 150)

                    assentos_ocupados_na_sessao.add(id_assento_sala)

                    # Insere o assento na reserva correspondente
                    query_assento = """
                        INSERT INTO reserva_assento (id_reserva, id_assento_sala) 
                        VALUES (?, ?)
                    """
                    cur.execute(query_assento, (id_reserva_nova, id_assento_sala))

    con.commit()
    print("SEED em massa executado com sucesso!")

except Exception as e:
    con.rollback()
    print(f"Erro ao executar o SEED: {str(e)}")
finally:
    cur.close()
    con.close()