# Social Media Article Generator (LangGraph + PostgreSQL)
 
A length-limited social-media article generator built with [LangGraph](https://langchain-ai.github.io/langgraph/). The workflow researches a topic, plans a structure, and writes an article — with every step checkpointed to PostgreSQL under a thread ID, so runs can be inspected, resumed, or audited after the fact.
 
---
 
## Architecture
 
The graph is a linear pipeline with three bounded validation/retry loops. Each stage has a worker node and a validator node; a conditional edge either advances the article to the next stage or sends it back for another attempt, capped at 3 attempts per stage.
 
```
START
  │
  ▼
researcher ──► validate_research ──┬──► planner (if ok / attempts ≥ 3)
  ▲                                 │
  └─────────────── retry ───────────┘
                                    │
                                    ▼
planner ──► validate_outline ──────┬──► writer (if ok / attempts ≥ 3)
  ▲                                 │
  └─────────────── retry ───────────┘
                                    │
                                    ▼
writer ──► validate_article ───────┬──► END (if ok / attempts ≥ 3)
  ▲                                 │
  └─────────────── retry ───────────┘
```
 
### Node responsibilities
 
| Node | Role | State keys written |
|---|---|---|
| `researcher` | Searches the topic via Tavily, structures results into Markdown | `research`, `research_attempts` |
| `validate_research` | Checks research has 3 results, titles, snippets, and a summary | `research_validation` |
| `planner` | Builds an outline (intro, 3 sections with bullets, conclusion) from research | `outline`, `outline_attempts` |
| `validate_outline` | Checks the outline has intro, 2–3 sections, and a conclusion | `outline_validation` |
| `writer` | Drafts the article from the outline, targeting ~90% of the word limit | `article`, `article_attempts` |
| `validate_article` | Rewrites for coherence and trims to a complete sentence within the word limit | `article`, `article_validation` |
 
Every stage's retry loop is bounded at **3 attempts** to prevent infinite loops if the model never returns `"ok"`.
 
---
 
## Prerequisites
 
- Python 3.10+
- An OpenAI API key (used via `langchain_openai.ChatOpenAI`, model: `gpt-4o-mini`)
- A Tavily API key (used via `TavilySearchResults`)
- A running PostgreSQL instance (local or hosted)
---
 
## Installation
 
```bash
git clone <your-repo-url>
cd <your-repo-directory>
 
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
 
pip install langgraph langchain-openai langchain-community langgraph-checkpoint-postgres python-dotenv
```
 
---
 
## Configuration
 
### 1. Environment variables
 
Create a `.env` file in the project root:
 
```
OPENAI_API_KEY=your_openai_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
```
 
> **Never commit `.env`.** Add it to `.gitignore` before your first commit.
 
### 2. Database connection — action required
 
The script currently hardcodes a placeholder connection string:
 
```python
DB_URI = "postgresql://username:password@localhost:5432/database_name"
```
 
**Before running this in any shared or public context, move this to an environment variable:**
 
```python
DB_URI = os.environ["DATABASE_URL"]
```
 
And add to `.env`:
```
DATABASE_URL=postgresql://username:password@localhost:5432/database_name
```
 
This is flagged in the source as a security TODO — credentials should never live in source code, especially before pushing to GitHub.
 
### 3. Create the database
 
```bash
createdb database_name
```
 
The first run automatically creates the required checkpoint tables and indexes via `checkpointer.setup()`.
 
---
 
## Usage
 
### Run interactively
 
```bash
python agent.py
```
 
You'll be prompted for a topic:
 
```
Enter a topic: The rise of AI agents in enterprise software, within 300 words
```
 
The script extracts the word limit from your input (defaults to 500 if none is specified) and prints:
- The generated thread ID
- Number of stored checkpoints
- The final article
- The latest stored state
- Full checkpoint history (newest first)
### Use programmatically
 
```python
from agent import generate_article
 
result, config, latest_state, state_history = generate_article(
    "Why most RAG implementations fail in production, within 400 words"
)
 
print(result["article"])
print(config["configurable"]["thread_id"])
```
 
### Resume a previous thread
 
Pass an existing `thread_id` to continue or re-inspect a prior run:
 
```python
generate_article("Same or follow-up topic", thread_id="existing-thread-id")
```
 
---
 
## How the word limit works
 
- `extract_word_limit()` looks for a pattern like `"within 200 words"` in the topic string; falls back to **500 words** if not found.
- The `writer` node targets ~90% of the limit to leave headroom for the final edit pass.
- The `validate_article` node rewrites the draft for coherence and calls `fit_complete_word_limit()`, which trims to the limit **without cutting a sentence mid-way** — it backs up to the last complete sentence boundary instead.
---
 
## Project structure
 
```
.
├── agent.py          # Graph definition, nodes, and CLI entry point
├── .env              # API keys and DB connection string (not committed)
├── .gitignore
└── README.md
```
 
---
 
## Key design decisions
 
**Why PostgreSQL checkpointing?**
`PostgresSaver` persists every state transition under a `thread_id`, so a run's full history — including intermediate research, outlines, and retries — can be audited or resumed later, rather than living only in memory for the duration of the script.
 
**Why bounded retries instead of unlimited?**
Each stage has an `*_attempts` counter capped at 3. Without this, a validator that never returns `"ok"` would loop forever. `recursion_limit: 30` in the graph config is a second safety net against routing bugs.
 
**Why a separate rewrite pass in `validate_article`?**
Rather than just checking pass/fail, `validate_article` actively rewrites the draft for coherence and enforces the word limit by trimming to the last complete sentence — so the "validation" step also improves the output, not just gates it.
