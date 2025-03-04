from gevent import monkey, spawn, kill
monkey.patch_all()
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from DatabaseHandler import DatabaseHandler  # Your DatabaseHandler class
from openai_service import ChatGPT
from pymongo import MongoClient
from config import COLLECTION,MONGO_URI,DB_NAME  # This contains your US_CONSITITON_SET, AUS_LAW_SET, etc.
from flask_session import Session
from bson import ObjectId
import logging

import uuid
app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
app.secret_key = 'ambre'
Session(app)
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
# Instantiate the DatabaseHandler and ChatGPT service.

# Configure logging.
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)
active_searches = {}
def serialize_results(results):
    serialized = []
    for case, similarity in results:
        # Convert all ObjectId fields in the case dictionary to strings.
        for key, value in case.items():
            if isinstance(value, ObjectId):
                case[key] = str(value)
        serialized.append((case, similarity))
    return serialized

@app.context_processor
def inject_document_type():
    # Get document type from the session (or a default value)
    document_type = session.get('document_type', 'Default Document')
    return dict(document_type=document_type)

@app.route('/', methods=['GET'])
def index():
    chat_service = ChatGPT(db)
    allowed, count = chat_service.can_search_today()  # Returns (True/False, current count)
    return render_template('index.html', configurations=COLLECTION, search_allowed=allowed, search_count=count)
@app.route('/cancel', methods=['POST'])
def cancel():
    search_id = session.get('search_id')
    g = active_searches.get(search_id)
    if g:
        kill(g)  # Stop the running greenlet.
        active_searches.pop(search_id, None)
        return jsonify({"status": "cancelled", "message": "Search cancelled."})
    else:
        return jsonify({"status": "no_active_search", "message": "No active search to cancel."})

# New route: After cancellation, redirect here.
@app.route('/cancelled', methods=['GET'])
def cancelled():
    return render_template('base.html', error="Search cancelled.", show_home=True)
@app.route('/search', methods=['POST'])
def search():
    chat_service = ChatGPT(db)
    if not chat_service.can_search_today():  # call the method with parentheses
        return render_template('base.html', error="Reached the limit of the search today. Please try again tomorrow.", show_home=True)

    query = request.form.get('query')
    # Get the configuration key from the form; if missing or invalid, default to "US_CONSTITUTION_SET".
    config_key = request.form.get('collection', 'US_CONSTITUTION_SET').strip()
    if config_key not in COLLECTION:
        logger.warning("Invalid configuration key provided: '%s'. Defaulting to US_CONSTITUTION_SET.", config_key)
        config_key = "US_CONSTITUTION_SET"
    
    # Save the selected document type in the session.
    session['document_type'] = COLLECTION[config_key]["document_type"]
    
    # Process the query using the updated backend function.
    db_handler = DatabaseHandler(COLLECTION[config_key])
    results, query_processed = db_handler.process_query(query)
    
    if not query_processed:
        return render_template('index.html', error="Daily search limit reached. Please try again tomorrow.")
    if not results:
        session.pop('results', None)
        session.pop('current_idx', None)
        return render_template('result.html', error="No cases matched your query sufficiently.")
    
    # Convert ObjectIds to strings before storing in the session.
    session['results'] = serialize_results(results)
    session['current_idx'] = 0
    return redirect(url_for('result'))



@app.route('/eula')
def eula():
    return render_template('eula.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/result', methods=['GET'])
def result():
    results = session.get('results')
    current_idx = session.get('current_idx', 0)
    if not results or current_idx >= len(results):
        return render_template('result.html', error="No more cases available. Please enter a new query.")
    
    case, similarity = results[current_idx]
    # Instantiate ChatGPT using the global database (MongoClient remains open).
    chat_service = ChatGPT(db)
    summary = chat_service.summarize_cases(case)
    return render_template('result.html', summary=summary, similarity=similarity, idx=current_idx+1, total=len(results))

@app.route('/next', methods=['GET'])
def next_result():
    if 'results' in session:
        session['current_idx'] = session.get('current_idx', 0) + 1
    return redirect(url_for('result'))

@app.route('/more', methods=['GET'])
def more_details():
    results = session.get('results')
    current_idx = session.get('current_idx', 0)
    if not results or current_idx >= len(results):
        return redirect(url_for('result'))
    
    case, similarity = results[current_idx]
    # Build details dictionary excluding '_id' and 'map_id'
    details = { key: value for key, value in case.items() if key not in ["_id", "map_id"] }
    return render_template('details.html', details=details)

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
