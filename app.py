import json
import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify # jsonify added
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np # Used for efficient array sorting

# --- Configuration ---
app = Flask(__name__)
app.secret_key = 'your_super_secret_key'
EVENT_FILE = 'events_college.json'
ADMIN_USER = 'admin'
ADMIN_PASS = 'password123'

# --- Utility Functions and Global Data ---

def format_date(date_str):
    """Formats YYYY-MM-DD date string for display."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%B %d, %Y")
    except ValueError:
        return date_str

app.jinja_env.globals.update(format_date=format_date)

def load_events():
    """Reads events from the JSON file."""
    if os.path.exists(EVENT_FILE):
        with open(EVENT_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_events(events_list):
    """Writes the current list of events to the JSON file."""
    with open(EVENT_FILE, 'w') as f:
        json.dump(events_list, f, indent=4)

def get_ai_components(events_list):
    """Trains and returns the TF-IDF Vectorizer and Matrix."""
    if not events_list:
        return None, None # Returns None if no data exists

    corpus = [
        f"{e.get('title', '')} {e.get('description', '')} {e.get('venue', '')}" 
        for e in events_list
    ]
    
    # Train the model
    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf_matrix = vectorizer.fit_transform(corpus)
    return vectorizer, tfidf_matrix

# --- Chatbot Logic (New AI Component) ---

def get_chatbot_response(message):
    """Provides rule-based answers based on keywords in the user's message."""
    message = message.lower()
    
    if 'admin' in message or 'login' in message or 'credentials' in message:
        return f"The admin username is '{ADMIN_USER}' and the password is '{ADMIN_PASS}'."
    elif 'upcoming' in message or 'next 7 days' in message or 'filter' in message:
        return "The homepage automatically filters events for the next 7 days in the 'Upcoming Events' section."
    elif 'recommendation' in message or 'search' in message or 'event' in message or 'interested' in message:
        return "To get personalized recommendations, please use the search bar at the top! I use AI (TF-IDF) for matching."
    elif 'hello' in message or 'hi' in message or 'hey' in message:
        return "Hello! I'm your College Event Assistant. How can I help you find an event?"
    else:
        return "I'm an AI assistant. I can help with event search, admin access, or the 7-day filter."

# --- Recommendation Logic (Simplified) ---

def recommend_events_simple(user_interest, events_list, top_n=3):
    """Calculates Cosine Similarity and uses simple sorting for Top N."""
    vectorizer, tfidf_matrix = get_ai_components(events_list)
    
    if vectorizer is None:
        return []

    # 1. Transform user interest
    user_tfidf = vectorizer.transform([user_interest])

    # 2. Calculate Cosine Similarity
    cosine_sim = cosine_similarity(user_tfidf, tfidf_matrix).flatten()

    # 3. Simple O(n log n) sorting to get indices of top scores
    top_indices = cosine_sim.argsort()[::-1]
    
    recommended_events = []
    
    # Filter for non-zero scores and collect the top N events
    for i in top_indices:
        if cosine_sim[i] > 0.0 and len(recommended_events) < top_n:
            recommended_events.append(events_list[i])
        elif len(recommended_events) >= top_n:
            break
            
    return recommended_events

# --- Flask Routes ---

@app.before_request
def check_initialization():
    """Ensures the AI components are always trained on the latest data."""
    global GLOBAL_EVENTS
    GLOBAL_EVENTS = load_events()
    global GLOBAL_VECTORIZER, GLOBAL_MATRIX
    GLOBAL_VECTORIZER, GLOBAL_MATRIX = get_ai_components(GLOBAL_EVENTS)

# Define global variables for data storage
GLOBAL_EVENTS = []
GLOBAL_VECTORIZER = None
GLOBAL_MATRIX = None

@app.route('/')
def home():
    # 1. Define the current date and the cutoff date (7 days from now).
    today = datetime.now().date()
    seven_days_from_now = today + timedelta(days=7) 
    
    # 2. Filter events for the Upcoming Events section (next 7 days).
    upcoming_events = []
    for e in GLOBAL_EVENTS:
        try:
            event_date = datetime.strptime(e['date'], "%Y-%m-%d").date()
            # Filter Logic: event must be today or later AND within the next 7 days.
            if event_date >= today and event_date <= seven_days_from_now:
                upcoming_events.append(e)
        except ValueError:
            continue
            
    return render_template(
        'index.html', 
        events=upcoming_events, 
        all_events=GLOBAL_EVENTS,
        datetime=datetime
    )

@app.route('/recommend', methods=['POST'])
def recommend():
    user_interest = request.form['interest']
    
    # Call the simplified recommendation function
    recommended = recommend_events_simple(user_interest, GLOBAL_EVENTS, top_n=5)
    
    return render_template('recommend.html', recommended=recommended, interest=user_interest)

@app.route('/chatbot_talk', methods=['POST'])
def chatbot_talk():
    """Route to receive user message and return chatbot response via JSON."""
    data = request.get_json()
    user_message = data.get('message', '')

    if not user_message:
        return jsonify({'response': "I didn't receive your message. Please try again!"})
    
    bot_response = get_chatbot_response(user_message)
    
    return jsonify({'response': bot_response})

# --- Admin/Auth Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == ADMIN_USER and request.form['password'] == ADMIN_PASS:
            session['logged_in'] = True
            flash("Logged in successfully!", "success")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid credentials.", "danger")
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash("You have been logged out.", "info")
    return redirect(url_for('home'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('logged_in'):
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))
    
    # Pass the global event list
    return render_template(
        'admin_dashboard.html', 
        events=GLOBAL_EVENTS,
        datetime=datetime
    )

@app.route('/add_event', methods=['POST'])
def add_event():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    required_fields = ['title', 'description', 'date', 'venue', 'url'] 
    if any(not request.form.get(field) for field in required_fields):
        flash("All fields are required.", "danger")
        return redirect(url_for('admin_dashboard'))

    new_event = {
        "title": request.form['title'],
        "description": request.form['description'],
        "date": request.form['date'],
        "venue": request.form['venue'],
        "url": request.form['url']
    }
    
    # Add to global list and save
    GLOBAL_EVENTS.append(new_event)
    save_events(GLOBAL_EVENTS)
    flash(f"Event '{new_event['title']}' added successfully!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/edit_event/<int:index>', methods=['GET', 'POST'])
def edit_event(index):
    """Handles viewing and submitting edits for a specific event by its list index."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if not (0 <= index < len(GLOBAL_EVENTS)):
        flash("Event not found.", "danger")
        return redirect(url_for('admin_dashboard'))

    event_to_edit = GLOBAL_EVENTS[index]
    
    if request.method == 'POST':
        # --- Handle Form Submission (POST Request) ---
        try:
            # 1. Update the event dictionary with new form data
            event_to_edit['title'] = request.form['title']
            event_to_edit['description'] = request.form['description']
            event_to_edit['date'] = request.form['date']
            event_to_edit['venue'] = request.form['venue']
            event_to_edit['url'] = request.form['url']

            # 2. Save the updated global list back to the JSON file
            save_events(GLOBAL_EVENTS)

            flash(f"Event '{event_to_edit['title']}' updated successfully!", "success")
            return redirect(url_for('admin_dashboard'))
        
        except KeyError as e:
            flash(f"Missing form field: {e}. Please check your HTML form names.", "danger")
            return redirect(url_for('edit_event', index=index))
    
    # --- Handle Page View (GET Request) ---
    return render_template(
        'edit_event.html', 
        event=event_to_edit,
        index=index
    )

@app.route('/delete_event/<int:index>')
def delete_event(index):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    if 0 <= index < len(GLOBAL_EVENTS):
        # Delete from global list and save
        del GLOBAL_EVENTS[index]
        save_events(GLOBAL_EVENTS)
        flash("Event deleted successfully!", "success")
    else:
        flash("Event not found.", "danger")
        
    return redirect(url_for('admin_dashboard'))

# --- Run App ---

if __name__ == '__main__':
    # Initial load of data and model before starting the server
    GLOBAL_EVENTS = load_events()
    GLOBAL_VECTORIZER, GLOBAL_MATRIX = get_ai_components(GLOBAL_EVENTS)
    app.run(debug=True)
