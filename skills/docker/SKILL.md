---
name: docker
description: "Docker CLI for managing containers, images, compose stacks, viewing logs, and inspecting services."
keywords: ["docker", "container", "containers", "docker-compose", "compose", "images", "docker logs"]
metadata:
  emoji: "🐳"
  requires: { bins: ["docker"] }
---

# Docker Skill Guide

Use `docker` CLI commands to manage local containers and compose environments.

## Common Operations
- **List Running Containers**: `docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"`
- **List All Containers**: `docker ps -a`
- **View Container Logs**: `docker logs --tail 50 <container_name_or_id>`
- **Restart Container**: `docker restart <container_name_or_id>`
- **Stop Container**: `docker stop <container_name_or_id>`
- **Docker Compose Up**: `docker compose up -d`
- **Docker Compose Down**: `docker compose down`

## How to Execute in Python
Use `subprocess.run(["docker", ...], capture_output=True, text=True, check=False)` and print the resulting stdout or stderr.

