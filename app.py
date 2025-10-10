import os
import pickle
from flask import Flask, session, redirect, url_for, request, render_template, flash
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "test_secret_key")

# Gmail API Scope
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# ------------------- AUTHENTICATION -------------------
def get_gmail_service():
    """Authenticate and return Gmail API service"""
    creds = None

    # Load token if available
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    # If no valid credentials, prompt user to log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = Flow.from_client_secrets_file(
                "client_secret.json",
                scopes=SCOPES,
                redirect_uri=url_for('oauth2callback', _external=True)
            )
            auth_url, _ = flow.authorization_url(prompt='consent')
            session['flow'] = flow
            return redirect(auth_url)

    # Build Gmail service
    service = build('gmail', 'v1', credentials=creds)
    return service


@app.route("/")
def index():
    return redirect(url_for("authorize"))


@app.route("/authorize")
def authorize():
    flow = Flow.from_client_secrets_file(
        "client_secret.json",
        scopes=SCOPES,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    authorization_url, state = flow.authorization_url(prompt='consent')
    session['state'] = state
    session['flow'] = flow
    return redirect(authorization_url)


@app.route("/oauth2callback")
def oauth2callback():
    state = session['state']
    flow = Flow.from_client_secrets_file(
        "client_secret.json",
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    with open("token.pickle", "wb") as token:
        pickle.dump(creds, token)
    session['credentials'] = creds_to_dict(creds)
    flash("Login successful!")
    return redirect(url_for("delete_page"))


def creds_to_dict(creds):
    return {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }


# ------------------- DELETE PAGE -------------------
@app.route("/delete")
def delete_page():
    return render_template("delete.html")


# ------------------- PERFORM DELETE -------------------
@app.route("/perform_delete", methods=['POST'])
def perform_delete():
    if 'credentials' not in session:
        return redirect(url_for('authorize'))

    creds = Credentials(**session['credentials'])
    service = build('gmail', 'v1', credentials=creds)

    categories = request.form.getlist('category')
    custom_email = request.form.get('custom_email', '').strip()
    action = request.form.get('action', 'trash')

    query_parts = []

    # Standard categories
    if 'flipkart' in categories:
        query_parts.append('from:flipkart.com')
    if 'amazon' in categories:
        query_parts.append('from:amazon.in')
    if 'gpay' in categories:
        query_parts.append('from:gpay.in')
    if 'unread' in categories:
        query_parts.append('is:unread')

    # Custom email
    if 'custom' in categories:
        if custom_email:
            query_parts.append(f'from:{custom_email}')
        else:
            flash("You selected Custom Email but didn’t enter an address.")
            return redirect(url_for('delete_page'))

    if not query_parts:
        flash("Please select at least one option.")
        return redirect(url_for('delete_page'))

    q = " OR ".join(query_parts)

    try:
        deleted = 0
        res = service.users().messages().list(userId='me', q=q, maxResults=500).execute()
        messages = res.get('messages', [])

        while 'nextPageToken' in res:
            res = service.users().messages().list(userId='me', q=q, pageToken=res['nextPageToken']).execute()
            messages.extend(res.get('messages', []))

        for m in messages:
            mid = m['id']
            if action == 'trash':
                service.users().messages().trash(userId='me', id=mid).execute()
            else:
                service.users().messages().delete(userId='me', id=mid).execute()
            deleted += 1

        flash(f"✅ {deleted} messages deleted for: {q}")

    except HttpError as e:
        flash(f"⚠ Gmail API error: {e}")

    return redirect(url_for('delete_page'))


# ------------------- MAIN -------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)), debug=True)
