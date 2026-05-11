import sqlite3

conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Таблица пользователей
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    role TEXT
)
''')

# Таблица оценок
cursor.execute('''
CREATE TABLE IF NOT EXISTS grades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    subject TEXT,
    grade INTEGER
)
''')

conn.commit()

def register(username, password, role):
    cursor.execute(
        "INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)",
        (username, password, role)
    )
    conn.commit()
    print("Пользователь создан!")

def login(username, password):
    cursor.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, password)
    )
    user = cursor.fetchone()

    if user:
        print("Успешный вход!")
    else:
        print("Ошибка входа!")

def add_grade(user_id, subject, grade):
    cursor.execute(
        "INSERT INTO grades (user_id, subject, grade) VALUES (?, ?, ?)",
        (user_id, subject, grade)
    )
    conn.commit()
    print("Оценка добавлена!")

def show_grades():
    cursor.execute("SELECT * FROM grades")
    rows = cursor.fetchall()

    for row in rows:
        print(row)

register("admin", "1234", "teacher")
login("admin", "1234")

add_grade(1, "Math", 5)
show_grades()

conn.close()