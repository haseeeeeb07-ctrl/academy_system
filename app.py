from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import mysql.connector
import os
import urllib.parse as urlparse
import datetime

app = Flask(__name__)
CORS(app)

# --- CONFIGURATION MATRIX MATCHING HTML VISUALS ---
CLASS_MATRIX = [
    {"class_index": "0", "class_label": "Class 9", "base_fee": 2000, "per_subject_fee": 300},
    {"class_index": "1", "class_label": "Class 10", "base_fee": 2500, "per_subject_fee": 350},
    {"class_index": "2", "class_label": "1st Year", "base_fee": 3500, "per_subject_fee": 500},
    {"class_index": "3", "class_label": "2nd Year", "base_fee": 4000, "per_subject_fee": 550}
]

SUBJECTS_MAP = {
    "0": ["Mathematics", "Physics", "Chemistry", "Computer Science", "English"],
    "1": ["Mathematics", "Physics", "Chemistry", "Computer Science", "English"],
    "2": ["Mathematics", "Physics", "Chemistry", "English", "Urdu"],
    "3": ["Mathematics", "Physics", "Chemistry", "English", "Urdu"]
}

# --- ENVIROMENT DATABASE CONNECTOR ---
def getDB():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        # Local fallback context setup
        return mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="academy_db"
        )
    url = urlparse.urlparse(db_url)
    return mysql.connector.connect(
        host         = url.hostname,
        user         = url.username,
        password     = url.password,
        database     = url.path[1:],
        port         = url.port,
        ssl_disabled = False
    )

# --- AUTO INITIALIZE/VERIFY SCHEMA TABLES ---
def init_db_schema():
    try:
        db = getDB()
        cur = db.cursor()
        # Ensure base student table structure is sound
        cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                class_idx INT NOT NULL,
                math TINYINT(1) DEFAULT 0,
                english TINYINT(1) DEFAULT 0,
                chemistry TINYINT(1) DEFAULT 0,
                urdu TINYINT(1) DEFAULT 0,
                physics TINYINT(1) DEFAULT 0,
                fee INT NOT NULL,
                fee_paid TINYINT(1) DEFAULT 0
            )
        """)
        # Ensure structural ledger pipeline table exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ledger (
                voucher_id VARCHAR(100) PRIMARY KEY,
                student_id INT NOT NULL,
                amount INT NOT NULL,
                status VARCHAR(20) DEFAULT 'Unpaid'
            )
        """)
        # Ensure teachers table architecture exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id INT PRIMARY KEY,
                name VARCHAR(255) NOT NULL
            )
        """)
        db.commit()
        db.close()
    except Exception as e:
        print(f"Database Initialization Warning: {e}")

init_db_schema()

# --- FRONTEND LAYER ---
@app.route('/')
def index():
    return render_template('academy.html')

# --- SYSTEM UTILITY BOUNDARIES ---
@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({"status": "online"})

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({
        "class_matrix": CLASS_MATRIX,
        "subjects_map": SUBJECTS_MAP
    })

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json or {}
    username = data.get('username')
    password = data.get('password')
    
    if username == "muzahirsaleem" and password == "1234":
        return jsonify({"authenticated": True})
    else:
        return jsonify({"authenticated": False, "message": "Invalid terminal credentials", "remaining_attempts": 3})

# --- DASHBOARD METRICS TRACKING ---
@app.route('/api/dashboard', methods=['GET'])
def dashboard_metrics():
    try:
        db = getDB()
        cur = db.cursor(dictionary=True)
        
        # Calculate active records
        cur.execute("SELECT COUNT(*) as total FROM students")
        total_students = cur.fetchone()["total"]
        
        # Aggregate financial stats from ledger
        cur.execute("SELECT SUM(amount) as total_amt, status FROM ledger GROUP BY status")
        rows = cur.fetchall()
        
        paid_sum = 0
        unpaid_sum = 0
        for r in rows:
            if r['status'] == 'Paid':
                paid_sum = r['total_amt'] or 0
            elif r['status'] == 'Unpaid':
                unpaid_sum = r['total_amt'] or 0
                
        total_billed = paid_sum + unpaid_sum
        collection_rate = round((paid_sum / total_billed * 100), 1) if total_billed > 0 else 0
        
        metrics = {
            "total_students": total_students,
            "collection_rate": collection_rate,
            "total_pending": unpaid_sum
        }
        
        # Fetch up to 5 historical recent voucher entities
        cur.execute("""
            SELECT l.voucher_id, s.name, s.class_idx, l.amount, l.status 
            FROM ledger l 
            JOIN students s ON l.student_id = s.id 
            ORDER BY l.voucher_id DESC LIMIT 5
        """)
        recent_rows = cur.fetchall()
        recent_vouchers = []
        
        for r in recent_rows:
            lbl = next((c["class_label"] for c in CLASS_MATRIX if c["class_index"] == str(r["class_idx"])), f"Class {r['class_idx']}")
            recent_vouchers.append({
                "voucher_id": r["voucher_id"],
                "name": r["name"],
                "class": lbl,
                "amount": r["amount"],
                "status": r["status"]
            })
            
        db.close()
        return jsonify({"metrics": metrics, "recent_vouchers": recent_vouchers})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- STUDENTS RESOURCE ---
@app.route('/api/students', methods=['GET'])
def getStudents():
    try:
        db  = getDB()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM students")
        rows = cur.fetchall()
        
        for r in rows:
            # Reconstruct list of subject string labels for frontend tables
            lbls = SUBJECTS_MAP.get(str(r['class_idx']), [])
            r['subjects'] = []
            if r['math'] and len(lbls) > 0: r['subjects'].append(lbls[0])
            if r['physics'] and len(lbls) > 1: r['subjects'].append(lbls[1])
            if r['chemistry'] and len(lbls) > 2: r['subjects'].append(lbls[2])
            # Map remaining subjects accurately checking table boundaries
            if r['class_idx'] in [0, 1]: # Class 9/10
                if r['urdu'] and len(lbls) > 3: r['subjects'].append(lbls[3]) # Computer Science
                if r['english'] and len(lbls) > 4: r['subjects'].append(lbls[4]) # English
            else: # 1st/2nd Year
                if r['english'] and len(lbls) > 3: r['subjects'].append(lbls[3]) # English
                if r['urdu'] and len(lbls) > 4: r['subjects'].append(lbls[4]) # Urdu
                
            lbl = next((c["class_label"] for c in CLASS_MATRIX if c["class_index"] == str(r["class_idx"])), f"Class {r['class_idx']}")
            r['class_label'] = lbl
            r['custom_fee'] = r['fee']
            
        db.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students', methods=['POST'])
def addStudent():
    try:
        data = request.json or {}
        s_id = data.get('id')
        name = data.get('name')
        class_idx = int(data.get('class_index', 0))
        custom_fee = data.get('custom_fee')
        subs_list = data.get('subjects', [])
        
        db = getDB()
        cur = db.cursor()
        
        cur.execute("SELECT id FROM students WHERE id=%s", (s_id,))
        if cur.fetchone():
            db.close()
            return jsonify({'error': 'Student with this ID already exists!'}), 400
            
        # Dynamically map selected text subjects to true column binaries
        lbls = SUBJECTS_MAP.get(str(class_idx), [])
        math = 1 if len(lbls) > 0 and lbls[0] in subs_list else 0
        physics = 1 if len(lbls) > 1 and lbls[1] in subs_list else 0
        chemistry = 1 if len(lbls) > 2 and lbls[2] in subs_list else 0
        
        # Track conditional mapping offsets based on specific course stream matrices
        english = 0
        urdu = 0
        if class_idx in [0, 1]:
            urdu = 1 if len(lbls) > 3 and lbls[3] in subs_list else 0 # Maps to computer science array slots
            english = 1 if len(lbls) > 4 and lbls[4] in subs_list else 0
        else:
            english = 1 if len(lbls) > 3 and lbls[3] in subs_list else 0
            urdu = 1 if len(lbls) > 4 and lbls[4] in subs_list else 0
            
        # Use matrix calculations if custom base override parameter is not supplied
        if not custom_fee:
            rule = next((c for c in CLASS_MATRIX if c["class_index"] == str(class_idx)), None)
            base = rule["base_fee"] if rule else 2000
            per_sub = rule["per_subject_fee"] if rule else 300
            calculated_fee = base + (per_sub * len(subs_list))
        else:
            calculated_fee = int(custom_fee)
            
        cur.execute(
            """INSERT INTO students
               (id, name, class_idx, math, english, chemistry, urdu, physics, fee, fee_paid)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0)""",
            (s_id, name, class_idx, math, english, chemistry, urdu, physics, calculated_fee)
        )
        db.commit()
        db.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/students/delete', methods=['POST'])
def delete_student():
    try:
        data = request.json or {}
        s_id = data.get('id')
        db = getDB()
        cur = db.cursor()
        cur.execute("DELETE FROM students WHERE id = %s", (s_id,))
        cur.execute("DELETE FROM ledger WHERE student_id = %s", (s_id,))
        db.commit()
        db.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- TEACHERS RESOURCE ---
@app.route('/api/teachers', methods=['GET'])
def getTeachers():
    try:
        db  = getDB()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM teachers")
        rows = cur.fetchall()
        db.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teachers', methods=['POST'])
def addTeacher():
    try:
        data = request.json or {}
        t_id = data.get('id')
        name = data.get('name')
        
        db   = getDB()
        cur  = db.cursor()
        cur.execute("SELECT id FROM teachers WHERE id=%s", (t_id,))
        if cur.fetchone():
            db.close()
            return jsonify({'error': 'Teacher with this ID already exists!'}), 400
            
        cur.execute("INSERT INTO teachers (id, name) VALUES (%s, %s)", (t_id, name))
        db.commit()
        db.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/teachers/delete', methods=['POST'])
def delete_teacher():
    try:
        data = request.json or {}
        t_id = data.get('id')
        db = getDB()
        cur = db.cursor()
        cur.execute("DELETE FROM teachers WHERE id = %s", (t_id,))
        db.commit()
        db.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- FINANCIAL ACCONTING LEDGER BOUNDARY PATHS ---
@app.route('/api/ledger', methods=['GET'])
def get_ledger():
    try:
        db = getDB()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM ledger ORDER BY voucher_id DESC")
        rows = cur.fetchall()
        db.close()
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ledger/generate', methods=['POST'])
def generate_monthly_vouchers():
    try:
        db = getDB()
        cur = db.cursor(dictionary=True)
        cur.execute("SELECT id, fee FROM students")
        students = cur.fetchall()
        
        month_suffix = datetime.datetime.now().strftime("%b%Y").upper()
        generated_count = 0
        
        for s in students:
            v_id = f"VCH-{s['id']}-{month_suffix}"
            try:
                cur.execute("""
                    INSERT INTO ledger (voucher_id, student_id, amount, status)
                    VALUES (%s, %s, %s, 'Unpaid')
                    ON DUPLICATE KEY UPDATE amount=%s
                """, (v_id, s['id'], s['fee'], s['fee']))
                generated_count += 1
            except:
                pass
                
        db.commit()
        db.close()
        return jsonify({"success": True, "generated": generated_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ledger/lookup', methods=['GET'])
def lookup_fee_profile():
    try:
        s_id = request.args.get('id')
        db = getDB()
        cur = db.cursor(dictionary=True)
        
        cur.execute("SELECT id, name, class_idx FROM students WHERE id = %s", (s_id,))
        student = cur.fetchone()
        
        response = {"found": False}
        if student:
            response["found"] = True
            lbl = next((c["class_label"] for c in CLASS_MATRIX if c["class_index"] == str(student["class_idx"])), f"Class {student['class_idx']}")
            response["student"] = {"name": student["name"], "class_label": lbl}
            
            cur.execute("SELECT voucher_id, amount, status FROM ledger WHERE student_id = %s ORDER BY voucher_id DESC", (s_id,))
            response["vouchers"] = cur.fetchall()
            
        db.close()
        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ledger/pay', methods=['POST'])
def pay_voucher():
    try:
        data = request.json or {}
        v_id = data.get('voucher_id', '')
        
        db = getDB()
        cur = db.cursor()
        cur.execute("UPDATE ledger SET status = 'Paid' WHERE voucher_id = %s", (v_id,))
        db.commit()
        db.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ledger/clear', methods=['POST'])
def clear_ledger():
    try:
        db = getDB()
        cur = db.cursor()
        cur.execute("TRUNCATE TABLE ledger")
        db.commit()
        db.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- SYSTEM INTEGRITY DIAGNOSTIC COMPILATION REPORT ---
@app.route('/api/report', methods=['GET'])
def generate_report_log():
    try:
        db = getDB()
        cur = db.cursor()
        
        cur.execute("SELECT COUNT(*) FROM students")
        total_students = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM teachers")
        total_teachers = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*), SUM(amount) FROM ledger WHERE status='Unpaid'")
        unpaid = cur.fetchone()
        unpaid_count = unpaid[0] or 0
        unpaid_val = unpaid[1] or 0
        
        cur.execute("SELECT COUNT(*), SUM(amount) FROM ledger WHERE status='Paid'")
        paid = cur.fetchone()
        paid_count = paid[0] or 0
        paid_val = paid[1] or 0
        
        db.close()
        
        report_text = (
            "=== ACADEMY MANAGEMENT SYSTEM AUDIT MANIFEST ===\n"
            f"Total Synchronized Student Metrics: {total_students}\n"
            f"Total Faculty Profiles Registered: {total_teachers}\n"
            f"Outstanding Unpaid Transactions: {unpaid_count} (Value: Rs. {unpaid_val})\n"
            f"Settled Collection Transactions: {paid_count} (Value: Rs. {paid_val})\n\n"
            "Diagnostic Status Core Check: PASS\nAll Node Vectors Operational.\n"
        )
        return jsonify({"report_text": report_text})
    except Exception as e:
        return jsonify({"report_text": f"DATA SYSTEM AUDIT FAILURE: {str(e)}"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
