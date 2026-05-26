from datetime import datetime, timedelta
from database import get_database
import random

con = get_database()

# Configurações iniciais com base na imagem e no código fornecido
id_sala = 1
status = 1  # Conforme o padrão '1' visto na imagem e no INSERT do código
hoje = datetime.now()

inserts = []

print("-- SEED: Inserindo sessões para os últimos 30 dias na Sala 1\n")

for i in range(1, 31):
    # Calcula a data retroativa
    data_calculada = hoje - timedelta(days=i)
    data_str = data_calculada.strftime('%Y-%m-%d')

    # Sorteia um ID de filme fictício (Ex: entre os IDs 1, 3, 6, 20 que aparecem no seu print)
    id_filme = random.choice([1, 3, 6, 20])

    # Sorteia horários diferentes para dar realismo e evitar qualquer colisão
    horario_str = random.choice(['10:00:00', '13:30:00', '16:00:00', '19:15:00', '21:45:00'])

    # Sorteia um valor de assento realista
    valor_assento = round(random.uniform(10.0, 35.0), 2)

    # Cria o comando SQL correspondente à estrutura da sua tabela
    query = f"INSERT INTO sessao (id_filme, id_sala, status, data, horario, valor_assento) VALUES ({id_filme}, {id_sala}, {status}, '{data_str}', '{horario_str}', {valor_assento});"
    inserts.append(query)

cur = con.cursor()

# Exibe todos os comandos na tela
for sql in inserts:
    cur.execute(sql)

con.commit()