"""
Orchestrator - LangGraph-based multi-agent coordinator
FIXED VERSION - Corrects state management and None-safe formatting
Manages the workflow between Detective, Historian, Analyzer, and Responder agents
"""

from typing import Dict, Any
from datetime import datetime
from langgraph.graph import StateGraph, END
from agents.state import IncidentState, AlertPayload
from agents.detective import DetectiveAgent
from agents.historian import HistorianAgent
from agents.analyzer import AnalyzerAgent
from agents.responder import ResponderAgent


class IncidentOrchestrator:
    """
    Orchestrates the incident response workflow using LangGraph.
    
    Workflow:
    1. Receive Alert → Start
    2. Detective Agent → Investigates
    3. Historian Agent → Finds similar incidents
    4. Analyzer Agent → Determines root cause
    5. Responder Agent → Executes or requests approval
    6. Complete → Generate report
    """
    
    def __init__(
        self,
        detective_agent: DetectiveAgent,
        historian_agent: HistorianAgent,
        analyzer_agent: AnalyzerAgent,
        responder_agent: ResponderAgent
    ):
        """
        Initialize the orchestrator with all agents
        
        Args:
            detective_agent: Agent for investigation
            historian_agent: Agent for finding similar incidents
            analyzer_agent: Agent for root cause analysis
            responder_agent: Agent for executing remediation
        """
        self.detective = detective_agent
        self.historian = historian_agent
        self.analyzer = analyzer_agent
        self.responder = responder_agent
        
        # Build the workflow graph
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """
        Build the LangGraph workflow
        
        Workflow structure:
        START → detective → historian → analyzer → responder → END
        """
        # Create the graph with IncidentState as the state schema
        workflow = StateGraph(IncidentState)
        
        # Add nodes for each agent
        workflow.add_node("detective", self._run_detective)
        workflow.add_node("historian", self._run_historian)
        workflow.add_node("analyzer", self._run_analyzer)
        workflow.add_node("responder", self._run_responder)
        
        # Define the edges (workflow flow)
        workflow.set_entry_point("detective")
        workflow.add_edge("detective", "historian")
        workflow.add_edge("historian", "analyzer")
        workflow.add_edge("analyzer", "responder")
        workflow.add_edge("responder", END)
        
        # Compile the graph
        return workflow.compile()
    
    def _run_detective(self, state: IncidentState) -> Dict[str, Any]:
        """Run the detective agent"""
        print(f"\n{'='*80}")
        print(f"🔍 DETECTIVE AGENT - Starting Investigation")
        print(f"{'='*80}")
        
        result = self.detective.investigate(state)
        
        print(f"\n✅ Investigation Complete:")
        print(f"  - Error Count: {result['detective_findings'].error_count}")
        print(f"  - Affected Hosts: {len(result['detective_findings'].affected_hosts)}")
        print(f"  - Duration: {result['detective_findings'].investigation_duration_seconds:.2f}s")
        
        return result
    
    def _run_historian(self, state: IncidentState) -> Dict[str, Any]:
        """Run the historian agent"""
        print(f"\n{'='*80}")
        print(f"📚 HISTORIAN AGENT - Searching History")
        print(f"{'='*80}")
        
        result = self.historian.search_history(state)
        
        print(f"\n✅ History Search Complete:")
        print(f"  - Similar Incidents Found: {len(result['historian_matches'].similar_incidents)}")
        if result['historian_matches'].similar_incidents:
            best = result['historian_matches'].similar_incidents[0]
            print(f"  - Best Match: {best.incident_id} ({best.similarity_score:.1f}% similar)")
        print(f"  - Duration: {result['historian_matches'].search_duration_seconds:.2f}s")
        
        return result
    
    def _run_analyzer(self, state: IncidentState) -> Dict[str, Any]:
        """Run the analyzer agent"""
        print(f"\n{'='*80}")
        print(f"🧠 ANALYZER AGENT - Performing Root Cause Analysis")
        print(f"{'='*80}")
        
        result = self.analyzer.analyze(state)
        
        print(f"\n✅ Analysis Complete:")
        print(f"  - Root Cause: {result['analyzer_diagnosis'].primary_root_cause.cause}")
        print(f"  - Confidence: {result['analyzer_diagnosis'].primary_root_cause.confidence:.1f}%")
        print(f"  - Recommended Action: {result['analyzer_diagnosis'].recommended_action.action}")
        print(f"  - Risk Level: {result['analyzer_diagnosis'].recommended_action.risk_level}")
        print(f"  - Duration: {result['analyzer_diagnosis'].analysis_duration_seconds:.2f}s")
        
        return result
    
    def _run_responder(self, state: IncidentState) -> Dict[str, Any]:
        """Run the responder agent"""
        print(f"\n{'='*80}")
        print(f"⚡ RESPONDER AGENT - Executing Response")
        print(f"{'='*80}")
        
        result = self.responder.respond(state)
        
        print(f"\n✅ Response Complete:")
        print(f"  - Decision: {result['responder_action'].decision}")
        print(f"  - Status: {result['responder_action'].execution_status}")
        print(f"  - Action Taken: {result['responder_action'].action_taken}")
        print(f"  - Duration: {result['responder_action'].execution_duration_seconds:.2f}s")
        
        return result
    
    def handle_alert(self, alert: AlertPayload) -> IncidentState:
        """
        Handle an incoming alert and orchestrate the response
        
        Args:
            alert: Alert payload from monitoring system
            
        Returns:
            Final incident state with all agent outputs
        """
        # Generate unique incident ID
        incident_id = f"INC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        print(f"\n{'#'*80}")
        print(f"# 🚨 NEW INCIDENT: {incident_id}")
        print(f"# Service: {alert.service}")
        print(f"# Severity: {alert.severity}")
        print(f"# Message: {alert.message}")
        print(f"{'#'*80}\n")
        
        # Create initial state
        initial_state = IncidentState(
            incident_id=incident_id,
            alert=alert
        )
        
        initial_state.add_timeline_event(
            agent="orchestrator",
            event="Incident workflow started",
            details={
                "alert_id": alert.alert_id,
                "service": alert.service,
                "severity": alert.severity
            }
        )
        
        # Run the workflow
        try:
            # FIXED: LangGraph returns the final state as a dict, extract the actual state
            workflow_result = self.workflow.invoke(initial_state)
            
            # The result might be a dict with state fields, convert back to IncidentState
            if isinstance(workflow_result, dict):
                # Update the initial_state with all the dict values
                for key, value in workflow_result.items():
                    if hasattr(initial_state, key):
                        setattr(initial_state, key, value)
                final_state = initial_state
            else:
                final_state = workflow_result
            
            # Ensure the state is marked as completed
            if final_state.workflow_status != "completed":
                final_state.mark_completed()
            
            print(f"\n{'#'*80}")
            print(f"# ✅ INCIDENT RESOLVED: {incident_id}")
            # FIXED: None-safe formatting
            duration = final_state.total_duration_seconds if final_state.total_duration_seconds is not None else 0.0
            print(f"# Total Duration: {duration:.2f}s")
            print(f"# Status: {final_state.workflow_status}")
            print(f"{'#'*80}\n")
            
            return final_state
            
        except Exception as e:
            initial_state.mark_failed(str(e))
            print(f"\n{'#'*80}")
            print(f"# ❌ INCIDENT FAILED: {incident_id}")
            print(f"# Error: {str(e)}")
            print(f"{'#'*80}\n")
            raise
    
    def generate_report(self, state: IncidentState) -> Dict[str, Any]:
        """
        Generate a comprehensive incident report
        
        Args:
            state: Final incident state
            
        Returns:
            Dictionary with complete incident details
        """
        report = {
            "incident_id": state.incident_id,
            "status": state.workflow_status,
            "total_duration_seconds": state.total_duration_seconds,
            "started_at": state.started_at.isoformat(),
            "completed_at": state.completed_at.isoformat() if state.completed_at else None,
            
            "alert": {
                "alert_id": state.alert.alert_id,
                "service": state.alert.service,
                "severity": state.alert.severity,
                "message": state.alert.message,
                "timestamp": state.alert.timestamp.isoformat()
            },
            
            "investigation": {
                "affected_service": state.detective_findings.affected_service,
                "error_count": state.detective_findings.error_count,
                "affected_hosts": state.detective_findings.affected_hosts,
                "affected_regions": state.detective_findings.affected_regions,
                "key_errors": state.detective_findings.key_error_messages,
                "duration_seconds": state.detective_findings.investigation_duration_seconds
            } if state.detective_findings else None,
            
            "similar_incidents": [
                {
                    "incident_id": inc.incident_id,
                    "similarity_score": inc.similarity_score,
                    "root_cause": inc.root_cause,
                    "resolution": inc.resolution_applied
                }
                for inc in state.historian_matches.similar_incidents
            ] if state.historian_matches else [],
            
            "root_cause_analysis": {
                "cause": state.analyzer_diagnosis.primary_root_cause.cause,
                "confidence": state.analyzer_diagnosis.primary_root_cause.confidence,
                "explanation": state.analyzer_diagnosis.primary_root_cause.explanation,
                "reasoning_steps": state.analyzer_diagnosis.reasoning_steps
            } if state.analyzer_diagnosis else None,
            
            "remediation": {
                "decision": state.responder_action.decision,
                "action_taken": state.responder_action.action_taken,
                "status": state.responder_action.execution_status,
                "execution_log": state.responder_action.execution_log,
                "notifications_sent": state.responder_action.notifications_sent
            } if state.responder_action else None,
            
            "timeline": state.timeline,
            "errors": state.errors
        }
        
        return report