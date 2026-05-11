from flask import Blueprint, request, send_file
from funcao import gerar_payload_pix
import qrcode
import io

pix_blueprint = Blueprint('pix_blueprint', __name__, url_prefix='/pix')

@pix_blueprint.route("/", methods=['POST'])
def pix_qrcode():
    data = request.json
    chave = data.get("chave")
    nome = data.get("nome")
    cidade = data.get("cidade")
    valor = float(data.get("valor", 0))

    payload = gerar_payload_pix(chave, nome, cidade, valor)

    img = qrcode.make(payload)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return send_file(buffer, mimetype="image/png")