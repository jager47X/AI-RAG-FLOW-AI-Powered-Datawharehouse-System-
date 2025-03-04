from flask import Flask, render_template, request, redirect, url_for, session
from db import DatabaseHandler  # Your DatabaseHandler class
from chatgpt import summarize_cases
from config import COLLECTION  # This contains your US_CONSITITON_SET, AUS_LAW_SET, etc.
from flask_session import Session
from bson import ObjectId

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
app.secret_key = 'your-secret-key'
Session(app)

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
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    query = request.form.get('query')
    collection = request.form.get('collection', 'US_CONSITITON_SET')
    
    if not query or not collection:
        return redirect(url_for('index'))
    
    # Save the selected document type in the session.
    session['document_type'] = COLLECTION[collection]["document_type"]
    
    # Process the query using the updated backend function.
    db_handler = DatabaseHandler(COLLECTION[collection])
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
    summary = summarize_cases(case, similarity)
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
    
    # Unpack the current result (each result is a tuple: (case, similarity))
    case, similarity = results[current_idx]
    # Get the document type from the session (set during search)
    doc_type = session.get('document_type', 'Default')
    
    # Define a mapping for different document types.
    # You can expand this mapping as needed.
    if doc_type == "US Constitution":
        details = {
            "article": case.get('article', 'N/A'),
            "section": case.get('section', 'N/A'),
            "title": case.get('title', 'N/A'),
            "text": case.get('text', 'N/A')
        }
    elif doc_type == "Australia Laws 2024":
        details = {
         "version_id": case.get('version_id'),
         "type": case.get('type'),
         "jurisdiction": case.get('jurisdiction'),
         "source": case.get('source'),
         "citation": case.get('citation'),
         "url": case.get('url'),
         "text": case.get("text"),
    }
    else:
        # Default arbitrary mapping if document type isn't recognized.
        details = {key: case.get(key, 'N/A') for key in case.keys()}

    return render_template('details.html', details=details)

if __name__ == '__main__':
    app.run(debug=True, threaded=True)
