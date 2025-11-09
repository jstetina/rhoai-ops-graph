#!/bin/bash
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Ensure JENKINS_MCP_LIB_PATH is set and points to jenkins_mcp library, then append it to PYTHONPATH
if [ -z "$JENKINS_MCP_LIB_PATH" ]; then
    echo "Error: JENKINS_MCP_LIB_PATH environment variable is not set."
    echo "Please set JENKINS_MCP_LIB_PATH to the full path of your jenkins_mcp library."
    exit 1
fi

export PYTHONPATH="$JENKINS_MCP_LIB_PATH${PYTHONPATH+:$PYTHONPATH}"

# Source config.env if it exists
if [ -f "config.env" ]; then
    source config.env
else
    echo "Please set the following environment variables in config.env:"
    echo "  export JENKINS_URL=your_jenkins_url"
    echo "  export JENKINS_USER=your_username"
    echo "  export JENKINS_PASSWORD=your_password"
    echo ""
    echo "Then run this script again."
    exit 1
fi

echo "Jenkins configuration found:"
echo "  URL: $JENKINS_URL"
echo "  User: $JENKINS_USER"
echo ""

streamlit run app.py

