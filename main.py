from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = "tavenziq-development-secret-key"


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
        message = request.form.get("message", "").strip()

        if not name or not phone or not message:
            flash("Please fill in your name, phone number and message.", "error")
            return redirect(url_for("contact"))

        print("NEW CUSTOMER ENQUIRY")
        print("Name:", name)
        print("Email:", email)
        print("Phone:", phone)
        print("Message:", message)

        flash("Thank you! Your enquiry has been received.", "success")
        return redirect(url_for("contact"))

    return render_template("contact.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
