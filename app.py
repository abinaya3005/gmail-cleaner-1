import os
import pickle
from flask import Flask, render_template, request
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Allow local HTTP (for testing only)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Needed for sessions

# Gmail API service
def get_gmail_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    service = build('gmail', 'v1', credentials=creds)
    return service

# Delete emails by query
def delete_emails(query):
    service = get_gmail_service()
    try:
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])
        deleted_count = 0
        for msg in messages:
            service.users().messages().delete(userId='me', id=msg['id']).execute()
            deleted_count += 1
        return deleted_count
    except HttpError as error:
        print(f'An error occurred: {error}')
        return 0

# Home page
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        category = request.form.get('category')
        custom_query = request.form.get('custom_query', '').strip()
        
        if category == 'custom' and not custom_query:
            return render_template('index.html', error="Please enter a custom search query!")

        # Predefined queries
        queries = {
            'flipkart': 'from:flipkart.com',
            'amazon': 'from:amazon.in',
            'gpay': 'from:gpay@google.com',
            'unread': 'is:unread'
        }

        query = custom_query if category == 'custom' else queries.get(category, '')

        deleted_count = delete_emails(query)

        return render_template('delete.html', category=category, count=deleted_count, query=query)

    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
        
