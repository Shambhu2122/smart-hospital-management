Smart Hospital - local educational demo (do not use real patient data).

Windows CMD:
1. Open this folder in CMD
2. python -m venv .venv
3. .venv\Scripts\python.exe -m pip install -r requirements.txt
4. .venv\Scripts\python.exe server.py create-admin
5. Optional: .venv\Scripts\python.exe server.py create-doctor
6. .venv\Scripts\python.exe server.py
7. Open http://127.0.0.1:5000

Patients use Sign Up; doctor/admin use created accounts. Password min 6 chars including a digit. Do not share hospital.db. Keep server local. This is a classroom prototype, not production-grade healthcare software.
