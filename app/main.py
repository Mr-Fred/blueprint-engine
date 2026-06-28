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
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.utils import FilesystemJail
from app.types import DebateState
from app.agent import app as adk_app, root_agent, ACTIVE_DIRECTIVES, FORCE_SYNTHESIS_FLAGS

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

# In-memory store to track session states of active debates
# maps project_id -> DebateState
DEBATE_SESSIONS: Dict[str, DebateState] = {}

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
        DEBATE_SESSIONS[project_id] = DebateState(
            project_id=project_id,
            concept=req.concept,
        )
        
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
            
            # Restore state if not loaded
            if pid not in DEBATE_SESSIONS:
                state_file = item / "state.json"
                if state_file.exists():
                    try:
                        state_data = json.loads(state_file.read_text(encoding="utf-8"))
                        DEBATE_SESSIONS[pid] = DebateState.model_validate(state_data)
                    except Exception:
                        pass
                else:
                    # Older project fallback
                    prd_file = item / "PRD.md"
                    arch_file = item / "ARCHITECTURE.md"
                    if prd_file.exists() or arch_file.exists():
                        DEBATE_SESSIONS[pid] = DebateState(
                            project_id=pid,
                            concept="Restored Project",
                            consensus_achieved=True,
                            final_prd=prd_file.read_text(encoding="utf-8") if prd_file.exists() else None,
                            final_architecture=arch_file.read_text(encoding="utf-8") if arch_file.exists() else None,
                        )
            
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
    """
    GET /api/projects/{project_id}/stream: Streams the live turn-by-turn multi-agent debate.
    Ensures non-blocking async generator iterations.
    """
    if project_id not in DEBATE_SESSIONS:
        raise HTTPException(status_code=404, detail="Project not found")
        
    session_state = DEBATE_SESSIONS[project_id]
    
    async def sse_generator():
        session_service = InMemorySessionService()
        # Use async session creation to align with standard async execution
        session = await session_service.create_session(user_id="judge", app_name="mad_engine")
        runner = Runner(agent=root_agent, session_service=session_service, app_name="mad_engine")
        
        # Ingest project_id and concept inside initial node payload
        initial_input = {
            "project_id": project_id,
            "concept": session_state.concept
        }
        
        message = types.Content(
            role="user", 
            parts=[types.Part.from_text(text=json.dumps(initial_input))]
        )
        
        try:
            # Use run_async to loop natively and async-safely without blocking the event loop
            async for event in runner.run_async(
                new_message=message,
                user_id="judge",
                session_id=session.id,
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            ):
                yield f"data: {event.model_dump_json()}\n\n"
                await asyncio.sleep(0.01)
                
            # Send dynamic final complete message
            final_state = DEBATE_SESSIONS.get(project_id)
            if final_state:
                yield f"data: {{\"event_type\": \"COMPLETE\", \"state\": {final_state.model_dump_json()}}}\n\n"
                
        except Exception as e:
            yield f"data: {{\"event_type\": \"ERROR\", \"message\": \"{str(e)}\"}}\n\n"
            
    return StreamingResponse(sse_generator(), media_type="text/event-stream")

class InterveneRequest(BaseModel):
    directive: str = Field(..., description="The judge directive feedback to inject")

@app.post("/api/projects/{project_id}/intervene")
async def intervene(project_id: str, req: InterveneRequest):
    """
    POST /api/projects/{project_id}/intervene: Publishes a dynamic human feedback directive.
    """
    if project_id not in DEBATE_SESSIONS:
        raise HTTPException(status_code=404, detail="Project not found")
        
    ACTIVE_DIRECTIVES[project_id] = req.directive
    return {"status": "queued", "directive": req.directive}

@app.post("/api/projects/{project_id}/force-synthesis")
async def force_synthesis(project_id: str):
    """
    POST /api/projects/{project_id}/force-synthesis: Triggers immediate compilation of PRD & Architecture.
    """
    if project_id not in DEBATE_SESSIONS:
        raise HTTPException(status_code=404, detail="Project not found")
        
    FORCE_SYNTHESIS_FLAGS[project_id] = True
    return {"status": "triggered"}

@app.get("/api/projects/{project_id}/state", response_model=DebateState)
async def get_project_state(project_id: str):
    """
    GET /api/projects/{project_id}/state: Fetches current debate rounds history and final files.
    """
    if project_id not in DEBATE_SESSIONS:
        raise HTTPException(status_code=404, detail="Project not found")
        
    return DEBATE_SESSIONS[project_id]
