"""
Quick script to create the border_screening database if it doesn't exist.
"""
import psycopg2

conn = psycopg2.connect(host='localhost', user='postgres', password='naishal@7', dbname='postgres')
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT datname FROM pg_database WHERE datname = 'border_screening'")
exists = cur.fetchone()

if exists:
    print("✅ Database 'border_screening' already exists.")
else:
    cur.execute("CREATE DATABASE border_screening")
    print("✅ Database 'border_screening' created successfully.")

cur.close()
conn.close()
