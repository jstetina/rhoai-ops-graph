"""
Streamlit app for Jenkins log analysis using LangGraph and MCP.
"""
import streamlit as st
import asyncio
from agent import JenkinsAnalysisAgent
import os
    # Page config
st.set_page_config(
    page_title="Jenkins AI",
    page_icon="🔧",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
        background-color: #0066cc;
        color: white;
        font-weight: bold;
        border-radius: 5px;
        padding: 0.5rem 1rem;
    }
    .stButton>button:hover {
        background-color: #0052a3;
    }
    .status-box {
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .success {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
    }
    .info {
        background-color: #d1ecf1;
        border-left: 4px solid #17a2b8;
    }
    .error {
        background-color: #f8d7da;
        border-left: 4px solid #dc3545;
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.title("Jenkins AI")
st.markdown("Control and analyze Jenkins jobs with AI-powered insights")

# Initialize session state
if 'agent' not in st.session_state:
    st.session_state.agent = None
if 'analysis_history' not in st.session_state:
    st.session_state.analysis_history = []
if 'all_jobs' not in st.session_state:
    st.session_state.all_jobs = []
if 'jobs_loaded' not in st.session_state:
    st.session_state.jobs_loaded = False
if 'auto_initialized' not in st.session_state:
    st.session_state.auto_initialized = False

# Auto-initialize agent if env vars are present and not already initialized
if not st.session_state.auto_initialized and not st.session_state.agent:
    default_base_url = os.getenv("AGENT_MODEL_URL")
    default_model = os.getenv("AGENT_MODEL_ID")
    default_api_token = os.getenv("AGENT_MODEL_API_TOKEN")
    
    # Check for Jenkins env vars
    jenkins_configured = all([
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USER"),
        os.getenv("JENKINS_PASSWORD")
    ])
    
    # Auto-initialize if all required vars are present
    if jenkins_configured and default_base_url and default_model:
        try:
            st.session_state.agent = JenkinsAnalysisAgent(
                base_url=default_base_url,
                model=default_model,
                api_key=default_api_token if default_api_token else None
            )
            
            # Fetch all Jenkins jobs
            try:
                all_jobs = st.session_state.agent.jenkins_client.get_job_full_paths()
                st.session_state.all_jobs = sorted(all_jobs)
                st.session_state.jobs_loaded = True
            except Exception as e:
                st.session_state.all_jobs = []
                st.session_state.jobs_loaded = False
            
            st.session_state.auto_initialized = True
        except Exception as e:
            pass  # Silent fail, user can manually initialize

# Sidebar for configuration (collapsed by default)
with st.sidebar:
    st.header("Model Configuration")
    
    # Check for Jenkins environment variables
    import os
    jenkins_configured = all([
        os.getenv("JENKINS_URL"),
        os.getenv("JENKINS_USER"),
        os.getenv("JENKINS_PASSWORD")
    ])
    
    if not jenkins_configured:
        st.error("Jenkins environment variables not set!")
        st.code("""
export JENKINS_URL=your_jenkins_url
export JENKINS_USER=your_username
export JENKINS_PASSWORD=your_password
        """)
    
    st.divider()
    
    # Base URL input - load from env if available
    default_base_url = os.getenv("AGENT_MODEL_URL", "http://localhost:11434/v1")
    base_url = st.text_input(
        "LLM Base URL",
        value=default_base_url,
        help="OpenAI-compatible API endpoint (e.g., Ollama, vLLM, etc.)"
    )
    
    # Model name - load from env if available
    default_model = os.getenv("AGENT_MODEL_ID", "llama3:8b")
    model = st.text_input(
        "Model Name",
        value=default_model,
        help="Name of the model to use"
    )
    
    # Optional API key - load from env if available
    default_api_token = os.getenv("AGENT_MODEL_API_TOKEN", "")
    api_key = st.text_input(
        "API Token (optional)",
        value=default_api_token,
        type="password",
        help="Optional authentication token"
    )
    
    st.divider()
    
    # Show connection status
    if st.session_state.agent:
        st.success("Agent initialized")
    else:
        st.info("Configure endpoint and initialize agent")
    
    if st.button("Save Configuration", disabled=not jenkins_configured) and base_url and model:
        with st.spinner("Initializing agent..."):
            try:
                st.session_state.agent = JenkinsAnalysisAgent(
                    base_url=base_url,
                    model=model,
                    api_key=api_key if api_key else None
                )
                st.success("Configuration saved and agent initialized!")
                
                # Fetch all Jenkins jobs
                with st.spinner("Loading Jenkins jobs..."):
                    try:
                        all_jobs = st.session_state.agent.jenkins_client.get_job_full_paths()
                        st.session_state.all_jobs = sorted(all_jobs)
                        st.session_state.jobs_loaded = True
                        st.success(f"Loaded {len(all_jobs)} Jenkins jobs")
                    except Exception as e:
                        st.warning(f"Could not load Jenkins jobs: {e}")
                        st.session_state.all_jobs = []
                        st.session_state.jobs_loaded = False
                
                st.rerun()
            except Exception as e:
                st.error(f"Failed to initialize agent: {e}")

# Main content
col1, col2 = st.columns([2, 1])

with col1:
    st.header("Job Details")
    
    # Job input
    if st.session_state.jobs_loaded and st.session_state.all_jobs:
        job_name = st.selectbox(
            "Job Name",
            options=st.session_state.all_jobs,
            index=None,
            placeholder="Click and type to search...",
            help=f"Search through {len(st.session_state.all_jobs)} available Jenkins jobs"
        )
    else:
        job_name = st.text_input(
            "Job Name",
            placeholder="e.g., job-configurator",
            help="Enter the full Jenkins job name (initialize agent to see full job list)"
        )
    
    # Build number input (optional)
    use_latest = st.checkbox("Use latest build", value=True)
    
    build_number = None
    if not use_latest:
        build_number = st.number_input(
            "Build Number",
            min_value=1,
            value=1,
            help="Enter specific build number"
        )
    
    # Analysis type
    analysis_type = st.multiselect(
        "Analysis Type",
        [
            "Summary",
            "Error Analysis",
            "Performance Insights",
            "Test Results",
            "Recommendations"
        ],
        default=["Summary", "Error Analysis"],
        help="Select what aspects to analyze"
    )

with col2:
    st.header("Quick Actions")
    
    if st.button("Get Job Info", disabled=not job_name or not st.session_state.agent):
        with st.spinner("Fetching job info..."):
            try:
                result = asyncio.run(
                    st.session_state.agent.get_job_info(job_name)
                )
                st.json(result)
            except Exception as e:
                st.error(f"Error: {e}")
    
    if st.button("Get Recent Builds", disabled=not job_name or not st.session_state.agent):
        with st.spinner("Fetching recent builds..."):
            try:
                result = asyncio.run(
                    st.session_state.agent.get_recent_builds(job_name, limit=5)
                )
                st.write("Recent build numbers:", result)
            except Exception as e:
                st.error(f"Error: {e}")

st.divider()

# Analyze button
if st.button("Analyze Logs", type="primary", disabled=not job_name or not st.session_state.agent):
    
    if not st.session_state.agent:
        st.error("Please initialize the agent first!")
    else:
        with st.spinner("Analyzing logs... This may take a moment."):
            try:
                # Create analysis request
                analysis_request = {
                    "job_name": job_name,
                    "build_number": build_number,
                    "analysis_types": analysis_type
                }
                
                # Run analysis
                result = asyncio.run(
                    st.session_state.agent.analyze_logs(
                        job_name=job_name,
                        build_number=build_number,
                        analysis_types=analysis_type
                    )
                )
                
                # Store in history
                st.session_state.analysis_history.insert(0, {
                    "request": analysis_request,
                    "result": result
                })
                
                # Display results
                st.success("Analysis complete!")
                
                # Create tabs for different sections
                tabs = st.tabs(["Summary", "Detailed Analysis", "Agent Reasoning", "Raw Logs"])
                
                with tabs[0]:
                    st.markdown("### Summary")
                    if "summary" in result:
                        st.markdown(result["summary"])
                    else:
                        st.info("No summary available")
                
                with tabs[1]:
                    st.markdown("### Detailed Analysis")
                    if "analysis" in result:
                        st.markdown(result["analysis"])
                    else:
                        st.info("No detailed analysis available")
                
                with tabs[2]:
                    st.markdown("### Agent Reasoning")
                    if "reasoning" in result:
                        st.json(result["reasoning"])
                    else:
                        st.info("No reasoning data available")
                
                with tabs[3]:
                    st.markdown("### Raw Logs")
                    if "logs" in result:
                        st.code(result["logs"], language="log")
                    else:
                        st.info("No logs available")
                
            except Exception as e:
                st.error(f"Analysis failed: {e}")
                st.exception(e)

# History section
if st.session_state.analysis_history:
    st.divider()
    st.header("Analysis History")
    
    for idx, item in enumerate(st.session_state.analysis_history[:5]):
        with st.expander(f"Analysis #{idx + 1}: {item['request']['job_name']}"):
            st.json(item['request'])
            if st.button(f"View Results #{idx + 1}"):
                st.json(item['result'])
