"""Web scraping tool for extracting content from websites."""

from __future__ import annotations

import re

import httpx
from langchain_core.tools import tool


@tool
def scrape_webpage(url: str) -> str:
    """Scrape and extract text content from a webpage.

    Args:
        url: The URL to scrape content from.
    """
    from bs4 import BeautifulSoup

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        }
        response = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Clean up whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Truncate if too long
        if len(text) > 15000:
            text = text[:15000] + "\n\n... [Content truncated]"

        return text if text.strip() else "No text content found on the page."
    except Exception as e:
        return f"Scraping error: {str(e)}"


@tool
def scrape_reddit_posts(subreddit: str, query: str = "", limit: int = 10) -> str:
    """Search Reddit for posts in a subreddit to find user pain points and discussions.

    Args:
        subreddit: The subreddit name (without r/).
        query: Optional search query within the subreddit.
        limit: Maximum number of posts to return.
    """
    try:
        headers = {
            "User-Agent": "AgentOrchestra/1.0 (Research Bot)"
        }

        if query:
            url = f"https://www.reddit.com/r/{subreddit}/search.json?q={query}&restrict_sr=1&limit={limit}&sort=relevance"
        else:
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"

        response = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        response.raise_for_status()
        data = response.json()

        posts = data.get("data", {}).get("children", [])
        if not posts:
            return "No posts found."

        formatted = []
        for i, post in enumerate(posts, 1):
            p = post.get("data", {})
            formatted.append(
                f"{i}. **{p.get('title', 'No title')}**\n"
                f"   Score: {p.get('score', 0)} | Comments: {p.get('num_comments', 0)}\n"
                f"   Subreddit: r/{p.get('subreddit', subreddit)}\n"
                f"   URL: https://reddit.com{p.get('permalink', '')}\n"
                f"   {(p.get('selftext', '') or 'No text')[:300]}\n"
            )
        return "\n".join(formatted)
    except Exception as e:
        return f"Reddit scraping error: {str(e)}"


@tool
def scrape_producthunt(query: str = "", limit: int = 10) -> str:
    """Search ProductHunt for trending products and launches.

    Args:
        query: Optional search query for specific products.
        limit: Maximum number of results.
    """
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        }

        if query:
            url = f"https://www.producthunt.com/search?q={query}"
        else:
            url = "https://www.producthunt.com"

        response = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(response.text, "html.parser")

        # Extract product cards/listings
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)

        if len(text) > 10000:
            text = text[:10000] + "\n\n... [Content truncated]"

        return text if text.strip() else "No products found."
    except Exception as e:
        return f"ProductHunt scraping error: {str(e)}"
