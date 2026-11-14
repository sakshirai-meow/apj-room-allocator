import csv
import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

connection = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", 3306)),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    ssl_ca=os.getenv("DB_SSL_CA"),
    ssl_verify_cert=True,
    ssl_verify_identity=True
)

cursor = connection.cursor()

with open("timetable.csv", "r", encoding = "utf-8") as file:

    reader =  csv.DictReader(file)

    records = []

    for row in reader:

        records.append((
            row["room"],
            row["academic_year"],
            row["day"],
            row["slot"],
            row["class_info"] or None
        ))

query = """
INSERT INTO timetable
(room, academic_year, day, slot, class_info)
VALUES (%s ,%s, %s, %s, %s)
"""

try:
    cursor.executemany(query, records)
    connection.commit()

    print(len(records), "records inserted successfully!")

except mysql.connector.Error as err:

    connection.rollback()
    print("Error:", err)

finally:
    cursor.close()
    connection.close()