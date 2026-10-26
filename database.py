"""
Smart Hospital Management System - Database Layer
==================================================
Pure Python SQLite database layer with zero external dependencies.
Handles tables, relational constraints, data seeding, and CRUD queries.
"""

import sqlite3
import os
import hashlib
import secrets
from typing import List, Dict, Any, Optional, Tuple

DB_FILE = os.environ.get("HOSPITAL_DB_PATH", os.path.join(os.path.dirname(__file__), "hospital.db"))

def get_db_connection() -> sqlite3.Connection:
    """Creates a database connection with row factory and foreign keys enabled."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db(force_reseed: bool = False):
    """Initializes the database schema and seeds default data if tables are empty."""
    conn = get_db_connection()
    cursor = conn.cursor()

    if force_reseed:
        cursor.execute("DROP TABLE IF EXISTS bills;")
        cursor.execute("DROP TABLE IF EXISTS appointments;")
        cursor.execute("DROP TABLE IF EXISTS patients;")
        cursor.execute("DROP TABLE IF EXISTS beds;")
        cursor.execute("DROP TABLE IF EXISTS medicines;")
        cursor.execute("DROP TABLE IF EXISTS settings;")
        cursor.execute("DROP TABLE IF EXISTS users;")

    # 1. Patients Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        age INTEGER NOT NULL,
        gender TEXT NOT NULL,
        condition TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Critical', 'Discharged')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Appointments Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id TEXT NOT NULL,
        doctor TEXT NOT NULL,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'Approved', 'Completed', 'Cancelled')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE RESTRICT
    );
    """)

    # 3. Beds Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS beds (
        id INTEGER PRIMARY KEY,
        ward TEXT NOT NULL CHECK(ward IN ('ICU', 'General', 'Private')),
        status TEXT NOT NULL DEFAULT 'Available' CHECK(status IN ('Available', 'Occupied', 'Maintenance')),
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Medicines Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS medicines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        stock INTEGER NOT NULL DEFAULT 0,
        price REAL NOT NULL DEFAULT 0.0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 5. Bills Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bills (
        id TEXT PRIMARY KEY,
        patient_id TEXT NOT NULL,
        amount REAL NOT NULL DEFAULT 0.0,
        status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Paid', 'Pending')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE RESTRICT
    );
    """)

    # 6. Settings Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)

    # 7. Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'Doctor' CHECK(role IN ('Admin', 'Doctor', 'Receptionist', 'Nurse', 'Patient')),
        full_name TEXT NOT NULL,
        email TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()

    # Seed initial data if empty
    cursor.execute("SELECT COUNT(*) FROM patients")
    patient_count = cursor.fetchone()[0]

    if patient_count == 0:
        _seed_initial_data(conn)

    # Seed default users if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    if user_count == 0:
        _seed_default_users(conn)

    conn.close()


def _seed_initial_data(conn: sqlite3.Connection):
    """Populates default demonstration data."""
    cursor = conn.cursor()

    # Default Patients
    initial_patients = [
        ("P001", "Rahul Sharma", 32, "Male", "Fever", "Active"),
        ("P002", "Priya Patil", 27, "Female", "Diabetes", "Active"),
        ("P003", "Amit Kumar", 45, "Male", "Cardiology", "Critical"),
        ("P004", "Sneha Joshi", 29, "Female", "Checkup", "Discharged"),
    ]
    cursor.executemany(
        "INSERT INTO patients (id, name, age, gender, condition, status) VALUES (?, ?, ?, ?, ?, ?);",
        initial_patients
    )

    # Default Appointments
    initial_appointments = [
        (1, "P001", "Dr. Mehta", "2026-10-25", "09:30", "Pending"),
        (2, "P002", "Dr. Desai", "2026-10-25", "10:15", "Approved"),
        (3, "P003", "Dr. Shah", "2026-10-25", "11:00", "Pending"),
    ]
    cursor.executemany(
        "INSERT INTO appointments (id, patient_id, doctor, date, time, status) VALUES (?, ?, ?, ?, ?, ?);",
        initial_appointments
    )

    # Default Beds (16 beds)
    initial_beds = []
    for i in range(16):
        bed_id = i + 101
        ward = "ICU" if i < 4 else ("General" if i < 10 else "Private")
        if i % 5 == 0:
            status = "Maintenance"
        elif i % 3 == 0:
            status = "Available"
        else:
            status = "Occupied"
        initial_beds.append((bed_id, ward, status))

    cursor.executemany(
        "INSERT INTO beds (id, ward, status) VALUES (?, ?, ?);",
        initial_beds
    )

    # Default Medicines
    initial_medicines = [
        ("Paracetamol", 250, 20.0),
        ("Amoxicillin", 140, 85.0),
        ("Metformin", 320, 45.0),
        ("Cetirizine", 180, 30.0),
        ("Insulin", 40, 450.0),
    ]
    cursor.executemany(
        "INSERT INTO medicines (name, stock, price) VALUES (?, ?, ?);",
        initial_medicines
    )

    # Default Bills
    initial_bills = [
        ("INV001", "P001", 2500.0, "Paid"),
        ("INV002", "P002", 4800.0, "Pending"),
        ("INV003", "P003", 12500.0, "Paid"),
    ]
    cursor.executemany(
        "INSERT INTO bills (id, patient_id, amount, status) VALUES (?, ?, ?, ?);",
        initial_bills
    )

    # Default Settings
    initial_settings = [
        ("hospital_name", "Smart Hospital"),
        ("hospital_website", "smarthospital.com"),
    ]
    cursor.executemany(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?);",
        initial_settings
    )

    conn.commit()


# =====================================================================
# PASSWORD HASHING & AUTHENTICATION UTILITIES
# =====================================================================

def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hashes password using PBKDF2-HMAC-SHA256 with a secure salt."""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return hashed, salt


def verify_password(password: str, salt: str, password_hash: str) -> bool:
    """Verifies a password against the stored salt and hash."""
    hashed, _ = hash_password(password, salt)
    return secrets.compare_digest(hashed, password_hash)


def _seed_default_users(conn: sqlite3.Connection):
    """Seeds default user accounts for fast role-based login."""
    cursor = conn.cursor()
    default_users = [
        ("admin", "admin123", "Admin", "Dr. Sarah Jenkins", "admin@smarthospital.org"),
        ("doctor", "doctor123", "Doctor", "Dr. Rajesh Patel", "dr.patel@smarthospital.org"),
        ("recep", "recep123", "Receptionist", "Anita Sharma", "anita.reception@smarthospital.org"),
        ("user", "user123", "Patient", "Rahul Sharma", "rahul.user@gmail.com"),
    ]
    for username, pwd, role, full_name, email in default_users:
        pwd_hash, salt = hash_password(pwd)
        cursor.execute("""
            INSERT OR IGNORE INTO users (username, password_hash, salt, role, full_name, email)
            VALUES (?, ?, ?, ?, ?, ?);
        """, (username, pwd_hash, salt, role, full_name, email))
    conn.commit()


# =====================================================================
# USERS & AUTHENTICATION CRUD
# =====================================================================

def authenticate_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticates username and password against users table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, password_hash, salt, role, full_name, email, created_at
        FROM users
        WHERE LOWER(username) = LOWER(?);
    """, (username.strip(),))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    if verify_password(password, row["salt"], row["password_hash"]):
        return {
            "id": row["id"],
            "username": row["username"],
            "role": row["role"],
            "full_name": row["full_name"],
            "email": row["email"],
            "created_at": row["created_at"]
        }
    return None


def create_user(data: Dict[str, Any]) -> Dict[str, Any]:
    """Registers a new user."""
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", "")).strip()
    full_name = str(data.get("full_name") or data.get("name") or username).strip()
    role = str(data.get("role", "Patient")).strip()
    email = str(data.get("email", "")).strip() or None

    if not username:
        raise ValueError("Username is required.")
    if not password or len(password) < 4:
        raise ValueError("Password must be at least 4 characters long.")
    if role not in ["Admin", "Doctor", "Receptionist", "Nurse", "Patient"]:
        role = "Patient"

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if username exists
    cursor.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?);", (username,))
    if cursor.fetchone():
        conn.close()
        raise ValueError(f"Username '{username}' is already taken.")

    pwd_hash, salt = hash_password(password)

    cursor.execute("""
        INSERT INTO users (username, password_hash, salt, role, full_name, email)
        VALUES (?, ?, ?, ?, ?, ?);
    """, (username, pwd_hash, salt, role, full_name, email))
    user_id = cursor.lastrowid
    conn.commit()

    cursor.execute("""
        SELECT id, username, role, full_name, email, created_at
        FROM users WHERE id = ?;
    """, (user_id,))
    new_user = dict(cursor.fetchone())
    conn.close()
    return new_user


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Fetches user details by ID (excluding sensitive credentials)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, role, full_name, email, created_at
        FROM users WHERE id = ?;
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Fetches user details by username (excluding sensitive credentials)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, role, full_name, email, created_at
        FROM users WHERE LOWER(username) = LOWER(?);
    """, (username.strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_users() -> List[Dict[str, Any]]:
    """Lists all users without password hashes."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, role, full_name, email, created_at
        FROM users
        ORDER BY id ASC;
    """)
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users


# =====================================================================
# PATIENTS CRUD
# =====================================================================

def get_patients(search: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves patients with optional search filter."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if search:
        search_pattern = f"%{search.strip().lower()}%"
        cursor.execute("""
            SELECT id, name, age, gender, condition, status, created_at
            FROM patients
            WHERE LOWER(name) LIKE ? OR LOWER(id) LIKE ? OR LOWER(condition) LIKE ?
            ORDER BY created_at DESC
        """, (search_pattern, search_pattern, search_pattern))
    else:
        cursor.execute("""
            SELECT id, name, age, gender, condition, status, created_at
            FROM patients
            ORDER BY created_at DESC
        """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_patient(patient_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves single patient by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients WHERE id = ?", (patient_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def create_patient(data: Dict[str, Any]) -> Dict[str, Any]:
    """Inserts a new patient record."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Generate patient ID if not provided
    patient_id = data.get("id")
    if not patient_id:
        cursor.execute("SELECT id FROM patients WHERE id LIKE 'P%' ORDER BY id DESC")
        existing_ids = cursor.fetchall()
        max_num = 0
        for row in existing_ids:
            try:
                num = int(row[0].replace("P", ""))
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
        patient_id = f"P{max_num + 1:03d}"

    name = data["name"].strip()
    age = int(data["age"])
    gender = data.get("gender", "Other")
    condition = data["condition"].strip()
    status = data.get("status", "Active")

    cursor.execute("""
        INSERT INTO patients (id, name, age, gender, condition, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (patient_id, name, age, gender, condition, status))

    conn.commit()
    conn.close()
    return get_patient(patient_id) # type: ignore


def update_patient(patient_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Updates an existing patient record."""
    conn = get_db_connection()
    cursor = conn.cursor()

    existing = get_patient(patient_id)
    if not existing:
        conn.close()
        return None

    name = data.get("name", existing["name"]).strip()
    age = int(data.get("age", existing["age"]))
    gender = data.get("gender", existing["gender"])
    condition = data.get("condition", existing["condition"]).strip()
    status = data.get("status", existing["status"])

    cursor.execute("""
        UPDATE patients
        SET name = ?, age = ?, gender = ?, condition = ?, status = ?
        WHERE id = ?
    """, (name, age, gender, condition, status, patient_id))

    conn.commit()
    conn.close()
    return get_patient(patient_id)


def delete_patient(patient_id: str) -> Tuple[bool, str]:
    """
    Deletes patient if no appointments or bills are linked.
    Returns (success, message).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM appointments WHERE patient_id = ?", (patient_id,))
    if cursor.fetchone()[0] > 0:
        conn.close()
        return False, "Cannot delete patient with linked appointment records."

    cursor.execute("SELECT COUNT(*) FROM bills WHERE patient_id = ?", (patient_id,))
    if cursor.fetchone()[0] > 0:
        conn.close()
        return False, "Cannot delete patient with linked billing records."

    cursor.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()

    if deleted:
        return True, "Patient deleted successfully."
    return False, "Patient not found."


# =====================================================================
# APPOINTMENTS CRUD
# =====================================================================

def get_appointments() -> List[Dict[str, Any]]:
    """Retrieves all appointments with joined patient details."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.id, a.patient_id as patientId, p.name as patientName,
               a.doctor, a.date, a.time, a.status, a.created_at
        FROM appointments a
        LEFT JOIN patients p ON a.patient_id = p.id
        ORDER BY a.date DESC, a.time DESC, a.id DESC
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def create_appointment(data: Dict[str, Any]) -> Dict[str, Any]:
    """Books a new appointment."""
    conn = get_db_connection()
    cursor = conn.cursor()

    patient_id = data["patientId"]
    doctor = data["doctor"].strip()
    date = data["date"].strip()
    time = data["time"].strip()
    status = data.get("status", "Pending")

    cursor.execute("""
        INSERT INTO appointments (patient_id, doctor, date, time, status)
        VALUES (?, ?, ?, ?, ?)
    """, (patient_id, doctor, date, time, status))

    appointment_id = cursor.lastrowid
    conn.commit()

    cursor.execute("""
        SELECT a.id, a.patient_id as patientId, p.name as patientName,
               a.doctor, a.date, a.time, a.status, a.created_at
        FROM appointments a
        LEFT JOIN patients p ON a.patient_id = p.id
        WHERE a.id = ?
    """, (appointment_id,))
    row = dict(cursor.fetchone())
    conn.close()
    return row


def update_appointment_status(appointment_id: int, status: str) -> Optional[Dict[str, Any]]:
    """Updates appointment status."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE appointments SET status = ? WHERE id = ?", (status, appointment_id))
    conn.commit()

    cursor.execute("""
        SELECT a.id, a.patient_id as patientId, p.name as patientName,
               a.doctor, a.date, a.time, a.status, a.created_at
        FROM appointments a
        LEFT JOIN patients p ON a.patient_id = p.id
        WHERE a.id = ?
    """, (appointment_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def delete_appointment(appointment_id: int) -> bool:
    """Cancels/deletes an appointment record."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM appointments WHERE id = ?", (appointment_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# =====================================================================
# BEDS CRUD
# =====================================================================

def get_beds() -> List[Dict[str, Any]]:
    """Retrieves all hospital beds."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, ward, status, updated_at FROM beds ORDER BY id ASC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def update_bed_status(bed_id: int, status: str) -> Optional[Dict[str, Any]]:
    """Updates bed status (Available, Occupied, Maintenance)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE beds
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, bed_id))
    conn.commit()

    cursor.execute("SELECT id, ward, status, updated_at FROM beds WHERE id = ?", (bed_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# =====================================================================
# PHARMACY / MEDICINES CRUD
# =====================================================================

def get_medicines() -> List[Dict[str, Any]]:
    """Retrieves all medicines from inventory."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, stock, price, updated_at FROM medicines ORDER BY name ASC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def create_or_update_medicine(data: Dict[str, Any]) -> Dict[str, Any]:
    """Adds a new medicine or updates stock/price if already existing."""
    conn = get_db_connection()
    cursor = conn.cursor()
    name = data["name"].strip()
    stock = int(data.get("stock", 0))
    price = float(data.get("price", 0.0))

    cursor.execute("""
        INSERT INTO medicines (name, stock, price, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(name) DO UPDATE SET
            stock = excluded.stock,
            price = excluded.price,
            updated_at = CURRENT_TIMESTAMP
    """, (name, stock, price))
    conn.commit()

    cursor.execute("SELECT id, name, stock, price, updated_at FROM medicines WHERE name = ?", (name,))
    row = dict(cursor.fetchone())
    conn.close()
    return row


def delete_medicine(medicine_id: int) -> bool:
    """Deletes medicine from inventory."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM medicines WHERE id = ?", (medicine_id,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# =====================================================================
# BILLING CRUD
# =====================================================================

def get_bills() -> List[Dict[str, Any]]:
    """Retrieves all bills with patient details."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.id, b.patient_id as patientId, p.name as patientName,
               b.amount, b.status, b.created_at
        FROM bills b
        LEFT JOIN patients p ON b.patient_id = p.id
        ORDER BY b.created_at DESC
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def create_bill(data: Dict[str, Any]) -> Dict[str, Any]:
    """Creates a new billing invoice."""
    conn = get_db_connection()
    cursor = conn.cursor()

    bill_id = data.get("id")
    if not bill_id:
        cursor.execute("SELECT id FROM bills WHERE id LIKE 'INV%' ORDER BY id DESC")
        existing_ids = cursor.fetchall()
        max_num = 0
        for row in existing_ids:
            try:
                num = int(row[0].replace("INV", ""))
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
        bill_id = f"INV{max_num + 1:03d}"

    patient_id = data["patientId"]
    amount = float(data["amount"])
    status = data.get("status", "Pending")

    cursor.execute("""
        INSERT INTO bills (id, patient_id, amount, status)
        VALUES (?, ?, ?, ?)
    """, (bill_id, patient_id, amount, status))
    conn.commit()

    cursor.execute("""
        SELECT b.id, b.patient_id as patientId, p.name as patientName,
               b.amount, b.status, b.created_at
        FROM bills b
        LEFT JOIN patients p ON b.patient_id = p.id
        WHERE b.id = ?
    """, (bill_id,))
    row = dict(cursor.fetchone())
    conn.close()
    return row


def update_bill_status(bill_id: str, status: str) -> Optional[Dict[str, Any]]:
    """Updates bill payment status."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE bills SET status = ? WHERE id = ?", (status, bill_id))
    conn.commit()

    cursor.execute("""
        SELECT b.id, b.patient_id as patientId, p.name as patientName,
               b.amount, b.status, b.created_at
        FROM bills b
        LEFT JOIN patients p ON b.patient_id = p.id
        WHERE b.id = ?
    """, (bill_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


# =====================================================================
# SETTINGS
# =====================================================================

def get_settings() -> Dict[str, str]:
    """Retrieves hospital system settings."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    settings = {row["key"]: row["value"] for row in cursor.fetchall()}
    conn.close()
    return {
        "name": settings.get("hospital_name", "Smart Hospital"),
        "website": settings.get("hospital_website", "smarthospital.com")
    }


def save_settings(data: Dict[str, str]) -> Dict[str, str]:
    """Saves hospital system settings."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if "name" in data:
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('hospital_name', ?)", (data["name"].strip(),))
    if "website" in data:
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('hospital_website', ?)", (data["website"].strip(),))
    conn.commit()
    conn.close()
    return get_settings()


# =====================================================================
# DASHBOARD STATS & ALERTS
# =====================================================================

def get_dashboard_stats() -> Dict[str, Any]:
    """Computes aggregated dashboard metrics."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Active Patients
    cursor.execute("SELECT COUNT(*) FROM patients WHERE status != 'Discharged'")
    active_patients = cursor.fetchone()[0]

    # Critical Patients
    cursor.execute("SELECT COUNT(*) FROM patients WHERE status = 'Critical'")
    critical_patients = cursor.fetchone()[0]

    # Beds occupancy
    cursor.execute("SELECT COUNT(*) FROM beds")
    total_beds = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM beds WHERE status = 'Occupied'")
    occupied_beds = cursor.fetchone()[0]
    occupancy_rate = round((occupied_beds / total_beds * 100)) if total_beds > 0 else 0

    # Revenue
    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM bills WHERE status = 'Paid'")
    revenue = cursor.fetchone()[0]

    # Recent Appointments (last 5)
    cursor.execute("""
        SELECT a.id, a.patient_id as patientId, p.name as patientName,
               a.doctor, a.date, a.time, a.status
        FROM appointments a
        LEFT JOIN patients p ON a.patient_id = p.id
        ORDER BY a.id DESC
        LIMIT 5
    """)
    recent_appointments = [dict(row) for row in cursor.fetchall()]

    # First 8 Beds Overview
    cursor.execute("SELECT id, ward, status FROM beds ORDER BY id ASC LIMIT 8")
    dashboard_beds = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        "activePatients": active_patients,
        "criticalPatients": critical_patients,
        "totalBeds": total_beds,
        "occupiedBeds": occupied_beds,
        "occupancy": occupancy_rate,
        "revenue": revenue,
        "recentAppointments": recent_appointments,
        "dashboardBeds": dashboard_beds
    }


def get_alerts() -> List[Dict[str, Any]]:
    """Retrieves critical patient emergency alerts."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, age, gender, condition, status
        FROM patients
        WHERE status = 'Critical'
        ORDER BY name ASC
    """)
    alerts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return alerts
