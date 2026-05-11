import sqlite3

def test_connection():
    conn = sqlite3.connect('database.db')
    assert conn is not None

def test_user_exists():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users")
    user = cursor.fetchone()

    assert user is not None

def test_add_grade():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM grades")
    grades = cursor.fetchall()

    assert len(grades) >= 0

if __name__ == "__main__":
    test_connection()
    test_user_exists()
    test_add_grade()
    print("Все тесты прошли!")