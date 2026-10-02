import sys
import asyncio
import base64
import os
import re
import uuid
import tempfile
import httpx
import gradio as gr
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

# --- GLOBAL STATE & MEMORY ---
agent = None
current_api_key = None
current_active_mode = None
THREAD_CONFIG = {"configurable": {"thread_id": f"rhino_copilot_{uuid.uuid4().hex[:8]}"}}
last_generated_code = "# No custom geometry logic generated yet.\nimport rhinoscriptsyntax as rs\n"

def encode_image(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

async def init_agent(api_key_override: str = "", current_mode: str = "🎨 Form & Model"):
    global agent, current_api_key, current_active_mode
    
    # Re-initialize the agent if the API key OR the Mode changes
    needs_reinit = (agent is None) or (api_key_override and api_key_override != current_api_key) or (current_mode != current_active_mode)
    
    if needs_reinit:
        print(f"[Rhino Co-Pilot] Initializing / Shifting to mode: {current_mode}")
        current_api_key = api_key_override if api_key_override else None
        current_active_mode = current_mode
        
        client = MultiServerMCPClient({
            "rhino_copilot": {
                "command": sys.executable,
                "args": ["copilot_mcp.py"],
                "transport": "stdio"
            }
        })
        tools = await client.get_tools()
        
        llm_kwargs = {"model": "gemini-3.6-flash"}
        if current_api_key:
            llm_kwargs["api_key"] = current_api_key
            
        llm = ChatGoogleGenerativeAI(**llm_kwargs)
        
        # --- DYNAMIC SYSTEM PROMPTS ---
        base_prompt = "You are Rhino Co-Pilot, an expert computational design assistant inside Rhino 8.\n"
        
        if current_mode == "🎨 Form & Model":
            mode_rules = (
                "MODE: GENERATION & MODELING\n"
                "1. Focus strictly on executing Python 3 geometry using `run_rhino_python`.\n"
                "2. Ensure all coordinates and dimensions are strictly in millimeters (mm).\n"
                "3. DO NOT bake text into the Rhino viewport for communication. Only model geometry.\n"
                "4. Be proactive. After successfully generating geometry, always end your response by asking a logical follow-up design question.\n"
            )
        elif current_mode == "🔍 QA/QC Audit":
            mode_rules = (
                "MODE: INSPECTION & VALIDATION\n"
                "1. DO NOT model new geometry. Your sole job is to inspect the active viewport or selection.\n"
                "2. Check for inverted normals, open boundaries, or millimeter tolerance deviations.\n"
                "3. Report findings clearly in the chat text. Do not bake text into Rhino.\n"
                "4. Context-Aware Fallbacks: If the viewport or selection is empty, respond casually (e.g., 'The viewport is empty. What are we cooking up today?').\n"
            )
        else: # 🚀 Pipeline Transfer
            mode_rules = (
                "MODE: DATA PIPELINE & EXPORT\n"
                "1. Focus on transitioning Rhino logic into Revit-ready automation and data handoffs.\n"
                "2. If asked how to transfer or strategize an export, immediately run `analyze_geometry_for_revit` to read the topology and suggest DirectShape vs. Native Elements based on the results.\n"
                "3. If asked to directly push geometry to Revit, first use `run_rhino_python` to extract exact millimeter coordinates from Rhino, then instantly use `run_revit_python` to generate the native Revit elements using the DB.Transaction API.\n"
                "4. If asked to build a pyRevit script, format the Python logic and use the `scaffold_pyrevit_button` tool.\n"
                "5. Report success in the chat interface and ask if the user wants to adjust any transfer parameters.\n"
            )
        
        system_prompt = base_prompt + mode_rules
        memory = MemorySaver()
        agent = create_react_agent(llm, tools, prompt=system_prompt, checkpointer=memory)
        print("[Rhino Co-Pilot] Core Agent initialized successfully.")

async def predict(message, history, api_key_input, mode_selection):
    global last_generated_code
    await init_agent(api_key_input, mode_selection)
    
    text_prompt = message.get("text", "")
    files = message.get("files", [])
    
    content_payload = []
    if text_prompt:
        content_payload.append({"type": "text", "text": text_prompt})
        
    for file_path in files:
        if os.path.exists(file_path):
            b64_img = encode_image(file_path)
            content_payload.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
            })
            
    if not content_payload:
        yield "System idle. Awaiting design directive or CAD viewport capture."
        return

    user_content = content_payload if files else text_prompt
    response = ""
    yield f"Analyzing active document parameters in {mode_selection} mode..."
    
    try:
        # Strict recursion limit to prevent infinite loops and quota drains
        run_config = {
            "configurable": {"thread_id": THREAD_CONFIG["configurable"]["thread_id"]},
            "recursion_limit": 5 
        }

        async for chunk in agent.astream(
            {"messages": [HumanMessage(content=user_content)]},
            config=run_config
        ):
            if "agent" in chunk:
                msg = chunk["agent"]["messages"][-1].content
                if isinstance(msg, list):
                    text_delta = "".join([part.get("text", "") for part in msg if isinstance(part, dict)])
                    response += text_delta
                else:
                    response += str(msg)
                
                # Extract Python logic for the Script Pipeline tab
                code_matches = re.findall(r"```(?:python)?\s*(.*?)\s*```", response, re.DOTALL)
                if code_matches:
                    last_generated_code = code_matches[-1].strip()
                
                if response.strip():
                    yield response
                    
            elif "tools" in chunk:
                tool_msg = chunk["tools"]["messages"][0]
                yield response + f"\n\n[System] Invoking local port connection: `{tool_msg.name}`...\n"
                
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            yield response + "\n\n⚠️ **System Alert - Quota Exhausted:** My API limits have been reached for this key. Please insert a secondary Google API Key into the 'Connection Protocol' sidebar on the left and submit your prompt again to continue."
        else:
            yield response + f"\n\n[Error] Pipeline failure: {error_msg}"

def capture_rhino_viewport():
    """Captures the active Rhino viewport buffer via localhost port 5050."""
    try:
        res = httpx.get("http://localhost:5050/capture_viewport", timeout=5.0)
        data = res.json()
        if data.get("status") == "success":
            img_bytes = base64.b64decode(data["image"])
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp.write(img_bytes)
            tmp.close()
            return {"text": "Evaluate this geometry block. Report open edges, tolerance violations, or unclosed surfaces.", "files": [tmp.name]}
    except Exception as e:
        print(f"Viewport capture error: {e}")
    return {"text": "", "files": []}

def get_latest_script() -> str:
    return last_generated_code

def export_script_file() -> str:
    export_path = os.path.join(tempfile.gettempdir(), "rhino_ai_automation.py")
    with open(export_path, "w", encoding="utf-8") as f:
        f.write(last_generated_code)
    return export_path

def reset_session():
    """Clears LangGraph memory thread and resets active script buffer."""
    global THREAD_CONFIG, last_generated_code
    THREAD_CONFIG = {"configurable": {"thread_id": f"rhino_copilot_{uuid.uuid4().hex[:8]}"}}
    last_generated_code = "# Session reset.\nimport rhinoscriptsyntax as rs\n"
    return "# Active session memory flushed. Model context cleared."

def update_mode_header(mode):
    """Dynamically colors the UI indicator based on active mode."""
    colors = {
        "🎨 Form & Model": "#3b82f6",  # Blue
        "🔍 QA/QC Audit": "#10b981",   # Green
        "🚀 Pipeline Transfer": "#8b5cf6" # Purple
    }
    color = colors.get(mode, "#ffffff")
    return f"<h3 style='color: {color}; margin-bottom: 0px;'>Active System State: {mode}</h3>"


# --- ENTERPRISE SOFTWARE STYLING ---
enterprise_css = """
footer, #footer { visibility: hidden !important; display: none !important; }
body, .gradio-container { background-color: #121212 !important; font-family: 'Inter', -apple-system, system-ui, sans-serif !important; color: #e0e0e0 !important; }
.gr-sidebar, .sidebar { background-color: #1a1a1a !important; border-right: 1px solid #333 !important; }
.gr-panel, .gr-box, .gr-accordion { background-color: #1e1e1e !important; border: 1px solid #333 !important; border-radius: 4px !important; box-shadow: none !important; }
button.primary, .gr-button-primary { background-color: #2563eb !important; color: #ffffff !important; border: 1px solid #1d4ed8 !important; border-radius: 4px !important; font-weight: 500 !important; transition: background-color 0.15s ease !important; }
button.primary:hover, .gr-button-primary:hover { background-color: #1d4ed8 !important; box-shadow: none !important; transform: none !important; }
button.secondary, .gr-button-secondary { background-color: #2a2a2a !important; color: #d4d4d4 !important; border: 1px solid #404040 !important; border-radius: 4px !important; }
button.secondary:hover, .gr-button-secondary:hover { background-color: #333333 !important; color: #ffffff !important; }
.message.user { background-color: #1e293b !important; border-left: 3px solid #3b82f6; border-radius: 2px !important; }
.message.bot { background-color: #1a1a1a !important; border-left: 3px solid #10b981; border-radius: 2px !important; }
input, textarea { background-color: #2a2a2a !important; border: 1px solid #404040 !important; color: #fff !important; }
.gr-radio { background-color: #1e1e1e !important; border: 1px solid #333 !important; border-radius: 8px !important; padding: 10px !important;}
"""

custom_theme = gr.themes.Monochrome(font=[gr.themes.GoogleFont("Inter"), "sans-serif"])

# --- UI APPLICATION ---
with gr.Blocks(title="Rhino Co-Pilot", fill_height=True) as demo:
    
    with gr.Row():
        with gr.Sidebar():
            gr.Markdown("## ⚙️ Rhino Co-Pilot")
            gr.Markdown("<p style='color: #888; font-size: 0.85rem; margin-top: -10px;'>Computational Automation Bridge</p>")
            gr.Markdown("---")
            
            with gr.Accordion("Connection Protocol", open=True):
                api_key_box = gr.Textbox(label="Google API Key", placeholder="Enter secondary key to bypass limit...", type="password")
                engine_dropdown = gr.Dropdown(choices=["Gemini 3.6 Flash", "Local Network Engine"], value="Gemini 3.6 Flash", label="Neural Routing", interactive=True)
            
            with gr.Accordion("Document Parameters", open=True):
                gr.Markdown("**Port Status:** 5050 (Rhino) / 5051 (Revit)<br>**Target CAD:** Rhino 8 / Revit (CPython 3)<br>**Global Units:** Millimeters (mm)")
                
            gr.Markdown("### Automation Tools")
            snap_btn = gr.Button("Capture Active Viewport", variant="primary")
            audit_btn = gr.Button("Run QA/QC Inspection", variant="secondary")
            reset_btn = gr.Button("Clear Memory Buffer", variant="secondary")

        with gr.Column():
            with gr.Tabs():
                with gr.TabItem("Terminal Chat"):
                    
                    # Visual Mode Header
                    mode_header = gr.HTML("<h3 style='color: #3b82f6; margin-bottom: 0px;'>Active System State: 🎨 Form & Model</h3>")
                    
                    # The Gear Shifter
                    mode_selector = gr.Radio(
                        choices=["🎨 Form & Model", "🔍 QA/QC Audit", "🚀 Pipeline Transfer"],
                        value="🎨 Form & Model",
                        label="Computational Mode Override",
                        interactive=True
                    )
                    
                    chat_box = gr.MultimodalTextbox(
                        placeholder="Define parametric layout, attach a structural diagram, or capture the viewport...",
                        container=True,
                        scale=7
                    )
                    
                    chat = gr.ChatInterface(
                        fn=predict,
                        additional_inputs=[api_key_box, mode_selector],
                        multimodal=True,
                        textbox=chat_box,
                        fill_height=True,
                        examples=[
                            [{"text": "Array structural panels using a UV domain marching algorithm with strict 15 mm reveal gaps."}, "", "🎨 Form & Model"],
                            [{"text": "Evaluate the selected mesh for manifold violations or inverted normals."}, "", "🔍 QA/QC Audit"],
                            [{"text": "How should we transfer this complex canopy geometry to Revit?"}, "", "🚀 Pipeline Transfer"]
                        ]
                    )
                
                with gr.TabItem("Script Extraction"):
                    gr.Markdown("### Algorithm Buffer")
                    gr.Markdown("Python 3 routines generated during the active session are stored here. Export as a standalone `.py` file for integration into team pyRevit or Grasshopper workflows.")
                    
                    script_review = gr.Code(language="python", value=last_generated_code, lines=20, interactive=True, label="Active Script Buffer")
                    
                    with gr.Row():
                        refresh_code_btn = gr.Button("Refresh Buffer", variant="secondary")
                        export_file_btn = gr.DownloadButton("Export .py Module", variant="primary")

            # --- EVENT BINDINGS ---
            # Update the visual header instantly when the user clicks a new mode
            mode_selector.change(fn=update_mode_header, inputs=mode_selector, outputs=mode_header)
            
            snap_btn.click(fn=capture_rhino_viewport, outputs=chat_box)
            audit_btn.click(lambda: {"text": "Perform a rigorous QA/QC inspection on all selected geometry.", "files": []}, outputs=chat_box)
            reset_btn.click(fn=reset_session, outputs=script_review)
            refresh_code_btn.click(fn=get_latest_script, outputs=script_review)
            export_file_btn.click(fn=export_script_file, outputs=export_file_btn)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    demo.launch(inbrowser=True, theme=custom_theme, css=enterprise_css)
