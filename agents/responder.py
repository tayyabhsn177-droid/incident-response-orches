"""
Responder Agent - Executes remediation safely or requests human approval
"""

import time
from typing import Dict, Any, List
from datetime import datetime
from langchain_openai import ChatOpenAI
from agents.state import IncidentState, ResponderAction


class ResponderAgent:
    """
    Responder Agent executes incident remediation based on analyzer recommendations.
    Makes decisions on auto-execution vs human approval based on confidence and risk.
    """
    
    SYSTEM_PROMPT = """You are a Responder Agent that executes incident remediation.

Your job:
1. Review Analyzer's recommended action and confidence score
2. Determine if auto-execution is safe based on decision rules
3. Execute action via appropriate workflow tool OR request human approval
4. Document all actions taken
5. Notify relevant channels (Slack, PagerDuty)
6. Monitor for 5 minutes to confirm resolution

Decision Rules:
- Confidence ≥ 85% AND Risk = LOW → Auto-execute immediately
- Confidence 70-84% OR Risk = MEDIUM → Request approval (2 min timeout)
- Confidence < 70% OR Risk = HIGH → Present findings, no auto-action

Safety is paramount. When in doubt, request human approval.
"""

    # Confidence and risk thresholds
    AUTO_EXECUTE_MIN_CONFIDENCE = 85.0
    APPROVAL_MIN_CONFIDENCE = 70.0
    
    def __init__(self, model_name: str = "gpt-4o", workflow_tools: Dict[str, Any] = None):
        """
        Initialize the Responder Agent
        
        Args:
            model_name: OpenAI model to use
            workflow_tools: Dictionary of workflow execution tools
        """
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.workflow_tools = workflow_tools or {}
    
    def respond(self, state: IncidentState) -> Dict[str, Any]:
        """
        Execute or request approval for remediation
        
        Args:
            state: Current incident state with analyzer diagnosis
            
        Returns:
            Dictionary to update the state with responder action
        """
        start_time = time.time()
        
        try:
            state.add_timeline_event(
                agent="responder",
                event="Response evaluation started",
                details={}
            )
            
            diagnosis = state.analyzer_diagnosis
            
            # Make decision: auto-execute, request approval, or alert human
            decision = self._make_decision(
                confidence=diagnosis.primary_root_cause.confidence,
                risk_level=diagnosis.recommended_action.risk_level
            )
            
            # Execute based on decision
            action = self._execute_decision(state, decision)
            
            execution_duration = time.time() - start_time
            action.execution_duration_seconds = execution_duration
            
            state.add_timeline_event(
                agent="responder",
                event="Response completed",
                details={
                    "duration_seconds": execution_duration,
                    "decision": action.decision,
                    "status": action.execution_status
                }
            )
            
            # Mark incident as completed
            state.mark_completed()
            
            return {
                "responder_action": action,
                "workflow_status": "completed"
            }
            
        except Exception as e:
            state.add_timeline_event(
                agent="responder",
                event="Response failed",
                details={"error": str(e)}
            )
            raise
    
    def _make_decision(self, confidence: float, risk_level: str) -> str:
        """
        Decide whether to auto-execute, request approval, or alert human
        
        Args:
            confidence: Confidence score from analyzer (0-100)
            risk_level: Risk level (LOW, MEDIUM, HIGH)
            
        Returns:
            Decision: AUTO_EXECUTE, REQUEST_APPROVAL, or ALERT_HUMAN
        """
        if risk_level == "HIGH":
            return "ALERT_HUMAN"
        
        if confidence >= self.AUTO_EXECUTE_MIN_CONFIDENCE and risk_level == "LOW":
            return "AUTO_EXECUTE"
        
        if confidence >= self.APPROVAL_MIN_CONFIDENCE:
            return "REQUEST_APPROVAL"
        
        return "ALERT_HUMAN"
    
    def _execute_decision(self, state: IncidentState, decision: str) -> ResponderAction:
        """Execute the decided action"""
        diagnosis = state.analyzer_diagnosis
        recommended_action = diagnosis.recommended_action
        
        execution_log = []
        notifications_sent = []
        
        if decision == "AUTO_EXECUTE":
            execution_log.append(f"{datetime.utcnow().isoformat()}: Auto-execution approved (confidence: {diagnosis.primary_root_cause.confidence}%, risk: {recommended_action.risk_level})")
            
            # Execute the action
            success = self._execute_remediation(
                action=recommended_action.action,
                service=state.detective_findings.affected_service,
                execution_log=execution_log
            )
            
            # Send notifications
            notification_msg = self._create_notification(state, decision, "SUCCESS" if success else "FAILED")
            self._send_slack_notification(notification_msg)
            notifications_sent.append("Slack: incident-alerts")
            
            # Monitor the service
            monitoring_status = self._monitor_service(
                service=state.detective_findings.affected_service,
                duration_seconds=60  # Monitor for 1 minute
            )
            
            return ResponderAction(
                decision=decision,
                action_taken=recommended_action.action,
                execution_status="SUCCESS" if success else "FAILED",
                execution_log=execution_log,
                notifications_sent=notifications_sent,
                monitoring_status=monitoring_status,
                execution_duration_seconds=0.0
            )
        
        elif decision == "REQUEST_APPROVAL":
            execution_log.append(f"{datetime.utcnow().isoformat()}: Requesting human approval (confidence: {diagnosis.primary_root_cause.confidence}%, risk: {recommended_action.risk_level})")
            
            # Send approval request notification
            approval_msg = self._create_approval_request(state)
            self._send_slack_notification(approval_msg)
            notifications_sent.append("Slack: incident-alerts (approval requested)")
            
            return ResponderAction(
                decision=decision,
                action_taken="Awaiting human approval",
                execution_status="PENDING_APPROVAL",
                execution_log=execution_log,
                notifications_sent=notifications_sent,
                monitoring_status="Awaiting approval decision",
                execution_duration_seconds=0.0
            )
        
        else:  # ALERT_HUMAN
            execution_log.append(f"{datetime.utcnow().isoformat()}: Human intervention required (confidence: {diagnosis.primary_root_cause.confidence}%, risk: {recommended_action.risk_level})")
            
            # Send alert to on-call engineer
            alert_msg = self._create_human_alert(state)
            self._send_slack_notification(alert_msg)
            notifications_sent.append("Slack: incident-alerts")
            notifications_sent.append("PagerDuty: on-call engineer")
            
            return ResponderAction(
                decision=decision,
                action_taken="No automatic action taken - human alerted",
                execution_status="PENDING_APPROVAL",
                execution_log=execution_log,
                notifications_sent=notifications_sent,
                monitoring_status="Awaiting human investigation",
                execution_duration_seconds=0.0
            )
    
    def _execute_remediation(self, action: str, service: str, execution_log: List[str]) -> bool:
        """
        Execute the actual remediation action
        This is a placeholder - in production would call actual workflows
        """
        execution_log.append(f"{datetime.utcnow().isoformat()}: Executing: {action}")
        
        # Simulate execution
        if "rollback" in action.lower():
            execution_log.append(f"{datetime.utcnow().isoformat()}: Initiating deployment rollback for {service}")
            execution_log.append(f"{datetime.utcnow().isoformat()}: Rolling back to previous version")
            execution_log.append(f"{datetime.utcnow().isoformat()}: Rollback completed successfully")
            return True
        
        elif "restart" in action.lower():
            execution_log.append(f"{datetime.utcnow().isoformat()}: Initiating pod restart for {service}")
            execution_log.append(f"{datetime.utcnow().isoformat()}: Performing rolling restart")
            execution_log.append(f"{datetime.utcnow().isoformat()}: All pods restarted successfully")
            return True
        
        elif "scale" in action.lower():
            execution_log.append(f"{datetime.utcnow().isoformat()}: Initiating scaling operation for {service}")
            execution_log.append(f"{datetime.utcnow().isoformat()}: Scaling replicas")
            execution_log.append(f"{datetime.utcnow().isoformat()}: Scaling completed successfully")
            return True
        
        execution_log.append(f"{datetime.utcnow().isoformat()}: Action type not recognized, simulation only")
        return True
    
    def _monitor_service(self, service: str, duration_seconds: int) -> str:
        """
        Monitor service health after remediation
        This is a placeholder
        """
        return f"Service {service} monitored for {duration_seconds}s. Error rate decreased by 95%. Service healthy."
    
    def _create_notification(self, state: IncidentState, decision: str, status: str) -> str:
        """Create Slack notification message"""
        diagnosis = state.analyzer_diagnosis
        findings = state.detective_findings
        
        msg = f"""🤖 **Incident Response Agent** - {state.incident_id}

🚨 **ALERT**: {state.alert.message}
⏰ **Detected at**: {state.alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

🔍 **INVESTIGATION**:
• Affected: {findings.affected_service} in {', '.join(findings.affected_regions)}
• Errors: {findings.error_count} (spike detected)
• Root Cause: {diagnosis.primary_root_cause.cause} ({diagnosis.primary_root_cause.confidence:.1f}% confidence)

✅ **ACTION TAKEN**:
• {diagnosis.recommended_action.action}
• Status: {status}
• Decision: {decision}
• Time to resolve: {state.total_duration_seconds:.1f}s

📊 **MONITORING**:
• Service health: Monitoring in progress
• Full details available in incident report
"""
        return msg
    
    def _create_approval_request(self, state: IncidentState) -> str:
        """Create approval request message"""
        diagnosis = state.analyzer_diagnosis
        
        msg = f"""⚠️ **Approval Requested** - {state.incident_id}

**Recommended Action**: {diagnosis.recommended_action.action}
**Risk Level**: {diagnosis.recommended_action.risk_level}
**Confidence**: {diagnosis.primary_root_cause.confidence:.1f}%

**Root Cause**: {diagnosis.primary_root_cause.cause}

**Options**:
• ✅ Approve and execute
• ❌ Reject and investigate manually

Reply within 2 minutes or incident will be escalated.
"""
        return msg
    
    def _create_human_alert(self, state: IncidentState) -> str:
        """Create human intervention alert"""
        diagnosis = state.analyzer_diagnosis
        findings = state.detective_findings
        
        msg = f"""🚨 **Human Intervention Required** - {state.incident_id}

**Service**: {findings.affected_service}
**Error Count**: {findings.error_count}
**Affected Regions**: {', '.join(findings.affected_regions)}

**Analysis**:
• Root Cause: {diagnosis.primary_root_cause.cause}
• Confidence: {diagnosis.primary_root_cause.confidence:.1f}%
• Risk Level: {diagnosis.recommended_action.risk_level}

**Suggested Action**: {diagnosis.recommended_action.action}

⚠️ Confidence or risk level too high for auto-execution. Please investigate manually.

**Key Errors**:
{chr(10).join(f'• {err}' for err in findings.key_error_messages[:3])}
"""
        return msg
    
    def _send_slack_notification(self, message: str):
        """
        Send notification to Slack
        This is a placeholder - in production would use actual Slack webhook
        """
        print(f"\n{'='*80}\nSLACK NOTIFICATION:\n{'-'*80}\n{message}\n{'='*80}\n")
        # In production:
        # requests.post(SLACK_WEBHOOK_URL, json={"text": message})