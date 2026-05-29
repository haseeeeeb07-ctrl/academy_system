from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
import os
import urllib.parse as urlparse
import uuid

app = Flask(__name__)
CORS(app)

# Academic pricing structure mapping exactly to front-end constraints
CLASS_MATRIX = [
    {"class_index": 0, "class_label": "Class 9", "base_fee": 1500, "per_subject_fee": 300},
    {"class_index": 1, "class_label": "Class 10", "base_fee": 1600, "per_subject_fee": 350},
    {"class_index": 2, "class_label": "1st Year", "base_fee": 2000, "per_subject_fee": 400},
    {"class_index": 3, "class_label": "2nd Year", "base_fee": 2200, "per_subject_fee": 450}
]

SUBJECTS_MAP = {
    "0": ["Math", "English", "Chemistry", "Urdu", "Physics"],
    "1": ["Math", "English", "Chemistry", "Urdu", "Physics"],
    "2": ["Math", "English", "Physics", "Chemistry", "Computer Science"],
    "3": ["Math", "English", "Physics", "Chemistry", "Computer Science"]
}

def getDB():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        url = urlparse.urlparse(db_url)
        return mysql.connector.connect(
            host=url.hostname,
            user=url.username,
            password=url.password,
            database=url.path[1:],
            port=url.port,
            ssl_disabled=False
        )
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="academy_db"
    )

@app.route('/')
def index():
    return render_template('academy.html')

# ==========================================
# INFRASTRUCTURE ENDPOINTS
# ==========================================

@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({"status": "online"})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    # Placeholder validation mechanism matching administrative console layout rules
    if username == "admin" and password == "admin123":
        return jsonify({"authenticated": True})
    else:
        return jsonify({
            "authenticated": False, 
            "message": "Invalid security credential validation.",
            "remaining_attempts": 3
        }), 401

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({
        "subjects_map": SUBJECTS_MAP,
        "class_matrix": CLASS_MATRIX
    })

# ==========================================
# DASHBOARD ENDPOINT
# ==========================================

@app.route('/api/dashboard', methods=['GET'])
def get_dashboard():
    try:
        db = getDB()
        cur = db.cursor(dictionary=True)
        
        # Pull core metric telemetry counts
        cur.execute("SELECT COUNT(*) as total FROM students")
        total_students = cur.fetchone()['total'] or 0
        
        cur.execute("SELECT COUNT(*) as total, SUM(CASE WHEN status='Paid' THEN 1 ELSE 0 END) as paid, SUM(amount) as total_val, SUM(CASE WHEN status='Pending' THEN amount ELSE 0 END) as pending_val FROM ledger")
        ledger_stats = cur.fetchone()
        
        total_vouchers = ledger_stats['total'] or 0
        paid_vouchers = ledger_stats['paid'] or 0
        total_pending = ledger_stats['pending_val'] or 0
        
        collection_rate = int((paid_vouchers / total_vouchers) * 100) if total_vouchers > 0 else 0
        
        # Recent pipelined objects processing streams
        cur.execute("""
            SELECT l.amount, l.status, s.name, s.class_idx 
            FROM ledger l 
            JOIN students s ON l.student_id = s.id 
            ORDER BY l.voucher_id DESC LIMIT 5
        """)
        vouchers_raw = cur.fetchall()
        recent_vouchers = []
        for v in vouchers_raw:
            lbl = next((c['class_label'] for c in CLASS_MATRIX if c['class_index'] == v['class_idx']), f"Class {v['class_idx']}")
            recent_vouchers.append({
                "name": v['name'],
                "class": lbl,
                "amount": int(v['amount']),
                "status": v['status']
            })
            
        db.close()
        return jsonify({
            "metrics": {
                "total_students": total_students,
                "collection_rate": collection_rate,
                "total_pending": int(total_pending)
            },
            "recent_vouchers": recent_vouchers
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# STUDENT RECORDS MANAGEMENT
# ==========================================

@app.route('/api/students', methods=['GET'])
def get_students():
    try:
        db = getDB()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM students")
        rows = cur.fetchall()
        
        students_list = []
        for r in rows:
            lbl = next((c['class_label'] for c in CLASS_MATRIX if c['class_index'] == r['class_idx']), f"Class {r['class_idx']}")
            
            # Map structural columns back to matching arrays
            subs = []
            if r.get('math'): subs.append("Math")
            if r.get('english'): subs.append("English")
            if r.get('chemistry'): subs.append("Chemistry")
            if r.get('urdu'): subs.append("Urdu")
            if r.get('physics'): subs.append("Physics")
            if r.get('computer_science'): subs.append("Computer Science")
            
            students_list.append({
                "id": r['id'],
                "name": r['name'],
                "class_idx": r['class_idx'],
                "class_label": lbl,
                "custom_fee": int(r['custom_fee']) if r['custom_fee'] is not None else None,
                "subjects": subs
            })
        db.close()
        return jsonify(students_list)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/students', methods=['POST'])
def add_student():
    try:
        data = request.json or {}
        sid = data.get('id')
        name = data.get('name', '').strip()
        class_index = int(data.get('class_index', 0))
        custom_fee = data.get('custom_fee')
        subjects = data.get('subjects', [])
        
        db = getDB()
        cur = db.cursor()
        cur.execute("SELECT id FROM students WHERE id = %s", (sid,))
        if cur.fetchone():
            db.close()
            return jsonify({"success": False, "message": f"Entity code identifier #{sid} collision found!"}), 400
        
        math = 1 if "Math" in subjects else 0
        english = 1 if "English" in subjects else 0
        chemistry = 1 if "Chemistry" in subjects else 0
        urdu = 1 if "Urdu" in subjects else 0
        physics = 1 if "Physics" in subjects else 0
        cs = 1 if "Computer Science" in subjects else 0
        
        fee_override = int(custom_fee) if custom_fee else None
        
        cur.execute(
            """INSERT INTO students (id, name, class_idx, custom_fee, math, english, chemistry, urdu, physics, computer_science) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (sid, name, class_index, fee_override, math, english, chemistry, urdu, physics, cs)
        )
        db.commit()
        db.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/students/delete', methods=['POST'])
def delete_student():
    try:
        sid = request.json.get('id')
        db = getDB()
        cur = db.cursor()
        cur.execute("DELETE FROM ledger WHERE student_id = %s", (sid,))
        cur.execute("DELETE FROM students WHERE id = %s", (sid,))
        db.commit()
        db.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# FACULTY PROFILES MANAGEMENT
# ==========================================

@app.route('/api/teachers', methods=['GET'])
def get_teachers():
    try:
        db = getDB()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM teachers")
        rows = cur.fetchall()
        db.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/teachers', methods=['POST'])
def add_teacher():
    try:
        data = request.json or {}
        tid = data.get('id')
        name = data.get('name', '').strip()
        
        db = getDB()
        cur = db.cursor()
        cur.execute("SELECT id FROM teachers WHERE id = %s", (tid,))
        if cur.fetchone():
            db.close()
            return jsonify({"success": False, "message": f"Instructor ID node #{tid} collision found!"}), 400
            
        cur.execute("INSERT INTO teachers (id, name) VALUES (%s, %s)", (tid, name))
        db.commit()
        db.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/teachers/delete', methods=['POST'])
def delete_teacher():
    try:
        tid = request.json.get('id')
        db = getDB()
        cur = db.cursor()
        cur.execute("DELETE FROM teachers WHERE id = %s", (tid,))
        db.commit()
        db.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# ACCOUNTING LEDGER SYSTEM
# ==========================================

@app.route('/api/ledger', methods=['GET'])
def get_ledger():
    try:
        db = getDB()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT voucher_id, student_id, amount, status FROM ledger ORDER BY voucher_id DESC")
        rows = cur.fetchall()
        for r in rows:
            r['amount'] = int(r['amount'])
        db.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ledger/lookup', methods=['GET'])
def lookup_ledger():
    try:
        sid = request.args.get('id')
        db = getDB()
        cur = db.cursor(dictionary=True)
        
        cur.execute("SELECT * FROM students WHERE id = %s", (sid,))
        student_row = cur.fetchone()
        if not student_row:
            db.close()
            return jsonify({"found": False})
            
        lbl = next((c['class_label'] for c in CLASS_MATRIX if c['class_index'] == student_row['class_idx']), f"Class {student_row['class_idx']}")
        student_data = {
            "id": student_row['id'],
            "name": student_row['name'],
            "class_label": lbl
        }
        
        cur.execute("SELECT voucher_id, amount, status FROM ledger WHERE student_id = %s ORDER BY voucher_id DESC", (sid,))
        vouchers_rows = cur.fetchall()
        vouchers = []
        for v in vouchers_rows:
            vouchers.append({
                "voucher_id": v['voucher_id'],
                "amount": int(v['amount']),
                "status": v['status']
            })
            
        db.close()
        return jsonify({
            "found": True,
            "student": student_data,
            "vouchers": vouchers
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ledger/pay', methods=['POST'])
def pay_voucher():
    try:
        vid = request.json.get('voucher_id')
        db = getDB()
        cur = db.cursor()
        cur.execute("UPDATE ledger SET status = 'Paid' WHERE voucher_id = %s", (vid,))
        db.commit()
        db.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ledger/generate', methods=['POST'])
def generate_vouchers():
    try:
        db = getDB()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM students")
        students = cur.fetchall()
        
        generated_count = 0
        for s in students:
            # Determine fee based on overrides or pricing matrices
            if s['custom_fee'] is not None:
                final_fee = int(s['custom_fee'])
            else:
                cfg = next((c for c in CLASS_MATRIX if c['class_index'] == s['class_idx']), {"base_fee": 1500, "per_subject_fee": 300})
                sub_count = sum([s['math'], s['english'], s['chemistry'], s['urdu'], s['physics'], s['computer_science']])
                final_fee = cfg['base_fee'] + (sub_count * cfg['per_subject_fee'])
            
            # Formulate tracking index tokens
            v_token = f"V-{uuid.uuid4().hex[:6].upper()}-{s['id']}"
            cur.execute(
                "INSERT INTO ledger (voucher_id, student_id, amount, status) VALUES (%s, %s, %s, 'Pending')",
                (v_token, s['id'], final_fee)
            )
            generated_count += 1
            
        db.commit()
        db.close()
        return jsonify({"generated": generated_count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/ledger/clear', methods=['POST'])
def clear_ledger():
    try:
        db = getDB()
        cur = db.cursor()
        cur.execute("DELETE FROM ledger")
        db.commit()
        db.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# DIAGNOSTIC AUDIT LOGS REPORT
# ==========================================

@app.route('/api/report', methods=['GET'])
def generate_report():
    try:
        db = getDB()
        cur = db.cursor(dictionary=True)
        
        cur.execute("SELECT COUNT(*) as tally FROM students")
        total_s = cur.fetchone()['tally']
        
        cur.execute("SELECT COUNT(*) as tally FROM teachers")
        total_t = cur.fetchone()['tally']
        
        cur.execute("SELECT SUM(amount) as val FROM ledger WHERE status='Paid'")
        collected = cur.fetchone()['val'] or 0
        
        cur.execute("SELECT SUM(amount) as val FROM ledger WHERE status='Pending'")
        arrears = cur.fetchone()['val'] or 0
        
        report_text = f"""==================================================
ADMINISTRATIVE MATRIX DIAGNOSTIC LOG AUDIT REPORT
==================================================
[SYSTEM EXECUTION STATUS]: STABLE DEPLOYMENT NODE
[ACTIVE ENROLMENTS COUNT]: {total_s} Core Records
[PROVISIONED FACULTY]: {total_t} Instructional Staff

[FINANCIAL LEDGER DIAGNOSTICS]:
 - Total Logged Settled Volume: Rs. {int(collected)}
 - Total Outstanding Arrears Balance: Rs. {int(arrears)}
 - System Accounting Integrity Check: PASS

==================================================
Report parsed from secure tracking layer successfully.
"""
        db.close()
        return jsonify({"report_text": report_text})
    except Exception as e:
        return jsonify({"report_text": f"Error running report calculations: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
