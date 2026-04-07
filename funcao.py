from flask import current_app
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


def enviando_email(destinatario, assunto, mensagem):
    try:
        user = "sophia.biliattoo@gmail.com"
        senha = "eahu tqrv kaxi jsnb"

        msg = MIMEText(mensagem)
        msg['Subject'] = assunto
        msg['From'] = user
        msg['To'] = destinatario

        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=30)
        server.starttls()
        server.login(user, senha)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print("Houve um erro ao enviar email: " + str(e))

def remove_bearer(token):
    if token.startswith('Bearer '):
        return token[len('Bearer '):]
    else:
        return token



# def enviando_email(destinatario, assunto, mensagem):
#         user = "sophia.biliattoo@gmail.com"
#         senha = "eahu tqrv kaxi jsnb"
#
#         msg = MIMEText(mensagem)
#         msg['Subject'] = assunto
#         msg['From'] = user
#         msg['To'] = destinatario
#
#         server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
#
#         server.login(user, senha)
#         server.send_message(msg)
#         server.quit()
#
#

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