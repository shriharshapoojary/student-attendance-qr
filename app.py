from flask import Flask, render_template, request, jsonify
from flask_mysqldb import MySQL
from datetime import datetime
import os
from dotenv import load_dotenv
import qrcode
from io import BytesIO
import base64

load_dotenv()

app = Flask(__name__)
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')
app.config['MYSQL_PORT'] = int(os.getenv('MYSQL_PORT', 3306))

mysql = MySQL(app)

# ==================== Database Setup ====================
def init_db():
    """Initialize database tables"""
    cursor = mysql.connection.cursor()
    
    # Students table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            roll_number VARCHAR(50) UNIQUE NOT NULL,
            branch VARCHAR(50) NOT NULL,
            class VARCHAR(50) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Attendance table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            attendance_id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT NOT NULL,
            name VARCHAR(100) NOT NULL,
            roll_number VARCHAR(50) NOT NULL,
            branch VARCHAR(50) NOT NULL,
            class VARCHAR(50) NOT NULL,
            latitude DECIMAL(10, 8),
            longitude DECIMAL(11, 8),
            scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    ''')
    
    mysql.connection.commit()
    cursor.close()
    print("Database initialized successfully!")

# ==================== Routes ====================

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/admin')
def admin():
    """Admin dashboard"""
    return render_template('admin.html')

@app.route('/admin/students', methods=['GET'])
def get_students():
    """Get all students"""
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT student_id, name, roll_number, branch, class FROM students')
    students = cursor.fetchall()
    cursor.close()
    
    students_list = [
        {
            'student_id': s[0],
            'name': s[1],
            'roll_number': s[2],
            'branch': s[3],
            'class': s[4]
        }
        for s in students
    ]
    
    return jsonify(students_list)

@app.route('/admin/add-student', methods=['POST'])
def add_student():
    """Add a new student"""
    data = request.json
    
    try:
        cursor = mysql.connection.cursor()
        cursor.execute('''
            INSERT INTO students (name, roll_number, branch, class)
            VALUES (%s, %s, %s, %s)
        ''', (data['name'], data['roll_number'], data['branch'], data['class']))
        
        mysql.connection.commit()
        student_id = cursor.lastrowid
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': 'Student added successfully',
            'student_id': student_id
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/admin/delete-student/<int:student_id>', methods=['DELETE'])
def delete_student(student_id):
    """Delete a student"""
    try:
        cursor = mysql.connection.cursor()
        cursor.execute('DELETE FROM students WHERE student_id = %s', (student_id,))
        mysql.connection.commit()
        cursor.close()
        
        return jsonify({'success': True, 'message': 'Student deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/admin/attendance-records', methods=['GET'])
def get_attendance_records():
    """Get all attendance records"""
    cursor = mysql.connection.cursor()
    cursor.execute('''
        SELECT attendance_id, name, roll_number, branch, class, latitude, longitude, scanned_at
        FROM attendance
        ORDER BY scanned_at DESC
    ''')
    records = cursor.fetchall()
    cursor.close()
    
    records_list = [
        {
            'attendance_id': r[0],
            'name': r[1],
            'roll_number': r[2],
            'branch': r[3],
            'class': r[4],
            'latitude': float(r[5]) if r[5] else None,
            'longitude': float(r[6]) if r[6] else None,
            'scanned_at': r[7].strftime('%Y-%m-%d %H:%M:%S')
        }
        for r in records
    ]
    
    return jsonify(records_list)

@app.route('/attendance', methods=['GET'])
def attendance_page():
    """Attendance marking page - student manually enters info"""
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT student_id, name, roll_number, branch, class FROM students ORDER BY name')
    students = cursor.fetchall()
    cursor.close()
    
    students_list = [
        {
            'student_id': s[0],
            'name': s[1],
            'roll_number': s[2],
            'branch': s[3],
            'class': s[4]
        }
        for s in students
    ]
    
    return render_template('attendance.html', students=students_list)

@app.route('/api/record-attendance', methods=['POST'])
def record_attendance():
    """Record attendance with geolocation"""
    data = request.json
    
    try:
        # Get student info from selected student_id
        cursor = mysql.connection.cursor()
        cursor.execute('SELECT name, roll_number, branch, class FROM students WHERE student_id = %s', (data['student_id'],))
        student = cursor.fetchone()
        
        if not student:
            return jsonify({'success': False, 'error': 'Student not found'}), 400
        
        cursor.execute('''
            INSERT INTO attendance (student_id, name, roll_number, branch, class, latitude, longitude)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (
            data['student_id'],
            student[0],
            student[1],
            student[2],
            student[3],
            data.get('latitude'),
            data.get('longitude')
        ))
        
        mysql.connection.commit()
        cursor.close()
        
        return jsonify({
            'success': True,
            'message': 'Attendance recorded successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/admin/export-attendance', methods=['GET'])
def export_attendance():
    """Export attendance as CSV"""
    import csv
    from flask import send_file
    
    cursor = mysql.connection.cursor()
    cursor.execute('''
        SELECT name, roll_number, branch, class, latitude, longitude, scanned_at
        FROM attendance
        ORDER BY scanned_at DESC
    ''')
    records = cursor.fetchall()
    cursor.close()
    
    # Create CSV
    output = BytesIO()
    writer = csv.writer(output.detach())
    writer.writerow(['Name', 'Roll Number', 'Branch', 'Class', 'Latitude', 'Longitude', 'Scanned At'])
    
    for record in records:
        writer.writerow(record)
    
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name='attendance.csv')

# ==================== QR Code Generation ====================
def generate_qr_code(data):
    """Generate QR code and return as base64"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    buffered.seek(0)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    
    return f"data:image/png;base64,{img_str}"

# ==================== Error Handlers ====================
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

# ==================== Main ====================
if __name__ == '__main__':
    # Initialize database on first run
    try:
        init_db()
    except Exception as e:
        print(f"Database initialization warning: {e}")
    
    app.run(
        host=os.getenv('APP_HOST', '0.0.0.0'),
        port=int(os.getenv('APP_PORT', 5000)),
        debug=True
    )