---
name: browser
description: "Universal browser navigation, Google/DuckDuckGo searches, and Chrome/Brave tab management."
keywords: ["browser", "chrome", "brave", "search", "google", "web", "tab", "website", "url", "open", "internet"]
metadata:
  openclaw:
    emoji: "🌐"
    requires: { bins: [] }
---

# Universal Browser Skill Guide

Use this skill when any developer or user asks to search the web, open a webpage, or launch Google Chrome or Brave.

## Search Queries & URL Patterns
* **Google**: `https://www.google.com/search?q={query}`
* **DuckDuckGo**: `https://duckduckgo.com/?q={query}`
* **YouTube**: `https://www.youtube.com/results?search_query={query}`
* **GitHub Search**: `https://github.com/search?q={query}`

## Python Automation Pattern in PRIVACY68
```python
import webbrowser
import urllib.parse

def search_web(query: str, engine: str = "google"):
    encoded = urllib.parse.quote_plus(query)
    if engine == "duckduckgo":
        url = f"https://duckduckgo.com/?q={encoded}"
    elif engine == "youtube":
        url = f"https://www.youtube.com/results?search_query={encoded}"
    else:
        url = f"https://www.google.com/search?q={encoded}"
    
    webbrowser.open(url)
    print(f"Searched {engine.title()} for: {query}")

def open_url(url: str):
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url
    webbrowser.open(url)
    print(f"Opened: {url}")

# Example: search for latest AI research
search_web("deepseek v3 paper", engine="google")
```

