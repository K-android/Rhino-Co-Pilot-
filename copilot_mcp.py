"""
Rhino Co-Pilot MCP Server
Handles zero-trust geometry conditioning, metadata injection, and execution for Revit migration.
"""

import httpx
from mcp.server.fastmcp import FastMCP

# Initialize the MCP Server
mcp = FastMCP("Rhino_Revit_Bridge")
RHINO_FLASK_URL = "http://localhost:5050/execute_code"

def execute_in_rhino(script_code: str) -> str:
    """Helper function to push Python code to the Rhino Flask server."""
    try:
        response = httpx.post(RHINO_FLASK_URL, json={"code": script_code}, timeout=15.0)
        return response.text
    except Exception as e:
        return f"Pipeline connection error. Ensure Rhino Flask server is running on port 5050. Details: {e}"

# ---------------------------------------------------------------------------
# 1. CORE EXECUTION TOOL
# ---------------------------------------------------------------------------

@mcp.tool()
def run_rhino_python(code: str) -> str:
    """
    Executes raw Python 3 geometry logic in Rhino using rhinoscriptsyntax.
    Use this when explicitly instructed to generate or manipulate 3D form.
    """
    return execute_in_rhino(code)

# ---------------------------------------------------------------------------
# 2. ZERO-TRUST JANITOR & CLEANUP
# ---------------------------------------------------------------------------

@mcp.tool()
def run_zero_trust_cleanup() -> str:
    """
    Runs a zero-trust automated sanitation routine on the active Rhino document.
    Call this when the user asks to clean up, sort, or organize a messy CAD file.
    """
    rhino_script = '''
import rhinoscriptsyntax as rs

def zero_trust_janitor():
    rs.EnableRedraw(False)
    
    # Setup Standard Layers
    layers = {"K_Curves": (0,0,255), "K_Surfaces": (255,0,0), "K_Meshes": (0,255,0), "K_Broken_Geometry": (255,165,0)}
    for name, color in layers.items():
        if not rs.IsLayer(name):
            rs.AddLayer(name, color)
            
    all_objs = rs.AllObjects()
    if not all_objs: return "Model is empty."
    
    moved, deleted = 0, 0
    for obj in all_objs:
        if rs.IsCurve(obj):
            if rs.CurveLength(obj) < 1.0:
                rs.DeleteObject(obj)
                deleted += 1
            elif not rs.IsCurveClosed(obj) and rs.IsCurvePlanar(obj):
                rs.ObjectLayer(obj, "K_Broken_Geometry")
                moved += 1
            else:
                rs.ObjectLayer(obj, "K_Curves")
                moved += 1
        elif rs.IsSurface(obj) or rs.IsPolysurface(obj):
            rs.ObjectLayer(obj, "K_Surfaces")
            moved += 1
        elif rs.IsMesh(obj):
            rs.ObjectLayer(obj, "K_Meshes")
            moved += 1
            
    rs.EnableRedraw(True)
    return f"Cleanup Complete: Sorted {moved} objects. Purged {deleted} micro-segments."

print(zero_trust_janitor())
'''
    return execute_in_rhino(rhino_script)

# ---------------------------------------------------------------------------
# 3. REVIT-PROOFING & DATA CONDITIONING
# ---------------------------------------------------------------------------

@mcp.tool()
def audit_revit_solids() -> str:
    """
    Scans all polysurfaces to ensure they are closed, manifold solids.
    Use this to prevent open polysurfaces from failing to generate volumes in Revit.
    """
    rhino_script = '''
import rhinoscriptsyntax as rs

def audit_solids():
    rs.EnableRedraw(False)
    error_layer = "K_Revit_OpenSolids"
    if not rs.IsLayer(error_layer): rs.AddLayer(error_layer, (255, 0, 0))
    
    breps = rs.ObjectsByType(16)
    if not breps: return "No polysurfaces found."
    
    failed = 0
    for brep in breps:
        if not rs.IsPolysurfaceClosed(brep):
            rs.ObjectLayer(brep, error_layer)
            failed += 1
            
    rs.EnableRedraw(True)
    return f"Solid Audit: {failed} open polysurfaces isolated to {error_layer}."
    
print(audit_solids())
'''
    return execute_in_rhino(rhino_script)

@mcp.tool()
def assign_rhino_inside_category(revit_category: str) -> str:
    """
    Tags selected Rhino geometry with the 'RevitCategory' parameter (e.g., 'OST_Walls').
    Use this so Rhino.Inside.Revit knows exactly what BIM element category to generate.
    """
    rhino_script = f'''
import rhinoscriptsyntax as rs

def tag_category():
    objs = rs.GetObjects("Select objects for Revit", preselect=True)
    if not objs: return "No objects selected."
    
    for obj in objs:
        rs.SetUserText(obj, "RevitCategory", "{revit_category}")
        
    return f"Successfully tagged {{len(objs)}} objects as {revit_category}."
    
print(tag_category())
'''
    return execute_in_rhino(rhino_script)

@mcp.tool()
def enforce_revit_tolerances() -> str:
    """
    Verifies document is in millimeters and isolates invalid geometry objects.
    Use this to prevent scaling errors and API crashes during Revit import.
    """
    rhino_script = '''
import rhinoscriptsyntax as rs

def check_tolerances():
    report = []
    
    if rs.UnitSystem() != 2:
        report.append("CRITICAL: Document is NOT in millimeters. Revit scale will fail.")
    else:
        report.append("Units: Millimeters (Pass)")
        
    bad_objs = [obj for obj in rs.AllObjects() if not rs.IsObjectValid(obj)]
    if bad_objs:
        bad_layer = "K_Revit_BadObjects"
        if not rs.IsLayer(bad_layer): rs.AddLayer(bad_layer, (255, 100, 100))
        for b in bad_objs: rs.ObjectLayer(b, bad_layer)
        report.append(f"Found {len(bad_objs)} invalid objects. Moved to {bad_layer}.")
    else:
        report.append("Geometry Validity: All clear (Pass)")
        
    return "\\n".join(report)

print(check_tolerances())
'''
    return execute_in_rhino(rhino_script)

# ---------------------------------------------------------------------------
# 4. INSPECTION & PIPELINE STRATEGY
# ---------------------------------------------------------------------------

@mcp.tool()
def inspect_rhino_selection() -> str:
    """
    Checks the user's active Rhino selection. Returns object count and types.
    Use this when you need context on what the user has highlighted.
    """
    rhino_script = '''
import rhinoscriptsyntax as rs

def inspect_selection():
    objs = rs.GetObjects("Select", preselect=True)
    if not objs: return "No objects currently selected."
    
    types = {}
    for obj in objs:
        obj_type = rs.ObjectType(obj)
        types[obj_type] = types.get(obj_type, 0) + 1
        
    return f"Selected {len(objs)} objects. Type breakdown: {types}"
    
print(inspect_selection())
'''
    return execute_in_rhino(rhino_script)

@mcp.tool()
def run_rigorous_qaqc() -> str:
    """
    Runs a detailed QA/QC check on selected objects, hunting for naked edges.
    """
    rhino_script = '''
import rhinoscriptsyntax as rs
import scriptcontext as sc

def qaqc():
    objs = rs.GetObjects("Select objects for QA/QC", preselect=True)
    if not objs: return "No objects selected to audit."
    
    naked_edges = 0
    for obj in objs:
        if rs.IsPolysurface(obj):
            brep = rs.coercebrep(obj)
            if brep:
                for edge in brep.Edges:
                    if edge.Valence == Rhino.Geometry.EdgeAdjacency.Naked:
                        naked_edges += 1
                        
    return f"QA/QC Report: Found {naked_edges} naked/open edges in selection."

print(qaqc())
'''
    return execute_in_rhino(rhino_script)

@mcp.tool()
def analyze_geometry_for_revit() -> str:
    """
    Evaluates the active selection and suggests the safest Revit API translation method.
    """
    rhino_script = '''
import rhinoscriptsyntax as rs

def analyze_for_revit():
    objs = rs.GetObjects("Select", preselect=True)
    if not objs: return "No geometry selected to analyze."
    
    meshes, breps, curves = 0, 0, 0
    for obj in objs:
        if rs.IsMesh(obj): meshes += 1
        elif rs.IsPolysurface(obj) or rs.IsSurface(obj): breps += 1
        elif rs.IsCurve(obj): curves += 1
        
    strategy = "Revit Transfer Strategy:\\n"
    if meshes > 0: strategy += "- Meshes detected: Use DirectShape fallback.\\n"
    if breps > 0: strategy += "- Breps detected: Use FreeformElement or Native Family mapping.\\n"
    if curves > 0: strategy += "- Curves detected: Use Model Lines or Adaptive Component rigs.\\n"
    
    return strategy

print(analyze_for_revit())
'''
    return execute_in_rhino(rhino_script)

@mcp.tool()
def scaffold_pyrevit_button() -> str:
    """
    Generates a blank, formatted pyRevit pushbutton template. 
    Returns the string text to the user. No Rhino execution required.
    """
    boilerplate = '''# -*- coding: utf-8 -*-
__title__ = "Custom pyRevit Tool"
__doc__ = """Executes automated Revit API operations."""

from pyrevit import revit, DB, UI

doc = revit.doc
uidoc = revit.uidoc

def main():
    selection = [doc.GetElement(id) for id in uidoc.Selection.GetElementIds()]
    if not selection:
        UI.TaskDialog.Show("Selection Error", "Please select Revit elements.")
        return
        
    with revit.Transaction("Automated Operation"):
        # Custom logic goes here
        pass

if __name__ == "__main__":
    main()
'''
    return f"Provide this boilerplate to the user for their pyRevit .pushbutton folder:\n\n```python\n{boilerplate}\n```"

if __name__ == "__main__":
    # Start the MCP server process
    mcp.run(transport="stdio")
