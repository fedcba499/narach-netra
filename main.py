import sqlite3
import folium
from flask import Flask, render_template,redirect,url_for, jsonify, request, session
from authlib.integrations.flask_client import OAuth
import config

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

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute('INSERT INTO locations (email, latitude, longitude) VALUES (?, ?, ?)', (email, latitude, longitude))

    conn.commit()
    conn.close()

    return jsonify({"status": "success"}), 200

@app.route("/map")
def show_map():
    email = request.args.get("map-email") or session["user"]["email"]
    
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT latitude, longitude, timestamp FROM locations WHERE email = ? ORDER BY timestamp", (email,),
    ).fetchall()
    conn.close()

    if not rows:
        return f"No locations found for {email}"
    
    points = [(row["latitude"], row["longitude"]) for row in rows]

    m = folium.Map(location=points[-1], zoom_start=15)

    folium.PolyLine(points, color="blue", weight=3).add_to(m)

    folium.Marker(points[0], popup="Start", icon=folium.Icon(color="green")).add_to(m)
    folium.Marker(points[-1], popup="Latest", icon=folium.Icon(color="red")).add_to(m)

    map_html = m._repr_html_()

    return render_template("index.html", user=session.get("user"),  map_html=map_html)

if __name__ == "__main__":
    app.run(debug=True)