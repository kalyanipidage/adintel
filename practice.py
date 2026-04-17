import sqlite3

conn = sqlite3.connect("app.db")
conn.execute("UPDATE users SET is_admin=1 WHERE username='admin'")
conn.commit()
conn.close()