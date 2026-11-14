from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
import mysql.connector
from class_management import check_availability, book_slot, cancel_booking, get_confirmed_bookings, cancel_class, get_room_schedule, get_cancelled_classes, reinstate_class
from datetime import date, timedelta
import generate_weekly_schedules
import os
from dotenv import load_dotenv

load_dotenv()

from flask import send_from_directory

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

@app.route("/style.css")
def serve_css():
    return send_from_directory("public", "style.css")


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

class User(UserMixin):

    def __init__(self, user_id, username, password_hash):
        self.id = user_id
        self.username = username
        self.password_hash = password_hash

def get_booking_date_limits():

    today = date.today()

    this_monday = today - timedelta(days=today.weekday())

    next_friday = this_monday + timedelta(days=11)

    return this_monday, next_friday



@login_manager.user_loader
def load_user(user_id):

    connection = mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME")
    )

    cursor = connection.cursor()

    query = """
    SELECT user_id, username, password_hash
    FROM users
    WHERE user_id = %s
    """

    cursor.execute(query, (user_id,))
    record = cursor.fetchone()

    cursor.close()
    connection.close()

    if record:
        return User(record[0], record[1], record[2])

    return None


@app.route("/")
def home():

    return render_template("index.html")

@app.route("/login", methods=["GET","POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )

        cursor = connection.cursor()

        query = """
        SELECT user_id, username, password_hash
        FROM users
        WHERE username = %s
        """
        cursor.execute(query, (username,))
        record = cursor.fetchone()

        cursor.close()
        connection.close()

        if record and check_password_hash(record[2], password):

            user = User(record[0], record[1], record[2])
            login_user(user)
            flash("Login successful! Welcome, " + user.username + ".")

            return redirect(url_for("home"))

        else:
            flash("Invalid username or password.")

    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():

    logout_user()
    return redirect(url_for("home"))


@app.route("/timetable", methods=["GET", "POST"])                                 
def timetable():

    if request.method == "POST":

        room = request.form["room"]

        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )

        cursor = connection.cursor()

        query = """
        SELECT day, slot, class_info
        FROM timetable
        WHERE room = %s
        ORDER BY FIELD(day, 'Mon', 'Tue', 'Wed', 'Thu', 'Fri'), slot
        """
        cursor.execute(query, (room,))
        records = cursor.fetchall()

        days = ["Mon", "Tue", "Wed", "Thu", "Fri"]

        timetable_grid = {}

        for record in records:
            day = record[0]
            slot = record[1]
            class_info = record[2]

            if slot not in timetable_grid:
                timetable_grid[slot] = {}

            timetable_grid[slot][day] = class_info or "Free"

        slots = sorted(
            timetable_grid.keys(),
            key=lambda x: int(x.split()[0][1:])
        )

        cursor.close()
        connection.close()

        return render_template(
            "timetable.html",
            records=records,
            selected_room=room,
            days=days,
            slots=slots,
            timetable_grid=timetable_grid
        )

    return render_template("timetable.html")


    

@app.route("/availability", methods=["GET","POST"])
def availability():

    if request.method == "POST":

        availability_date = request.form["date"]
        slot = request.form["slot"]

        available_rooms = check_availability(availability_date, slot)

        return render_template(
            "availability.html",
            available_rooms=available_rooms,
            selected_date=availability_date,
            selected_slot=slot
        )

    return render_template("availability.html")


@app.route("/book", methods=["GET", "POST"])
@login_required
def book():

    min_date, max_date = get_booking_date_limits()

    if request.method == "POST":

        room = request.form["room"]
        booking_date = request.form["date"]
        slot = request.form["slot"]
        purpose = request.form["purpose"]

        selected_date = date.fromisoformat(booking_date)

        if not min_date <= selected_date <= max_date:

            flash("You can only book dates within this week's and next week's schedule.")
            return redirect(url_for("book"))

        booker_name = current_user.username

        success, message = book_slot(
            room, booking_date, slot, purpose, booker_name
        )

        flash(message)
        return redirect(url_for("book"))

    return render_template(
        "book.html",
        min_date=min_date.isoformat(),
        max_date=max_date.isoformat()
    )

@app.route("/cancel-booking")
@login_required
def cancel_booking_page():

    bookings = get_confirmed_bookings()

    return render_template(
        "cancel_booking.html",
        bookings=bookings
    )

@app.route("/cancel-booking-action", methods=["POST"])
@login_required
def cancel_booking_action():

    room = request.form["room"]
    booking_date = request.form["date"]
    slot = request.form["slot"]

    success, message = cancel_booking(room, booking_date, slot)

    flash(message)

    return redirect(url_for("cancel_booking_page"))


@app.route("/cancel-class")
@login_required
def cancel_class_page():
    min_date, max_date = get_booking_date_limits()

    room = request.args.get("room")
    selected_date = request.args.get("date")

    classes = []

    if room and selected_date:
        selected_date_obj = date.fromisoformat(selected_date)

        if not min_date <= selected_date_obj <= max_date:
            flash("Please select a date within the current and next week's schedule.")
            return redirect(url_for("cancel_class_page"))

        schedule = get_room_schedule(room, selected_date)
        classes = [row for row in schedule if row[2] == "class"]

    return render_template(
        "cancel_class.html",
        classes=classes,
        room=room,
        selected_date=selected_date,
        min_date=min_date.isoformat(),
        max_date=max_date.isoformat()
    )

@app.route("/cancel-class-action", methods=["POST"])
@login_required
def cancel_class_action():
    room = request.form["room"]
    cancellation_date = request.form["date"]
    slot = request.form["slot"]

    success, message = cancel_class(room, cancellation_date, slot)

    flash(message)

    return redirect(url_for(
        "cancel_class_page",
        room=room,
        date=cancellation_date
    ))


@app.route("/reinstate-class")
@login_required
def reinstate_class_page():

    min_date, max_date = get_booking_date_limits()

    room = request.args.get("room")
    selected_date = request.args.get("date")

    cancelled_classes = []

    if room and selected_date:
        selected_date_obj = date.fromisoformat(selected_date)

        if not min_date <= selected_date_obj <= max_date:
            flash("Please select a date within the current and next week's schedule.")
            return redirect(url_for("reinstate_class_page"))

        cancelled_classes = get_cancelled_classes(
            room, selected_date_obj
        )

    return render_template(
        "reinstate_class.html",
        cancelled_classes=cancelled_classes,
        room=room,
        selected_date=selected_date,
        min_date=min_date.isoformat(),
        max_date=max_date.isoformat()
    )

@app.route("/reinstate-class-action", methods=["POST"])
@login_required
def reinstate_class_action():

    room = request.form["room"]
    reinstatement_date = date.fromisoformat(request.form["date"])
    slot = request.form["slot"]

    success, message = reinstate_class(room, reinstatement_date, slot)

    flash(message)

    return redirect(url_for(
        "reinstate_class_page",
        room=room,
        date=reinstatement_date.isoformat()
    ))

if __name__ == "__main__":

    generate_weekly_schedules.main()
    app.run(debug=False, use_reloader=False)