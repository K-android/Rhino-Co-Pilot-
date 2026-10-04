"""
EXPERIMENTAL PROOF OF CONCEPT
AI-generated code executes locally with current user permissions via exec().
Review generated operations before execution and test ONLY on non-production copies.
"""

import sys
import asyncio
import base64
import os
import re
import uuid
import tempfile
import mimetypes
import httpx
import gradio as gr
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

# --- GLOBAL STATE & PERSISTENT MEMORY ---
agent = None
current_api_key = None
current_active_mode = None
current_engine_choice = None
current_target_model = None
global_memory = MemorySaver()
THREAD_CONFIG = {"configurable": {"thread_id": f"rhino_copilot_{uuid.uuid4().hex[:8]}"}}
last_generated_code = "# No custom geometry logic generated yet.\nimport rhinoscriptsyntax as rs\n"

def encode_image(file_path: str):
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "image/png" if file_path.lower().endswith(".png") else "image/jpeg"
    with open(file_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return mime_type, encoded

async def init_agent(
    api_key_override: str = "", 
    current_mode: str = "🎨 Form & Model", 
    engine_choice: str = "Groq Cloud Engine", 
    gemini_model: str = "gemini-1.5-flash", 
    groq_model: str = "openai/gpt-oss-120b", 
    local_model: str = "qwen2.5-coder:7b"
):
    global agent, current_api_key, current_active_mode, current_engine_choice, current_target_model, global_memory
    
    active_model_target = groq_model
    if engine_choice == "Gemini Cloud Engine":
        active_model_target = gemini_model
    elif engine_choice == "Local Network Engine":
        active_model_target = local_model
    
    needs_reinit = (
        (agent is None) or 
        (api_key_override and api_key_override != current_api_key) or 
        (current_mode != current_active_mode) or
        (engine_choice != current_engine_choice) or
        (active_model_target != current_target_model)
    )
    
    if needs_reinit:
        print(f"[Rhino Co-Pilot] Engine: {engine_choice} | Mode: {current_mode} | Target: {active_model_target}")
        current_api_key = api_key_override if api_key_override else None
        current_active_mode = current_mode
        current_engine_choice = engine_choice
        current_target_model = active_model_target
        
        client = MultiServerMCPClient({
            "rhino_copilot": {
                "command": sys.executable,
                "args": ["copilot_mcp.py"],
                "transport": "stdio"
            }
        })
        tools = await client.get_tools()
        
        # --- LLM ROUTING MECHANISM ---
        if engine_choice == "Local Network Engine":
            try:
                from langchain_ollama import ChatOllama
                llm = ChatOllama(
                    model=active_model_target,
                    temperature=0,
                    base_url="http://localhost:11434"
                )
            except ImportError:
                raise RuntimeError("Local engine selected but `langchain-ollama` is not installed. Run `pip install langchain-ollama`.")
                
        elif engine_choice == "Groq Cloud Engine":
            if not current_api_key:
                raise ValueError("Groq Engine requires an API key in the sidebar.")
            try:
                from langchain_groq import ChatGroq
                llm = ChatGroq(
                    model=active_model_target,
                    api_key=current_api_key,
                    temperature=0
                )
            except ImportError:
                raise RuntimeError("Groq engine selected but `langchain-groq` is not installed. Run `pip install langchain-groq`.")
                
        else:  # Gemini Cloud Engine
            if not current_api_key:
                raise ValueError("Gemini Engine requires an API key in the sidebar.")
            llm_kwargs = {"model": active_model_target}
            if current_api_key:
                llm_kwargs["api_key"] = current_api_key
            llm = ChatGoogleGenerativeAI(**llm_kwargs)
        
        # --- TOKEN-CONSERVATION & GATEKEEPER SYSTEM PROMPTS ---
        base_prompt = (
            "You are Rhino Co-Pilot, an expert computational automation engine for Rhino 8 and Revit.\n\n"
            "STRICT TOKEN & TOOL DISCIPLINE RULES:\n"
            "1. CONVERSATIONAL GATEKEEPER: If the user message is a greeting, casual remark, or general question, RESPOND DIRECTLY WITH CONCISE TEXT. NEVER CALL ANY TOOL.\n"
            "2. EXPLICIT TRIGGER ONLY: NEVER invoke any tool unless the user explicitly requests an action on CAD geometry, document inspection, or QA/QC audit.\n"
            "3. NO RECURSIVE RETRY LOOPS: If a tool returns an error, DO NOT attempt to call another tool to fix it. Immediately explain the error directly to the user in text and ask for guidance.\n"
            "4. NO REDUNDANT SELECTION CHECKS: Do not invoke `inspect_rhino_selection` unless strictly required.\n"
            "5. GEOMETRY API ENFORCEMENT: For any custom geometry script, you MUST strictly use `rhinoscriptsyntax`. DO NOT use raw `RhinoCommon`.\n\n"
        )
        
        if current_mode == "🎨 Form & Model":
            mode_rules = (
                "MODE: GENERATION & MODELING\n"
                "1. When requested to generate geometry, write the complete Python logic using `rhinoscriptsyntax` and invoke `run_rhino_python`.\n"
                "2. Do not dump raw Python script blocks in conversational chat if executing the tool.\n"
                "3. All model units must strictly respect millimeters (mm).\n"
            )
        elif current_mode == "🔍 QA/QC Audit":
            mode_rules = (
                "MODE: INSPECTION & VALIDATION\n"
                "1. If requested to organize or purge bad lines, use `run_zero_trust_cleanup`.\n"
                "2. If requested to check for open edges, use `run_rigorous_qaqc`.\n"
                "3. Report findings succinctly and wait for instructions.\n"
            )
        else:  # 🚀 Pipeline Transfer
            mode_rules = (
                "MODE: DATA PIPELINE & EXPORT (REVIT-PROOFING)\n"
                "1. To prep geometry for Revit, ALWAYS run `enforce_revit_tolerances` first to check units.\n"
                "2. If transferring polysurfaces, run `audit_revit_solids` to isolate open geometry that will fail volume generation.\n"
                "3. To tag geometry for Rhino.Inside.Revit, use `assign_rhino_inside_category`.\n"
                "4. If asked for a pyRevit template, invoke `scaffold_pyrevit_button`.\n"
            )
        
        system_prompt = base_prompt + mode_rules
        agent = create_react_agent(llm, tools, prompt=system_prompt, checkpointer=global_memory)
        print("[Rhino Co-Pilot] Core Agent initialized with Revit-proofing tool stack.")

async def predict(message, history, api_key_input, mode_selection, engine_selection, gemini_selection, groq_selection, local_selection):
    global last_generated_code
    
    if engine_selection in ["Groq Cloud Engine", "Gemini Cloud Engine"] and not api_key_input:
        yield f"⚠️ **System Alert:** {engine_selection} selected, but no API key provided. Please enter your key in the Connection Protocol sidebar."
        return
        
    await init_agent(api_key_input, mode_selection, engine_selection, gemini_selection, groq_selection, local_selection)
    
    text_prompt = message.get("text", "")
    files = message.get("files", [])
    
    content_payload = []
    if text_prompt:
        content_payload.append({"type": "text", "text": text_prompt})
        
    for file_path in files:
        if os.path.exists(file_path):
            mime_type, b64_img = encode_image(file_path)
            content_payload.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{b64_img}"}
            })
            
    if not content_payload:
        yield "System idle. Awaiting design directive or CAD viewport capture."
        return

    user_content = content_payload if files else text_prompt
    response = ""
    yield f"Processing via {current_target_model}..."
    
    try:
        run_config = {
            "configurable": {"thread_id": THREAD_CONFIG["configurable"]["thread_id"]},
            "recursion_limit": 6
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
                
                # Intercept code blocks accidentally printed in chat
                code_matches = re.findall(r"```(?:python)?\s*(.*?)\s*```", response, re.DOTALL)
                if code_matches:
                    last_generated_code = code_matches[-1].strip()
                    
                # Intercept custom geometry code from the run_rhino_python tool payload
                agent_message = chunk["agent"]["messages"][-1]
                if hasattr(agent_message, 'tool_calls') and agent_message.tool_calls:
                    for tc in agent_message.tool_calls:
                        if tc['name'] == 'run_rhino_python':
                            last_generated_code = tc['args'].get('code', last_generated_code)

                if response.strip():
                    yield response
                    
            elif "tools" in chunk:
                tool_msg = chunk["tools"]["messages"][0]
                yield response + f"\n\n[System] Invoking tool: `{tool_msg.name}`...\n"
                
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            yield response + "\n\n⚠️ **System Alert - Quota Exhausted:** API quota limit reached. Switch engines or provide a new key in the sidebar."
        elif "GRAPH_RECURSION_LIMIT" in error_msg or "recursion limit" in error_msg.lower():
            yield response + "\n\n⚠️ **Safety Interruption:** Execution loop cut off to save tokens. Clarify the prompt or run 'Clear Memory Buffer'."
        else:
            yield response + f"\n\n[Error] Pipeline failure: {error_msg}"

def capture_rhino_viewport():
    try:
        res = httpx.get("http://localhost:5050/capture_viewport", timeout=5.0)
        data = res.json()
        if data.get("status") == "success":
            img_bytes = base64.b64decode(data["image"])
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp.write(img_bytes)
            tmp.close()
            return {"text": "Evaluate this viewport capture. Check for topology errors or open edges.", "files": [tmp.name]}
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
    """Generates a new LangGraph thread ID and clears the visual script buffer."""
    global THREAD_CONFIG, last_generated_code, global_memory
    THREAD_CONFIG = {"configurable": {"thread_id": f"rhino_copilot_{uuid.uuid4().hex[:8]}"}}
    last_generated_code = "# Session reset.\nimport rhinoscriptsyntax as rs\n"
    return "# Active session memory flushed. Model context cleared.", None

def update_mode_header(mode):
    colors = {
        "🎨 Form & Model": "#3b82f6",
        "🔍 QA/QC Audit": "#10b981",
        "🚀 Pipeline Transfer": "#8b5cf6"
    }
    color = colors.get(mode, "#ffffff")
    return f"<h3 style='color: {color}; margin-bottom: 0px;'>Active System State: {mode}</h3>"

def toggle_model_dropdowns(engine):
    return (
        gr.update(visible=(engine == "Gemini Cloud Engine")),
        gr.update(visible=(engine == "Groq Cloud Engine")),
        gr.update(visible=(engine == "Local Network Engine"))
    )

enterprise_css = """
footer, #footer { visibility: hidden !important; display: none !important; }
body, .gradio-container { background-color: #121212 !important; font-family: 'Inter', -apple-system, system-ui, sans-serif !important; color: #e0e0e0 !important; }
.gr-sidebar, .sidebar { background-color: #1a1a1a !important; border-right: 1px solid #333 !important; }
.gr-panel, .gr-box, .gr-accordion { background-color: #1e1e1e !important; border: 1px solid #333 !important; border-radius: 4px !important; box-shadow: none !important; }
button.primary, .gr-button-primary { background-color: #2563eb !important; color: #ffffff !important; border: 1px solid #1d4ed8 !important; border-radius: 4px !important; font-weight: 500 !important; }
button.secondary, .gr-button-secondary { background-color: #2a2a2a !important; color: #d4d4d4 !important; border: 1px solid #404040 !important; border-radius: 4px !important; }
.message.user { background-color: #1e293b !important; border-left: 3px solid #3b82f6; border-radius: 2px !important; }
.message.bot { background-color: #1a1a1a !important; border-left: 3px solid #10b981; border-radius: 2px !important; }
input, textarea { background-color: #2a2a2a !important; border: 1px solid #404040 !important; color: #fff !important; }
.gr-radio { background-color: #1e1e1e !important; border: 1px solid #333 !important; border-radius: 8px !important; padding: 10px !important;}
.safety-warning { background-color: #2d1810; border: 1px solid #b45309; border-radius: 4px; padding: 8px; font-size: 0.75rem; color: #fde68a; margin-bottom: 12px; }
"""

custom_theme = gr.themes.Monochrome(font=[gr.themes.GoogleFont("Inter"), "sans-serif"])

with gr.Blocks(title="Rhino Co-Pilot", fill_height=True) as demo:
    with gr.Row():
        with gr.Sidebar():
            gr.Markdown("## ⚙ Rhino Co-Pilot")
            gr.Markdown("<p style='color: #888; font-size: 0.85rem; margin-top: -10px;'>Computational Automation Bridge</p>")
            
            gr.HTML("""
            <div class='safety-warning'>
                <strong>⚠ Experimental POC</strong><br>
                Executes generated code locally via user permissions. Test only on non-production models.
            </div>
            """)
            
            with gr.Accordion("Connection Protocol", open=True):
                api_key_box = gr.Textbox(label="Cloud API Key", placeholder="Enter Groq or Gemini Key...", type="password")
                
                engine_dropdown = gr.Dropdown(
                    choices=["Gemini Cloud Engine", "Groq Cloud Engine", "Local Network Engine"], 
                    value="Groq Cloud Engine", 
                    label="Neural Routing", 
                    interactive=True
                )
                
                gemini_model_dropdown = gr.Dropdown(
                    choices=["gemini-1.5-pro", "gemini-1.5-flash"],
                    value="gemini-1.5-flash",
                    label="Gemini Model Target",
                    visible=False,
                    interactive=True
                )
                
                groq_model_dropdown = gr.Dropdown(
                    choices=[
                        "llama-3.3-70b-versatile", 
                        "llama-3.1-8b-instant", 
                        "openai/gpt-oss-120b", 
                        "openai/gpt-oss-20b",
                        "qwen/qwen3.8-27b"
                    ],
                    value="openai/gpt-oss-120b",
                    label="Groq Model Target",
                    visible=True,
                    interactive=True
                )
                
                local_model_dropdown = gr.Dropdown(
                    choices=["qwen2.5-coder:7b", "llama3.1:8b", "mistral:7b"],
                    value="qwen2.5-coder:7b",
                    label="Ollama Model Target",
                    visible=False,
                    interactive=True
                )
                
                engine_dropdown.change(
                    fn=toggle_model_dropdowns,
                    inputs=engine_dropdown,
                    outputs=[gemini_model_dropdown, groq_model_dropdown, local_model_dropdown]
                )
            
            with gr.Accordion("Document Parameters", open=True):
                gr.Markdown("**Ports:** 5050 (Rhino) / 5051 (Revit)<br>**Runtime:** CPython 3<br>**Units:** Millimeters (mm)")
                
            gr.Markdown("### Automation Tools")
            snap_btn = gr.Button("Capture Active Viewport", variant="primary")
            audit_btn = gr.Button("Run Selection Inspection", variant="secondary")
            reset_btn = gr.Button("Clear Memory Buffer", variant="secondary")

        with gr.Column():
            with gr.Tabs():
                with gr.TabItem("Terminal Chat"):
                    mode_header = gr.HTML("<h3 style='color: #3b82f6; margin-bottom: 0px;'>Active System State: 🎨 Form & Model</h3>")
                    
                    mode_selector = gr.Radio(
                        choices=["🎨 Form & Model", "🔍 QA/QC Audit", "🚀 Pipeline Transfer"],
                        value="🎨 Form & Model",
                        label="Computational Mode Override",
                        interactive=True
                    )
                    
                    chat_box = gr.MultimodalTextbox(
                        placeholder="Define parametric layout, attach a diagram, or capture the viewport...",
                        container=True,
                        scale=7
                    )
                    
                    chat = gr.ChatInterface(
                        fn=predict,
                        additional_inputs=[
                            api_key_box, 
                            mode_selector, 
                            engine_dropdown, 
                            gemini_model_dropdown, 
                            groq_model_dropdown, 
                            local_model_dropdown
                        ],
                        multimodal=True,
                        textbox=chat_box,
                        fill_height=True
                    )
                
                with gr.TabItem("Script Extraction"):
                    gr.Markdown("### Algorithm Buffer")
                    gr.Markdown("Python 3 routines generated during the active session are stored here. Export as a standalone `.py` file for team workflow integration.")
                    
                    script_review = gr.Code(language="python", value=last_generated_code, lines=20, interactive=True, label="Active Script Buffer")
                    
                    with gr.Row():
                        refresh_code_btn = gr.Button("Refresh Buffer", variant="secondary")
                        export_file_btn = gr.DownloadButton("Export .py Module", variant="primary")

            reset_btn.click(fn=reset_session, outputs=[script_review, chat.chatbot])
            
            mode_selector.change(fn=update_mode_header, inputs=mode_selector, outputs=mode_header)
            snap_btn.click(fn=capture_rhino_viewport, outputs=chat_box)
            audit_btn.click(lambda: {"text": "Inspect the active selection in Rhino and summarize the object count and types.", "files": []}, outputs=chat_box)
            refresh_code_btn.click(fn=get_latest_script, outputs=script_review)
            export_file_btn.click(fn=export_script_file, outputs=export_file_btn)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    demo.launch(inbrowser=True, theme=custom_theme, css=enterprise_css)
