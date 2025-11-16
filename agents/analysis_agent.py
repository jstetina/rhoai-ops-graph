"""
LangGraph agent for Jenkins log analysis using MCP tools.
"""
import os
import sys
import logging
from typing import List, Optional, Dict, Any, Literal
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from prompt_config import SYSTEM_PROMPT, create_analysis_prompt
from jenkins_mcp.jenkins.client import JenkinsClient
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """State for the Jenkins analysis agent."""
    messages: List[Any]
    job_name: str
    build_number: Optional[int]
    analysis_types: List[str]
    logs: Optional[str]
    analysis: Optional[str]
    summary: Optional[str]
    reasoning: Dict[str, str]
    error: Optional[str]
    status: Optional[str]  # For routing decisions: "success", "error", "needs_analysis"


# Initialize global Jenkins client and LLM
def _init_jenkins_client():
    """Initialize Jenkins client from environment variables."""
    jenkins_url = os.environ.get('JENKINS_URL')
    jenkins_user = os.environ.get('JENKINS_USER')
    jenkins_password = os.environ.get('JENKINS_PASSWORD')
    
    if not jenkins_url or not jenkins_user or not jenkins_password:
        raise ValueError("JENKINS_URL, JENKINS_USER, and JENKINS_PASSWORD environment variables must be set")
    
    return JenkinsClient(jenkins_url, jenkins_user, jenkins_password)


def _init_llm():
    """Initialize LLM from environment variables."""
    base_url = os.environ.get('LLM_BASE_URL')
    model = os.environ.get('LLM_MODEL')
    api_key = os.environ.get('LLM_API_KEY', 'dummy')
    
    if not base_url or not model:
        raise ValueError("LLM_BASE_URL and LLM_MODEL environment variables must be set")
    
    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=0.7
    )


# Node functions
def _fetch_logs_node(state: AgentState) -> AgentState:
    """Node: Fetch logs from Jenkins."""
    logger.info("Node: fetch_logs - Fetching logs from Jenkins...")
    state["reasoning"]["fetch_logs"] = "Fetching logs from Jenkins"
    
    try:
        jenkins_client = _init_jenkins_client()
        logs = jenkins_client.get_build_logs(
            state["job_name"], 
            state.get("build_number")
        )
        state["logs"] = logs
        state["status"] = "needs_analysis"
        logger.info(f"Successfully fetched {len(logs)} characters of log data")
    except Exception as e:
        logger.error(f"Error fetching logs: {str(e)}", exc_info=True)
        state["error"] = f"Failed to fetch logs: {str(e)}"
        state["status"] = "error"
    
    return state


async def _analyze_logs_node(state: AgentState) -> AgentState:
    """Node: Analyze logs with LLM."""
    logger.info("Node: analyze_logs - Analyzing logs with LLM...")
    state["reasoning"]["analyze_logs"] = "Analyzing logs with LLM"
    
    try:
        llm = _init_llm()
        analysis_prompt = create_analysis_prompt(
            state["logs"], 
            state["analysis_types"]
        )
        
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=analysis_prompt)
        ]
        
        logger.info(f"Sending request to LLM...")
        response = await llm.ainvoke(messages)
        logger.info("Received response from LLM")
        
        state["analysis"] = response.content
        state["status"] = "needs_parsing"
        
    except Exception as e:
        logger.error(f"Error analyzing logs: {str(e)}", exc_info=True)
        state["error"] = f"Failed to analyze logs: {str(e)}"
        state["status"] = "error"
    
    return state


def _parse_response_node(state: AgentState) -> AgentState:
    """Node: Parse LLM response into structured format."""
    logger.info("Node: parse_response - Parsing LLM response...")
    state["reasoning"]["parse_response"] = "Parsing LLM response"
    
    try:
        full_analysis = state["analysis"]
        
        if "SUMMARY:" in full_analysis:
            parts = full_analysis.split("DETAILED ANALYSIS:", 1)
            summary_part = parts[0].replace("SUMMARY:", "").strip()
            analysis_part = parts[1].strip() if len(parts) > 1 else ""
            
            state["summary"] = summary_part
            state["analysis"] = analysis_part
            logger.info("Successfully parsed summary and detailed analysis")
        else:
            state["summary"] = full_analysis[:500] + "..."
            logger.warning("Could not find structured format, using fallback parsing")
        
        state["status"] = "success"
        
    except Exception as e:
        logger.error(f"Error parsing response: {str(e)}", exc_info=True)
        state["error"] = f"Failed to parse response: {str(e)}"
        state["status"] = "error"
    
    return state


def _route_after_fetch(state: AgentState) -> Literal["analyze_logs", "error"]:
    """Conditional edge: Route based on fetch status."""
    if state.get("status") == "error":
        logger.info("Routing to error (fetch failed)")
        return "error"
    logger.info("Routing to analyze_logs")
    return "analyze_logs"


def _route_after_analysis(state: AgentState) -> Literal["parse_response", "error"]:
    """Conditional edge: Route based on analysis status."""
    if state.get("status") == "error":
        logger.info("Routing to error (analysis failed)")
        return "error"
    logger.info("Routing to parse_response")
    return "parse_response"


def _build_graph():
    """Build the LangGraph workflow."""
    logger.info("Building LangGraph workflow...")
    
    # Create the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("fetch_logs", _fetch_logs_node)
    workflow.add_node("analyze_logs", _analyze_logs_node)
    workflow.add_node("parse_response", _parse_response_node)
    workflow.add_node("error", lambda state: state)  # Error handler node
    
    # Add edges
    workflow.add_edge(START, "fetch_logs")
    
    # Conditional routing after fetch
    workflow.add_conditional_edges(
        "fetch_logs",
        _route_after_fetch,
        {
            "analyze_logs": "analyze_logs",
            "error": "error"
        }
    )
    
    # Conditional routing after analysis
    workflow.add_conditional_edges(
        "analyze_logs",
        _route_after_analysis,
        {
            "parse_response": "parse_response",
            "error": "error"
        }
    )
    
    # End edges
    workflow.add_edge("parse_response", END)
    workflow.add_edge("error", END)
    
    # Compile the graph
    compiled_graph = workflow.compile()
    logger.info("LangGraph workflow compiled successfully")
    
    return compiled_graph


def build_agent():
    """Build and initialize the Jenkins analysis agent."""
    load_dotenv()
    logger.info("Building Jenkins analysis agent...")
    return _build_graph()


# For LangGraph: create the agent at module level
agent = build_agent()


# Keep the JenkinsAnalysisAgent class for backward compatibility and utility methods
class JenkinsAnalysisAgent:
    """Agent that uses MCP tools to analyze Jenkins logs with LangGraph."""
    
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: Optional[str] = None
    ):
        """
        Initialize the agent with OpenAI-compatible endpoint.
        
        Args:
            base_url: Base URL of the LLM API endpoint
            model: Model name to use
            api_key: Optional API key/token for authentication
        """
        self.base_url = base_url
        self.api_key = api_key or "dummy"
        self.model = model
        
        # Initialize Jenkins client with credentials from environment
        jenkins_url = os.environ.get('JENKINS_URL')
        jenkins_user = os.environ.get('JENKINS_USER')
        jenkins_password = os.environ.get('JENKINS_PASSWORD')
        
        if not jenkins_url or not jenkins_user or not jenkins_password:
            raise ValueError("JENKINS_URL, JENKINS_USER, and JENKINS_PASSWORD environment variables must be set")
        
        self.jenkins_client = JenkinsClient(jenkins_url, jenkins_user, jenkins_password)
    
    async def get_job_info(self, job_name: str) -> Dict:
        """Get information about a Jenkins job."""
        return self.jenkins_client.get_job_info(job_name)
    
    async def get_recent_builds(self, job_name: str, limit: int = 10) -> List[int]:
        """Get recent build numbers for a job."""
        return self.jenkins_client.get_recent_build_numbers(job_name, limit)
    
    async def get_logs(self, job_name: str, build_number: Optional[int] = None) -> str:
        """Get logs for a specific build or latest build."""
        return self.jenkins_client.get_build_logs(job_name, build_number)


if __name__ == "__main__":
    print("Analysis agent initialized successfully")
    print(f"Agent: {agent}")
