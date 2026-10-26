import os, sqlite3, secrets, re, sys
from functools import wraps
from datetime import datetime
from flask import Flask, request, jsonify, session, render_template, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE=os.path.dirname(os.path.abspath(__file__))
DB=os.environ.get('HOSPITAL_DB_PATH') or os.path.join(BASE,'hospital.db')
app=Flask(__name__)
app.secret_key=os.environ.get('HOSPITAL_SECRET') or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('HOSPITAL_HTTPS','0')=='1', MAX_CONTENT_LENGTH=1024*1024)

def conn():
    if 'db' not in g:
        g.db=sqlite3.connect(DB); g.db.row_factory=sqlite3.Row; g.db.execute('PRAGMA foreign_keys=ON')
    return g.db
@app.teardown_appcontext
def close(exc):
    db=g.pop('db',None)
    if db: db.close()
def rows(sql,args=()): return [dict(x) for x in conn().execute(sql,args).fetchall()]
def one(sql,args=()):
    r=conn().execute(sql,args).fetchone();return dict(r) if r else None
def init():
    with app.app_context():
        c=conn();c.executescript('''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','doctor','patient')), name TEXT NOT NULL, patient_id TEXT);
        CREATE TABLE IF NOT EXISTS patients(id TEXT PRIMARY KEY, name TEXT NOT NULL, age INTEGER NOT NULL, gender TEXT NOT NULL, condition TEXT NOT NULL DEFAULT 'Checkup', status TEXT NOT NULL DEFAULT 'Active', user_id INTEGER UNIQUE REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY AUTOINCREMENT, patientId TEXT NOT NULL REFERENCES patients(id), doctor TEXT NOT NULL, date TEXT NOT NULL, time TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Pending');
        CREATE TABLE IF NOT EXISTS beds(id INTEGER PRIMARY KEY, ward TEXT NOT NULL, status TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS medicines(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, stock INTEGER NOT NULL, price REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS bills(id TEXT PRIMARY KEY, patientId TEXT NOT NULL REFERENCES patients(id), amount REAL NOT NULL, status TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        if not one('SELECT id FROM beds LIMIT 1'):
            c.executemany('INSERT INTO beds VALUES (?,?,?)',[(i+101,'ICU' if i<4 else 'General' if i<10 else 'Private','Available') for i in range(16)])
        for k,v in [('name','Smart Hospital'),('website','smarthospital.com')]:c.execute('INSERT OR IGNORE INTO settings VALUES (?,?)',(k,v))
        c.commit()
def error(msg,code=400):return jsonify(error=msg),code
def current():
    if not session.get('uid'):return None
    return one('SELECT id,username,role,name,patient_id FROM users WHERE id=?',(session['uid'],))
def login_required(fn):
    @wraps(fn)
    def wrapped(*a,**kw):
        u=current()
        if not u:return error('Please log in',401)
        if request.method not in ('GET','HEAD','OPTIONS') and request.headers.get('X-CSRF-Token')!=session.get('csrf'):
            return error('Invalid CSRF token',403)
        return fn(u,*a,**kw)
    return wrapped
def staff(u):return u['role'] in ('admin','doctor')
def allowed(u):
    if not staff(u):return error('Staff access only',403)
def data():return request.get_json(silent=True) or {}
def require_fields(d,*fields):return all(str(d.get(f,'')).strip() for f in fields)
def patient_scope(u):
    return '' if staff(u) else ' WHERE id=?'
def patient_args(u):return () if staff(u) else (u['patient_id'] or '',)
@app.route('/')
def index():return render_template('index.html')
@app.get('/api/health')
def health():return jsonify(status='healthy')
@app.get('/api/auth/me')
def me():
    u=current();return jsonify(user=u,csrf=session.get('csrf')) if u else error('Not logged in',401)
@app.post('/api/auth/login')
def login():
    d=data();u=one('SELECT * FROM users WHERE username=?',(str(d.get('username','')).strip().lower(),))
    if not u or not check_password_hash(u['password'],str(d.get('password',''))):return error('Invalid username or password',401)
    session.clear();session['uid']=u['id'];session['csrf']=secrets.token_urlsafe(24)
    return me()
@app.post('/api/auth/signup')
def signup():
    d=data();username=str(d.get('username','')).strip().lower();password=str(d.get('password',''));name=str(d.get('name','')).strip()
    if not re.fullmatch(r'[a-z0-9_]{3,30}',username) or not name or len(name)>100 or len(password)<6 or not re.search(r'\d',password):return error('Username: 3-30 letters/numbers/_. Password: at least 6 characters including a digit.')
    if one('SELECT id FROM users WHERE username=?',(username,)):return error('Username already exists',409)
    c=conn();pid='P'+secrets.token_hex(5).upper()
    try:
        cur=c.execute('INSERT INTO users(username,password,role,name,patient_id) VALUES (?,?,?,?,?)',(username,generate_password_hash(password),'patient',name,pid))
        c.execute('INSERT INTO patients VALUES (?,?,?,?,?,?,?)',(pid,name,int(d.get('age',18)) if str(d.get('age',18)).isdigit() and 1<=int(d.get('age',18))<=120 else 18,str(d.get('gender','Other')) if d.get('gender') in ('Male','Female','Other') else 'Other','Checkup','Active',cur.lastrowid));c.commit()
    except sqlite3.IntegrityError:return error('Account could not be created',409)
    session.clear();session['uid']=cur.lastrowid;session['csrf']=secrets.token_urlsafe(24)
    return me()
@app.post('/api/auth/logout')
@login_required
def logout(u):session.clear();return jsonify(ok=True)
@app.get('/api/patients')
@login_required
def patients(u):
    q=request.args.get('search','').strip()
    if staff(u):return jsonify(rows('SELECT id,name,age,gender,condition,status FROM patients WHERE name LIKE ? OR id LIKE ? ORDER BY rowid DESC',('%'+q+'%','%'+q+'%')))
    return jsonify(rows('SELECT id,name,age,gender,condition,status FROM patients WHERE id=?',(u['patient_id'],)))
@app.post('/api/patients')
@login_required
def add_patient(u):
    if not staff(u):return allowed(u)
    d=data()
    if not require_fields(d,'name','age','gender','condition') or not str(d['age']).isdigit() or not 1<=int(d['age'])<=120:return error('Invalid patient data')
    pid='P'+secrets.token_hex(5).upper()
    conn().execute('INSERT INTO patients(id,name,age,gender,condition,status) VALUES (?,?,?,?,?,?)',(pid,str(d['name'])[:100],int(d['age']),d['gender'],str(d['condition'])[:100],d.get('status','Active')));conn().commit()
    return jsonify(one('SELECT id,name,age,gender,condition,status FROM patients WHERE id=?',(pid,))),201
@app.delete('/api/patients/<pid>')
@login_required
def del_patient(u,pid):
    if u['role']!='admin':return error('Admin only',403)
    if one('SELECT user_id FROM patients WHERE id=?',(pid,)) and one('SELECT user_id FROM patients WHERE id=?',(pid,))['user_id']:return error('Cannot delete registered account patient')
    try:conn().execute('DELETE FROM patients WHERE id=?',(pid,));conn().commit()
    except sqlite3.IntegrityError:return error('Patient has linked appointments or bills',409)
    return jsonify(ok=True)
@app.get('/api/appointments')
@login_required
def appointments(u):
    sql='SELECT a.*,p.name patientName FROM appointments a JOIN patients p ON p.id=a.patientId'
    return jsonify(rows(sql+(' ORDER BY a.id DESC' if staff(u) else ' WHERE a.patientId=? ORDER BY a.id DESC'),() if staff(u) else (u['patient_id'],)))
@app.post('/api/appointments')
@login_required
def add_appointment(u):
    d=data();pid=d.get('patientId') if staff(u) else u['patient_id']
    if not pid or not one('SELECT id FROM patients WHERE id=?',(pid,)) or not require_fields(d,'doctor','date','time'):return error('Invalid appointment details')
    try:datetime.strptime(d['date'],'%Y-%m-%d');datetime.strptime(d['time'],'%H:%M')
    except (ValueError,TypeError):return error('Invalid date or time')
    c=conn().execute('INSERT INTO appointments(patientId,doctor,date,time,status) VALUES (?,?,?,?,?)',(pid,str(d['doctor'])[:100],d['date'],d['time'],'Pending'));conn().commit()
    return jsonify(one('SELECT a.*,p.name patientName FROM appointments a JOIN patients p ON p.id=a.patientId WHERE a.id=?',(c.lastrowid,))),201
@app.patch('/api/appointments/<int:aid>/status')
@login_required
def appointment_status(u,aid):
    if not staff(u):return allowed(u)
    s=data().get('status')
    if s not in ('Approved','Completed','Cancelled'):return error('Invalid status')
    conn().execute('UPDATE appointments SET status=? WHERE id=?',(s,aid));conn().commit();return jsonify(status=s)
@app.get('/api/beds')
@login_required
def beds(u):return jsonify(rows('SELECT * FROM beds')) if staff(u) else error('Staff access only',403)
@app.patch('/api/beds/<int:bid>/status')
@login_required
def bed_status(u,bid):
    if not staff(u):return allowed(u)
    s=data().get('status')
    if s not in ('Available','Occupied','Maintenance'):return error('Invalid status')
    conn().execute('UPDATE beds SET status=? WHERE id=?',(s,bid));conn().commit();return jsonify(status=s)
@app.get('/api/medicines')
@login_required
def medicines(u):return jsonify(rows('SELECT * FROM medicines ORDER BY name'))
@app.post('/api/medicines')
@login_required
def add_medicine(u):
    if not staff(u):return allowed(u)
    d=data()
    try:name=str(d['name']).strip()[:100];stock=int(d['stock']);price=float(d['price']);assert name and stock>=0 and price>=0
    except (KeyError,TypeError,ValueError,AssertionError):return error('Invalid medicine')
    conn().execute('INSERT INTO medicines(name,stock,price) VALUES (?,?,?) ON CONFLICT(name) DO UPDATE SET stock=excluded.stock,price=excluded.price',(name,stock,price));conn().commit()
    return jsonify(one('SELECT * FROM medicines WHERE name=?',(name,)))
@app.get('/api/bills')
@login_required
def bills(u):
    sql='SELECT b.*,p.name patientName FROM bills b JOIN patients p ON p.id=b.patientId'
    return jsonify(rows(sql+(' ORDER BY b.rowid DESC' if staff(u) else ' WHERE b.patientId=? ORDER BY b.rowid DESC'),() if staff(u) else (u['patient_id'],)))
@app.post('/api/bills')
@login_required
def add_bill(u):
    if not staff(u):return allowed(u)
    d=data()
    try:amount=float(d['amount']);assert amount>0 and d.get('status') in ('Pending','Paid') and one('SELECT id FROM patients WHERE id=?',(d.get('patientId'),))
    except (ValueError,TypeError,KeyError,AssertionError):return error('Invalid bill')
    bid='INV'+secrets.token_hex(5).upper();conn().execute('INSERT INTO bills VALUES (?,?,?,?)',(bid,d['patientId'],amount,d['status']));conn().commit()
    return jsonify(one('SELECT b.*,p.name patientName FROM bills b JOIN patients p ON p.id=b.patientId WHERE b.id=?',(bid,))),201
@app.patch('/api/bills/<bid>/status')
@login_required
def bill_status(u,bid):
    if not staff(u):return allowed(u)
    if data().get('status')!='Paid':return error('Invalid status')
    conn().execute("UPDATE bills SET status='Paid' WHERE id=?",(bid,));conn().commit();return jsonify(status='Paid')
@app.get('/api/settings')
@login_required
def settings(u):return jsonify({x['key']:x['value'] for x in rows('SELECT * FROM settings')}) if staff(u) else error('Staff access only',403)
@app.post('/api/settings')
@login_required
def save_settings(u):
    if u['role']!='admin':return error('Admin only',403)
    d=data()
    for key in ('name','website'):
        if key in d:conn().execute('UPDATE settings SET value=? WHERE key=?',(str(d[key])[:200],key))
    conn().commit();return settings.__wrapped__(u)
@app.get('/api/alerts')
@login_required
def alerts(u):return jsonify(rows("SELECT id,name,age,gender,condition FROM patients WHERE status='Critical'")) if staff(u) else error('Staff access only',403)
@app.post('/api/reset')
@login_required
def reset(u):return error('Database reset disabled to protect records',403)
@app.get('/api/stats')
@login_required
def stats(u):return jsonify(patients=len(rows('SELECT id FROM patients')) if staff(u) else 1)

def cli():
    import getpass
    init()
    if len(sys.argv)>1 and sys.argv[1] in ('create-admin','create-doctor'):
        role='admin' if sys.argv[1]=='create-admin' else 'doctor'
        if role=='doctor' and not one("SELECT id FROM users WHERE role='admin' LIMIT 1"):
            print('Create an admin first');return
        username=input('Username: ').strip().lower();name=input('Full name: ').strip();pw=getpass.getpass('Password (at least 6 characters with a digit): ')
        if not re.fullmatch('[a-z0-9_]{3,30}',username) or not name or len(pw)<6 or not re.search(r'\d',pw):print('Invalid username or password');return
        try:conn().execute('INSERT INTO users(username,password,role,name) VALUES (?,?,?,?)',(username,generate_password_hash(pw),role,name));conn().commit();print(role.title()+' account created successfully.')
        except sqlite3.IntegrityError:print('Username already exists')
    else:
        print('Open http://127.0.0.1:5000');app.run(host='127.0.0.1',port=5000,debug=False)
if __name__=='__main__':
    with app.app_context():cli()
