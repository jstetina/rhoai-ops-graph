"""
LangGraph agent for Jenkins log analysis using MCP tools.
"""
import os
import sys
import logging
from typing import List, Optional, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from typing_extensions import TypedDict
from prompt_config import SYSTEM_PROMPT, create_analysis_prompt
from jenkins_mcp.jenkins.client import JenkinsClient

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
    reasoning: Optional[Dict]
    error: Optional[str]


class JenkinsAnalysisAgent:
    """Agent that uses MCP tools to analyze Jenkins logs."""
    
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
        self.llm = ChatOpenAI(
            base_url=base_url,
            api_key=self.api_key,
            model=model,
            temperature=0.7
        )
        
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
    
    async def analyze_logs(
        self,
        job_name: str,
        build_number: Optional[int] = None,
        analysis_types: List[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze Jenkins logs using LLM.
        
        Args:
            job_name: Name of the Jenkins job
            build_number: Specific build number (None for latest)
            analysis_types: Types of analysis to perform
            
        Returns:
            Dictionary containing analysis results
        """
        if analysis_types is None:
            analysis_types = ["Summary", "Error Analysis"]
        
        logger.info(f"Starting analysis for job: {job_name}, build: {build_number or 'latest'}")
        logger.info(f"Analysis types: {', '.join(analysis_types)}")
        
        # Initialize state
        state = AgentState(
            messages=[],
            job_name=job_name,
            build_number=build_number,
            analysis_types=analysis_types,
            logs=None,
            analysis=None,
            summary=None,
            reasoning={},
            error=None
        )
        
        try:
            # Step 1: Get logs
            logger.info("Step 1: Fetching logs from Jenkins...")
            state["reasoning"]["step_1"] = "Fetching logs from Jenkins"
            logs = await self.get_logs(job_name, build_number)
            state["logs"] = logs
            logger.info(f"Retrieved {len(logs)} characters of log data")
            
            # Step 2: Analyze logs with LLM
            logger.info("Step 2: Preparing prompt for LLM...")
            state["reasoning"]["step_2"] = "Analyzing logs with LLM"
            
            analysis_prompt = create_analysis_prompt(logs, analysis_types)
            logger.info(f"Prompt created, length: {len(analysis_prompt)} characters")
            
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=analysis_prompt)
            ]
            
            logger.info(f"Sending request to LLM at {self.base_url} using model {self.model}...")
            response = await self.llm.ainvoke(messages)
            logger.info("Received response from LLM")
            
            # Parse response
            full_analysis = response.content
            logger.info(f"LLM response length: {len(full_analysis)} characters")
            
            # Extract summary and detailed analysis
            logger.info("Step 3: Parsing LLM response...")
            if "SUMMARY:" in full_analysis:
                parts = full_analysis.split("DETAILED ANALYSIS:", 1)
                summary_part = parts[0].replace("SUMMARY:", "").strip()
                analysis_part = parts[1].strip() if len(parts) > 1 else ""
                
                state["summary"] = summary_part
                state["analysis"] = analysis_part
                logger.info("Successfully parsed summary and detailed analysis")
            else:
                state["summary"] = full_analysis[:500] + "..."
                state["analysis"] = full_analysis
                logger.warning("Could not find structured format in LLM response, using fallback parsing")
            
            state["reasoning"]["step_3"] = "Analysis complete"
            logger.info("Analysis completed successfully!")
            
            return {
                "summary": state["summary"],
                "analysis": state["analysis"],
                "logs": state["logs"],
                "reasoning": state["reasoning"]
            }
            
        except Exception as e:
            logger.error(f"Analysis failed with error: {str(e)}", exc_info=True)
            state["error"] = str(e)
            state["reasoning"]["error"] = str(e)
            raise
