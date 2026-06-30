# MAD Engine - Multi-Agent Self-Correcting Software Architect Debate

Capstone Project for the 5-Day AI Agents: Intensive Vibe Coding Course With Google

The **MAD Engine** (Multi-Agent Architect Debate System) is an interactive, real-time software blueprint and design debate system powered by the Agent Development Kit (ADK) 2.0. This project serves as a capstone to demonstrate the knowledge and skills gained during the Intensive Vibe Coding Course and applies them to a real-world use case.

## Key Concepts Demonstrated

This project showcases several advanced AI integration patterns and concepts learned during the course:

1. **Multi-Agent Systems built with ADK 2.0**
   - The core engine uses `google.adk.workflow.Workflow` to orchestrate a debate between three specialized AI architects: Performance, Security, and DevOps.
   - We utilize asynchronous streaming (`StreamingMode.SSE`) and parallel node executions (`JoinNode`) to evaluate complex architectural trade-offs.

2. **Security & Sandboxing Features**
   - **FilesystemJail:** Implements rigorous filesystem sandboxing (`app/utils.py`). All project output generation is strictly contained within designated, per-project jails to prevent path traversal and unauthorized data access.

3. **Human-in-the-Loop & Dynamic Directives**
   - A real-time `Interactions API` allows humans to inject feedback ("Judge Directives") while the agents are actively debating and designing, ensuring human oversight over AI processes.

4. **Extensibility for MCP Servers & Skills**
   - The architecture is built with modularity in mind. Agents can easily be augmented with Model Context Protocol (MCP) tools and independent agent skills to query external documentation, run security audits on real-time codebases, or fetch cloud pricing dynamically.

## Technology Stack

- **Backend Framework**: Python FastAPI
- **Agent Orchestration**: Google Agent Development Kit (ADK) 2.0
- **AI Models**: Google Gemini / Vertex AI (via `google-genai` SDK)
- **Frontend Framework**: Next.js (React, TypeScript, Tailwind CSS)
- **Real-Time Communication**: Server-Sent Events (SSE) for incremental stream parsing

---

## Onboarding for Developers

Follow these instructions to get the project running locally on your machine.

### Prerequisites

- **Node.js** (v18+)
- **Python** (v3.10+)
- **uv** (Fast Python package installer)

### 1. Backend Setup (FastAPI & ADK)

Navigate to the project root and start the FastAPI server:

```bash
# Navigate to the project root
cd blueprint-engine

# The project uses `uv` for running the uvicorn server directly with dependencies.
# Start the backend server on port 8000
uv run uvicorn app.main:app --reload --port 8000
```

> **Note on Environment Variables:** Ensure that you have configured your environment for Google Vertex AI or Gemini APIs (e.g. configuring Application Default Credentials).

### 2. Frontend Setup (Next.js)

Open a second terminal window, navigate to the `frontend` directory, and start the development server:

```bash
# Navigate to the frontend directory
cd blueprint-engine/frontend

# Install node dependencies
npm install

# Start the Next.js development server
npm run dev
```

The frontend will be accessible at `http://localhost:3000`.

---

## Usage Guide

1. **Launch a Project:** Head to the UI and type in a complex software concept (e.g. "Build an end-to-end encrypted messaging engine") or select a suggested topic.
2. **Watch the Debate:** The dashboard will spawn three AI agents (Performance, Security, DevOps) that debate the concept. The live feed streams their responses incrementally.
3. **Intervene:** Use the input field at the bottom of the stream to inject Judge Directives and steer the debate.
4. **Synthesis:** Once consensus is achieved (or forced), the system compiles and saves a `PRD.md` and `ARCHITECTURE.md` into the strictly jailed `outputs/` folder.
5. **Persistence:** The system restores past sessions automatically on load. You can review compiled documents or delete old sessions directly from the Active Registry sidebar.

---

*This project is designed to bridge cutting-edge Agentic workflows with production-grade engineering principles, illustrating how modern tools like Google ADK 2.0 can revolutionize software design.*
