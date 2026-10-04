#! python3
"""
⚠️ EXPERIMENTAL PROOF OF CONCEPT
AI-generated code executes locally with the current user's permissions via exec().
Review generated operations before use and test ONLY on non-production model copies.
"""

import threading
from pyrevit import revit, DB, UI
from pyrevit.revit.events import execute_in_revit_context
from flask import Flask, request, jsonify

app = Flask(__name__)

def execute_on_main_thread(code_string):
    """Executes the AI's Python string safely within Revit's main API context."""
    print("\n--- [SECURITY LOG] AI EXECUTING REVIT PYTHON ---")
    print(code_string)
    print("------------------------------------------------\n")
    
    exec_globals = {'revit': revit, 'DB': DB, 'UI': UI, 'doc': revit.doc}
    exec(code_string, exec_globals)

@app.route('/execute_revit', methods=['POST'])
def execute_revit():
    data = request.get_json()
    code = data.get('code', '')
    
    try:
        # Hand off the execution from the Flask background thread to Revit's main UI thread
        execute_in_revit_context(execute_on_main_thread, code)
        return jsonify({"status": "success", "message": "Execution safely queued to Revit's main thread."})
    except Exception as e:
        print(f"[EXECUTION ERROR]: {str(e)}")
        return jsonify({"status": "error", "error": str(e)})

def run_server():
    # Runs on Port 5051
    app.run(host='127.0.0.1', port=5051, use_reloader=False)

# Launch the server in a background daemon thread
server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

print("🚀 Rhino CO-Pilot Revit Bridge active on Port 5051. Awaiting commands...")
