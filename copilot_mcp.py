from mcp.server.fastmcp import FastMCP
import httpx
import os
import json

# Initialize the FastMCP server
mcp = FastMCP("K_CAD_Automation_Bridge")

@mcp.tool()
def run_rhino_python(code: str) -> str:
    """
    Executes Python 3 code directly inside the active Rhino document via Port 5050.
    Use this to generate geometry, modify elements, or extract coordinates.
    """
    try:
        res = httpx.post(
            "http://localhost:5050/execute", 
            json={"code": code}, 
            timeout=15.0
        )
        data = res.json()
        if data.get("status") == "success":
            return data.get("output", "Command executed successfully with no print output.")
        else:
            return f"Rhino Execution Error: {data.get('message', 'Unknown error')}"
    except Exception as e:
        return f"Bridge connection failed. Is copilot_flask.py running in Rhino on Port 5050? Error: {str(e)}"

@mcp.tool()
def run_revit_python(code: str) -> str:
    """
    Executes Python 3 code directly inside the active Revit document via Port 5051.
    Use this to push geometry, automate parameters, or instantiate Revit families.
    """
    try:
        res = httpx.post(
            "http://localhost:5051/execute_revit", 
            json={"code": code}, 
            timeout=15.0
        )
        data = res.json()
        if data.get("status") == "success":
            return data.get("output", "Revit pipeline executed successfully.")
        else:
            return f"Revit API Error: {data.get('message', 'Unknown error')}"
    except Exception as e:
        return f"Bridge connection failed. Ensure the pyRevit listener is running on Port 5051. Error: {str(e)}"

@mcp.tool()
def analyze_geometry_for_revit() -> str:
    """
    Analyzes the user's currently selected Rhino geometry to determine the optimal export path to Revit.
    Call this when the user asks how to transfer, export, or convert a model to Revit.
    """
    # Package the Rhino-side logic and send it to Port 5050 to execute securely inside the CAD environment
    rhino_script = '''
import rhinoscriptsyntax as rs
import json

selected = rs.GetObjects("Select objects", preselect=True)
if not selected:
    print("No geometry currently selected in the viewport.")
else:
    breakdown = {"meshes": 0, "planar_surfaces": 0, "complex_polysurfaces": 0, "blocks": 0, "curves": 0}
    
    for obj in selected:
        if rs.IsMesh(obj):
            breakdown["meshes"] += 1
        elif rs.IsBlockInstance(obj):
            breakdown["blocks"] += 1
        elif rs.IsCurve(obj):
            breakdown["curves"] += 1
        elif rs.IsPolysurface(obj) or rs.IsSurface(obj):
            if rs.IsSurfacePlanar(obj) or rs.IsPolysurfacePlanar(obj):
                breakdown["planar_surfaces"] += 1
            else:
                breakdown["complex_polysurfaces"] += 1
                
    print(f"Analyzed {len(selected)} objects.")
    print(f"Topology breakdown: {json.dumps(breakdown)}")
    print("INSTRUCTIONS FOR AI: Based on this breakdown, present the user with the most viable Revit translation options using Rhino.Inside.Revit.")
    print("Do not write the script yet. Just explain the pros and cons of Native Elements vs. DirectShape vs. Family Instances.")
'''
    return run_rhino_python(rhino_script)

@mcp.tool()
def scaffold_pyrevit_button(button_name: str, python_logic: str) -> str:
    """
    Generates a valid pyRevit .pushbutton folder structure and script.py file.
    Use this when the user asks to create a Revit automation tool or pyRevit script.
    """
    # Create the standard pyRevit nested folder structure using the Windows user profile path
    desktop = os.path.join(os.environ["USERPROFILE"], "Desktop")
    base_dir = os.path.join(desktop, "K_CAD_Engine.extension", "Automation.tab", "Pipeline.panel")
    button_dir = os.path.join(base_dir, f"{button_name.replace(' ', '_')}.pushbutton")
    
    os.makedirs(button_dir, exist_ok=True)
    script_path = os.path.join(button_dir, "script.py")
    
    # Inject standard pyRevit boilerplate for API access and UI forms if missing
    if "from pyrevit import" not in python_logic:
        boilerplate = (
            "#! python3\n"
            "from pyrevit import revit, DB, UI, forms\n"
            "doc = revit.doc\n"
            "uidoc = revit.uidoc\n\n"
        )
        python_logic = boilerplate + python_logic
        
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(python_logic)
        
    return f"Successfully scaffolded pyRevit extension button at: {button_dir}"

if __name__ == "__main__":
    # Start the standard input/output server for LangGraph client integration
    mcp.run(transport='stdio')
