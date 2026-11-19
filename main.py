
import os
from functools import wraps

import cloudinary
from cloudinary import uploader

from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash

from database import get_db_connection, init_db

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "development-only-change-this-secret-key"
)

# Cloudinary configuration
cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True
)

init_db()


@app.context_processor
def inject_site_branding():
    connection = get_db_connection()

    try:
        settings = {
            row["setting_key"]: row["setting_value"]
            for row in connection.execute(
                """
                SELECT setting_key, setting_value
                FROM site_settings
                """
            ).fetchall()
        }

    finally:
        connection.close()

    return {
        "site_logo": settings.get("site_logo"),
        "site_favicon": settings.get("site_favicon")
    }

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
    connection = get_db_connection()

    try:
        featured_media = connection.execute(
            """
            SELECT * FROM media
            WHERE is_published = 1
            ORDER BY created_at DESC, id DESC
            LIMIT 6
            """
        ).fetchall()
    finally:
        connection.close()

    return render_template(
        "index.html",
        featured_media=featured_media
    )

@app.route("/gallery")
def gallery():
    categories = [
        "Events & Entertainment",
        "Cereals & General Supplies",
        "Tours & Travel",
        "Company Branding"
    ]

    selected_category = request.args.get("category", "All").strip()

    if selected_category not in categories and selected_category != "All":
        selected_category = "All"

    connection = get_db_connection()

    try:
        if selected_category == "All":
            media_items = connection.execute(
                """
                SELECT * FROM media
                WHERE is_published = 1
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        else:
            media_items = connection.execute(
                """
                SELECT * FROM media
                WHERE is_published = 1 AND category = ?
                ORDER BY created_at DESC, id DESC
                """,
                (selected_category,)
            ).fetchall()
    finally:
        connection.close()

    return render_template(
        "gallery.html",
        media_items=media_items,
        categories=categories,
        selected_category=selected_category
    )

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

# Maximum upload size: 60 MB
app.config["MAX_CONTENT_LENGTH"] = 60 * 1024 * 1024

ALLOWED_MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".webp", ".gif",
    ".mp4", ".mov", ".webm"
}

ALLOWED_MEDIA_CATEGORIES = [
    "Events & Entertainment",
    "Cereals & General Supplies",
    "Tours & Travel",
    "Company Branding"
]


@app.route("/admin/media", methods=["GET", "POST"])
@admin_required
def admin_media():

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        caption = request.form.get("caption", "").strip()
        category = request.form.get("category", "").strip()
        is_published = 1 if request.form.get("is_published") == "1" else 0
        uploaded_file = request.files.get("media_file")

        if not title or category not in ALLOWED_MEDIA_CATEGORIES:
            flash("Please provide a title and select a valid category.", "error")
            return redirect(url_for("admin_media"))

        if not uploaded_file or not uploaded_file.filename:
            flash("Please select a photo or video to upload.", "error")
            return redirect(url_for("admin_media"))

        extension = os.path.splitext(uploaded_file.filename)[1].lower()

        if extension not in ALLOWED_MEDIA_EXTENSIONS:
            flash("Unsupported file type. Please upload an image or video.", "error")
            return redirect(url_for("admin_media"))

        media_type = "video" if extension in {
            ".mp4", ".mov", ".webm"
        } else "image"

        try:
            result = uploader.upload(
                uploaded_file,
                resource_type=media_type,
                folder="tavenziq-enterprises/media",
                use_filename=True,
                unique_filename=True,
                overwrite=False
            )

            connection = get_db_connection()

            try:
                connection.execute(
                    """
                    INSERT INTO media (
                        title,
                        caption,
                        category,
                        media_type,
                        cloudinary_public_id,
                        media_url,
                        is_published
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        title,
                        caption,
                        category,
                        media_type,
                        result["public_id"],
                        result["secure_url"],
                        is_published
                    )
                )

                connection.commit()

            finally:
                connection.close()

            flash("Media uploaded successfully.", "success")

        except Exception:
            app.logger.exception("Media upload failed.")
            flash(
                "Upload failed. Please check the file and try again.",
                "error"
            )

        return redirect(url_for("admin_media"))

    connection = get_db_connection()

    try:
        media_items = connection.execute(
            """
            SELECT * FROM media
            ORDER BY created_at DESC, id DESC
            """
        ).fetchall()
    finally:
        connection.close()

    return render_template(
        "admin_media.html",
        media_items=media_items,
        categories=ALLOWED_MEDIA_CATEGORIES
    )


@app.route("/admin/media/<int:media_id>/visibility", methods=["POST"])
@admin_required
def toggle_media_visibility(media_id):

    connection = get_db_connection()

    try:
        media = connection.execute(
            "SELECT * FROM media WHERE id = ?",
            (media_id,)
        ).fetchone()

        if not media:
            flash("Media item not found.", "error")
            return redirect(url_for("admin_media"))

        new_status = 0 if media["is_published"] else 1

        connection.execute(
            "UPDATE media SET is_published = ? WHERE id = ?",
            (new_status, media_id)
        )

        connection.commit()

        flash("Media publication status updated.", "success")

    finally:
        connection.close()

    return redirect(url_for("admin_media"))


@app.route("/admin/media/<int:media_id>/delete", methods=["POST"])
@admin_required
def delete_media(media_id):

    connection = get_db_connection()

    try:
        media = connection.execute(
            "SELECT * FROM media WHERE id = ?",
            (media_id,)
        ).fetchone()

        if not media:
            flash("Media item not found.", "error")
            return redirect(url_for("admin_media"))

        result = uploader.destroy(
            media["cloudinary_public_id"],
            resource_type=media["media_type"],
            invalidate=True
        )

        if result.get("result") not in ["ok", "not found"]:
            flash("Cloudinary could not delete this file.", "error")
            return redirect(url_for("admin_media"))

        connection.execute(
            "DELETE FROM media WHERE id = ?",
            (media_id,)
        )

        connection.commit()

        flash("Media item deleted successfully.", "success")

    except Exception:
        app.logger.exception("Media deletion failed.")
        flash("Unable to delete this media item.", "error")

    finally:
        connection.close()

    return redirect(url_for("admin_media"))

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

# WEBSITE BRANDING MANAGER

ALLOWED_BRANDING_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".ico"
}


@app.route("/admin/branding", methods=["GET", "POST"])
@admin_required
def admin_branding():

    if request.method == "POST":

        asset_type = request.form.get("asset_type", "").strip()

        if asset_type not in ["logo", "favicon"]:
            flash("Invalid branding image selection.", "error")
            return redirect(url_for("admin_branding"))

        uploaded_file = request.files.get("branding_file")

        if not uploaded_file or not uploaded_file.filename:
            flash("Please select an image to upload.", "error")
            return redirect(url_for("admin_branding"))

        extension = os.path.splitext(uploaded_file.filename)[1].lower()

        if extension not in ALLOWED_BRANDING_EXTENSIONS:
            flash("Please upload PNG, JPG, JPEG, WEBP or ICO.", "error")
            return redirect(url_for("admin_branding"))

        try:
            # Upload the new image to Cloudinary.
            result = uploader.upload(
                uploaded_file,
                resource_type="image",
                folder="tavenziq-enterprises/branding",
                use_filename=True,
                unique_filename=True,
                overwrite=False
            )

            setting_key = (
                "site_logo" if asset_type == "logo"
                else "site_favicon"
            )

            connection = get_db_connection()

            try:
                old_setting = connection.execute(
                    """
                    SELECT setting_value
                    FROM site_settings
                    WHERE setting_key = ?
                    """,
                    (setting_key,)
                ).fetchone()

                connection.execute(
                    """
                    INSERT INTO site_settings (
                        setting_key, setting_value
                    )
                    VALUES (?, ?)
                    ON CONFLICT(setting_key)
                    DO UPDATE SET setting_value = excluded.setting_value
                    """,
                    (setting_key, result["secure_url"])
                )

                connection.commit()

            finally:
                connection.close()

            # Delete the previous Cloudinary image after saving the new one.
            if old_setting and old_setting["setting_value"]:
                old_url = old_setting["setting_value"]

                # Only delete previous assets belonging to this branding folder.
                if "/tavenziq-enterprises/branding/" in old_url:
                    try:
                        old_public_id = old_url.split("/upload/")[-1]
                        old_public_id = old_public_id.split("/")[-1]
                        old_public_id = os.path.splitext(old_public_id)[0]

                        uploader.destroy(
                            "tavenziq-enterprises/branding/" + old_public_id,
                            resource_type="image",
                            invalidate=True
                        )
                    except Exception:
                        app.logger.exception(
                            "Could not delete previous branding image."
                        )

            flash("Website branding image updated successfully.", "success")

        except Exception:
            app.logger.exception("Branding image upload failed.")
            flash("Unable to upload the branding image. Please try again.", "error")

        return redirect(url_for("admin_branding"))

    connection = get_db_connection()

    try:
        settings = connection.execute(
            """
            SELECT setting_key, setting_value
            FROM site_settings
            WHERE setting_key IN ('site_logo', 'site_favicon')
            """
        ).fetchall()

        branding = {
            row["setting_key"]: row["setting_value"]
            for row in settings
        }

    finally:
        connection.close()

    return render_template(
        "admin_branding.html",
        branding=branding
    )

@app.route("/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("admin_login"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
