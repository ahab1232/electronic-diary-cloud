from flask import Flask, render_template, request, redirect, session, abort
import sqlite3
import random
import re 
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "123456789"
DB_NAME = "database.db"

def get_db():
    conn = sqlite3.connect(DB_NAME, timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def clean_text(value, max_len=500):
    value = (value or "").strip()
    value = re.sub(r"\s+", " ", value)
    return value[:max_len]

def weekday_name(offset=0):
    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    d = datetime.now() + timedelta(days=offset)
    return days[d.weekday()]

def require_role(*roles):
    # Исправленная проверка авторизации
    if "user_id" not in session:
        abort(403)
    if session.get("role") not in roles:
        abort(403)

@app.route("/")
def home():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
    user = cur.fetchone()
    db.close()
    if user:
        session["user_id"] = user["id"]
        session["user"] = user["username"] # КРИТИЧНО ДЛЯ РАБОТЫ ЧАТА
        session["role"] = user["role"]
        session["full_name"] = user["full_name"]
        session["class_name"] = user["class_name"]
        return redirect("/dashboard")
    return render_template("login.html", error="Неверный логин или пароль")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")

    db = get_db()
    cur = db.cursor()
    role = session.get("role")
    today = weekday_name(0)
    tomorrow = weekday_name(1)

    cur.execute("SELECT class_name FROM classes ORDER BY class_name")
    classes = cur.fetchall()

    cur.execute("SELECT receiver_name, phone, message_text FROM feedback ORDER BY id")
    feedback_contacts = cur.fetchall()

    base = dict(
        role=role,
        full_name=session.get("full_name"),
        today=today,
        tomorrow=tomorrow,
        classes=classes,
        feedback_contacts=feedback_contacts,
        teachers=[], students=[], subjects=[], grades=[],
        schedule_list=[], homework_list=[], class_notes=[],
        selected_class="", class_teacher="", class_characteristic="",
        child_name="", deputy_selected_class=""
    )

    if role == "admin":
        cur.execute("SELECT id, full_name, username, class_name FROM users WHERE role='teacher' ORDER BY class_name")
        base["teachers"] = cur.fetchall()
        cur.execute("SELECT class_name, class_note FROM class_notes ORDER BY class_name")
        base["class_notes"] = cur.fetchall()

    elif role == "deputy":
        class_filter = request.args.get("class_filter", "")
        base["deputy_selected_class"] = class_filter
        if class_filter:
            cur.execute("SELECT class_name, week_day, lesson_number, lesson_time, subject FROM schedule WHERE class_name=? ORDER BY week_day, lesson_number", (class_filter,))
            base["schedule_list"] = cur.fetchall()
            cur.execute("SELECT class_name, class_note FROM class_notes WHERE class_name=?", (class_filter,))
            base["class_notes"] = cur.fetchall()
        else:
            cur.execute("SELECT class_name, week_day, lesson_number, lesson_time, subject FROM schedule ORDER BY class_name, week_day, lesson_number")
            base["schedule_list"] = cur.fetchall()
            cur.execute("SELECT class_name, class_note FROM class_notes ORDER BY class_name")
            base["class_notes"] = cur.fetchall()

    elif role in ["teacher", "student"]:
        class_name = session.get("class_name")
        base["selected_class"] = class_name
        
        if role == "teacher":
            cur.execute("SELECT id, full_name FROM users WHERE role='student' AND class_name=? ORDER BY full_name", (class_name,))
            base["students"] = cur.fetchall()
            cur.execute("SELECT id, class_name, subject, grade FROM grades WHERE class_name=? ORDER BY id DESC", (class_name,))
            base["grades"] = cur.fetchall()
        else:
            cur.execute("SELECT id, class_name, subject, grade FROM grades WHERE user_id=? ORDER BY id DESC", (session["user_id"],))
            base["grades"] = cur.fetchall()

        cur.execute("SELECT subject_name FROM subjects WHERE class_name=? ORDER BY subject_name", (class_name,))
        base["subjects"] = cur.fetchall()
        cur.execute("SELECT week_day, lesson_number, lesson_time, subject FROM schedule WHERE class_name=? ORDER BY id", (class_name,))
        base["schedule_list"] = cur.fetchall()
        cur.execute("SELECT id, subject, task_text, due_day FROM homework WHERE class_name=? ORDER BY id DESC", (class_name,))
        base["homework_list"] = cur.fetchall()
        cur.execute("SELECT teacher_name FROM classes WHERE class_name=?", (class_name,))
        row = cur.fetchone()
        base["class_teacher"] = row["teacher_name"] if row else ""
        cur.execute("SELECT class_note FROM class_notes WHERE class_name=?", (class_name,))
        row = cur.fetchone()
        base["class_characteristic"] = row["class_note"] if row else ""

    elif role == "parent":
        cur.execute("SELECT student_username FROM parent_links WHERE parent_username=?", (session["user"],))
        link = cur.fetchone()
        if link:
            cur.execute("SELECT id, full_name, class_name FROM users WHERE username=?", (link["student_username"],))
            st = cur.fetchone()
            if st:
                base["child_name"], base["selected_class"] = st["full_name"], st["class_name"]
                cur.execute("SELECT id, class_name, subject, grade FROM grades WHERE user_id=?", (st["id"],))
                base["grades"] = cur.fetchall()
                cur.execute("SELECT week_day, lesson_number, lesson_time, subject FROM schedule WHERE class_name=? ORDER BY id", (st["class_name"],))
                base["schedule_list"] = cur.fetchall()
                cur.execute("SELECT id, subject, task_text, due_day FROM homework WHERE class_name=? ORDER BY id DESC", (st["class_name"],))
                base["homework_list"] = cur.fetchall()
                cur.execute("SELECT teacher_name FROM classes WHERE class_name=?", (st["class_name"],))
                row = cur.fetchone()
                base["class_teacher"] = row["teacher_name"] if row else ""
                cur.execute("SELECT class_note FROM class_notes WHERE class_name=?", (st["class_name"],))
                row = cur.fetchone()
                base["class_characteristic"] = row["class_note"] if row else ""

    db.close()
    return render_template("dashboard.html", **base)

@app.route("/add", methods=["POST"])
def add():
    require_role("teacher")
    user_id, subject, grade = request.form.get("student_id"), clean_text(request.form.get("subject")), int(request.form.get("grade"))
    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO grades VALUES (NULL,?,?,?,?)", (user_id, session.get("class_name"), subject, grade))
    db.commit()
    db.close()
    return redirect("/dashboard")

@app.route("/delete/<int:grade_id>")
def delete_grade(grade_id):
    require_role("teacher")
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM grades WHERE id=?", (grade_id,))
    db.commit()
    db.close()
    return redirect("/dashboard")

@app.route("/add_homework", methods=["POST"])
def add_homework():
    require_role("teacher")
    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO homework VALUES (NULL,?,?,?,?)", (session.get("class_name"), clean_text(request.form.get("subject")), clean_text(request.form.get("task_text")), clean_text(request.form.get("due_day"))))
    db.commit()
    db.close()
    return redirect("/dashboard")

@app.route("/delete_homework/<int:hw_id>")
def delete_homework(hw_id):
    require_role("teacher")
    db = get_db()
    cur = db.cursor()
    cur.execute("DELETE FROM homework WHERE id=?", (hw_id,))
    db.commit()
    db.close()
    return redirect("/dashboard")

@app.route("/update_homework", methods=["POST"])
def update_homework():
    require_role("teacher")
    hw_id, new_text = request.form.get("hw_id"), clean_text(request.form.get("new_task_text"))
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE homework SET task_text=? WHERE id=?", (new_text, hw_id))
    db.commit()
    db.close()
    return redirect("/dashboard")


@app.route("/ai_chat", methods=["POST"])
def ai_chat():
    msg = request.form.get("message", "").lower().strip()

    if not msg:
        return "Напишите вопрос."

    class_name = session.get("class_name")

    if not class_name:
        return "Зайдите в систему как учитель или ученик."

    db = get_db()
    cur = db.cursor()

    if "распис" in msg:
        cur.execute("""
            SELECT week_day, lesson_number, subject
            FROM schedule
            WHERE class_name=?
            ORDER BY id
            LIMIT 10
        """, (class_name,))

        rows = cur.fetchall()

        if not rows:
            db.close()
            return "Расписание не найдено."

        text = "<b>Расписание:</b><br>"

        for r in rows:
            text += f"{r['week_day']} — {r['lesson_number']} урок — {r['subject']}<br>"

        db.close()
        return text

    if "домаш" in msg:
        cur.execute("""
            SELECT subject, task_text, due_day
            FROM homework
            WHERE class_name=?
            ORDER BY id DESC
            LIMIT 5
        """, (class_name,))

        rows = cur.fetchall()

        if not rows:
            db.close()
            return "Домашнего задания нет."

        text = "<b>Домашнее задание:</b><br>"

        for r in rows:
            text += f"{r['subject']} — {r['task_text']} ({r['due_day']})<br>"

        db.close()
        return text

    if "роль" in msg:
        role = session.get("role")
        return f"Ваша роль: {role}"

    if "как меня зовут" in msg or "кто я" in msg:
        return f"Вы: {session.get('full_name')}"

    db.close()

    return """
    Я умею:
    <br>• Показывать расписание
    <br>• Показывать домашнее задание
    <br>• Говорить вашу роль
    <br>• Говорить ваше имя
    """

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)

    # Получаем данные из сессии
    class_name = session.get("class_name")
    role = session.get("role")
    full_name = session.get("full_name")
    
    # Словари для перевода ролей на русский
    roles_ru = {
        "admin": "Администратор",
        "teacher": "Учитель",
        "student": "Ученик",
        "parent": "Родитель",
        "deputy": "Завуч"
    }

    db = get_db()
    cur = db.cursor()

    # 1. Ответ на "Кто я?" или "Как меня зовут?"
    if "кто я" in msg or "как меня зовут" in msg:
        
    # 2. Ответ на "Какая роль?"
    if "роль" in msg:
        res_role = roles_ru.get(role, role)
        return f"Ваша текущая роль: {res_role}."

    # 3. Ответ на "Какой сегодня день?"
    if "какой сегодня день" in msg or "день недели" in msg:
        today = weekday_name(0)
        return f"Сегодня {today}."

    # 4. Ответ на "Домашнее задание"
    if "домаш" in msg:
        if not class_name:
            return "К сожалению, я не могу найти ваш класс, чтобы показать задание."
            
        cur.execute("SELECT subject, task_text, due_day FROM homework WHERE class_name=? ORDER BY id DESC LIMIT 5", (class_name,))
        rows = cur.fetchall()
        db.close()
        
        if not rows:
            return "Домашних заданий для вашего класса пока нет."
            
        text = "<b>Список заданий:</b><br>"
        for r in rows:
            text += f"• {r[0]}: {r[1]} (Срок: {r[2]})<br>"
        return text

    # 5. Ответ на "Расписание"
    if "распис" in msg:   
        if not class_name:
            return "Я не знаю вашего класса, чтобы показать расписание."
            
        cur.execute("SELECT week_day, lesson_number, subject FROM schedule WHERE class_name=? LIMIT 7", (class_name,))
        rows = cur.fetchall()
        db.close()
        
        if not rows:
            return "Расписание не найдено."
            
        text = "<b>Ваше расписание:</b><br>"
        for r in rows:
            text += f"{r[0]} | Урок №{r[1]}: {r[2]}<br>" 
        return text

    db.close()
    return "Я понимаю вопросы про расписание, домашнее задание, какой сегодня день и вашу роль в системе."