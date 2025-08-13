import os
import pyodbc
import uuid
from dotenv import load_dotenv

load_dotenv()

server = os.getenv("server").strip()
database = os.getenv("database").strip()
sql_username = os.getenv("sql_username").strip()
password = os.getenv("password").strip()
driver = os.getenv("driver").strip()

print(f"Server: {server}")
print(f"Database: {database}")
print(f"Username: {sql_username}")
print(f"Driver: {driver}")
print(f"Password length: {len(password)}")

connection_string = f"Driver={driver};Server={server};Database={database};Uid={sql_username};Pwd={password};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"

try:
    conn = pyodbc.connect(connection_string)
    cursor = conn.cursor()
    print("Connection successful!")

    # Drop and recreate table with candidate_id as NVARCHAR primary key (string)
    cursor.execute('''
    IF OBJECT_ID('dbo.candidates', 'U') IS NOT NULL
        DROP TABLE dbo.candidates;

    CREATE TABLE candidates (
        candidate_id NVARCHAR(50) PRIMARY KEY,
        name NVARCHAR(100),
        status NVARCHAR(50),
        email NVARCHAR(100),
        location NVARCHAR(100)
    )
    ''')
    conn.commit()

    # Delete all rows in candidates table
    cursor.execute("DELETE FROM candidates")
    conn.commit()
    print("Deleted all rows from candidates table.")

    # Prepare candidate data with generated string candidate_ids
    candidates_data = [
        (str(uuid.uuid4()), 'Sumit Kumar', 'Applied', 'ssumitk14@gmail.com', 'India'),
        (str(uuid.uuid4()), 'Uponika Roy', 'Applied', 'uponika@gmail.com', 'London'),
    ]

    insert_query = '''
    INSERT INTO candidates (candidate_id, name, status, email, location)
    VALUES (?, ?, ?, ?, ?)
    '''

    cursor.executemany(insert_query, candidates_data)
    conn.commit()

    print("Inserted candidates with string candidate_id successfully.")

    cursor.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")

