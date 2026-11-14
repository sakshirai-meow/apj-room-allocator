import mysql.connector
from werkzeug.security import generate_password_hash
import os
from dotenv import load_dotenv

load_dotenv()

connection = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME")
)

cursor = connection.cursor()

while True:

    print("\n--- Create CR Account ---")

    username = input("Enter username: ")
    password = input("Enter password: ")

    password_hash = generate_password_hash(password)

    query = """
    INSERT INTO users (username, password_hash)
    VALUES (%s, %s)
    """

    try:
        cursor.execute(query, (username, password_hash))
        connection.commit()

        print("CR account created successfully!")

    except mysql.connector.Error as error:
        connection.rollback()
        print("Error:", error)

    choice = input("\nDo you want to create another account? (yes/no): ").lower()

    if choice == "no":
        break

cursor.close()
connection.close()

print("\nAccount creation process ended.")