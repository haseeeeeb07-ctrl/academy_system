from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import mysql.connector

app = Flask(__name__)
CORS(app)

def getDB():
    return mysql.connector.connect(
        host     = "localhost",
        user     = "root",
        password = "144971",
        database = "academy_db"
    )

@app.route('/')
def index():
    return send_from_directory('.', 'academy.html')

@app.route('/api/students', methods=['GET'])
def getStudents():
    try:
        db  = getDB()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM students")
        rows = cur.fetchall()
        for r in rows:
            r['subs'] = []
            if r['math']:      r['subs'].append(0)
            if r['english']:   r['subs'].append(1)
            if r['chemistry']: r['subs'].append(2)
            if r['urdu']:      r['subs'].append(3)
            if r['physics']:   r['subs'].append(4)
            r['feePaid'] = bool(r['fee_paid'])
        db.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students', methods=['POST'])
def addStudent():
    try:
        data = request.json
        db   = getDB()
        cur  = db.cursor()
        cur.execute("SELECT id FROM students WHERE id=%s", (data['id'],))
        if cur.fetchone():
            db.close()
            return jsonify({'error': 'ID already exists!'}), 400
        math      = 1 if 0 in data['subs'] else 0
        english   = 1 if 1 in data['subs'] else 0
        chemistry = 1 if 2 in data['subs'] else 0
        urdu      = 1 if 3 in data['subs'] else 0
        physics   = 1 if 4 in data['subs'] else 0
        cur.execute(
            """INSERT INTO students
               (id, name, class_idx, math, english, chemistry, urdu, physics, fee, fee_paid)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (data['id'], data['name'], data['cls'],
             math, english, chemistry, urdu, physics,
             data['fee'], 0)
        )
        db.commit()
        db.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students/<int:sid>/pay', methods=['PUT'])
def payFee(sid):
    try:
        db  = getDB()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM students WHERE id=%s", (sid,))
        s = cur.fetchone()
        if not s:
            db.close()
            return jsonify({'error': 'Student not found!'}), 404
        if s['fee_paid']:
            db.close()
            return jsonify({'error': f"Fee already paid for {s['name']}!"}), 400
        cur.execute("UPDATE students SET fee_paid=1 WHERE id=%s", (sid,))
        db.commit()
        db.close()
        return jsonify({'success': True, 'name': s['name'], 'fee': s['fee']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students/reset', methods=['PUT'])
def resetStudentFees():
    try:
        db  = getDB()
        cur = db.cursor()
        cur.execute("UPDATE students SET fee_paid=0")
        db.commit()
        db.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students/search/<int:sid>', methods=['GET'])
def searchStudent(sid):
    try:
        db  = getDB()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM students WHERE id=%s", (sid,))
        s = cur.fetchone()
        if not s:
            db.close()
            return jsonify({'error': 'Student not found!'}), 404
        s['subs'] = []
        if s['math']:      s['subs'].append(0)
        if s['english']:   s['subs'].append(1)
        if s['chemistry']: s['subs'].append(2)
        if s['urdu']:      s['subs'].append(3)
        if s['physics']:   s['subs'].append(4)
        s['feePaid'] = bool(s['fee_paid'])
        db.close()
        return jsonify(s)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teachers', methods=['GET'])
def getTeachers():
    try:
        db  = getDB()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM teachers")
        rows = cur.fetchall()
        for r in rows:
            r['salaryPaid'] = bool(r['salary_paid'])
        db.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teachers', methods=['POST'])
def addTeacher():
    try:
        data = request.json
        db   = getDB()
        cur  = db.cursor()
        cur.execute("SELECT id FROM teachers WHERE id=%s", (data['id'],))
        if cur.fetchone():
            db.close()
            return jsonify({'error': 'ID already exists!'}), 400
        cur.execute(
            "INSERT INTO teachers (id,name,dept,salary,salary_paid) VALUES (%s,%s,%s,%s,%s)",
            (data['id'], data['name'], data['dept'], data['salary'], 0)
        )
        db.commit()
        db.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teachers/<int:tid>/pay', methods=['PUT'])
def paySalary(tid):
    try:
        db  = getDB()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM teachers WHERE id=%s", (tid,))
        t = cur.fetchone()
        if not t:
            db.close()
            return jsonify({'error': 'Teacher not found!'}), 404
        if t['salary_paid']:
            db.close()
            return jsonify({'error': f"Salary already paid for {t['name']}!"}), 400
        cur.execute("UPDATE teachers SET salary_paid=1 WHERE id=%s", (tid,))
        db.commit()
        db.close()
        return jsonify({'success': True, 'name': t['name'], 'salary': t['salary']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teachers/reset', methods=['PUT'])
def resetTeacherSalaries():
    try:
        db  = getDB()
        cur = db.cursor()
        cur.execute("UPDATE teachers SET salary_paid=0")
        db.commit()
        db.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teachers/search/<int:tid>', methods=['GET'])
def searchTeacher(tid):
    try:
        db  = getDB()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM teachers WHERE id=%s", (tid,))
        t = cur.fetchone()
        if not t:
            db.close()
            return jsonify({'error': 'Teacher not found!'}), 404
        t['salaryPaid'] = bool(t['salary_paid'])
        db.close()
        return jsonify(t)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("====================================")
    print("  Academy Management System Server  ")
    print("  Running on http://localhost:5000   ")
    print("====================================")
    app.run(debug=True, port=5000)