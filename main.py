
import os
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash

from database import get_db_connection, init_db

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "development-only-change-this-secret-key"
)

init_db()


def admin_required(view_function):
    @wraps(view_function)
    def wrapped_view(*args, **kwargs):
        if "admin_id" not in session:
            flash("Please log in to access the admin area.", "error")
            return redirect(url_for("admin_login"))
        return view_function(*args, **kwargs)
    return wrapped_view


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/services")
def services():
    return render_template("services.html")


@app.route("/events")
def events():
    return render_template("events.html")


@app.route("/supplies")
def supplies():
    return render_template("supplies.html")


@app.route("/travel")
def travel():
    return render_template("travel.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        service = request.form.get("service", "").strip()
        message = request.form.get("message", "").strip()

        allowed_services = [
            "Events & Entertainment",
            "Cereals & General Supplies",
            "Tours & Travel",
            "Other Enquiry"
        ]

        if not name or not phone or not message or service not in allowed_services:
            flash("Please complete all required fields correctly.", "error")
            return redirect(url_for("contact"))

        connection = get_db_connection()
        try:
            connection.execute(
                """
                INSERT INTO enquiries (name, email, phone, service, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, email, phone, service, message)
            )
            connection.commit()
        finally:
            connection.close()

        flash("Thank you! Your enquiry has been received.", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html")


@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if "admin_id" in session:
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        connection = get_db_connection()
        try:
            admin = connection.execute(
                "SELECT * FROM admins WHERE username = ?",
                (username,)
            ).fetchone()
        finally:
            connection.close()

        if admin and check_password_hash(admin["password_hash"], password):
            session.clear()
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            flash("Welcome to TAVENZIQ administration.", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Incorrect username or password.", "error")

    return render_template("admin_login.html")



@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    service_filter = request.args.get("service", "").strip()

    connection = get_db_connection()

    try:
        conditions = []
        parameters = []

        if search:
            conditions.append("""
                (
                    name LIKE ?
                    OR email LIKE ?
                    OR phone LIKE ?
                    OR message LIKE ?
                )
            """)
            search_value = f"%{search}%"
            parameters.extend([search_value] * 4)

        if status_filter in ["New", "In Progress", "Completed"]:
            conditions.append("status = ?")
            parameters.append(status_filter)

        allowed_services = [
            "Events & Entertainment",
            "Cereals & General Supplies",
            "Tours & Travel",
            "Other Enquiry"
        ]

        if service_filter in allowed_services:
            conditions.append("service = ?")
            parameters.append(service_filter)

        sql = "SELECT * FROM enquiries"

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY created_at DESC, id DESC"

        enquiries = connection.execute(
            sql, parameters
        ).fetchall()

        total = connection.execute(
            "SELECT COUNT(*) FROM enquiries"
        ).fetchone()[0]

        new_count = connection.execute(
            "SELECT COUNT(*) FROM enquiries WHERE status = 'New'"
        ).fetchone()[0]

        progress_count = connection.execute(
            "SELECT COUNT(*) FROM enquiries WHERE status = 'In Progress'"
        ).fetchone()[0]

        completed_count = connection.execute(
            "SELECT COUNT(*) FROM enquiries WHERE status = 'Completed'"
        ).fetchone()[0]

    finally:
        connection.close()

    return render_template(
        "admin_dashboard.html",
        enquiries=enquiries,
        total=total,
        new_count=new_count,
        progress_count=progress_count,
        completed_count=completed_count,
        search=search,
        status_filter=status_filter,
        service_filter=service_filter
    )

@app.route("/admin/enquiry/<int:enquiry_id>/status", methods=["POST"])
@admin_required
def update_enquiry_status(enquiry_id):
    status = request.form.get("status", "").strip()

    if status not in ["New", "In Progress", "Completed"]:
        flash("Invalid enquiry status.", "error")
        return redirect(url_for("admin_dashboard"))

    connection = get_db_connection()
    try:
        result = connection.execute(
            "UPDATE enquiries SET status = ? WHERE id = ?",
            (status, enquiry_id)
        )
        connection.commit()

        if result.rowcount == 0:
            flash("Enquiry not found.", "error")
        else:
            flash("Enquiry status updated successfully.", "success")
    finally:
        connection.close()

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/enquiry/<int:enquiry_id>/delete", methods=["POST"])
@admin_required
def delete_enquiry(enquiry_id):
    connection = get_db_connection()

    try:
        result = connection.execute(
            "DELETE FROM enquiries WHERE id = ?",
            (enquiry_id,)
        )
        connection.commit()

        if result.rowcount == 0:
            flash("Enquiry not found.", "error")
        else:
            flash("Enquiry deleted successfully.", "success")

    finally:
        connection.close()

    return redirect(url_for("admin_dashboard"))

@app.route("/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("admin_login"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
