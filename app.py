import os
from dotenv import load_dotenv
from flask import Flask, redirect, url_for, session, request, render_template, flash
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables
load_dotenv()

# Allow HTTP for local testing
if os.environ.get("FLASK_ENV") == "development":
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "change-me")

# Gmail API setup
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# Load Google credentials from environment variables
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

@app.route("/")
def index():
    logged_in = 'credentials' in session
    return render_template("index.html", logged_in=logged_in)

@app.route("/authorize")
def authorize():
    redirect_uri = url_for('oauth2callback', _external=True)
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )
    auth_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    session['state'] = state
    return redirect(auth_url)

@app.route("/oauth2callback")
def oauth2callback():
    state = session.get('state')
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        },
        scopes=SCOPES,
        state=state,
        redirect_uri=url_for('oauth2callback', _external=True)
    )
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    session['credentials'] = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }
    return redirect(url_for('delete_page'))

def get_gmail_service():
    if 'credentials' not in session:
        return None
    creds = Credentials(**session['credentials'])
    session['credentials'] = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }
    return build('gmail', 'v1', credentials=creds)

@app.route("/delete", methods=['GET'])
def delete_page():
    if 'credentials' not in session:
        return redirect(url_for('authorize'))
    return render_template("delete.html")

@app.route("/perform_delete", methods=['POST'])
def perform_delete():
    if 'credentials' not in session:
        return redirect(url_for('authorize'))

    service = get_gmail_service()
    categories = request.form.getlist('category')
    custom_email = request.form.get('custom_email', '').strip()
    action = request.form.get('action', 'trash')

    query_parts = []

    # Predefined categories
    if 'flipkart' in categories:
        query_parts.append('from:flipkart.com')
    if 'amazon' in categories:
        query_parts.append('from:amazon.in')
    if 'gpay' in categories:
        query_parts.append('from:gpay.in')

    # Always include custom email if typed
    if custom_email:
        query_parts.append(f'from:{custom_email}')

    if not query_parts:
        flash("Please select at least one category or enter your own email.")
        return redirect(url_for('delete_page'))

    q = " OR ".join(query_parts)
    flash(f"Query being sent to Gmail: {q}")  # Debug line

    try:
        messages = []
        res = service.users().messages().list(userId='me', q=q, maxResults=500).execute()
        if 'messages' in res:
            messages.extend(res['messages'])
        while 'nextPageToken' in res:
            res = service.users().messages().list(userId='me', q=q, pageToken=res['nextPageToken']).execute()
            if 'messages' in res:
                messages.extend(res['messages'])

        deleted = 0
        for m in messages:
            mid = m['id']
            if action == 'trash':
                service.users().messages().trash(userId='me', id=mid).execute()
            else:
                service.users().messages().delete(userId='me', id=mid).execute()
            deleted += 1
        flash(f"{deleted} messages deleted for query: {q}")
    except HttpError as e:
        flash(f"Gmail API error: {e}")

    return redirect(url_for('delete_page'))

@app.route("/logout")
def logout():
    session.pop('credentials', None)
    return redirect(url_for('index'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
