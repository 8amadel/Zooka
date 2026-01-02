import os
import uuid
import asyncio
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from google.cloud import spanner
import vertexai
from vertexai import agent_engines

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev_key_for_session_security')

# --- SPANNER CONFIGURATION ---
PROJECT_ID = os.environ.get("PROJECT_ID")
REGION_ID = os.environ.get("REGION_ID")
INSTANCE_NAME = os.environ.get("SPANNER_INSTANCE_NAME")
DATABASE_NAME = os.environ.get("SPANNER_DATABASE_NAME")
AGENT_RESOURCE_ID = os.environ.get("AGENT_RESOURCE_ID")

vertexai.init(project=PROJECT_ID, location=REGION_ID)
remote_app = agent_engines.get(AGENT_RESOURCE_ID)

_database = None

def get_database():
    global _database
    
    if _database is None:

        spanner_client = spanner.Client(project=PROJECT_ID)
        instance = spanner_client.instance(INSTANCE_NAME)
        _database = instance.database(DATABASE_NAME)
        
    return _database

async def chat_with_zooka_init(username):

    USER_ID = username
    raw_sessions_list = await remote_app.async_list_sessions(user_id=USER_ID)
    open_sessions = raw_sessions_list.get('sessions', [])
    for session in open_sessions:
        session_id = session.get('id')
        if session_id:
            await cleanup_session_logic(USER_ID, session_id)

    remote_session = await remote_app.async_create_session(user_id=USER_ID)
    session_id=remote_session["id"]
    return session_id

async def ask_question_logic(username, session_id, message):
    full_response = []
    async for event in remote_app.async_stream_query(
        user_id=username,
        session_id=session_id,
        message=message,
    ):
        data = event
        parts = data.get('content', {}).get('parts', [])
        if parts:
            text_chunk = parts[0].get('text', '')
            if text_chunk:
                full_response.append(text_chunk)
    
    return "".join(full_response)

async def cleanup_session_logic(username, session_id):

    remote_session = await remote_app.async_get_session(user_id=username, session_id=session_id)
    await remote_app.async_add_session_to_memory(session=remote_session)
    await remote_app.async_delete_session(user_id=username, session_id=session_id)
    return True

# --- ROUTES ---

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/auth', methods=['GET', 'POST'])
def auth():

    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username')
        password = request.form.get('password')
        db = get_database()
        if action == 'signup':
            confirm_password = request.form.get('confirm_password')
            if password != confirm_password:
                flash('Passwords do not match!')
                return redirect(url_for('auth'))
            
            # Check if user exists
            with db.snapshot() as snapshot:
                results = snapshot.execute_sql(
                    "SELECT username FROM users WHERE username = @username",
                    params={"username": username},
                    param_types={"username": spanner.param_types.STRING}
                )
                if list(results):
                    flash('Username already exists.')
                    return redirect(url_for('auth'))

            # Create user
            hashed_pw = generate_password_hash(password)
            def insert_user(transaction):
                transaction.execute_update(
                    "INSERT users (username, password_hash) VALUES (@username, @password_hash)",
                    params={"username": username, "password_hash": hashed_pw},
                    param_types={"username": spanner.param_types.STRING, "password_hash": spanner.param_types.STRING}
                )
            db.run_in_transaction(insert_user)
            flash('Signup successful! Please login.')
            
        elif action == 'login':
            # Verify User
            with db.snapshot() as snapshot:
                results = snapshot.execute_sql(
                    "SELECT password_hash FROM users WHERE username = @username",
                    params={"username": username},
                    param_types={"username": spanner.param_types.STRING}
                )
                row = next(iter(results), None)
                
                if row and check_password_hash(row[0], password):
                    session['username'] = username
                    # Call user's custom init function
                    session_id = asyncio.run(chat_with_zooka_init(username))
                    session['zooka_session_id'] = session_id
                    return redirect(url_for('chat_page'))
                else:
                    flash('Invalid credentials.')
                    
    return render_template('login.html')

@app.route('/zooka')
def chat_page():
    if 'username' not in session:
        return redirect(url_for('auth'))
    return render_template('chat.html', username=session['username'])

# --- API ENDPOINTS FOR CHAT ---

@app.route('/api/ask', methods=['POST'])
def api_ask():
    if 'username' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    data = request.json
    message = data.get('message')
    username = session['username']
    session_id = session.get('zooka_session_id')
    
    # Call user's custom question logic
    response_text = asyncio.run(ask_question_logic(username, session_id, message))
    
    return jsonify({'response': response_text})

@app.route('/api/end_session', methods=['POST'])
def api_end_session():
    if 'username' not in session:
        return jsonify({'status': 'ignored'})
        
    username = session['username']
    session_id = session.get('zooka_session_id')
    
    # Call user's custom cleanup logic
    asyncio.run(cleanup_session_logic(username, session_id))
    
    session.clear()
    return jsonify({'status': 'ok'})

if __name__ == "__main__":
    # Local testing config
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))