from flask import Flask, request, render_template, redirect, url_for
import sqlite3

app = Flask(__name__)

# Create a basic SQLite database for storing expenses
def init_db():
    with sqlite3.connect('expense.db') as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS expense
                        (id INTEGER PRIMARY KEY AUTOINCREMENT,
                         Name TEXT,
                         amount INTEGER)''')

@app.route('/')
def home():
    # Fetch all expenses from the database
    with sqlite3.connect('expense.db') as conn:
        expenses = conn.execute('SELECT * FROM expense').fetchall()
    return render_template('lib.html', expenses=expenses)

@app.route('/add', methods=['POST'])
def add_expense():
    Name = request.form['Name']
    amount = int(request.form['amount'])
    with sqlite3.connect('expense.db') as conn:
        conn.execute('INSERT INTO expense (Name, amount) VALUES (?, ?)', (Name, amount))
    return redirect(url_for('home'))

@app.route('/update', methods=['POST'])
def update_expense():
    expense_id = int(request.form['id'])
    Name = request.form['Name']
    amount = int(request.form['amount'])
    with sqlite3.connect('expense.db') as conn:
        conn.execute('UPDATE expense SET Name = ?, amount = ? WHERE id = ?', (Name, amount, expense_id))
    return redirect(url_for('home'))

@app.route('/delete', methods=['POST'])
def delete_expense():
    expense_id = int(request.form['id'])
    with sqlite3.connect('expense.db') as conn:
        conn.execute('DELETE FROM expense WHERE id = ?', (expense_id,))
    return redirect(url_for('home'))

@app.route('/search', methods=['GET'])
def search_expense():
    search_query = request.args.get('query', '')
    with sqlite3.connect('expense.db') as conn:
        results = conn.execute('SELECT * FROM expense WHERE Name LIKE ?', (f'%{search_query}%',)).fetchall()
    return render_template('search_results.html', results=results, query=search_query)

init_db()

if __name__ == '__main__':
    app.run(debug=True)
