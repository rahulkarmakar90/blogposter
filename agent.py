#Research, plan, and write a length-limited social-media article.

#The workflow uses LangGraph to coordinate specialized nodes and PostgreSQL to
#persist every graph checkpoint under a thread ID.


import os
import re
from uuid import uuid4
from typing import TypedDict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import StateGraph, START, END

load_dotenv()

# A deterministic model makes retries and validation more predictable.
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0,
    timeout=60,
    max_retries=2,
)

# Tavily supplies a small set of current sources for the research node.
search = TavilySearchResults(max_results=3)



# Shared graph state

class BlogState(TypedDict, total=False):
    """Values produced and consumed as an article moves through the graph."""

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


def extract_word_limit(user_input: str, default: int = 500) -> int:
    """Read a phrase such as 'within 200 words', falling back to a default."""

    match = re.search(r"(\d+)\s*words?", user_input, re.IGNORECASE)
    return max(1, int(match.group(1))) if match else default


def fit_complete_word_limit(text: str, word_limit: int) -> str:
    """Keep text within the limit without leaving a partial final sentence."""

    words = list(re.finditer(r"\S+", text))
    if len(words) <= word_limit:
        return text.strip()

    # Restrict the candidate to the word limit, then back up to the last
    # complete sentence instead of cutting a sentence in the middle.
    candidate = text[:words[word_limit - 1].end()].rstrip()
    sentence_ends = list(re.finditer(r"[.!?](?=\s|$)", candidate))

    if sentence_ends:
        return candidate[:sentence_ends[-1].end()].rstrip()

    return candidate



# Research stage

def researcher(state: BlogState):
    """Search the topic and turn the raw results into structured research."""

    topic = state["topic"]

    results = search.invoke(topic)

    prompt = f"""
You are a content researcher.

Topic:
{topic}

Search Results:
{results}

Generate:
- 3 search results with titles and snippets
- Summary of findings

Return Markdown only.
"""

    response = llm.invoke(prompt)

    return {
        "research": response.content,
        "research_attempts": state.get("research_attempts", 0) + 1
    }


def validate_research(state: BlogState):
    """Ask the model whether the research contains all required components."""

    prompt = f"""
Check if the following contains:

- 3 search results
- titles
- snippets
- summary

Reply ONLY:
ok
or
retry
"""

    response = llm.invoke(prompt + state["research"])

    return {
        "research_validation": response.content.lower()
    }

def route_research(state: BlogState):
    """Advance valid research or retry, with a three-attempt safety limit."""

    if (
        state["research_validation"].strip() == "ok"
        or state.get("research_attempts", 0) >= 3
    ):
        return "planner"

    return "researcher"



# Planning stage

def planner(state: BlogState):
    """Convert validated research into a structured article outline."""

    prompt = f"""
You are a content strategist. Based on this research:

{state["research"]}

Create:
- Intro
- 3 sections
- bullets
- conclusion

Markdown only.
"""

    response = llm.invoke(prompt)

    return {
        "outline": response.content,
        "outline_attempts": state.get("outline_attempts", 0) + 1
    }


def validate_outline(state: BlogState):
    """Check that the generated outline has the expected article structure."""

    prompt = f"""
Check if outline contains:
- intro
- 2-3 sections
- conclusion

Reply ONLY:
ok
or
retry
"""

    response = llm.invoke(prompt + state["outline"])

    return {
        "outline_validation": response.content.lower()
    }


def route_outline(state: BlogState):
    """Send a valid outline to the writer or retry the planner safely."""

    if (
        state["outline_validation"].strip() == "ok"
        or state.get("outline_attempts", 0) >= 3
    ):
        return "writer"

    return "planner"



# Writing and final editing stage

def writer(state: BlogState):
    """Draft an article from the outline, leaving room below the word limit."""

    word_limit = state["word_limit"]
    draft_target = max(1, int(word_limit * 0.9))

    retry_feedback = state.get("article_validation", "")

    prompt = f"""
    
    Write an article worthy of social media from this outline.

    Guidelines:

    - Audience believes hype and fear mongering
    - sensational hooks
    - fear of missing out
    - focus on WHY
    - Aim for approximately {draft_target} words
    - Finish every sentence and do not exceed {word_limit} words
    - Headings and bullet points count toward the word limit

    Outline:

    {state["outline"]}

    Feedback from a previous attempt:
    {retry_feedback}

    Return Markdown only.
    """

    response = llm.invoke(prompt)

    return {
        "article": response.content,
        "article_attempts": state.get("article_attempts", 0) + 1
    }

def validate_article(state: BlogState):
    """Rewrite for coherence, then enforce a complete ending within the limit."""

    article = state["article"]
    word_limit = state["word_limit"]

    prompt = f"""
Rewrite the draft below as a complete, coherent LinkedIn article of no more
than {word_limit} words. Aim for about {max(1, int(word_limit * 0.9))} words,
preserve the main message, and end with a complete conclusion.
Return only the article in Markdown, without a fenced code block.

Draft:
{article}
"""

    edited_article = llm.invoke(prompt).content
    article = fit_complete_word_limit(edited_article, word_limit)
    validation = "ok"

    return {
        "article": article,
        "article_validation": validation
    }


def route_article(state: BlogState):
    """Finish a valid article or return it to the writer when necessary."""

    if (
        state["article_validation"].strip() == "ok"
        or state.get("article_attempts", 0) >= 3
    ):
        return END

    return "writer"



# Graph construction

graph = StateGraph(BlogState)

# Register each processing and validation function as a graph node.
graph.add_node("researcher", researcher)
graph.add_node("validate_research", validate_research)

graph.add_node("planner", planner)
graph.add_node("validate_outline", validate_outline)

graph.add_node("writer", writer)
graph.add_node("validate_article", validate_article)

# Define the workflow entry point and the first validation step.
graph.add_edge(START, "researcher")
graph.add_edge("researcher", "validate_research")

# Conditional edges implement the bounded validation/retry loops.
graph.add_conditional_edges(
    "validate_research",
    route_research,
    {
        "planner": "planner",
        "researcher": "researcher"
    }
)

graph.add_edge("planner", "validate_outline")

graph.add_conditional_edges(
    "validate_outline",
    route_outline,
    {
        "writer": "writer",
        "planner": "planner"
    }
)

graph.add_edge("writer", "validate_article")

graph.add_conditional_edges(
    "validate_article",
    route_article,
    {
        END: END,
        "writer": "writer"
    }
)


def compile_graph_with_checkpointer(checkpointer):
    """Compile the graph with a persistence backend supplied by the caller."""

    return graph.compile(checkpointer=checkpointer)



# PostgreSQL persistence and command-line entry point

# SECURITY: replace this local development URI with an environment variable
# before publishing the project; credentials should never live in source code.
DB_URI = "postgresql://admin:admin@localhost:5432/checkpoint_practice"

with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    # Creates the checkpoint tables and indexes on the first run.
    checkpointer.setup()

    workflow_checkpointed = compile_graph_with_checkpointer(checkpointer)

    def generate_article(topic: str, thread_id: str | None = None):
        """Run the workflow and return its result plus persisted state history."""

        # A caller can reuse a thread ID; otherwise each article gets a new one.
        thread_id = thread_id or str(uuid4())
        config = {
            "configurable": {"thread_id": thread_id},
            # Prevent an unexpected routing bug from looping forever.
            "recursion_limit": 30
        }

        result = workflow_checkpointed.invoke(
            {
                "topic": topic,
                "word_limit": extract_word_limit(topic)
            },
            config
        )

        if result.get("article_validation") != "ok":
            raise RuntimeError(result["article_validation"])

        # Read PostgreSQL-backed checkpoints while the saver connection is open.
        latest_state = workflow_checkpointed.get_state(config)
        state_history = list(workflow_checkpointed.get_state_history(config))

        return result, config, latest_state, state_history


    # Run the interactive interface only when this file is executed directly.
    if __name__ == "__main__":
        topic = input("Enter a topic: ")

        result, config, latest_state, state_history = generate_article(topic)
        thread_id = config["configurable"]["thread_id"]

        print(f"\nThread ID: {thread_id}")
        print(f"Stored checkpoints: {len(state_history)}")
        print("\nArticle:\n")
        print(result["article"])

        print("\nLatest stored state:")
        print(latest_state.values)

        print("\nCheckpoint history (newest first):")
        for snapshot in state_history:
            print({
                "step": snapshot.metadata.get("step"),
                "next": snapshot.next,
                "values": snapshot.values
            })
            print("-" * 80)
