import os
import uuid
import asyncio
import json
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.adk.events.request_input import RequestInput
from google.genai import types

from app.utils import FilesystemJail
from app.types import DebateState, DebateRound
from app.agent import root_agent

app = FastAPI(
    title="MAD Engine (Multi-Agent Architect Debate System)",
    description="Interactive 3-agent software blueprint and design debate system powered by ADK 2.0.",
    version="2.0.0"
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Set to specific origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory stores
DEBATE_SESSIONS: Dict[str, DebateState] = {}
PROJECT_SESSIONS: Dict[str, str] = {}
GLOBAL_SESSION_SERVICE = DatabaseSessionService(db_url="sqlite+aiosqlite:///.agents/sessions.db")

def sync_debate_state_from_event(project_id: str, event: Any):
    """Helper to maintain separation of concerns: updates global state from emitted ADK events."""
    event_dict = event.model_dump() if hasattr(event, "model_dump") else getattr(event, "__dict__", {})
    state_update = event_dict.get("state")
    
    if state_update and isinstance(state_update, dict) and project_id in DEBATE_SESSIONS:
        current_round = state_update.get("current_round", 1)
        rounds = []
        for i in range(1, current_round):
            try:
                round_data = FilesystemJail.read_project_file(project_id, f"round_{i}.json")
                rounds.append(DebateRound.model_validate_json(round_data))
            except Exception:
                pass
        
        DEBATE_SESSIONS[project_id].current_round = state_update.get("current_round", 1)
        DEBATE_SESSIONS[project_id].rounds_history = rounds
        DEBATE_SESSIONS[project_id].consensus_achieved = state_update.get("consensus_achieved", False)
        
        if "final_prd" in state_update:
            DEBATE_SESSIONS[project_id].final_prd = state_update["final_prd"]
        if "final_architecture" in state_update:
            DEBATE_SESSIONS[project_id].final_architecture = state_update["final_architecture"]
            
        if "grill_history" in state_update:
            DEBATE_SESSIONS[project_id].grill_history = state_update["grill_history"]
            
        proposal = state_update.get("temp:latest_proposal") or state_update.get("latest_proposal")
        if proposal:
            DEBATE_SESSIONS[project_id].latest_proposal = proposal
            
        try:
            FilesystemJail.write_project_file(project_id, "state.json", DEBATE_SESSIONS[project_id].model_dump_json())
        except Exception as e:
            logger.error(f"Failed to persist state: {e}")

class ProjectCreateRequest(BaseModel):
    concept: str = Field(..., description="The software concept or idea to debate")

class ProjectCreateResponse(BaseModel):
    project_id: str
    output_dir: str
    status: str

@app.post("/api/projects", response_model=ProjectCreateResponse)
async def create_project(req: ProjectCreateRequest):
    """
    POST /api/projects: Initializes a new project workspace directory and registers session.
    """
    try:
        project_id = f"proj_{uuid.uuid4().hex[:8]}"
        project_dir = FilesystemJail.get_project_dir(project_id)
        
        # Initialize an empty DebateState in our tracking registry
        new_state = DebateState(
            project_id=project_id,
            concept=req.concept,
        )
        DEBATE_SESSIONS[project_id] = new_state
        
        try:
            FilesystemJail.write_project_file(project_id, "state.json", new_state.model_dump_json())
        except Exception as e:
            logger.error(f"Failed to persist initial state: {e}")
        
        return ProjectCreateResponse(
            project_id=project_id,
            output_dir=str(project_dir),
            status="initialized"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize project: {str(e)}")

class ProjectInfoResponse(BaseModel):
    project_id: str
    concept: str
    status: str

def ensure_project_loaded(pid: str):
    if pid in DEBATE_SESSIONS:
        return
    out_dir = FilesystemJail.BASE_OUTPUT_DIR
    item = out_dir / pid
    if not item.exists() or not item.is_dir():
        return
        
    state_file = item / "state.json"
    if state_file.exists():
        try:
            state_data = json.loads(state_file.read_text(encoding="utf-8"))
            DEBATE_SESSIONS[pid] = DebateState.model_validate(state_data)
        except Exception as e:
            print(f"Failed to load project {pid}: {e}")
    else:
        # Older project fallback
        prd_file = item / "PRD.md"
        arch_file = item / "ARCHITECTURE.md"
        
        if prd_file.exists() or arch_file.exists():
            DEBATE_SESSIONS[pid] = DebateState(
                project_id=pid,
                concept="Restored Project (Completed)",
                consensus_achieved=True,
                final_prd=prd_file.read_text(encoding="utf-8") if prd_file.exists() else None,
                final_architecture=arch_file.read_text(encoding="utf-8") if arch_file.exists() else None,
            )
        else:
            # It's an active/suspended project that didn't reach the end before restart
            DEBATE_SESSIONS[pid] = DebateState(
                project_id=pid,
                concept="Restored Project (In Progress)",
                consensus_achieved=False,
            )

@app.get("/api/projects", response_model=List[ProjectInfoResponse])
async def list_projects():
    """
    GET /api/projects: Returns a list of all existing projects, scanning the filesystem and restoring states as needed.
    """
    out_dir = FilesystemJail.BASE_OUTPUT_DIR
    if not out_dir.exists():
        return []
        
    projects = []
    
    # Scan outputs directory
    for item in out_dir.iterdir():
        if item.is_dir() and item.name.startswith("proj_"):
            pid = item.name
            ensure_project_loaded(pid)
            
            if pid in DEBATE_SESSIONS:
                state = DEBATE_SESSIONS[pid]
                status = "completed" if state.consensus_achieved else "active"
                projects.append(ProjectInfoResponse(
                    project_id=pid,
                    concept=state.concept,
                    status=status
                ))
    
    # Sort projects in reverse order roughly to show newest first
    projects.sort(key=lambda x: x.project_id, reverse=True)
    return projects

@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """
    DELETE /api/projects/{project_id}: Deletes the project directory and removes it from session state.
    """
    try:
        FilesystemJail.delete_project_dir(project_id)
        if project_id in DEBATE_SESSIONS:
            del DEBATE_SESSIONS[project_id]
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")



@app.get("/api/projects/{project_id}/stream")
async def stream_debate(project_id: str):
    ensure_project_loaded(project_id)
    """
    GET /api/projects/{project_id}/stream: Streams the live turn-by-turn multi-agent debate.
    Ensures non-blocking async generator iterations.
    """
    ensure_project_loaded(project_id)
    if project_id not in DEBATE_SESSIONS:
        raise HTTPException(status_code=404, detail="Project not found")
        
    session_state = DEBATE_SESSIONS[project_id]
    
    async def sse_generator():
        try:
            session = await GLOBAL_SESSION_SERVICE.get_session(session_id=project_id)
        except Exception:
            session = None
            
        if not session:
            session = await GLOBAL_SESSION_SERVICE.create_session(
                user_id="judge", 
                app_name="mad_engine",
                session_id=project_id,
                state=session_state.model_dump()
            )
        PROJECT_SESSIONS[project_id] = session.id
        runner = Runner(agent=root_agent, session_service=GLOBAL_SESSION_SERVICE, app_name="mad_engine")
        
        initial_input = {
            "project_id": project_id,
            "concept": session_state.concept
        }
        
        message = types.Content(
            role="user", 
            parts=[types.Part.from_text(text=json.dumps(initial_input))]
        )
        
        try:
            is_suspended = False
            async for event in runner.run_async(new_message=message, user_id="judge",
                session_id=session.id, 
                run_config=RunConfig(streaming_mode=StreamingMode.SSE)
                ):
                
                is_req_input = False
                if getattr(event, "content", None) and event.content.parts:
                    for part in event.content.parts:
                        fc = getattr(part, "function_call", None)
                        if fc and getattr(fc, "name", None) == "adk_request_input":
                            is_req_input = True
                            is_suspended = True
                            req_args = getattr(fc, "args", {}) or {}
                            if not isinstance(req_args, dict):
                                req_args = dict(req_args)
                            
                            payload = req_args.get("payload") or {}
                            message_desc = req_args.get("message") or "Awaiting input"
                            name = payload.get("name", "input") if isinstance(payload, dict) else "input"
                            
                            req_data = {
                                "request_input": {
                                    "name": name,
                                    "description": message_desc
                                }
                            }
                            yield f"data: {json.dumps(req_data)}\n\n"
                            break

                if not is_req_input:
                    sync_debate_state_from_event(project_id, event)
                    yield f"data: {event.model_dump_json()}\n\n"
                await asyncio.sleep(0.05)  # Small delay to prevent overwhelming the frontend with data
                
            # Send dynamic final complete message or suspended message
            final_state = DEBATE_SESSIONS.get(project_id)
            if is_suspended:
                if final_state:
                    yield f"data: {{\"event_type\": \"SUSPENDED\", \"state\": {final_state.model_dump_json()}}}\n\n"
            else:
                if final_state:
                    yield f"data: {{\"event_type\": \"COMPLETE\", \"state\": {final_state.model_dump_json()}}}\n\n"
                
        except Exception as e:
            yield f"data: {{\"event_type\": \"ERROR\", \"message\": \"{str(e)}\"}}\n\n"
            
    return StreamingResponse(sse_generator(), media_type="text/event-stream")

class ResumeRequest(BaseModel):
    input_name: str = Field(..., description="The name of the RequestInput (e.g., 'grill_question' or 'judge_review')")
    user_response: str = Field(..., description="The human text input")

@app.get("/api/projects/{project_id}/resume_stream")
async def resume_stream(project_id: str):
    ensure_project_loaded(project_id)
    """
    GET /api/projects/{project_id}/resume_stream: Reconnects to a paused ADK graph stream without sending new input.
    """
    ensure_project_loaded(project_id)
    if project_id not in DEBATE_SESSIONS:
        raise HTTPException(status_code=404, detail="Project not found")
        
    session_state = DEBATE_SESSIONS[project_id]
        
    async def sse_generator():
        try:
            session = await GLOBAL_SESSION_SERVICE.get_session(session_id=project_id)
        except Exception:
            session = None
            
        if not session:
            session = await GLOBAL_SESSION_SERVICE.create_session(
                user_id="judge", 
                app_name="mad_engine",
                session_id=project_id,
                state=session_state.model_dump()
            )
        runner = Runner(agent=root_agent, session_service=GLOBAL_SESSION_SERVICE, app_name="mad_engine")
        
        try:
            is_suspended = False
            async for event in runner.run_async(
                user_id="judge",
                session_id=project_id, 
                run_config=RunConfig(streaming_mode=StreamingMode.SSE)
            ):
                is_req_input = False
                if getattr(event, "content", None) and event.content.parts:
                    for part in event.content.parts:
                        fc = getattr(part, "function_call", None)
                        if fc and getattr(fc, "name", None) == "adk_request_input":
                            is_req_input = True
                            is_suspended = True
                            req_args = getattr(fc, "args", {}) or {}
                            if not isinstance(req_args, dict):
                                req_args = dict(req_args)
                            
                            payload = req_args.get("payload") or {}
                            message_desc = req_args.get("message") or "Awaiting input"
                            name = payload.get("name", "input") if isinstance(payload, dict) else "input"
                            
                            req_data = {
                                "request_input": {
                                    "name": name,
                                    "description": message_desc
                                }
                            }
                            yield f"data: {json.dumps(req_data)}\n\n"
                            break

                if not is_req_input:
                    sync_debate_state_from_event(project_id, event)
                    yield f"data: {event.model_dump_json()}\n\n"
                await asyncio.sleep(0.05)
                
            final_state = DEBATE_SESSIONS.get(project_id)
            if is_suspended:
                if final_state:
                    yield f"data: {{\"event_type\": \"SUSPENDED\", \"state\": {final_state.model_dump_json()}}}\n\n"
            else:
                if final_state:
                    yield f"data: {{\"event_type\": \"COMPLETE\", \"state\": {final_state.model_dump_json()}}}\n\n"
                
        except Exception as e:
            yield f"data: {{\"event_type\": \"ERROR\", \"message\": \"{str(e)}\"}}\n\n"
            
    return StreamingResponse(sse_generator(), media_type="text/event-stream")

@app.post("/api/projects/{project_id}/resume")
async def resume_debate(project_id: str, req: ResumeRequest):
    ensure_project_loaded(project_id)
    """
    POST /api/projects/{project_id}/resume: Resumes a paused ADK graph and streams the continuing debate.
    """
    ensure_project_loaded(project_id)
    if project_id not in DEBATE_SESSIONS:
        raise HTTPException(status_code=404, detail="Project not found")
        
    session_id = project_id
        
    async def sse_generator():
        runner = Runner(agent=root_agent, session_service=GLOBAL_SESSION_SERVICE, app_name="mad_engine")
        resume_payload = {req.input_name: req.user_response}
        
        try:
            is_suspended = False
            message = types.Content(
                role="user", 
                parts=[types.Part.from_text(text=json.dumps(resume_payload))]
            )
            
            async for event in runner.run_async(
                new_message=message,
                user_id="judge",
                session_id=session_id,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE)
            ):
                is_req_input = False
                if getattr(event, "content", None) and event.content.parts:
                    for part in event.content.parts:
                        fc = getattr(part, "function_call", None)
                        if fc and getattr(fc, "name", None) == "adk_request_input":
                            is_req_input = True
                            is_suspended = True
                            req_args = getattr(fc, "args", {}) or {}
                            if not isinstance(req_args, dict):
                                req_args = dict(req_args)
                            
                            payload = req_args.get("payload") or {}
                            message_desc = req_args.get("message") or "Awaiting input"
                            name = payload.get("name", "input") if isinstance(payload, dict) else "input"
                            
                            req_data = {
                                "request_input": {
                                    "name": name,
                                    "description": message_desc
                                }
                            }
                            yield f"data: {json.dumps(req_data)}\n\n"
                            break

                if not is_req_input:
                    sync_debate_state_from_event(project_id, event)
                    yield f"data: {event.model_dump_json()}\n\n"
                await asyncio.sleep(0.05)
                
            final_state = DEBATE_SESSIONS.get(project_id)
            if is_suspended:
                if final_state:
                    yield f"data: {{\"event_type\": \"SUSPENDED\", \"state\": {final_state.model_dump_json()}}}\n\n"
            else:
                if final_state:
                    yield f"data: {{\"event_type\": \"COMPLETE\", \"state\": {final_state.model_dump_json()}}}\n\n"
                
        except Exception as e:
            yield f"data: {{\"event_type\": \"ERROR\", \"message\": \"{str(e)}\"}}\n\n"
            
    return StreamingResponse(sse_generator(), media_type="text/event-stream")

@app.get("/api/projects/{project_id}/state", response_model=DebateState)
async def get_project_state(project_id: str):
    """
    GET /api/projects/{project_id}/state: Fetches current debate rounds history and final files.
    """
    ensure_project_loaded(project_id)
    if project_id not in DEBATE_SESSIONS:
        raise HTTPException(status_code=404, detail="Project not found")
        
    return DEBATE_SESSIONS[project_id]
