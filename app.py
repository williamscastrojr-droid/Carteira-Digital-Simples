from flask import Flask, jsonify, request, send_file, render_template
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "carteira.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # balance: single row table to store added balance (saldoBruto)
    c.execute("""CREATE TABLE IF NOT EXISTS balance (
        id INTEGER PRIMARY KEY CHECK (id=1),
        amount REAL NOT NULL
    )""")
    # ensure single row exists
    c.execute("INSERT OR IGNORE INTO balance (id, amount) VALUES (1, 0.0)")
    # gastos table
    c.execute("""CREATE TABLE IF NOT EXISTS gastos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        categoria TEXT NOT NULL,
        valor REAL NOT NULL,
        data TEXT NOT NULL
    )""")
    conn.commit()
    conn.close()

def get_db_conn():
    return sqlite3.connect(DB_PATH)

app = Flask(__name__, static_folder='static', template_folder='templates')
init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/state', methods=['GET'])
def api_state():
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("SELECT amount FROM balance WHERE id=1")
    balance = c.fetchone()[0]
    c.execute("SELECT id, categoria, valor, data FROM gastos ORDER BY id DESC")
    rows = c.fetchall()
    gastos = [{'id': r[0], 'categoria': r[1], 'valor': r[2], 'data': r[3]} for r in rows]
    conn.close()
    return jsonify({'balance': balance, 'gastos': gastos})

@app.route('/api/saldo', methods=['POST'])
def api_add_saldo():
    data = request.get_json() or {}
    amount = float(data.get('amount', 0))
    if amount <= 0:
        return jsonify({'error': 'Valor inválido'}), 400
    conn = get_db_conn()
    c = conn.cursor()
    # update balance (add)
    c.execute("UPDATE balance SET amount = amount + ? WHERE id=1", (amount,))
    conn.commit()
    c.execute("SELECT amount FROM balance WHERE id=1")
    balance = c.fetchone()[0]
    conn.close()
    return jsonify({'balance': balance})

@app.route('/api/gasto', methods=['POST'])
def api_add_gasto():
    data = request.get_json() or {}
    categoria = data.get('categoria')
    valor = float(data.get('valor', 0))
    if not categoria or valor <= 0:
        return jsonify({'error': 'Dados inválidos'}), 400
    now = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    conn = get_db_conn()
    c = conn.cursor()
    c.execute("INSERT INTO gastos (categoria, valor, data) VALUES (?, ?, ?)", (categoria, valor, now))
    conn.commit()
    gasto_id = c.lastrowid
    # Subtrai o gasto do saldo
    c.execute("UPDATE balance SET amount = amount - ? WHERE id=1", (valor,))
    conn.commit()
    c.execute("SELECT amount FROM balance WHERE id=1")
    balance = c.fetchone()[0]
    conn.close()
    return jsonify({'id': gasto_id, 'balance': balance, 'data': now})

@app.route('/api/gasto/<int:gasto_id>', methods=['DELETE'])
def api_delete_gasto(gasto_id):
    conn = get_db_conn()
    c = conn.cursor()
    # get valor to refund to balance
    c.execute("SELECT valor FROM gastos WHERE id = ?", (gasto_id,))
    r = c.fetchone()
    if not r:
        conn.close()
        return jsonify({'error': 'Gasto não encontrado'}), 404
    valor = r[0]
    c.execute("DELETE FROM gastos WHERE id = ?", (gasto_id,))
    c.execute("UPDATE balance SET amount = amount + ? WHERE id=1", (valor,))
    conn.commit()
    c.execute("SELECT amount FROM balance WHERE id=1")
    balance = c.fetchone()[0]
    conn.close()
    return jsonify({'balance': balance})

@app.route('/download-db')
def download_db():
    return send_file(DB_PATH, as_attachment=True, download_name='carteira.db')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
