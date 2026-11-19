---
name: gmail
description: "Compose, draft, search, and navigate Gmail inbox using browser URLs or Python automation."
keywords: ["gmail", "email", "mail", "inbox", "compose", "draft", "send email", "read email"]
metadata:
  openclaw:
    emoji: "✉️"
    requires: { bins: [] }
---

# Gmail Skill Guide

Use this skill when any developer or user asks to open Gmail, compose an email, or prepare a draft.

## Direct Compose URL Pattern
Format:
`https://mail.google.com/mail/?view=cm&fs=1&to={to}&su={subject}&body={body}`

With account (`authuser`):
`https://mail.google.com/mail/u/?view=cm&fs=1&authuser={email}&to={to}&su={subject}&body={body}`

## Python Automation Pattern in PRIVACY68
```python
import webbrowser
import urllib.parse
from services.gmail import gmail_service

# Quick compose via native GmailService
gmail_service.compose_email(
    to="recipient@example.com",
    subject="Meeting Agenda",
    body="Hi team, here is the agenda for our meeting."
)
print("Opened Gmail compose window.")
```

## Opening Inbox
```python
from services.gmail import gmail_service
gmail_service.open_inbox()
print("Opened Gmail inbox.")
```

