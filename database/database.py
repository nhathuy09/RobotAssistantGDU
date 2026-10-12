import sqlite3
import hashlib
import os
DB_PATH = os.path.join(os.path.dirname(__file__),"BD1.db")
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
print("Database connected successfully.")
cursor.close()
