"""
Prompt configurations for Jenkins log analysis.
"""

SYSTEM_PROMPT = """You are an expert Jenkins CI/CD analyst. 
Your role is to analyze Jenkins build logs and provide clear, actionable insights.
Focus on identifying errors, performance issues, and providing recommendations."""


def create_analysis_prompt(logs: str, analysis_types: list[str]) -> str:
    """
    Create a prompt for log analysis based on requested analysis types.
    
    Args:
        logs: The Jenkins build logs
        analysis_types: List of analysis types requested
        
    Returns:
        Formatted prompt string
    """
    max_log_length = 8000
    if len(logs) > max_log_length:
        logs = logs[:max_log_length // 2] + "\n\n... [TRUNCATED] ...\n\n" + logs[-max_log_length // 2:]
    
    prompt = f"""Analyze the following Jenkins build logs and provide insights.

ANALYSIS TYPES REQUESTED:
{', '.join(analysis_types)}

BUILD LOGS:
```
{logs}
```

Please provide your analysis in the following format:

SUMMARY:
[Provide a concise 2-3 sentence summary of the build status and key findings]

DETAILED ANALYSIS:
"""
    
    if "Summary" in analysis_types:
        prompt += "\n1. **Overall Status**: [What happened in this build?]"
    
    if "Error Analysis" in analysis_types:
        prompt += "\n2. **Errors Found**: [List any errors, failures, or warnings with line numbers if available]"
    
    if "Performance Insights" in analysis_types:
        prompt += "\n3. **Performance**: [Analyze build duration, slow steps, resource usage]"
    
    if "Test Results" in analysis_types:
        prompt += "\n4. **Test Results**: [Summarize test execution, passes, failures]"
    
    if "Recommendations" in analysis_types:
        prompt += "\n5. **Recommendations**: [Provide actionable recommendations to improve or fix issues]"
    
    return prompt

