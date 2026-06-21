import os
import sqlite3
import folium
from flask import Flask, render_template,redirect,url_for, jsonify, request, session, flash
from authlib.integrations.flask_client import OAuth
import config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
MAX_EMAILS = 10
COLORS = ["blue", "red", "green", "purple", "orange", "darkred", "cadetblue", "darkgreen", "pink", "gray"]

app = Flask(__name__)
app.secret_key = config.FLASK_SECRET_KEY

oauth = OAuth(app)
google = oauth.register(
    name="google",
    client_id=config.GOOGLE_CLIENT_ID,
    client_secret=config.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope":"openid email profile"},
)

@app.route('/')
def homepage():
    user = session.get('user')
    return render_template('index.html', user=user)

@app.route('/login')
def login():
    redirect_uri = url_for('auth', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth')
def auth():
    token = google.authorize_access_token()
    session["user"] = token.get("userinfo")
    return redirect("/")

@app.route('/logout')
def logout():
    session.pop("user", None)
    return redirect("/")

@app.route('/update_location', methods=['POST'])
def update_location():
    data = request.json

    email = data.get('email')
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('INSERT INTO locations (email, latitude, longitude) VALUES (?, ?, ?)', (email, latitude, longitude))

    conn.commit()
    conn.close()

    return jsonify({"status": "success"}), 200

@app.route("/add-email")
def add_email_to_session():
    emails = session.setdefault("email_list", [session["user"]["email"]])
    new_email = request.args.get("map-email")

    if new_email:
        # Check if the mail exists in the database
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM locations WHERE email = ? LIMIT 1", (new_email,))
        email_exists = cur.fetchone()
        conn.close()

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
    emails = session.get("email_list") or session["user"]["email"]
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    m = None

    for email, color in zip(emails, COLORS):

        points = [(row["latitude"], row["longitude"]) for row in conn.execute(
            "SELECT latitude, longitude FROM locations WHERE email = ? ORDER BY timestamp", (email,)
        )]
        if not points:
            continue
        if m is None:
            m = folium.Map(location=points[-1], zoom_start=15)

        folium.PolyLine(points, color=color, tooltip=email).add_to(m)
        folium.Marker(points[0], popup=f"{email} – Start", icon=folium.Icon(color=color)).add_to(m)
        folium.Marker(points[-1], popup=f"{email} – Latest", icon=folium.Icon(color=color)).add_to(m)

    conn.close()

    if m is None:
        return f"No locations found for {', '.join(emails)}"
    
    return render_template("index.html", user=session.get("user"), emails = session.get("email_list"), map_html=m._repr_html_())


if __name__ == "__main__":
    app.run(debug=True)