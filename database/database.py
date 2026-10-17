import sqlite3
import hashlib
import os
DB_PATH = os.path.join(os.path.dirname(__file__),"BD1.db")
def _init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users
                      (id INTEGER PRIMARY KEY, name TEXT, email TEXT)''')
    conn.commit()
    cursor.close()
    conn.close()
_init_db()



