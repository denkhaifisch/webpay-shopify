from flask import Flask, request, render_template, redirect
from transbank.error.transbank_error import TransbankError
from transbank.webpay.webpay_plus.transaction import Transaction, WebpayOptions
import os

# Inicializar la aplicación Flask
app = Flask(__name__)

# Configuración de Webpay Plus (entorno de producción)
options = WebpayOptions(
    commerce_code='597036244178',
    api_key='579B532A7440BB0C9079DED94D31EA1615BACEB56610332264630D42D0A36B1C',
    integration_type='TEST'
)
tx = Transaction(options)

# Ruta principal: formulario para ingresar ID del pedido y monto
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# Ruta para crear la transacción y redirigir a Webpay
@app.route('/pay', methods=['POST'])
def create_payment():
    buy_order = request.form.get('order_id')  # ID del pedido de Shopify
    amount = request.form.get('amount')       # Monto en CLP
    session_id = f"session_{buy_order}"
    return_url = request.host_url + "result"  # URL de retorno

    if not buy_order or not amount:
        return "Error: Debes proporcionar un ID de pedido y un monto", 400

    try:
        response = tx.create(buy_order, session_id, amount, return_url)
        return redirect(f"{response['url']}?token_ws={response['token']}")
    except TransbankError as e:
        return f"Error al iniciar el pago: {str(e)} - Detalles: {e.message}", 400

# Ruta para manejar el resultado del pago
@app.route('/result', methods=['GET', 'POST'])
def payment_result():
    token = request.args.get('token_ws') or request.form.get('token_ws')
    if not token:
        return "Error: No se proporcionó token", 400

    try:
        response = tx.commit(token=token)
        if response['status'] == 'AUTHORIZED':
            return f"Pago exitoso para el pedido {response['buy_order']}. Monto: {response['amount']}."
        else:
            return f"Pago fallido para el pedido {response['buy_order']}. Estado: {response['status']}", 400
    except TransbankError as e:
        return f"Error al procesar el pago: {str(e)}", 400

# Configuración para correr localmente o en Render
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)