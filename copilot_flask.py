#! python3
# r: flask
from flask import Flask, request, jsonify, cli
import rhinoscriptsyntax as rs
import scriptcontext as sc
import Rhino
import base64
import System

# Mute the Flask startup banner to prevent stdout threading errors in Rhino
cli.show_server_banner = lambda *args: None
app = Flask(__name__)

@app.route('/inspect_selection', methods=['GET'])
def inspect_selection():
    selected = rs.SelectedObjects()
    if not selected:
        return jsonify({"message": "No objects currently selected in Rhino."})

    report = []
    for obj_id in selected:
        obj_type = rs.ObjectType(obj_id)
        
        info = {
            "guid": str(obj_id),
            "type_code": obj_type,
            "layer": rs.ObjectLayer(obj_id),
        }
        
        if obj_type in [8, 16]:  # Surface or Polysurface
            is_closed = rs.IsPolysurfaceClosed(obj_id) if obj_type == 16 else rs.IsSurfaceClosed(obj_id, 0)
            info["is_closed"] = is_closed
            info["surface_area"] = rs.SurfaceArea(obj_id)[0] if rs.SurfaceArea(obj_id) else "Unknown"

        report.append(info)

    return jsonify({"selected_count": len(selected), "objects": report})

@app.route('/execute_code', methods=['POST'])
def execute_code():
    code = request.json.get('code', '')
    
    def run_safely():
        print("\n" + "="*40)
        print("🤖 GEMINI IS EXECUTING THIS CODE:")
        print(code)
        print("="*40)
        
        try:
            sc.doc = Rhino.RhinoDoc.ActiveDoc
            rs.Command("_-Layer _New \"AI_Generated\" _Enter", echo=False)
            rs.CurrentLayer("AI_Generated")
            
            local_scope = {"rs": rs, "Rhino": Rhino, "sc": sc}
            exec(code, local_scope)
            
            sc.doc.Views.Redraw()
            print("✅ SUCCESS: Geometry baked to viewport.\n")
            return {"status": "success", "message": "Code executed and view redrawn."}
            
        except Exception as e:
            print(f"❌ RHINO ERROR: {str(e)}\n")
            return {"status": "error", "error": str(e)}
            
    import Eto.Forms
    result = Eto.Forms.Application.Instance.Invoke(run_safely)
    return jsonify(result)

@app.route('/capture_viewport', methods=['GET'])
def capture_viewport():
    def run_safely():
        try:
            view = sc.doc.Views.ActiveView
            if not view:
                return {"status": "error", "error": "No active view found."}
                
            # Utilize RhinoCommon to generate a clean viewport bitmap
            capture = Rhino.Display.ViewCapture()
            capture.Width = view.ActiveViewport.Size.Width
            capture.Height = view.ActiveViewport.Size.Height
            capture.ScaleScreenItems = False
            capture.DrawAxes = False
            capture.DrawGrid = False
            capture.TransparentBackground = False
            
            bitmap = capture.CaptureToBitmap(view)
            
            # Stream directly to memory 
            stream = System.IO.MemoryStream()
            bitmap.Save(stream, System.Drawing.Imaging.ImageFormat.Png)
            image_bytes = stream.ToArray()
            b64_str = base64.b64encode(image_bytes).decode('utf-8')
            
            return {"status": "success", "image": b64_str}
        except Exception as e:
            return {"status": "error", "error": str(e)}
            
    import Eto.Forms
    result = Eto.Forms.Application.Instance.Invoke(run_safely)
    return jsonify(result)

if __name__ == '__main__':
    import threading
    threading.Thread(target=lambda: app.run(port=5050, debug=False, use_reloader=False)).start()
    print("Rhino Copilot Bridge ready on port 5050...")
