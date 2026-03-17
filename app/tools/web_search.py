"""Web search tool using DuckDuckGo (free, no API key needed)."""

from __future__ import annotations

from langchain_core.tools import tool


@tool
def web_search(query: str, max_results: int = 10) -> str:
    """Search the web using DuckDuckGo. Returns relevant results for research and analysis.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return (default 10).
    """
    from duckduckgo_search import DDGS

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No results found."

        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"{i}. **{r.get('title', 'No title')}**\n"
                f"   URL: {r.get('href', 'N/A')}\n"
                f"   {r.get('body', 'No description')}\n"
            )
        return "\n".join(formatted)
    except Exception as e:
        return f"Search error: {str(e)}"


@tool
def web_search_news(query: str, max_results: int = 10) -> str:
    """Search for recent news articles using DuckDuckGo News.

    Args:
        query: The news search query string.
        max_results: Maximum number of results to return (default 10).
    """
    from duckduckgo_search import DDGS

    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
        if not results:
            return "No news results found."

        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"{i}. **{r.get('title', 'No title')}**\n"
                f"   Source: {r.get('source', 'N/A')} | Date: {r.get('date', 'N/A')}\n"
                f"   URL: {r.get('url', 'N/A')}\n"
                f"   {r.get('body', 'No description')}\n"
            )
        return "\n".join(formatted)
    except Exception as e:
        return f"News search error: {str(e)}"
