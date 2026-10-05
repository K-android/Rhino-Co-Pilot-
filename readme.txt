======================================================================
Rhino Co-Pilot: Automation Engine
======================================================================

A locally hosted, context-aware Rhino and Revit automation agent. This system uses a Gradio interface, MCP-based tool routing, multimodal vision input, conversational memory, and AI-generated CAD operations to bridge the interoperability gap between Rhino 8 and Revit. 

By default, the reasoning backend uses the Gemini API, with support for local offline models via Ollama.

----------------------------------------------------------------------
! SECURITY & EXPERIMENTAL POC WARNING
----------------------------------------------------------------------
Experimental proof of concept. AI-generated code executes locally with the current user's permissions via exec(). 
* Do not use on live production models.
* Review all generated operations in the terminal before execution.
* Currently, this system lacks execution approval gating, validation, and sandboxing. Future production versions must implement a strict structured tool allowlist rather than unrestricted exec() injection.

----------------------------------------------------------------------
SYSTEM ARCHITECTURE
----------------------------------------------------------------------
The engine bridges standalone CAD applications through a dual-localhost Flask architecture, coordinated by a LangGraph ReAct agent.

Gradio UI (copilot_client.py)
   |
LangGraph ReAct Agent + MemorySaver
   |
Gemini / Local Ollama (Reasoning & Vision)
   |
FastMCP Tool Server (copilot_mcp.py)
   |-- Rhino Flask bridge (localhost:5050)
   |    |-- Inspect selection
   |    |-- Capture viewport
   |    `-- Execute Rhino Python (rhinoscriptsyntax)
   |
   `-- Revit Flask bridge (localhost:5051)
        `-- Execute Revit Python (Revit API via pyRevit)

----------------------------------------------------------------------
CORE OPERATING MODES
----------------------------------------------------------------------
The Co-Pilot relies on a dynamic gear-shifter pattern to keep the LLM strictly focused on the task at hand without losing conversational memory.

1. Form & Model: Generates parametric geometry and Python 3 algorithms inside Rhino 8. 
2. QA/QC Audit: Evaluates the active viewport and geometry selection for open boundaries, inverted normals, and tolerance deviations.
3. Pipeline Transfer: Analyzes Rhino geometry topology to determine the optimal Rhino.Inside.Revit transfer strategy (Native Elements vs. DirectShape) and dynamically scaffolds ready-to-use pyRevit UI extensions.

----------------------------------------------------------------------
PREREQUISITES
----------------------------------------------------------------------
* OS: Windows 10/11
* CAD: Rhino 8 (CPython 3 support required) & Revit 2024/2025
* Revit Environment: pyRevit installed.
* Python: Python 3.10+
* LLM Engine: A Google Gemini API Key OR Ollama installed locally with qwen2.5-coder:7b.

----------------------------------------------------------------------
INSTALLATION & SETUP
----------------------------------------------------------------------
1. Clone & Install Dependencies
   git clone https://github.com/YOUR_USERNAME/Rhino-Co-Pilot.git
   cd Rhino-Co-Pilot
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt

2. Start the Rhino Bridge (Port 5050)
   * Open Rhino 8.
   * Open the Python 3 Script Editor (_ScriptEditor).
   * Load and run copilot_flask.py.
   * The Rhino listener is now active.

3. Start the Revit Bridge (Port 5051)
   * Install revit_bridge.py as a custom pyRevit Pushbutton in your firm's .extension folder.
   * Click the button in the Revit UI. 
   * The daemon thread will start silently in the background, listening for API transactions.

4. Launch the AI Client
   python copilot_client.py
   * The Gradio interface will automatically open in your browser. Enter your API key in the sidebar (or switch to the Local Network Engine) to begin.

----------------------------------------------------------------------
USAGE WORKFLOW
----------------------------------------------------------------------
1. Contextual Commands: Type natural language commands (e.g., "Array structural panels with a 15mm reveal gap").
2. Vision Integration: Use the "Capture Active Viewport" button to send a screenshot to the AI for spatial evaluation.
3. Selection Awareness: Highlight objects in Rhino and ask the AI to "Inspect my selection" to analyze object types and counts.
4. Script Extraction: Any code generated during the session is logged in the "Script Extraction" tab for manual review and export to a .py file.

----------------------------------------------------------------------
ROADMAP & HARDENING
----------------------------------------------------------------------
[ ] Transition from exec() to structured JSON action allowlists.
[ ] Implement explicit "Approve/Reject" UI prompts before the server executes CAD commands.
[ ] Integrate native Rhino.Inside.Revit (RIR) cross-process memory limits.

----------------------------------------------------------------------
LICENSE
----------------------------------------------------------------------
MIT License. See LICENSE for details.
