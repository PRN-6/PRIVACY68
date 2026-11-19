---
name: docker
description: "Universal Docker CLI for managing containers, images, compose stacks, viewing logs, and inspecting services across any machine."
keywords: ["docker", "container", "containers", "docker-compose", "compose", "images", "docker logs", "docker ps", "dockerfile"]
metadata:
  emoji: "🐳"
  requires: { bins: ["docker"] }
---

# Universal Docker Skill Guide

Use this skill when any developer asks to manage local Docker containers, images, or compose environments.
Never assume containers are always running or that Docker Desktop is already started. Always provide clean diagnostic messages.

## 1. Checking Docker Daemon Status
```python
import shutil
import subprocess

def check_docker_available() -> tuple[bool, str]:
    if not shutil.which("docker"):
        return False, "Docker CLI is not installed or not on system PATH. Please install Docker Desktop."
    
    # Check if daemon is active
    test_run = subprocess.run(["docker", "info"], capture_output=True, text=True, check=False)
    if test_run.returncode != 0:
        err = test_run.stderr.lower()
        if "daemon is not running" in err or "cannot connect" in err or "error during connect" in err:
            return False, "Docker daemon is not running. Please start Docker Desktop first."
        return False, f"Docker error: {test_run.stderr.strip()}"
    return True, "Docker daemon is ready."
```

## 2. Common Operations (Any Machine)
- **List Running Containers**:
  `docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"`
- **List All Containers (Including Stopped)**:
  `docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"`
- **View Recent Logs**:
  `docker logs --tail 40 <container_name_or_id>`
- **Restart Container**:
  `docker restart <container_name_or_id>`
- **Stop Container**:
  `docker stop <container_name_or_id>`
- **Compose Management**:
  `docker compose up -d`
  `docker compose down`

## 3. Universal Execution Pattern in Python
```python
import subprocess
available, msg = check_docker_available()
if not available:
    print(msg)
else:
    res = subprocess.run(["docker", "ps", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"], capture_output=True, text=True, check=False)
    print(res.stdout.strip() or "No running containers found.")
```
