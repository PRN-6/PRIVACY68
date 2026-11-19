---
name: telegram
description: "Send Telegram notifications, alerts, photos, screenshots, and manage the Remote Gateway."
keywords: ["telegram", "tg", "telegram bot", "telegram message", "send telegram", "notify telegram", "telegram alert"]
metadata:
  openclaw:
    emoji: "✈️"
    requires: { bins: [] }
---

# Telegram Remote Gateway Skill Guide

Use this skill when any developer or user asks to send a Telegram message, push a notification to their phone, or send a desktop screenshot via Telegram.

## Python Automation Pattern in PRIVACY68
```python
from channels.telegram import telegram_channel

# Send a text alert to the authorized mobile device
telegram_channel.send_message("🔔 Notification from PRIVACY68: Operation completed successfully!")
print("Sent Telegram notification.")

# Send live desktop screenshot
img_bytes = telegram_channel.capture_screenshot_bytes()
if img_bytes:
    telegram_channel.send_photo(img_bytes, caption="📸 Current Desktop State")
    print("Sent desktop screenshot to Telegram.")
else:
    print("Could not capture desktop screenshot.")
```

