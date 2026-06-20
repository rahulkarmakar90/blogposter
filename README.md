AI-Powered LinkedIn Article Generator using LangGraph

An agentic workflow built with LangGraph, LangChain, OpenAI GPT-4o-mini, and Tavily Search that automatically:

1. Researches a topic from the web
2. Validates the research
3. Generates a structured outline
4. Validates the outline
5. Writes a social-media-ready article
6. Polishes the article and enforces a word limit
7. Persists every graph checkpoint to PostgreSQL

The project demonstrates how to build a multi-stage, self-validating AI workflow using LangGraph.

⸻

Workflow

                 START
                   │
                   ▼
          ┌────────────────┐
          │   Researcher   │
          └────────────────┘
                   │
                   ▼
     ┌─────────────────────────┐
     │ Validate Research       │
     └─────────────────────────┘
          │               │
      retry │             │ success
          ▼               ▼
    Researcher      ┌──────────────┐
                    │   Planner    │
                    └──────────────┘
                           │
                           ▼
          ┌────────────────────────┐
          │ Validate Outline       │
          └────────────────────────┘
              │               │
          retry │             │ success
              ▼               ▼
          Planner       ┌─────────────┐
                        │   Writer    │
                        └─────────────┘
                               │
                               ▼
          ┌────────────────────────┐
          │ Validate & Polish      │
          └────────────────────────┘
               │              │
          retry │             │ success
               ▼              ▼
            Writer           END

⸻

Features

* 🔍 Web research using Tavily Search
* 🤖 OpenAI GPT-4o-mini powered generation
* 📋 Automatic outline generation
* ✍️ LinkedIn-style article writing
* ✅ Multi-stage validation
* 🔁 Automatic retries (maximum 3 attempts per stage)
* 📏 Word-limit enforcement
* 💾 PostgreSQL checkpoint persistence
* 🧠 LangGraph state management
* 🔄 Thread-based resumable execution

⸻

Tech Stack

* Python
* LangGraph
* LangChain
* OpenAI API
* Tavily Search API
* PostgreSQL
* python-dotenv

⸻

Installation

Clone the repository:

git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>

Install dependencies:

pip install -r requirements.txt

⸻

Environment Variables

Create a .env file:

OPENAI_API_KEY=your_openai_key
TAVILY_API_KEY=your_tavily_key

⸻

PostgreSQL

Update the connection string:

DB_URI = "postgresql://username:password@localhost:5432/database_name"

The workflow automatically creates the checkpoint tables on first execution.

⸻

Running the Project

python agent.py

Example:

Enter a topic:
Why AI Agents will replace SaaS products within 300 words

The workflow will:

* Research the topic
* Validate research
* Build an outline
* Validate outline
* Generate an article
* Polish the article
* Save every checkpoint to PostgreSQL

⸻

Project Structure

.
├── agent.py
├── .env
├── requirements.txt
└── README.md

⸻

State Schema

The workflow uses a shared LangGraph state:

class BlogState(TypedDict):
    topic: str
    word_limit: int
    research: str
    research_validation: str
    outline: str
    outline_validation: str
    article: str
    article_validation: str
    research_attempts: int
    outline_attempts: int
    article_attempts: int

⸻

Checkpointing

The graph is compiled using a PostgreSQL checkpointer:

workflow = graph.compile(
    checkpointer=checkpointer
)

Each execution stores:

* Intermediate state
* Retry count
* Node outputs
* Execution history
* Thread state

allowing workflows to be resumed or inspected later.

⸻

Example Output

The generated article is:

* Markdown formatted
* Length limited
* Social-media optimized
* Edited for coherence
* Ends with a complete conclusion

⸻

Future Improvements

* LangSmith tracing
* Human-in-the-loop approval
* Streaming generation
* Multi-model routing
* Citation support
* Image generation
* Export to LinkedIn or Medium
* FastAPI/Streamlit UI


⸻

Author

Rahul Karmakar
Built as an experiment in Agentic AI Workflows using LangGraph, LangChain, and OpenAI.