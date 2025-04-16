from flask import Flask, request, render_template, redirect
from transbank.error.transbank_error import TransbankError
from transbank.webpay.webpay_plus.transaction import Transaction, WebpayOptions
import os
from transbank.common.integration_commerce_codes import IntegrationCommerceCodes
from transbank.common.integration_type import IntegrationType
from transbank.common.integration_api_keys import IntegrationApiKeys
from transbank.common.options import WebpayOptions

app = Flask(__name__)

# Validar y limpiar credenciales
commerce_code = os.getenv('WEBPAY_COMMERCE_CODE', '').strip()
api_key = os.getenv('WEBPAY_API_KEY', '').strip()
integration_type = os.getenv('WEBPAY_INTEGRATION_TYPE', 'LIVE').strip()
if not commerce_code or not api_key:
    raise ValueError("Faltan WEBPAY_COMMERCE_CODE o WEBPAY_API_KEY en las variables de entorno")

options = WebpayOptions(
    commerce_code=commerce_code,
    api_key=api_key,
    integration_type=integration_type,
)
tx = Transaction(options)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/pay', methods=['POST'])
def create_payment():
    print(f"Credenciales: commerce_code={commerce_code}, api_key={api_key}, integration_type={integration_type}")
    buy_order = request.form.get('order_id')
    amount = request.form.get('amount')
    print(f"Amount recibido: {amount}")

    if not buy_order or not amount:
        return "Error: Debes proporcionar un ID de pedido y un monto", 400
    
    try:
        amount = int(amount)
        if amount <= 0:
            raise ValueError("El monto debe ser mayor a cero")
    except ValueError:
        return "Error: El monto debe ser un número entero positivo", 400

    session_id = f"session_{buy_order}"
    return_url = "https://webpay-shopify.onrender.com/result" if 'onrender.com' in request.host_url else f"{request.host_url.rstrip('/')}/result"
    print(f"return_url: {return_url}")

    try:
        response = tx.create(buy_order, session_id, amount, return_url)
        print(f"Respuesta de Transbank: {response}")
        return redirect(f"{response['url']}?token_ws={response['token']}")
    except TransbankError as e:
        print(f"Error de Transbank: {str(e)} - Detalles: {e.message}")
        return f"Error al iniciar el pago: {str(e)} - Detalles: {e.message}", 400

@app.route('/result', methods=['GET', 'POST'])
def payment_result():
    token = request.args.get('token_ws') or request.form.get('token_ws')
    if not token:
        return "Error: No se proporcionó token", 400

    try:
        response = tx.commit(token=token)
        print(f"Confirmación de Transbank: {response}")
        if response['status'] == 'AUTHORIZED':
            return f"Pago exitoso para el pedido {response['buy_order']}. Monto: {response['amount']}."
        else:
            return f"Pago fallido para el pedido {response['buy_order']}. Estado: {response['status']}", 400
    except TransbankError as e:
        print(f"Error en confirmación: {str(e)}")
        return f"Error al procesar el pago: {str(e)}", 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)