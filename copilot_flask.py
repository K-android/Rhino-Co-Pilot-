#! python3
# r: flask, werkzeug
# -*- coding: utf-8 -*-
"""
EXPERIMENTAL PROOF OF CONCEPT
AI-generated code executes locally with the current user's permissions via exec().
Review generated operations before use and test ONLY on non-production model copies.
"""

from flask import Flask, request, jsonify
from werkzeug.serving import run_simple
import rhinoscriptsyntax as rs
import json
import base64
import tempfile
import System
import Rhino

app = Flask(__name__)

@app.route('/execute_code', methods=['POST'])
def execute_code():
    data = request.get_json()
    code = data.get('code', '')
    
    print("\n--- [SECURITY LOG] AI EXECUTING RHINO PYTHON ---")
    print(code)
    print("------------------------------------------------\n")
    
    try:
        # Note: Long-term architecture should replace exec() with a structured tool allowlist.
        exec(code, globals())
        Rhino.RhinoDoc.ActiveDoc.Views.Redraw()
        return jsonify({"status": "success", "message": "Code executed and view redrawn."})
    except Exception as e:
        print("[EXECUTION ERROR]: " + str(e))
        return jsonify({"status": "error", "error": str(e)})

@app.route('/inspect_selection', methods=['GET'])
def inspect_selection():
    selected = rs.GetObjects("Select objects", preselect=True)
    if not selected:
        return jsonify({"status": "success", "selection_count": 0, "details": "No geometry selected."})
    
    # Return basic data to the MCP tool
    return jsonify({
        "status": "success",
        "selection_count": len(selected),
        "details": "Geometry selected. Ready for topology analysis."
    })

@app.route('/run_qaqc', methods=['GET'])
def run_qaqc():
    try:
        selected = rs.GetObjects("Select objects", preselect=True)
        if not selected:
            return jsonify({"status": "success", "report": "No geometry selected for audit."})
        
        invalid_count = 0
        open_breps = 0
        
        for obj_id in selected:
            # Check Breps (Polysurfaces/Surfaces)
            if rs.IsBrep(obj_id):
                brep = rs.coercebrep(obj_id)
                if not brep.IsValid:
                    invalid_count += 1
                elif not brep.IsSolid:
                    open_breps += 1
            # Check Meshes
            elif rs.IsMesh(obj_id):
                mesh = rs.coercemesh(obj_id)
                if not mesh.IsValid:
                    invalid_count += 1
                elif not mesh.IsClosed:
                    open_breps += 1
                    
        report = f"Audit complete on {len(selected)} objects. Invalid/Corrupt geometries: {invalid_count}. Open/Non-manifold boundaries: {open_breps}."
        return jsonify({"status": "success", "report": report})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

@app.route('/capture_viewport', methods=['GET'])
def capture_viewport():
    try:
        view = Rhino.RhinoDoc.ActiveDoc.Views.ActiveView
        bitmap = view.CaptureToBitmap()
        tmp_path = tempfile.mktemp(suffix=".png")
        bitmap.Save(tmp_path, System.Drawing.Imaging.ImageFormat.Png)
        
        with open(tmp_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode('utf-8')
            
        return jsonify({"status": "success", "image": img_b64})
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)})

if __name__ == '__main__':
    print("🚀 K-CAD Rhino Bridge starting on Port 5050...")
    # Bypassing app.run() to avoid Rhino 8 Windows console OverflowErrors
    run_simple('127.0.0.1', 5050, app)
