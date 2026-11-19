---
name: whatsapp
description: "Send WhatsApp messages, open chats, and automate WhatsApp Web or Desktop application."
keywords: ["whatsapp", "chat", "message", "send message", "wa", "text", "whatsapp web"]
metadata:
  openclaw:
    emoji: "💬"
    requires: { bins: [] }
---

# WhatsApp Skill Guide

Use this skill when any developer or user asks to open WhatsApp, message a contact, or draft a WhatsApp text.

## Deep-Link Protocols
* **Web**: `https://web.whatsapp.com/send?phone={phone}&text={encoded_message}`
* **Native Windows App**: `whatsapp://send?phone={phone}&text={encoded_message}`

## Python Automation Pattern in PRIVACY68
```python
import webbrowser
import urllib.parse

def send_whatsapp(phone: str, message: str = ""):
    clean_phone = "".join(c for c in phone if c.isdigit() or c == "+")
    encoded_text = urllib.parse.quote(message) if message else ""
    
    url = f"https://web.whatsapp.com/send?phone={clean_phone}&text={encoded_text}"
    webbrowser.open(url)
    print(f"Opened WhatsApp conversation for {clean_phone}.")

# Example
send_whatsapp("+1234567890", "Hello! Sending this via PRIVACY68.")
```

## Opening WhatsApp Directly
```python
import webbrowser
webbrowser.open("https://web.whatsapp.com")
print("Opened WhatsApp Web.")
```

