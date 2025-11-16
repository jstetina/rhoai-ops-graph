"""
Prompt configurations for Jenkins log analysis.
"""

SYSTEM_PROMPT = """You are an expert Jenkins CI/CD analyst. 
Your role is to analyze Jenkins build logs and provide clear, actionable insights.
Focus on identifying errors, performance issues, and providing recommendations.

Always structure your response with:
- SUMMARY: A concise 2-3 sentence overview
- DETAILED ANALYSIS: In-depth findings organized by topic"""


ANALYSIS_TYPE_DESCRIPTIONS = {
    "Summary": "overall build status and key outcomes",
    "Error Analysis": "errors, failures, warnings, and stack traces",
    "Performance Insights": "build duration, slow steps, and resource usage",
    "Test Results": "test execution results, passes, failures, and flaky tests",
    "Recommendations": "actionable recommendations to fix issues or improve the build"
}


def create_analysis_prompt(logs: str, analysis_types: list[str]) -> str:
    """
    Create a prompt for log analysis based on requested analysis types.
    
    Args:
        logs: The Jenkins build logs
        analysis_types: List of analysis types requested
        
    Returns:
        Formatted prompt string
    """
    # Truncate logs if too long
    max_log_length = 8000
    if len(logs) > max_log_length:
        logs = logs[:max_log_length // 2] + "\n\n... [TRUNCATED] ...\n\n" + logs[-max_log_length // 2:]
    
    # Build list of requested analyses
    analysis_items = []
    for analysis_type in analysis_types:
        if analysis_type in ANALYSIS_TYPE_DESCRIPTIONS:
            analysis_items.append(f"- {analysis_type}: {ANALYSIS_TYPE_DESCRIPTIONS[analysis_type]}")
    
    analyses_text = "\n".join(analysis_items) if analysis_items else "- Complete analysis of all aspects"
    
    prompt = f"""Analyze the following Jenkins build logs focusing on these aspects:

{analyses_text}

BUILD LOGS:
```
{logs}
```

Provide your analysis in this format:

SUMMARY:
[2-3 sentence concise summary]

DETAILED ANALYSIS:
[Organize your findings by the requested analysis types above. Use clear headings and bullet points.]"""
    
    return prompt

