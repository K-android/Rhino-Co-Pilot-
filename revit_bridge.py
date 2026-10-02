#! python3
# pyRevit Pushbutton Script: K-CAD Engine Revit Listener
import threading
from pyrevit import revit, DB, UI
from pyrevit.revit.events import execute_in_revit_context
from flask import Flask, request, jsonify

app = Flask(__name__)

def execute_on_main_thread(code_string):
    """Executes the AI's Python string safely within Revit's main API context."""
    exec_globals = {'revit': revit, 'DB': DB, 'UI': UI, 'doc': revit.doc}
    exec(code_string, exec_globals)

@app.route('/execute_revit', methods=['POST'])
def execute_revit():
    data = request.get_json()
    code = data.get('code', '')
    
    try:
        # Hand off the execution from the Flask background thread to Revit's main UI thread
        execute_in_revit_context(execute_on_main_thread, code)
        return jsonify({"status": "success", "output": "Execution safely queued to Revit's main thread."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

def run_server():
    # Run on Port 5051 to keep it isolated from the Rhino Port (5050)
    app.run(host='127.0.0.1', port=5051, use_reloader=False)

# Launch the server in a background daemon thread
server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

print("🚀 K-CAD Revit Bridge active on Port 5051. Awaiting commands...")
