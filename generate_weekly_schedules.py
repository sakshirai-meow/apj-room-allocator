import mysql.connector
from datetime import date, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

def generate_weekly_schedule(week_start):

    days = ["Mon", "Tue", "Wed", "Thu", "Fri"]

    records = []
    i = 0

    
    for day in days:

        current_date = week_start + timedelta(days = i)
        cursor.execute("""
            SELECT room, slot, class_info
            FROM timetable
            WHERE day = %s
        """, (day,))

        timetable_rows = cursor.fetchall()

        for room, slot, class_info in timetable_rows:

            status = "available" if class_info is None else "class"

            records.append((
                room,
                current_date,
                slot,
                class_info,
                status,
                None,
                None
            ))

        i += 1

    query = """
        INSERT IGNORE INTO weekly_schedule
        (room, date, slot, class_info, status, 
        booked_by, booking_purpose)
        VALUES(%s, %s, %s, %s, %s, %s, %s)
    """

    cursor.executemany(query, records)

    print(len(records), "weekly schedule records generated!")

def refresh_weekly_schedule():

    today = date.today()
    current_monday = today - timedelta(days = today.weekday())
    next_monday = current_monday + timedelta(days = 7)
    last_friday = next_monday + timedelta(days = 4)

    cursor.execute("""
        DELETE FROM weekly_schedule
        WHERE date <%s OR date >%s
    """, (current_monday, last_friday))

    generate_weekly_schedule(current_monday)
    generate_weekly_schedule(next_monday)

    cursor.execute("""
        UPDATE weekly_schedule ws
        JOIN timetable t
        ON ws.room = t.room
        AND ws.slot = t.slot
        AND t.day = CASE DAYOFWEEK(ws.date)
            WHEN 2 THEN 'Mon'
            WHEN 3 THEN 'Tue'
            WHEN 4 THEN 'Wed'
            WHEN 5 THEN 'Thu'
            WHEN 6 THEN 'Fri'
        END

        SET ws.class_info = t.class_info,
            ws.status = CASE
                WHEN t.class_info IS NULL OR t.class_info = ''
                THEN 'available'
                ELSE 'class'
            END,
            ws.booked_by = NULL,
            ws.booking_purpose = NULL

        WHERE ws.date BETWEEN %s AND %s
    """, (current_monday, last_friday))

    apply_class_cancellations(current_monday, last_friday)
    apply_confirmed_bookings(current_monday, last_friday)


def apply_class_cancellations(current_monday, last_friday):

    cursor.execute("""
        SELECT cancellation_id, room, date, slot, status
        FROM class_cancellations
        WHERE date BETWEEN %s AND %s
        ORDER BY cancellation_id
    """, (current_monday, last_friday))

    cancellations = cursor.fetchall()
    latest_cancellations = {}

    for cancellation_id, room, cancellation_date, slot, status in cancellations:

        key = (room, cancellation_date, slot)
        latest_cancellations[key] = status

    for (room, cancellation_date, slot), status in latest_cancellations.items():

        if status == "cancelled":

            cursor.execute("""
                UPDATE weekly_schedule
                SET status = 'available',
                    class_info = NULL
                WHERE room = %s AND date = %s AND slot = %s
            """, (room, cancellation_date, slot))

        elif status == "reinstated":

            day_names = ["Mon", "Tue", "Wed", "Thu", "Fri"]
            day = day_names[cancellation_date.weekday()]

            cursor.execute("""
                SELECT class_info
                FROM timetable
                WHERE room = %s
                AND slot = %s
                AND day = %s
            """, (room, slot, day))

            original_class = cursor.fetchone()

            if original_class is not None:

                cursor.execute("""
                    UPDATE weekly_schedule
                    SET status = 'class',
                        class_info = %s,
                        booked_by = NULL,
                        booking_purpose = NULL
                    WHERE room = %s AND date = %s AND slot = %s
                """, (
                    original_class[0],
                    room,
                    cancellation_date,
                    slot
                ))


def apply_confirmed_bookings(current_monday, last_friday):

    cursor.execute("""
        SELECT booking_id, room, date, slot, purpose, booked_by
        FROM bookings
        WHERE date BETWEEN %s AND %s
        AND status = 'confirmed'
        ORDER BY booking_id DESC
    """, (current_monday, last_friday))

    bookings = cursor.fetchall()

    for booking_id, room, booking_date, slot, purpose, booked_by in bookings:

        cursor.execute("""
            UPDATE weekly_schedule
            SET status = 'booked',
                booked_by = %s,
                booking_purpose = %s
            WHERE room = %s
            AND date = %s
            AND slot = %s
            AND status = 'available'
        """, (
            booked_by,
            purpose,
            room,
            booking_date,
            slot
        ))

def main():

    global connection, cursor

    try:
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

        refresh_weekly_schedule()
        connection.commit()

        print("Weekly schedule refreshed successfully!")

    except mysql.connector.Error as err:

        if connection and connection.is_connected():
            connection.rollback()
        print("Error:", err)

    finally:

        if cursor:
            cursor.close()

        if connection and connection.is_connected():
            connection.close()


if __name__ == "__main__":
    main()