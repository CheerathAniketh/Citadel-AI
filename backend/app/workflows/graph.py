"""
Citadel AI Governance Workflow
LangGraph-based orchestration for bias detection and remediation

Flow: DISCOVER → MONITOR → ANALYZE → DETECT → REMEDIATE → ALERT → COMPLETE
"""

from langgraph.graph import StateGraph
from typing import Dict, Any
from datetime import datetime
import logging

from app.workflows.state import CitadelState, create_initial_state
from app.workflows.nodes import (
    discover_models,
    monitor_predictions,
    analyze_bias,
    detect_violation,
    remediate,
    alert,
    complete_workflow
)

logger = logging.getLogger(__name__)


def create_governance_graph():
    """
    Create LangGraph workflow for governance checks
    
    Node Flow:
        discover_models     → auto-discover AI models in cloud
        monitor_predictions → fetch recent predictions from models
        analyze_bias        → compute bias metrics (DI, SPD, EOD)
        detect_violation    → check if metrics exceed thresholds
        remediate           → suggest fixes if violations found
        alert               → send alerts via Slack/Jira/etc
        complete_workflow   → finalize and log execution time
    """
    workflow = StateGraph(CitadelState)
    
    # Add all nodes
    workflow.add_node("discover", discover_models)
    workflow.add_node("monitor", monitor_predictions)
    workflow.add_node("analyze", analyze_bias)
    workflow.add_node("detect", detect_violation)
    workflow.add_node("remediate", remediate)
    workflow.add_node("alert", alert)
    workflow.add_node("complete", complete_workflow)
    
    # Add edges (linear flow through all steps)
    workflow.add_edge("discover", "monitor")
    workflow.add_edge("monitor", "analyze")
    workflow.add_edge("analyze", "detect")
    workflow.add_edge("detect", "remediate")
    workflow.add_edge("remediate", "alert")
    workflow.add_edge("alert", "complete")
    
    # Set starting node
    workflow.set_entry_point("discover")
    
    # Set end node(s)
    workflow.set_finish_point("complete")
    
    # Compile into executable graph
    graph = workflow.compile()
    return graph


# Instantiate the graph once at module load
governance_graph = create_governance_graph()


async def run_governance_check(
    user_id: str,
    cloud_provider: str,
    cloud_credentials: dict
) -> dict:
    """
    Execute full governance workflow end-to-end
    
    This is the main entry point called by the API endpoint.
    It initializes the workflow state and runs through all nodes.
    
    Args:
        user_id: User ID for audit logging
        cloud_provider: Cloud provider string ('aws', 'gcp', 'azure')
        cloud_credentials: Dict of credentials for the cloud provider
    
    Returns:
        Dict containing final workflow state with:
        - workflow_status: 'completed' or 'failed'
        - discovered_models: List of found models
        - bias_metrics: Computed fairness metrics
        - alerts: List of detected violations
        - recommended_fixes: Suggested remediation actions
        - audit_log: Complete execution trace
        - workflow_end_time: ISO timestamp of completion
    
    Example:
        >>> result = await run_governance_check(
        ...     user_id="user_123",
        ...     cloud_provider="gcp",
        ...     cloud_credentials={"project_id": "my-project"}
        ... )
        >>> print(result['workflow_status'])
        'completed'
    """
    
    logger.info(f"🚀 Starting governance workflow for {cloud_provider}")
    
    # Initialize workflow state
    initial_state = create_initial_state(
        user_id=user_id,
        cloud_provider=cloud_provider,
        cloud_credentials=cloud_credentials
    )
    
    # Add startup log entry
    initial_state['audit_log'].append(
        f"[{datetime.utcnow().isoformat()}] 🚀 Governance check initiated by {user_id}"
    )
    
    try:
        # Execute the workflow graph synchronously
        # The graph invokes all nodes in sequence
        final_state = await governance_graph.ainvoke(initial_state) 
        
        logger.info(f"✅ Governance workflow completed successfully")
        
        # Return formatted response
        return {
            "workflow_status": final_state.get('workflow_status', 'completed'),
            "discovered_models": final_state.get('discovered_models', []),
            "discovered_count": final_state.get('discovered_count', 0),
            "bias_metrics": final_state.get('bias_metrics', {}),
            "violations": final_state.get('alerts', []),
            "alerts": final_state.get('alerts', []),
            "recommended_fixes": final_state.get('recommended_fixes', []),
            "audit_log": final_state.get('audit_log', []),
            "workflow_end_time": final_state.get('workflow_end_time'),
            "execution_time_ms": final_state.get('total_execution_time_ms'),
            "error": final_state.get('error')
        }
    
    except Exception as e:
        logger.error(f"❌ Governance workflow failed: {str(e)}", exc_info=True)
        
        # Return error state
        return {
            "workflow_status": "failed",
            "error": str(e),
            "audit_log": initial_state['audit_log'] + [
                f"[{datetime.utcnow().isoformat()}] ❌ Workflow failed: {str(e)}"
            ]
        }