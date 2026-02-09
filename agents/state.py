"""
State management for the Incident Response Orchestrator.
Defines the shared state that flows between agents.
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class AlertPayload(BaseModel):
    """Incoming alert from monitoring system"""
    alert_id: str
    severity: Literal["critical", "warning", "info"]
    service: str
    timestamp: datetime
    message: str
    tags: List[str] = Field(default_factory=list)


class DetectiveFindings(BaseModel):
    """Output from Detective Agent"""
    affected_service: str
    error_spike_time: datetime
    error_count: int
    error_types: List[str]
    affected_hosts: List[str]
    affected_regions: List[str]
    resource_metrics: Dict[str, float]
    recent_deployments: List[Dict[str, Any]]
    key_error_messages: List[str]
    investigation_duration_seconds: float


class SimilarIncident(BaseModel):
    """A single similar past incident"""
    incident_id: str
    similarity_score: float
    occurred_at: datetime
    symptoms: str
    root_cause: str
    resolution_applied: str
    time_to_resolve: str
    success_rate: str


class HistorianMatches(BaseModel):
    """Output from Historian Agent"""
    similar_incidents: List[SimilarIncident]
    recommendation: str
    search_duration_seconds: float


class Hypothesis(BaseModel):
    """A single root cause hypothesis"""
    hypothesis: str
    confidence: float  # 0-100
    supporting_evidence: List[str]
    validation_queries: List[str]


class RootCauseAnalysis(BaseModel):
    """Primary root cause determination"""
    cause: str
    confidence: float
    explanation: str


class RecommendedAction(BaseModel):
    """Action to take to resolve incident"""
    action: str
    risk_level: Literal["LOW", "MEDIUM", "HIGH"]
    estimated_resolution_time: str
    rollback_plan: str


class AnalyzerDiagnosis(BaseModel):
    """Output from Analyzer Agent"""
    hypotheses: List[Hypothesis]
    primary_root_cause: RootCauseAnalysis
    recommended_action: RecommendedAction
    reasoning_steps: List[str]
    analysis_duration_seconds: float


class ResponderAction(BaseModel):
    """Output from Responder Agent"""
    decision: Literal["AUTO_EXECUTE", "REQUEST_APPROVAL", "ALERT_HUMAN"]
    action_taken: str
    execution_status: Literal["SUCCESS", "FAILED", "PENDING_APPROVAL"]
    execution_log: List[str]
    notifications_sent: List[str]
    monitoring_status: str
    execution_duration_seconds: float


class IncidentState(BaseModel):
    """
    Complete state of an incident response workflow.
    This is passed between all agents in the LangGraph.
    """
    # Input
    incident_id: str
    alert: AlertPayload
    
    # Agent Outputs
    detective_findings: Optional[DetectiveFindings] = None
    historian_matches: Optional[HistorianMatches] = None
    analyzer_diagnosis: Optional[AnalyzerDiagnosis] = None
    responder_action: Optional[ResponderAction] = None
    
    # Metadata
    workflow_status: Literal["started", "investigating", "analyzing", "responding", "completed", "failed"] = "started"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    total_duration_seconds: Optional[float] = None
    
    # Timeline of events
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Error handling
    errors: List[str] = Field(default_factory=list)
    
    def add_timeline_event(self, agent: str, event: str, details: Optional[Dict] = None):
        """Add an event to the timeline"""
        self.timeline.append({
            "timestamp": datetime.now().isoformat(),
            "agent": agent,
            "event": event,
            "details": details or {}
        })
    
    def mark_completed(self):
        """Mark the workflow as completed and calculate total duration"""
        self.workflow_status = "completed"
        self.completed_at = datetime.now()
        self.total_duration_seconds = (self.completed_at - self.started_at).total_seconds()
    
    def mark_failed(self, error: str):
        """Mark the workflow as failed"""
        self.workflow_status = "failed"
        self.completed_at = datetime.now()
        self.errors.append(error)
        self.total_duration_seconds = (self.completed_at - self.started_at).total_seconds()