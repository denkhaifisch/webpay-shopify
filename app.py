from flask import Flask, request, render_template, redirect
import requests
import json
from supabase import create_client, Client
import os

app = Flask(__name__)

# Credenciales hardcodeadas
commerce_code = "597037325732"
api_key = "d89040c88af98fe38e1c47d5a0fc705c"

# Configuración de Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Validar credenciales de Supabase
if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Faltan SUPABASE_URL o SUPABASE_KEY en las variables de entorno")

# Inicializar cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/pay', methods=['POST'])
def create_payment():
    print(f"Credenciales: commerce_code={commerce_code}, api_key={api_key}")
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
    return_url = "https://webpay-shopify.onrender.com/result"
    print(f"buy_order: {buy_order}, session_id: {session_id}, amount: {amount}, return_url: {return_url}")

    # Guardar transacción inicial (PENDING) en Supabase
    transaction = {
        "order_id": buy_order,
        "amount": amount,
        "session_id": session_id,
        "status": "PENDING"
    }
    try:
        result = supabase.table("transactions").insert(transaction).execute()
        print(f"Transacción PENDING guardada: {result.data}")
    except Exception as e:
        print(f"Error al guardar en Supabase: {str(e)}")
        return f"Error al guardar transacción en base de datos: {str(e)}", 500

    headers = {
        "Tbk-Api-Key-Id": commerce_code,
        "Tbk-Api-Key-Secret": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "buy_order": buy_order,
        "session_id": session_id,
        "amount": amount,
        "return_url": return_url,
    }

    try:
        print(f"Enviando: {json.dumps(payload)}")
        response = requests.post(
            "https://webpay3g.transbank.cl/rswebpaytransaction/api/webpay/v1.2/transactions",
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        print(f"Respuesta: {data}")
        return redirect(f"{data['url']}?token_ws={data['token']}")
    except requests.exceptions.RequestException as e:
        print(f"Error HTTP: {str(e)}")
        # Guardar error en Supabase
        transaction = {
            "order_id": buy_order,
            "amount": amount,
            "session_id": session_id,
            "status": "FAILED",
            "response": {"error": str(e)}
        }
        try:
            supabase.table("transactions").insert(transaction).execute()
        except Exception as e2:
            print(f"Error al guardar fallo en Supabase: {str(e2)}")
        return f"Error al iniciar el pago: {str(e)}", 400

@app.route('/result', methods=['GET', 'POST'])
def payment_result():
    token = request.args.get('token_ws') or request.form.get('token_ws')
    if not token:
        return "Error: No se proporcionó token", 400

    headers = {
        "Tbk-Api-Key-Id": commerce_code,
        "Tbk-Api-Key-Secret": api_key,
        "Content-Type": "application/json",
    }
    try:
        print(f"Confirmando token: {token}")
        response = requests.put(
            f"https://webpay3g.transbank.cl/rswebpaytransaction/api/webpay/v1.2/transactions/{token}",
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        print(f"Confirmación: {data}")

        # Guardar resultado en Supabase
        transaction = {
            "order_id": data.get('buy_order'),
            "amount": data.get('amount'),
            "session_id": data.get('session_id'),
            "token_ws": token,
            "status": data.get('status'),
            "response": data
        }
        try:
            result = supabase.table("transactions").insert(transaction).execute()
            print(f"Transacción {data['status']} guardada: {result.data}")
        except Exception as e:
            print(f"Error al guardar en Supabase: {str(e)}")
            # Continuar aunque Supabase falle, para no interrumpir el flujo
            pass

        if data['status'] == 'AUTHORIZED':
            return f"Pago exitoso para el pedido {data['buy_order']}. Monto: {data['amount']}."
        else:
            return f"Pago fallido para el pedido {data['buy_order']}. Estado: {data['status']}", 400
    except requests.exceptions.RequestException as e:
        print(f"Error HTTP: {str(e)}")
        # Guardar error en Supabase
        transaction = {
            "order_id": None,
            "amount": None,
            "session_id": None,
            "token_ws": token,
            "status": "FAILED",
            "response": {"error": str(e)}
        }
        try:
            supabase.table("transactions").insert(transaction).execute()
        except Exception as e2:
            print(f"Error al guardar fallo en Supabase: {str(e2)}")
        return f"Error al procesar el pago: {str(e)}", 400

if __name__ == '__main__':
    port = 5000
    app.run(host='0.0.0.0', port=port, debug=False)