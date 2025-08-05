# Running ADO Story Extractor in Docker 🐳

This guide explains how to run the ADO Story Extractor agent in Docker containers.

## Prerequisites

1. **Docker** and **Docker Compose** installed on your system
2. **Azure DevOps** account with appropriate permissions
3. **OpenAI API** key for story extraction

## Quick Start

### 1. Configure Environment

First, set up your environment variables:

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your credentials
vim .env  # or use your preferred editor
```

Required variables in `.env`:
```env
ADO_ORGANIZATION=your-organization
ADO_PROJECT=your-project
ADO_PAT=your-personal-access-token
OPENAI_API_KEY=your-openai-api-key
```

### 2. Build the Docker Image

```bash
# Build the image
docker-compose build

# Or build directly with Docker
docker build -t ado-story-extractor .
```

## Usage Modes

### Mode 1: Demo (Recommended First Step)

Run the demo to understand the system without real credentials:

```bash
docker-compose run --rm ado-story-extractor python demo_epic_sync.py
```

### Mode 2: Basic CLI Usage

Validate configuration:
```bash
docker-compose run --rm ado-story-extractor python main.py validate-config
```

Check available work item types:
```bash
docker-compose run --rm ado-story-extractor python main.py check-types
```

Process a single requirement/epic:
```bash
docker-compose run --rm ado-story-extractor python main.py process 123
```

Preview stories without uploading:
```bash
docker-compose run --rm ado-story-extractor python main.py preview 123
```

### Mode 3: Enhanced Epic Synchronization

Synchronize an epic with change detection:
```bash
docker-compose run --rm ado-story-extractor python main_enhanced.py sync-epic 12345
```

Preview changes:
```bash
docker-compose run --rm ado-story-extractor python main_enhanced.py preview-epic 12345
```

### Mode 4: Continuous Monitoring (Standalone)

Create monitoring configuration:
```bash
docker-compose run --rm ado-story-extractor python monitor_daemon.py --create-config
```

Edit the generated `monitor_config.json` file to add your epic IDs, then run the monitoring service:

```bash
# Run in standalone mode (detached)
docker-compose up -d ado-story-extractor
```

To override the default command in docker-compose.yml, uncomment and modify the command line:
```yaml
command: ["python", "monitor_daemon.py", "--mode", "standalone"]
```

### Mode 5: API Server

Run the agent as an API server:

```bash
# Start the API server
docker-compose --profile api up -d ado-story-extractor-api
```

The API will be available at `http://localhost:8080` with endpoints:
- `http://localhost:8080/api/health`
- `http://localhost:8080/api/status`
- `http://localhost:8080/api/force-check`

## Docker Commands Reference

### Building and Running

```bash
# Build the image
docker-compose build

# Run a one-time command
docker-compose run --rm ado-story-extractor [command]

# Start services in background
docker-compose up -d

# Start API service
docker-compose --profile api up -d ado-story-extractor-api

# View logs
docker-compose logs -f ado-story-extractor

# Stop services
docker-compose down
```

### Direct Docker Commands

If you prefer using Docker directly instead of docker-compose:

```bash
# Build image
docker build -t ado-story-extractor .

# Run demo
docker run --rm --env-file .env ado-story-extractor python demo_epic_sync.py

# Run with volume mounts for persistence
docker run --rm \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/snapshots:/app/snapshots \
  -v $(pwd)/monitor_state.json:/app/monitor_state.json \
  -v $(pwd)/monitor_config.json:/app/monitor_config.json \
  ado-story-extractor python main.py validate-config

# Run API server
docker run -d \
  --name ado-story-extractor-api \
  --env-file .env \
  -p 8080:8080 \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/snapshots:/app/snapshots \
  -v $(pwd)/monitor_state.json:/app/monitor_state.json \
  -v $(pwd)/monitor_config.json:/app/monitor_config.json \
  ado-story-extractor python monitor_daemon.py --mode api --host 0.0.0.0 --port 8080
```

## Data Persistence

The Docker setup includes volume mounts for:
- `./logs` - Application logs
- `./snapshots` - Epic snapshots for change detection
- `./monitor_state.json` - Persistent state tracking
- `./monitor_config.json` - Monitoring configuration

These ensure your data persists between container restarts.

## Environment Variables

All environment variables from `.env` are automatically loaded. Key variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `ADO_ORGANIZATION` | Azure DevOps organization name | Yes |
| `ADO_PROJECT` | Project name in ADO | Yes |
| `ADO_PAT` | Personal Access Token | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `ADO_REQUIREMENT_TYPE` | Work item type for requirements | No |
| `ADO_USER_STORY_TYPE` | Work item type for user stories | No |

## Monitoring Configuration

Create `monitor_config.json` for continuous monitoring:

```json
{
  "poll_interval_seconds": 300,
  "max_concurrent_syncs": 3,
  "snapshot_directory": "snapshots",
  "log_level": "INFO",
  "epic_ids": ["123", "456"],
  "auto_sync": true,
  "auto_extract_new_epics": true,
  "retry_attempts": 3,
  "retry_delay_seconds": 60
}
```

## Production Deployment

For production deployment:

1. **Security**: Review and update the Dockerfile for production security requirements
2. **Resources**: Set appropriate CPU and memory limits in docker-compose.yml
3. **Logging**: Configure log rotation and centralized logging
4. **Monitoring**: Set up health checks and alerting
5. **Secrets**: Use Docker secrets or external secret management instead of .env files

Example production docker-compose.yml additions:

```yaml
services:
  ado-story-extractor:
    # ... existing configuration
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
        reservations:
          memory: 256M
          cpus: '0.25'
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8080/api/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Troubleshooting

### Common Issues

1. **Permission Issues**:
   ```bash
   # Fix volume mount permissions
   sudo chown -R $(id -u):$(id -g) logs snapshots
   ```

2. **Configuration Issues**:
   ```bash
   # Validate configuration
   docker-compose run --rm ado-story-extractor python main.py validate-config
   ```

3. **Viewing Logs**:
   ```bash
   # Container logs
   docker-compose logs -f ado-story-extractor
   
   # Application logs (if volume mounted)
   tail -f logs/epic_monitor.log
   ```

4. **Network Issues**:
   - Ensure the container can reach Azure DevOps and OpenAI APIs
   - Check firewall and proxy settings

### Debug Mode

Run with debug logging:

```bash
docker-compose run --rm \
  -e LOG_LEVEL=DEBUG \
  ado-story-extractor python main.py validate-config
```

## Development

For development with live code changes:

```bash
# Mount source code as volume for development
docker run --rm -it \
  --env-file .env \
  -v $(pwd):/app \
  -w /app \
  python:3.11-slim bash

# Inside container, install dependencies and run
pip install -r requirements.txt
python main.py validate-config
```

---

**Ready to get started?** 
1. Configure your `.env` file
2. Run: `docker-compose run --rm ado-story-extractor python demo_epic_sync.py` 🚀
