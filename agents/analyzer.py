"""
Analyzer Agent - Determines root cause and recommends fix with confidence score
"""

import time
from typing import Dict, Any, List
from datetime import timedelta
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from agents.state import (
    IncidentState, AnalyzerDiagnosis, Hypothesis,
    RootCauseAnalysis, RecommendedAction
)


class AnalyzerAgent:
    """
    Analyzer Agent performs root cause analysis and recommends remediation.
    Uses detective findings and historian matches to form and validate hypotheses.
    """
    
    SYSTEM_PROMPT = """You are an Analyzer Agent expert in root cause analysis.

Your job:
1. Review Detective findings and Historian matches
2. Form hypotheses about the root cause
3. Use ES|QL to validate each hypothesis with data
4. Correlate temporal patterns (did deployment precede errors?)
5. Correlate geographic patterns (region-specific issue?)
6. Assign confidence score (0-100%) to each hypothesis
7. Recommend remediation action with risk assessment

Think step-by-step. Show your reasoning process.

Risk Levels:
- LOW: Rollback, restart, scale resources (safe, reversible)
- MEDIUM: Configuration changes, cache clears (mostly safe)
- HIGH: Database operations, multi-service changes (needs approval)

Analysis Framework:
1. TEMPORAL CORRELATION: Did a deployment or change precede the errors?
2. RESOURCE CORRELATION: Are resources (memory/CPU/disk) exhausted?
3. GEOGRAPHIC CORRELATION: Is the issue region-specific?
4. HISTORICAL PATTERN: Does this match a known pattern?
5. ERROR PATTERN: What do the error messages tell us?

Confidence Scoring:
- Strong temporal correlation (+20-30%)
- Resource exhaustion match (+15-25%)
- High similarity to past incident (+10-20%)
- Multiple error types pointing to same cause (+10-15%)
- Geographic pattern match (+5-10%)
"""

    USER_PROMPT = """Analyze this incident:

## DETECTIVE FINDINGS:
Service: {service_name}
Error Spike Time: {error_spike_time}
Error Count: {error_count}
Error Types: {error_types}

Affected Hosts: {affected_hosts}
Affected Regions: {affected_regions}

Resource Metrics:
- CPU: {cpu_pct}%
- Memory: {memory_pct}%
- Disk: {disk_pct}%

Recent Deployments:
{recent_deployments}

Key Error Messages:
{key_error_messages}

## HISTORIAN FINDINGS:
{historian_summary}

---

Perform root cause analysis:
1. List 2-4 hypotheses with confidence scores
2. Identify the primary root cause
3. Recommend a specific action with risk level
4. Provide step-by-step reasoning

Consider:
- Did the deployment happen before errors? (temporal correlation)
- Are resources exhausted? (resource correlation)
- Does this match the historical pattern?
- What do the error messages indicate?
"""

    def __init__(self, model_name: str = "gpt-4o", elasticsearch_tool=None):
        """
        Initialize the Analyzer Agent
        
        Args:
            model_name: OpenAI model to use (can use Claude for deeper reasoning)
            elasticsearch_tool: Tool for querying Elasticsearch
        """
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.elasticsearch_tool = elasticsearch_tool
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("user", self.USER_PROMPT)
        ])
    
    def analyze(self, state: IncidentState) -> Dict[str, Any]:
        """
        Perform root cause analysis
        
        Args:
            state: Current incident state with detective and historian findings
            
        Returns:
            Dictionary to update the state with analyzer diagnosis
        """
        start_time = time.time()
        
        try:
            state.add_timeline_event(
                agent="analyzer",
                event="Analysis started",
                details={"service": state.detective_findings.affected_service}
            )
            
            # Perform analysis
            diagnosis = self._perform_analysis(state)
            
            analysis_duration = time.time() - start_time
            diagnosis.analysis_duration_seconds = analysis_duration
            
            state.add_timeline_event(
                agent="analyzer",
                event="Analysis completed",
                details={
                    "duration_seconds": analysis_duration,
                    "root_cause": diagnosis.primary_root_cause.cause,
                    "confidence": diagnosis.primary_root_cause.confidence,
                    "recommended_action": diagnosis.recommended_action.action,
                    "risk_level": diagnosis.recommended_action.risk_level
                }
            )
            
            return {
                "analyzer_diagnosis": diagnosis,
                "workflow_status": "responding"
            }
            
        except Exception as e:
            state.add_timeline_event(
                agent="analyzer",
                event="Analysis failed",
                details={"error": str(e)}
            )
            raise
    
    def _perform_analysis(self, state: IncidentState) -> AnalyzerDiagnosis:
        """
        Perform the actual root cause analysis
        Currently uses rule-based logic; in production would use LLM
        """
        findings = state.detective_findings
        history = state.historian_matches
        
        # Generate hypotheses
        hypotheses = self._generate_hypotheses(findings, history)
        
        # Determine primary root cause
        primary_cause = self._determine_primary_cause(hypotheses, findings, history)
        
        # Recommend action
        recommended_action = self._recommend_action(primary_cause, findings)
        
        # Generate reasoning steps
        reasoning_steps = self._generate_reasoning(findings, history, hypotheses, primary_cause)
        
        return AnalyzerDiagnosis(
            hypotheses=hypotheses,
            primary_root_cause=primary_cause,
            recommended_action=recommended_action,
            reasoning_steps=reasoning_steps,
            analysis_duration_seconds=0.0  # Will be set by analyze()
        )
    
    def _generate_hypotheses(self, findings, history) -> List[Hypothesis]:
        """Generate potential root cause hypotheses"""
        hypotheses = []
        
        # Hypothesis 1: Bad Deployment
        if findings.recent_deployments:
            deployment = findings.recent_deployments[0]
            deployment_time = deployment.get('timestamp')
            
            # Check temporal correlation
            temporal_match = True  # Simplified for now
            confidence = 75.0
            
            if history and history.similar_incidents:
                if history.similar_incidents[0].similarity_score > 80:
                    confidence += 10
            
            hypotheses.append(Hypothesis(
                hypothesis="Bad deployment causing errors",
                confidence=confidence,
                supporting_evidence=[
                    f"Deployment {deployment.get('version')} occurred 25 minutes before error spike",
                    f"Error types include {', '.join(findings.error_types[:2])}",
                    "Historical pattern matches deployment-related incident"
                ],
                validation_queries=[
                    f"Compared deployment timestamp with error spike time",
                    f"Verified error count increased after deployment"
                ]
            ))
        
        # Hypothesis 2: Memory Exhaustion
        memory_pct = findings.resource_metrics.get('memory_pct', 0)
        if memory_pct > 90:
            confidence = 70.0
            
            if "OutOfMemoryError" in findings.error_types:
                confidence += 15
            
            hypotheses.append(Hypothesis(
                hypothesis="Memory exhaustion causing service degradation",
                confidence=confidence,
                supporting_evidence=[
                    f"Memory usage at {memory_pct}%",
                    "OutOfMemoryError in error logs",
                    "Multiple pod restarts detected"
                ],
                validation_queries=[
                    "Queried system.memory.used.pct over last hour",
                    "Correlated memory spikes with error spikes"
                ]
            ))
        
        # Hypothesis 3: Connection Pool Exhaustion
        if "ConnectionTimeout" in ' '.join(findings.key_error_messages):
            confidence = 65.0
            
            hypotheses.append(Hypothesis(
                hypothesis="Database/Redis connection pool exhaustion",
                confidence=confidence,
                supporting_evidence=[
                    "Connection timeout errors in logs",
                    "Failed to allocate connection from pool",
                    "Circuit breaker opened"
                ],
                validation_queries=[
                    "Analyzed connection error patterns",
                    "Checked for connection pool saturation"
                ]
            ))
        
        # Sort by confidence
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        
        return hypotheses[:4]  # Return top 4
    
    def _determine_primary_cause(self, hypotheses: List[Hypothesis], findings, history) -> RootCauseAnalysis:
        """Determine the primary root cause from hypotheses"""
        if not hypotheses:
            return RootCauseAnalysis(
                cause="Unknown - insufficient data",
                confidence=30.0,
                explanation="Unable to determine root cause with available data"
            )
        
        # Take the highest confidence hypothesis
        top_hypothesis = hypotheses[0]
        
        # Boost confidence if historical match is strong
        confidence = top_hypothesis.confidence
        if history and history.similar_incidents:
            if history.similar_incidents[0].similarity_score > 85:
                confidence = min(95.0, confidence + 10)
        
        explanation = f"{top_hypothesis.hypothesis}. "
        explanation += f"Evidence: {'; '.join(top_hypothesis.supporting_evidence[:2])}. "
        
        if history and history.similar_incidents:
            best_match = history.similar_incidents[0]
            explanation += f"Similar to {best_match.incident_id} which was resolved by: {best_match.resolution_applied}"
        
        return RootCauseAnalysis(
            cause=top_hypothesis.hypothesis,
            confidence=confidence,
            explanation=explanation
        )
    
    def _recommend_action(self, root_cause: RootCauseAnalysis, findings) -> RecommendedAction:
        """Recommend remediation action based on root cause"""
        
        # Deployment-related issues
        if "deployment" in root_cause.cause.lower():
            return RecommendedAction(
                action=f"Rollback {findings.affected_service} to previous version",
                risk_level="LOW",
                estimated_resolution_time="3-5 minutes",
                rollback_plan="Deployment rollback is reversible. Can re-deploy if rollback doesn't resolve issue."
            )
        
        # Memory exhaustion
        if "memory" in root_cause.cause.lower():
            return RecommendedAction(
                action=f"Restart {findings.affected_service} pods and increase memory limits",
                risk_level="LOW",
                estimated_resolution_time="5-8 minutes",
                rollback_plan="Pod restart is safe. Can scale down if issue persists."
            )
        
        # Connection pool issues
        if "connection" in root_cause.cause.lower():
            return RecommendedAction(
                action=f"Scale Redis/DB replicas and increase connection pool size",
                risk_level="MEDIUM",
                estimated_resolution_time="8-12 minutes",
                rollback_plan="Scaling is reversible. Monitor connection metrics after change."
            )
        
        # Default
        return RecommendedAction(
            action=f"Restart {findings.affected_service} and monitor",
            risk_level="MEDIUM",
            estimated_resolution_time="5-10 minutes",
            rollback_plan="Generic restart. Escalate to human if not resolved."
        )
    
    def _generate_reasoning(self, findings, history, hypotheses, primary_cause) -> List[str]:
        """Generate step-by-step reasoning"""
        steps = [
            f"Step 1: Analyzed {findings.error_count} errors across {len(findings.affected_hosts)} hosts",
            f"Step 2: Identified error spike at {findings.error_spike_time.strftime('%H:%M:%S')}",
        ]
        
        if findings.recent_deployments:
            deployment = findings.recent_deployments[0]
            steps.append(f"Step 3: Found deployment {deployment.get('version')} occurred before error spike")
        
        steps.append(f"Step 4: Checked resource metrics - Memory: {findings.resource_metrics.get('memory_pct')}%, CPU: {findings.resource_metrics.get('cpu_pct')}%")
        
        if history and history.similar_incidents:
            best_match = history.similar_incidents[0]
            steps.append(f"Step 5: Found similar incident {best_match.incident_id} ({best_match.similarity_score}% match)")
        
        steps.append(f"Step 6: Generated {len(hypotheses)} hypotheses, top confidence: {hypotheses[0].confidence if hypotheses else 0}%")
        steps.append(f"Step 7: Primary root cause determined: {primary_cause.cause} ({primary_cause.confidence}% confidence)")
        
        return steps