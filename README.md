# Agent Orchestra

A multi-agent orchestration system for building, validating, and marketing SaaS/micro-SaaS products. An orchestrator agent manages specialized agents that work in parallel with handoffs, checkpoints for human approval, and shared context.

## Architecture

```
                    ┌─────────────────┐
                    │   Orchestrator   │
                    │  (Gemini 2.5 Pro)│
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
     ┌──────▼──────┐  ┌─────▼──────┐  ┌──────▼──────┐
     │   Research   │  │ Competitive │  │    Pre-     │
     │  Researcher  │  │  Analyst    │  │ Validation  │
     │(Gemini 2.5)  │  │(Gemini 2.5) │  │(Gemini 2.5) │
     └─────────────┘  └────────────┘  └─────────────┘
            │                │                │
            └────────────────┼────────────────┘
                             │ ← Checkpoint (User Approval)
            ┌────────────────┼────────────────┐
            │                │                │
     ┌──────▼──────┐  ┌─────▼──────┐  ┌──────▼──────┐
     │   Senior     │  │  Marketing  │  │    Lead     │
     │  Developer   │  │ Strategist  │  │ Generation  │
     │ (Kimi K2.5)  │  │(Kimi K2.5)  │  │(Kimi K2.5)  │
     └─────────────┘  └────────────┘  └─────────────┘
```

## Agents

| Agent | Model | Role |
|-------|-------|------|
| Orchestrator | Gemini 2.5 Pro | Task decomposition, coordination, review |
| Market Researcher | Gemini 2.5 Pro | Pain point discovery, trend analysis |
| Competitive Analyst | Gemini 2.5 Pro | Competitor analysis, gap identification |
| Pre-validation | Gemini 2.5 Pro | Idea validation, demand analysis |
| Senior Developer | Kimi K2.5 | Prototype building, code generation |
| Marketing Strategist | Kimi K2.5 | Go-to-market, content strategy |
| Lead Generation | Kimi K2.5 | Customer acquisition, outreach |

## Features

- **Parallel Execution**: Agents work simultaneously when tasks are independent
- **Human-in-the-Loop**: Checkpoints for user approval at key decision points
- **Agent Handoffs**: Output from one agent feeds into another's context
- **Skills System**: Each agent loads role-specific skills from SKILL.md files
- **Real-time Streaming**: SSE-based live progress updates
- **Tool Integration**: Web search, web scraping, code execution, data analysis

## Setup

### Prerequisites
- Python 3.11+
- Poetry

### Installation

```bash
# Clone the repository
git clone https://github.com/ALPHA0008/agent-orchestra.git
cd agent-orchestra

# Install dependencies
poetry install

# Copy environment variables
cp .env.example .env
# Edit .env with your API keys
```

### Configuration

Edit `.env` with your API keys:

```env
GOOGLE_AI_STUDIO_API_KEY=your_google_ai_studio_key
OPENROUTER_API_KEY=your_openrouter_key
```

### Running

```bash
# Start the FastAPI backend
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# In a separate terminal, start the Streamlit dashboard
poetry run streamlit run dashboard/app.py --server.port 8501
```

### API Endpoints

- `POST /api/tasks` - Submit a new task
- `GET /api/tasks/{id}` - Get task status and results
- `POST /api/tasks/{id}/approve` - Approve a checkpoint
- `GET /api/tasks/{id}/stream` - SSE stream for real-time updates
- `GET /api/agents` - List all agents

## Workflow

1. **Submit a task** → Orchestrator decomposes it into sub-tasks
2. **Research Phase** → Market Researcher + Competitive Analyst work in parallel
3. **Checkpoint** → You review research and approve
4. **Validation Phase** → Pre-validation agent assesses feasibility
5. **Checkpoint** → You review validation and approve
6. **Build & Market Phase** → Developer + Marketing + Lead Gen work in parallel
7. **Final Review** → Orchestrator compiles all results

## Skills

Each agent has role-specific skills loaded from `skills/` directory. Skills follow the [skills.sh](https://skills.sh) open standard.

## License

MIT
