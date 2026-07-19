"""
Citadel AI Governance Workflow
LangGraph-based orchestration for bias detection and remediation
"""

from langgraph.graph import StateGraph
from app.workflows.state import WorkflowState
from app.workflows.nodes import (
    discover_models,
    monitor_predictions,
    analyze_bias,
    detect_violations,
    remediate_bias,
    alert_on_violations,
    cleanup
)
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def create_governance_graph():
    """
    Create LangGraph workflow for governance checks
    
    Flow:
    DISCOVER → MONITOR → ANALYZE → DETECT → REMEDIATE → ALERT → CLEANUP
    """
    workflow = StateGraph(WorkflowState)
    
    # Add nodes
    workflow.add_node("discover", discover_models)
    workflow.add_node("monitor", monitor_predictions)
    workflow.add_node("analyze", analyze_bias)
    workflow.add_node("detect", detect_violations)
    workflow.add_node("remediate", remediate_bias)
    workflow.add_node("alert", alert_on_violations)
    workflow.add_node("cleanup", cleanup)
    
    # Add edges (connections between nodes)
    workflow.add_edge("discover", "monitor")
    workflow.add_edge("monitor", "analyze")
    workflow.add_edge("analyze", "detect")
    workflow.add_edge("detect", "remediate")
    workflow.add_edge("remediate", "alert")
    workflow.add_edge("alert", "cleanup")
    
    # Set entry point
    workflow.set_entry_point("discover")
    
    # Compile the graph
    graph = workflow.compile()
    return graph

# Global graph instance
governance_graph = create_governance_graph()

async def run_governance_check(
    user_id: str,
    cloud_provider: str,
    cloud_credentials: dict
) -> dict:
    """
    Execute full governance workflow
    
    Args:
        user_id: User ID for audit log
        cloud_provider: 'aws', 'gcp', or 'azure'
        cloud_credentials: Cloud provider credentials
    
    Returns:
        Final workflow state with results
    """
    logger.info(f"🚀 Starting governance workflow for {cloud_provider}")
    
    # Initialize state
    initial_state = WorkflowState(
        user_id=user_id,
        cloud_provider=cloud_provider,
        cloud_credentials=cloud_credentials,
        workflow_status="running",
        workflow_start_time=datetime.utcnow().isoformat(),
        discovered_models=[],
        discovered_count=0,
        recent_predictions=[],
        bias_metrics={},
        violations=[],
        alerts=[],
        recommended_fixes=[],
        audit_log=[
            {
                "timestamp": datetime.utcnow().isoformat(),
                "action": "workflow_started",
                "user_id": user_id,
                "cloud_provider": cloud_provider
            }
        ]
    )
    
    try:
        # Execute workflow
        final_state = governance_graph.invoke(initial_state)
        
        # Mark as complete
        final_state.workflow_status = "completed"
        final_state.workflow_end_time = datetime.utcnow().isoformat()
        
        logger.info(f"✅ Governance workflow completed")
        
        return {
            "workflow_status": final_state.workflow_status,
            "discovered_count": final_state.discovered_count,
            "discovered_models": final_state.discovered_models,
            "bias_metrics": final_state.bias_metrics,
            "violations": final_state.violations,
            "alerts": final_state.alerts,
            "recommended_fixes": final_state.recommended_fixes,
            "audit_log": final_state.audit_log,
            "workflow_end_time": final_state.workflow_end_time
        }
    
    except Exception as e:
        logger.error(f"❌ Governance workflow failed: {e}")
        return {
            "workflow_status": "failed",
            "error": str(e),
            "audit_log": initial_state.audit_log + [
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "action": "workflow_failed",
                    "error": str(e)
                }
            ]
        }