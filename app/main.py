import os
import uuid
import asyncio
import json
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

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
    custom_meta = event_dict.get("custom_metadata") or {}
    state_update = custom_meta.get("state")
    
    if state_update and isinstance(state_update, dict) and project_id in DEBATE_SESSIONS:
        current_round = state_update.get("current_round", 1)
        rounds = []

        raw_history = state_update.get("rounds_history")
        if isinstance(raw_history, list) and len(raw_history) > 0:
            for item in raw_history:
                try:
                    if isinstance(item, dict):
                        rounds.append(DebateRound.model_validate(item))
                    elif isinstance(item, DebateRound):
                        rounds.append(item)
                    elif isinstance(item, str):
                        rounds.append(DebateRound.model_validate_json(item))
                except Exception as e:
                    logger.error(f"Failed parsing round from state_update: {e}")

        if not rounds:
            for i in range(1, current_round):
                try:
                    round_data = FilesystemJail.read_project_file(project_id, f"round_{i}.json")
                    rounds.append(DebateRound.model_validate_json(round_data))
                except Exception:
                    pass
        
        DEBATE_SESSIONS[project_id].current_round = current_round
        if rounds or current_round == 1:
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
    caveman_mode: bool = Field(default=True, description="Whether to enable ultra-compressed caveman communication mode by default")

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
            caveman_mode=req.caveman_mode,
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

def resolve_project_artifacts(pid: str):
    """
    Safely resolves placeholder strings like '[Saved to PRD.md]' or missing fields by reading actual markdown files from disk.
    """
    if pid not in DEBATE_SESSIONS:
        return
    state = DEBATE_SESSIONS[pid]
    try:
        prd_path = FilesystemJail.resolve_jailed_path(pid, "PRD.md")
        arch_path = FilesystemJail.resolve_jailed_path(pid, "ARCHITECTURE.md")
        
        if (state.final_prd == "[Saved to PRD.md]" or not state.final_prd) and prd_path.exists():
            try:
                state.final_prd = prd_path.read_text(encoding="utf-8")
            except Exception as e:
                print(f"Failed reading PRD.md for {pid}: {e}")
                
        if (state.final_architecture == "[Saved to ARCHITECTURE.md]" or not state.final_architecture) and arch_path.exists():
            try:
                state.final_architecture = arch_path.read_text(encoding="utf-8")
            except Exception as e:
                print(f"Failed reading ARCHITECTURE.md for {pid}: {e}")
                
        state.consensus_achieved = prd_path.exists() or arch_path.exists()
    except Exception as e:
        print(f"Failed resolving paths for project {pid}: {e}")

def ensure_project_loaded(pid: str):
    if pid in DEBATE_SESSIONS:
        resolve_project_artifacts(pid)
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
    resolve_project_artifacts(pid)

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
                is_done = state.consensus_achieved or bool(state.final_prd) or bool(state.final_architecture) or (item / "PRD.md").exists() or (item / "ARCHITECTURE.md").exists()
                if is_done:
                    state.consensus_achieved = True
                status = "completed" if is_done else "active"
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



async def stream_adk_events(
    runner: Runner,
    project_id: str,
    message: Optional[types.Content] = None,
):
    """Unified SSE streaming generator that executes ADK Runner and yields enriched SSE frames."""
    try:
        is_suspended = False
        async for event in runner.run_async(
            new_message=message,
            user_id="judge",
            session_id=project_id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
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
                                "description": message_desc,
                            }
                        }
                        yield f"data: {json.dumps(req_data)}\n\n"
                        break

            if not is_req_input:
                sync_debate_state_from_event(project_id, event)

                event_dict = event.model_dump() if hasattr(event, "model_dump") else getattr(event, "__dict__", {})
                agent_name = None
                raw_path = getattr(event, "node_path", None) or event_dict.get("node_path")
                if raw_path:
                    path_str = str(raw_path).lower()
                    if "performance_agent_node" in path_str or "grill_node" in path_str:
                        agent_name = "Performance & Scaling Architect"
                    elif "security_agent_node" in path_str:
                        agent_name = "Security & Resilience Auditor"
                    elif "sre_agent_node" in path_str:
                        agent_name = "SRE & Maintainability Lead"
                    elif "evaluate_and_score_node" in path_str:
                        agent_name = "Master Architect Judge"
                    elif "synthesis_node" in path_str:
                        agent_name = "Synthesizing Final Assets..."

                if agent_name:
                    event_dict["agent_display_name"] = agent_name

                yield f"data: {json.dumps(event_dict)}\n\n"
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


@app.get("/api/projects/{project_id}/stream")
async def stream_debate(project_id: str):
    """
    GET /api/projects/{project_id}/stream: Streams the live turn-by-turn multi-agent debate.
    """
    ensure_project_loaded(project_id)
    if project_id not in DEBATE_SESSIONS:
        raise HTTPException(status_code=404, detail="Project not found")

    session_state = DEBATE_SESSIONS[project_id]

    try:
        session = await GLOBAL_SESSION_SERVICE.get_session(
            app_name="mad_engine",
            user_id="judge",
            session_id=project_id,
        )
    except Exception as e:
        print(f"Failed to get session: {e}")
        session = None

    if not session:
        session = await GLOBAL_SESSION_SERVICE.create_session(
            user_id="judge",
            app_name="mad_engine",
            session_id=project_id,
            state=session_state.model_dump(),
        )
    PROJECT_SESSIONS[project_id] = session.id
    runner = Runner(agent=root_agent, session_service=GLOBAL_SESSION_SERVICE, app_name="mad_engine")

    initial_input = {
        "project_id": project_id,
        "concept": session_state.concept,
        "caveman_mode": session_state.caveman_mode,
    }
    message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=json.dumps(initial_input))],
    )
    return StreamingResponse(stream_adk_events(runner, project_id, message=message), media_type="text/event-stream")


class ResumeRequest(BaseModel):
    input_name: str = Field(..., description="The name of the RequestInput (e.g., 'grill_question' or 'judge_review')")
    user_response: str = Field(..., description="The human text input")


@app.get("/api/projects/{project_id}/resume_stream")
async def resume_stream(project_id: str):
    """
    GET /api/projects/{project_id}/resume_stream: Reconnects to a paused ADK graph stream without sending new input.
    """
    ensure_project_loaded(project_id)
    if project_id not in DEBATE_SESSIONS:
        raise HTTPException(status_code=404, detail="Project not found")

    session_state = DEBATE_SESSIONS[project_id]

    try:
        session = await GLOBAL_SESSION_SERVICE.get_session(
            app_name="mad_engine",
            user_id="judge",
            session_id=project_id,
        )
    except Exception as e:
        print(f"Failed to get session: {e}")
        session = None

    if not session:
        session = await GLOBAL_SESSION_SERVICE.create_session(
            user_id="judge",
            app_name="mad_engine",
            session_id=project_id,
            state=session_state.model_dump(),
        )
    runner = Runner(agent=root_agent, session_service=GLOBAL_SESSION_SERVICE, app_name="mad_engine")
    return StreamingResponse(stream_adk_events(runner, project_id, message=None), media_type="text/event-stream")


@app.post("/api/projects/{project_id}/resume")
async def resume_debate(project_id: str, req: ResumeRequest):
    """
    POST /api/projects/{project_id}/resume: Resumes a paused ADK graph and streams the continuing debate.
    """
    ensure_project_loaded(project_id)
    if project_id not in DEBATE_SESSIONS:
        raise HTTPException(status_code=404, detail="Project not found")

    runner = Runner(agent=root_agent, session_service=GLOBAL_SESSION_SERVICE, app_name="mad_engine")
    resume_payload = {req.input_name: req.user_response}
    message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=json.dumps(resume_payload))],
    )
    return StreamingResponse(stream_adk_events(runner, project_id, message=message), media_type="text/event-stream")

@app.get("/api/projects/{project_id}/state", response_model=DebateState)
async def get_project_state(project_id: str):
    """
    GET /api/projects/{project_id}/state: Fetches current debate rounds history and final files.
    """
    ensure_project_loaded(project_id)
    if project_id not in DEBATE_SESSIONS:
        raise HTTPException(status_code=404, detail="Project not found")
        
    return DEBATE_SESSIONS[project_id]

class ToggleCavemanRequest(BaseModel):
    caveman_mode: bool = Field(..., description="The desired boolean state for caveman mode")

@app.post("/api/projects/{project_id}/toggle-caveman", response_model=DebateState)
async def toggle_caveman_mode(project_id: str, req: ToggleCavemanRequest):
    """
    POST /api/projects/{project_id}/toggle-caveman: Dynamically toggles caveman mode during an ongoing debate.
    """
    ensure_project_loaded(project_id)
    if project_id not in DEBATE_SESSIONS:
        raise HTTPException(status_code=404, detail="Project not found")
        
    DEBATE_SESSIONS[project_id].caveman_mode = req.caveman_mode
    try:
        FilesystemJail.write_project_file(project_id, "state.json", DEBATE_SESSIONS[project_id].model_dump_json())
    except Exception as e:
        logger.error(f"Failed to persist state during caveman toggle: {e}")
        
    return DEBATE_SESSIONS[project_id]
