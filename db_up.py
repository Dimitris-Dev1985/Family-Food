import sqlite3

DB = "family_food_app.db"

conn = sqlite3.connect(DB)
c = conn.cursor()


c.execute("ALTER TABLE users ADD COLUMN onboarding_done INTEGER DEFAULT 0;")


print("ok")

conn.commit()
conn.close()
