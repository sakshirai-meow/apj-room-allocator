import mysql.connector
from datetime import date, timedelta
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

# class management

def cancel_class(room, cancellation_date, slot):

    try:
        cursor.execute("""
            SELECT class_info, status 
            FROM weekly_schedule 
            WHERE room = %s
            AND date = %s 
            AND slot = %s
            FOR UPDATe
        """, (room, cancellation_date, slot))

        result = cursor.fetchone()

        if result is None:

            connection.rollback()
            return False, "Slot not found in weekly schedule."

        class_info, status = result

        if status != "class":

            connection.rollback()
            return False, "There is no scheduled class in the chosen slot."

        cursor.execute("""
            INSERT INTO class_cancellations
            (room, date, slot, class_info, status)
            VALUES(%s, %s, %s, %s, 'cancelled')
        """, (room, cancellation_date, slot, class_info))

        cursor.execute("""
            UPDATE weekly_schedule
            SET status = 'available',
                class_info = NULL
            WHERE room = %s
            AND date = %s
            AND slot = %s
        """, (room, cancellation_date, slot))

        connection.commit()

        return True, "Class cancelled successfully!"

    except mysql.connector.Error as err:

        connection.rollback()
        return False, "Database error: " + str(err)

def reinstate_class(room, reinstatement_date, slot):

    try:

        cursor.execute("""
            SELECT status
            FROM weekly_schedule
            WHERE room = %s
            AND date = %s
            AND slot = %s
            FOR UPDATE
        """, (room, reinstatement_date, slot))

        result = cursor.fetchone()

        if result is None:

            connection.rollback()
            return False, "Slot not found in the weekly schedule!"

        status = result[0] 
    
        if reinstatement_date.weekday() >= 5:
                    
            connection.rollback()
            return False, "Classes cannot be reinstated on weekends!"

        cursor.execute("""
            SELECT status
            FROM class_cancellations
            WHERE room = %s
            AND date = %s
            AND slot = %s
            ORDER BY cancellation_id DESC
            LIMIT 1
        """, (room, reinstatement_date, slot))

        latest_event = cursor.fetchone()

        if latest_event is None or latest_event[0] != "cancelled":

            connection.rollback()
            return False, "This class is not currently cancelled!"
        
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri"]
        day = day_names[reinstatement_date.weekday()]
        
        cursor.execute("""
            SELECT class_info
            FROM timetable
            WHERE room = %s
            AND day = %s
            AND slot = %s
        """, (room, day, slot))

        og_class = cursor.fetchone()

        if og_class is None or og_class[0] is None or og_class[0] == "":

            connection.rollback()
            return False, "Original class information not found!"

        class_info = og_class[0]

        if status == "available":
            pass

        elif status == "booked":

            cursor.execute("""
                UPDATE bookings
                SET status = 'cancelled'
                WHERE room = %s
                AND date = %s
                AND slot = %s
                AND status = 'confirmed'
            """, (room, reinstatement_date, slot))

            if cursor.rowcount == 0:
                raise Exception("No confirmed booking found for this booked slot!")

        else:
            connection.rollback()
            return False, "Slot is not available for reinstatement!"

        cursor.execute("""
            INSERT INTO class_cancellations
            (room, date, slot, class_info, status)
            VALUES(%s, %s, %s, %s, 'reinstated')
        """, (room, reinstatement_date, slot, class_info))

        cursor.execute("""
            UPDATE weekly_schedule
            SET status = 'class',
                class_info = %s,
                booked_by = NULL,
                booking_purpose = NULL
            WHERE room = %s
            AND date = %s
            AND slot = %s
        """, (class_info, room, reinstatement_date,slot))

        connection.commit()
        return True, "Class reinstated successfully!"

    except mysql.connector.Error as err:

        connection.rollback()
        return False, "Database error: " + str(err)

    except Exception as err:

        connection.rollback()
        return False, "Some Error: " + str(err)

def get_cancelled_classes(room, reinstatement_date):

    try:
        cursor.execute("""
            SELECT c.slot, c.class_info
            FROM class_cancellations c
            WHERE c.room = %s
            AND c.date = %s
            AND c.status = 'cancelled'
            AND c.cancellation_id = (
                SELECT MAX(c2.cancellation_id)
                FROM class_cancellations c2
                WHERE c2.room = c.room
                AND c2.date = c.date
                AND c2.slot = c.slot
            )
            ORDER BY c.slot
        """, (room, reinstatement_date))

        return cursor.fetchall()

    except mysql.connector.Error as err:
        print("Database error:", err)
        return []

#booking management

def book_slot(room, booking_date, slot, purpose, booker_name):

    try:
        cursor.execute("""
            SELECT status
            FROM weekly_schedule
            WHERE room = %s
            AND date = %s
            AND slot = %s
            FOR UPDATE
        """, (room, booking_date, slot))

        result = cursor.fetchone()

        if result is None:
            print("Slot not found!")
            connection.rollback()
            return False, "This slot was not found in the weekly schedule."

        status = result[0]

        if status != "available":
            connection.rollback()
            return False, "This slot is not available for booking."

        cursor.execute("""
            INSERT INTO bookings
            (room, date, slot, purpose, booked_by, status)
            VALUES (%s, %s, %s, %s, %s, 'confirmed')
        """, (room, booking_date, slot, purpose, booker_name))

        cursor.execute("""
            UPDATE weekly_schedule
            SET status = 'booked',
                booked_by = %s,
                booking_purpose = %s
            WHERE room = %s
            AND date = %s
            AND slot = %s
        """, (booker_name, purpose, room, booking_date, slot))

        connection.commit()
        return True, "Booking successful!"

    except mysql.connector.Error as err:
    
            connection.rollback()
            print("Error:", err)
    
    except Exception as err:
    
        connection.rollback()
        print("Error:", err)

def cancel_booking(room, booking_date, slot):

    try:
        cursor.execute("""
            SELECT status
            FROM weekly_schedule
            WHERE room = %s
            AND date = %s
            AND slot = %s
            FOR UPDATE
        """, (room, booking_date, slot))

        result = cursor.fetchone()

        if result is None:

            connection.rollback()
            return False, "Slot not found!"

        status = result[0]

        if status != "booked":
            connection.rollback()
            return False, "This slot does not have an active booking!"

        cursor.execute("""
            UPDATE bookings
            SET status = 'cancelled'
            WHERE room = %s
            AND date = %s
            AND slot = %s
            AND status = 'confirmed'
        """, (room, booking_date, slot))

        if cursor.rowcount == 0:
            raise Exception("No confirmed booking found for this slot!")

        cursor.execute("""
            UPDATE weekly_schedule
            SET status = 'available',
                booked_by = NULL,
                booking_purpose = NULL
            WHERE room = %s
            AND date = %s
            AND slot = %s
        """, (room, booking_date, slot))

        connection.commit()
        return True, "Booking cancelled successfully!"

    except mysql.connector.Error as err:
        connection.rollback()
        print("Error:", err)

    except Exception as err:
        connection.rollback()
        print("Error:", err)

def get_confirmed_bookings():

    try:
        cursor.execute("""
            SELECT room, date, slot, purpose, booked_by
            FROM bookings
            WHERE status = 'confirmed'
            ORDER BY date, room, slot
        """)

        records = cursor.fetchall()
        return records

    except mysql.connector.Error as err:
        print("Error:", err)
        return []


def check_availability(availability_date, slot):

    try:
        cursor.execute("""
            SELECT room
            FROM weekly_schedule
            WHERE date = %s
            AND slot = %s
            AND status = 'available'
            ORDER BY room
        """, (availability_date, slot))

        results = cursor.fetchall()

        available_rooms = []

        for row in results:

            room = row[0]
            available_rooms.append(room)

        if not available_rooms:
            print("No rooms are available for this date and slot!")

        else:
            print("Available rooms:")
            for room in available_rooms:
                print(room)

        return available_rooms

    except mysql.connector.Error as err:
        print("Error:", err)
        return []

# data retrievl

def get_room_schedule(room, schedule_date):   #for dates write like date(enter date by yyyy, mm, dd) or else will get string liek use datetime module

    try:
        cursor.execute("""
            SELECT slot, class_info, status
            FROM weekly_schedule
            WHERE room = %s
            AND date = %s
            ORDER BY slot
        """, (room, schedule_date))

        results = cursor.fetchall()

        if not results:

            print("No schedule found for this room and date!")
            return []

        print("Schedule for", room, "on", schedule_date)
        return results

    except mysql.connector.Error as err:

        print("Error:", err)
        return []

def get_booking_details(booking_date):

    try:
        cursor.execute("""
            SELECT room, slot, purpose, booked_by
            FROM bookings
            WHERE date = %s
            AND status = 'confirmed'
            ORDER BY room, slot
        """, (booking_date,))     #cuz we have to pass a tuple of values if not a comma after bookingdate it will not consider it as tuple

        results = cursor.fetchall()

        if not results:

            print("No confirmed bookings found for this date!")
            return []

        return results

    except mysql.connector.Error as err:

        print("Error:", err)
        return []

def get_available_slots(availability_date):

    try:
        cursor.execute("""
            SELECT room, slot
            FROM weekly_schedule
            WHERE date = %s
            AND status = 'available'
            ORDER BY room, slot
        """, (availability_date,))

        results = cursor.fetchall()

        if not results:

            print("No available slots found for this date!")
            return []

        return results

    except mysql.connector.Error as err:

        print("Error:", err)
        return []

