import os
import json
from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime, date
# We need to import the entire datetime module for the fix in home()
import datetime as dt 

# Define the file path for persistence
EVENTS_FILE_PATH = '/Users/umesh/Downloads/DS-Lab/DSA - CP/AI-Event-Tracker/events_college.json'

# Event Model (Class)
class Event:
    def __init__(self, name, date, category, organizer, url):
        self.name = name
        # Ensure date is always a date object in memory
        if isinstance(date, str):
            try:
                self.date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                # Fallback or error handling for bad date string
                self.date = date.today() 
                print(f"Warning: Invalid date format for {name}. Using today's date.")
        else:
            self.date = date 
            
        self.category = category
        self.organizer = organizer
        self.url = url
    
    def to_dict(self):
        """Converts the Event object to a dictionary for JSON writing."""
        return {
            'name': self.name,
            # Convert date object to string for JSON compatibility
            'date': self.date.strftime("%Y-%m-%d"), 
            'category': self.category,
            'organizer': self.organizer,
            'url': self.url
        }
    
    def __repr__(self):
        return f"Event(name='{self.name}', date='{self.date}', category='{self.category}')"


# Event Storage Class: Handles JSON loading/saving
class EventStorage:
    def __init__(self):
        self.events_by_name = {}
        self.events_by_category = {}
        self.load_from_json() 

    def load_from_json(self):
        """Loads events from the JSON file into memory."""
        if not os.path.exists(EVENTS_FILE_PATH):
            print(f"--- {EVENTS_FILE_PATH} not found. Starting fresh. ---")
            return
            
        try:
            with open(EVENTS_FILE_PATH, 'r') as f:
                data = json.load(f)
            
            for event_data in data:
                # The Event constructor handles the date string conversion
                self._add_event_to_memory(event_data)
            
            print(f"--- Successfully loaded {len(data)} events from {EVENTS_FILE_PATH} ---")
            
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            print(f"Error loading JSON data: {e}. Starting with no events.")

    def save_to_json(self):
        """Writes ALL current events in memory back to the JSON file."""
        try:
            all_data = [event.to_dict() for event in self.events_by_name.values()]
            with open(EVENTS_FILE_PATH, 'w') as f:
                json.dump(all_data, f, indent=4) 
            print(f"--- Saved {len(all_data)} events to {EVENTS_FILE_PATH} ---")
        except Exception as e:
            print(f"Error saving to JSON file: {e}")

    def _add_event_to_memory(self, event_data):
        """Internal helper to add an event dictionary to the in-memory structures."""
        
        # Ensure data is normalized before adding
        event = Event(
            event_data['name'],
            event_data['date'], 
            event_data['category'],
            event_data['organizer'],
            event_data.get('url', '#')
        )

        normalized_name = event.name.lower()
        if normalized_name in self.events_by_name:
            # print(f"Skipping duplicate event: {event.name}")
            return

        self.events_by_name[normalized_name] = event
        
        normalized_category = event.category.lower()
        if normalized_category not in self.events_by_category:
            self.events_by_category[normalized_category] = []
        self.events_by_category[normalized_category].append(event)
    
    def add_event(self, event_data):
        """Public method to add event, then save to disk."""
        self._add_event_to_memory(event_data)
        self.save_to_json() 

    def get_all_events(self):
        return list(self.events_by_name.values())

    def get_event_by_name(self, name):
        return self.events_by_name.get(name.lower())
    
    def get_events_by_category(self, category):
        return self.events_by_category.get(category.lower(), [])


# Flask application setup
app = Flask(__name__)
event_storage = EventStorage() 

@app.route('/', methods=['GET', 'POST'])
def home():
    # Fetch all events and sort them by date (e.date is now guaranteed to be a date object)
    all_events_list = sorted(event_storage.get_all_events(), key=lambda x: x.date)
    
    # Filter for upcoming events (Comparison now works!)
    upcoming_events = [e for e in all_events_list if e.date >= date.today()]
    featured_events = upcoming_events[:6] 
    
    search_event_result = None
    filtered_events_list = None
    
    # Handle form submissions
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add':
            # Data from the Add Event form
            new_event_data = {
                'name': request.form['name'],
                # Date is passed as a string (YYYY-MM-DD)
                'date': request.form['date'], 
                'category': request.form['category'],
                'organizer': request.form['organizer'],
                'url': request.form.get('url', '#')
            }
            # Add event and save to JSON
            event_storage.add_event(new_event_data)
            return redirect(url_for('home'))
        
        elif action == 'search':
            event_name = request.form['name']
            search_event_result = event_storage.get_event_by_name(event_name)
        
        elif action == 'filter':
            category_name = request.form['category']
            filtered_events_list = event_storage.get_events_by_category(category_name)

    return render_template(
        'index.html',
        events=featured_events,
        all_events=all_events_list,
        search_event=search_event_result,
        filtered_events=filtered_events_list,
        # FIX: Pass the entire datetime module for use in the template
        datetime=dt.datetime 
    )

if __name__ == "__main__":
    app.run(debug=True)