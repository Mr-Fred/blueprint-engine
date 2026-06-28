# Project Customizations and Guidelines

## Agent Architecture and Geometry

For all agentic systems in this project (and all future projects built under this framework), enforce the following modular code boundary directory structure strictly:

```
app/agents/[agent_role]/
├── agent.py         # Node generator execution logic (async generators, tools, etc.)
├── prompt.py        # System instructions and prompt templates (isolated per role)
├── skills/          # Custom skills specifically assigned to this agent role
└── references/      # Documentation, context, schemas, and reference material for the role
```

### Architectural Constraints
1. **Self-Contained Roles**: No prompt variables, execution states, or role instructions may cross folder boundaries. Each agent's functional boundary must be entirely contained within its subdirectory.
2. **Asynchronous Engines**: All agent nodes must use modern asynchronous generation (`aio` endpoints) to avoid event-loop starvation or freezing of streams.
3. **Strict Validation**: Graph states and scoring configurations must follow structured schemas with clear boundaries.
