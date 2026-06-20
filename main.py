from flask import Flask, render_template,redirect,url_for, session
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
    user = session.get('user["email"]')
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

if __name__ == "__main__":
    app.run(debug=True)