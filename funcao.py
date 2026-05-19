from datetime import datetime, timedelta
from email.message import EmailMessage

from flask import current_app, render_template
from flask_bcrypt import generate_password_hash
import random
import smtplib
from email.mime.text import MIMEText
import jwt
from hmac import new


def validar_senha(senha: str):
    if not senha:
        return False

    maiuscula = minuscula = numero = especial = False

    for s in senha:
        if s.isupper():
            maiuscula = True
        elif s.islower():
            minuscula = True
        elif s.isdigit():
            numero = True
        elif not s.isalnum():
            especial = True

    if len(senha) < 8 or len(senha) > 12:
        return False

    if not (maiuscula and minuscula and numero and especial):
        return False
    return True

#
# def enviando_email(destinatario, assunto, html_pronto):
#     try:
#         user = "sophia.biliattoo@gmail.com"
#         senha = "eahu tqrv kaxi jsnb"
#
#         msg = EmailMessage()
#         msg['Subject'] = assunto
#         msg['From'] = user
#         msg['To'] = destinatario
#
#         # Aqui usamos o HTML que já veio renderizado da rota
#         msg.set_content("Para ver esta mensagem, use um cliente de e-mail com suporte a HTML.")
#         msg.add_alternative(html_pronto, subtype='html')
#
#         # server = smtplib.SMTP('smtp.gmail.com', 587, timeout=30)
#         # server.starttls()
#         # server.login(user, senha)
#         # server.send_message(msg)
#         # server.quit()
#
#         with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
#             server.login(user, senha)
#             server.send_message(msg)
#
#         print("E-mail enviado com sucesso via Thread!")
#     except Exception as e:
#         print("Houve um erro ao enviar email: " + str(e))

def remove_bearer(token):
    if token.startswith('Bearer '):
        return token[len('Bearer '):]
    else:
        return token



def enviando_email(destinatario, assunto, mensagem):
        user = "sophia.biliattoo@gmail.com"
        senha = "eahu tqrv kaxi jsnb"

        msg = MIMEText(mensagem)
        msg['Subject'] = assunto
        msg['From'] = user
        msg['To'] = destinatario

        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)

        server.login(user, senha)
        server.send_message(msg)
        server.quit()



#
# def enviar_codigo(id_usuario, email):
#     cursor = con.cursor()
#     try:
#         codigo = random.randint(100000, 999999)
#
#         cursor.execute("""
#             UPDATE usuario
#             SET codigo = ?, verificar_validacao = 0
#             WHERE id_usuario = ?
#         """, (codigo, id_usuario))
#         con.commit()
#
#         assunto = "Código de validação"
#         mensagem = f"Olá, seja bem-vindo novamente! Seu código de validação é: {codigo}"
#
#         # thread = threading.Thread(
#         #     target=envio_email,
#         #     args=(email, assunto, mensagem)
#         # )
#         # thread.start()
#
#     except Exception as e:
#         print("Erro ao enviar código:", e)
#
#     finally:
#         cursor.close()

def decodificar_token(token):
    payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
    return payload

def gerar_token(payload):
    token = jwt.encode(
        payload,
        current_app.config['SECRET_KEY'],
        algorithm='HS256'
    )
    return token

def encode_password(password):
    return generate_password_hash(str(password)).decode('utf-8')

def converter_horario(data, horario):
    try:
        return datetime.strptime(f"{data} {horario}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return datetime.strptime(f"{data} {horario}", "%Y-%m-%d %H:%M")

def format_field(id, value):
    size = f"{len(value):02d}"
    return f"{id}{size}{value}"


def crc16(payload):
    polinomio = 0x1021
    resultado = 0xFFFF

    for c in payload:
        resultado ^= (ord(c) << 8)
        for _ in range(8):
            if (resultado & 0x8000):
                resultado = (resultado << 1) ^ polinomio
            else:
                resultado <<= 1
            resultado &= 0xFFFF

    return f"{resultado:04X}"

def gerar_payload_pix(chave, nome, cidade, valor, txid="***"):
    payload = ""

    payload += format_field("00", "01")

    merchant_account = ""
    merchant_account += format_field("00", "br.gov.bcb.pix")
    merchant_account += format_field("01", chave)

    payload += format_field("26", merchant_account)

    payload += format_field("52", "0000")
    payload += format_field("53", "986")

    if valor:
        payload += format_field("54", f"{valor:.2f}")

    payload += format_field("58", "BR")
    payload += format_field("59", nome[:25])
    payload += format_field("60", cidade[:15])

    additional = format_field("05", txid)
    payload += format_field("62", additional)

    payload += "6304"

    crc = crc16(payload)

    payload += crc

    return payload