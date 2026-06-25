from datetime import datetime, timezone
from pathlib import Path

import dataset
import folium
from authlib.integrations.flask_client import OAuth
from flask import Flask
from flask import flash
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import url_for
from flask import request
from flask import session

from config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SECRET_KEY

app = Flask(__name__)
app.secret_key = SECRET_KEY

oauth = OAuth()
oauth.init_app(app)
oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url=(
        "https://accounts.google.com/.well-known/openid-configuration"
    ),
    client_kwargs={"scope": "openid email profile"},
)


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"
db = dataset.connect(f"sqlite:///{DB_PATH}")
locations = db["locations"]

MAX_EMAILS = 10
COLORS = [
    "blue",
    "red",
    "green",
    "purple",
    "orange",
    "darkred",
    "cadetblue",
    "darkgreen",
    "pink",
    "gray",
]


def add_location_to_db(email, latitude, longitude):
    """Insert a new location record for the given email."""
    locations.insert(
        {
            "email": email,
            "latitude": latitude,
            "longitude": longitude,
            "timestamp": datetime.now(timezone.utc),
        }
    )


def check_email_exists(email):
    """Return the location row for the given email, if it exists."""
    return locations.find_one(email=email)


def get_points_from_db(email):
    """Return a list of coordinate pairs for the given email."""
    return [
        (row["latitude"], row["longitude"])
        for row in db["locations"].find(email=email, order_by="timestamp")
    ]


def get_google_client():
    """Return the registered Google OAuth client."""
    return oauth.create_client("google")


@app.route("/")
def homepage():
    """Render the application homepage."""
    user = session.get("user")
    return render_template("index.html", user=user)


@app.route("/login")
def login():
    """Redirect the user to Google OAuth login."""
    google = get_google_client()
    redirect_uri = url_for("auth", _external=True)
    return google.authorize_redirect(redirect_uri)


@app.route("/auth")
def auth():
    """Handle the OAuth callback and store the user session."""
    google = get_google_client()
    token = google.authorize_access_token()
    session["user"] = token.get("userinfo")
    return redirect("/")


@app.route("/logout")
def logout():
    """Clear session data and redirect to the homepage."""
    session.pop("user", None)
    return redirect("/")


@app.route("/update_location", methods=["POST"])
def update_location():
    """Store a posted location update in the database."""
    data = request.json

    email = data.get("email")
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    add_location_to_db(email, latitude, longitude)

    return jsonify({"status": "success"}), 200


@app.route("/add-email")
def add_email_to_session():
    """Add a new email to the current map session."""
    emails = session.setdefault("email_list", [session["user"]["email"]])
    new_email = request.args.get("map-email")

    if new_email:
        email_exists = check_email_exists(new_email)

        if not email_exists:
            flash(f"Email {new_email} not found. Please try another.", "error")
            return redirect(url_for("show_map"))

        if new_email in emails:
            emails.remove(new_email)
        emails.insert(0, new_email)
        session["email_list"] = emails[:MAX_EMAILS]

    return redirect(url_for("show_map"))


@app.route("/map")
def show_map():
    """Render the map page for selected user emails."""
    emails = session.get("email_list") or session["user"]["email"]

    m = None

    for email, color in zip(emails, COLORS):
        points = get_points_from_db(email)

        if not points:
            continue
        if m is None:
            m = folium.Map(location=points[-1], zoom_start=15)

        folium.PolyLine(points, color=color, tooltip=email).add_to(m)
        folium.Marker(
            points[0], popup=f"{email} – Start", icon=folium.Icon(color=color)
        ).add_to(m)
        folium.Marker(
            points[-1], popup=f"{email} – Latest", icon=folium.Icon(color=color)
        ).add_to(m)

    if m is None:
        return f"No locations found for {', '.join(emails)}"

    return render_template(
        "index.html",
        user=session.get("user"),
        emails=session.get("email_list"),
        map_html=m._repr_html_(),
    )


if __name__ == "__main__":
    app.run(debug=True)
