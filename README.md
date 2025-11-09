# Jenkins Log Analyzer Agent

AI-powered Jenkins log analysis using Streamlit, LangChain, and MCP.

## Features

- 🤖 AI-powered log analysis using LLM
- 🔍 Real-time job search and filtering
- 📊 Interactive Streamlit interface
- 🚀 Auto-initialization with environment variables
- 🐳 Docker support for easy deployment

## Quick Start

### Local Development

1. **Configure environment variables:**
   ```bash
   cp config.env.template config.env
   # Edit config.env with your credentials
   ```

2. **Run the application:**
   ```bash
   ./run.sh
   ```

3. **Access the app:**
   Open http://localhost:8501 in your browser

### Container Deployment

**Build:**
```bash
cd jenkins-agent

# Build with podman
podman build -t jenkins-log-analyzer .

# Or with docker
docker build -t jenkins-log-analyzer .
```

**Run the container:**
```bash
# Mount the jenkins_mcp library from host at runtime
# With podman
podman run -d -p 8501:8501 \
  -v /path/to/jenkins_mcp:/app/lib/jenkins_mcp:ro \
  --env-file config.env \
  jenkins-log-analyzer

# Or with docker
docker run -d -p 8501:8501 \
  -v /path/to/jenkins_mcp:/app/lib/jenkins_mcp:ro \
  --env-file config.env \
  jenkins-log-analyzer
```

## Configuration

Required environment variables in `config.env`:

```bash
# Jenkins Configuration
export JENKINS_URL=http://your-jenkins-url:8080/
export JENKINS_USER=your-username
export JENKINS_PASSWORD=your-api-token

# Model Configuration
export AGENT_MODEL_URL=https://your-model-endpoint
export AGENT_MODEL_ID=model-name
export AGENT_MODEL_API_TOKEN=your-token
```

## Usage

1. The app auto-initializes on startup if all environment variables are configured
2. Select a Jenkins job from the searchable dropdown
3. Choose analysis types (Summary, Error Analysis, etc.)
4. Click "Analyze Logs" to get AI-powered insights

## Architecture

- **Frontend**: Streamlit web interface
- **Backend**: LangChain for LLM integration
- **Jenkins Integration**: Python Jenkins client via MCP
- **LLM**: Configurable OpenAI-compatible endpoint

## Development

### Prerequisites

- Python 3.12+
- uv package manager
- Jenkins instance with API access
- OpenAI-compatible LLM endpoint

### Project Structure

```
jenkins-agent/
├── app.py              # Streamlit UI
├── agent.py            # LangGraph analysis agent
├── prompt_config.py    # LLM prompts
├── run.sh             # Local development script
├── config.env         # Environment variables (gitignored)
├── Dockerfile         # Container image
└── docker-compose.yml # Docker deployment
```

## License

See LICENSE file in the root directory.

