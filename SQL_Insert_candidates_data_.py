import os
import pyodbc
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

    # Create table (if not exists - you might want to add a check or drop table before creating)
    cursor.execute('''
    IF OBJECT_ID('dbo.candidates', 'U') IS NULL
    BEGIN
        CREATE TABLE candidates (
            candidate_id INT PRIMARY KEY IDENTITY(1,1),
            name NVARCHAR(100),
            status NVARCHAR(50),
            email NVARCHAR(100),
            location NVARCHAR(100)
        )
    END
    ''')
    conn.commit()

    # List of 10 candidate records (name, status, email, location)
    candidates_data = [        
        ('Bob Smith', 'Applied', 'bob.smith@example.com', 'Vancouver'),
        ('Charlie Lee', 'Interviewed', 'charlie.lee@example.com', 'Montreal'),
        ('Diana Prince', 'Hired', 'diana.prince@example.com', 'Calgary'),
        ('Ethan Hunt', 'Applied', 'ethan.hunt@example.com', 'Ottawa'),
        ('Fiona Gallagher', 'Rejected', 'fiona.gallagher@example.com', 'Halifax'),
        ('George Martin', 'Interviewed', 'george.martin@example.com', 'Edmonton'),
        ('Hannah Brown', 'Applied', 'hannah.brown@example.com', 'Winnipeg'),
        ('Ian Curtis', 'Hired', 'ian.curtis@example.com', 'Quebec City'),
        ('Jessica Jones', 'Interviewed', 'jessica.jones@example.com', 'Victoria'),
    ]

    # Insert multiple rows using executemany
    insert_query = '''
    INSERT INTO candidates (name, status, email, location)
    VALUES (?, ?, ?, ?)
    '''
    cursor.executemany(insert_query, candidates_data)
    conn.commit()

    print("Inserted 10 candidates successfully.")

    cursor.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")

