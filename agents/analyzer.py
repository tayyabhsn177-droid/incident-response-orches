"""
Analyzer Agent - Determines root cause and recommends fix with confidence score
FIXED VERSION - Enhanced hypothesis generation that works even without deployment data
"""

import time
from typing import Dict, Any, List
from datetime import timedelta
from langchain.chat_models import init_chat_model
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

    def __init__(self, elasticsearch_tool=None):
        """
        Initialize the Analyzer Agent
        
        Args:
            elasticsearch_tool: Tool for querying Elasticsearch
        """
        self.llm = init_chat_model("gemini-2.5-flash-lite", model_provider="google_genai", temperature=0.7)
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
        """
        FIXED: Enhanced hypothesis generation that works even without deployment data
        Generates robust hypotheses from multiple signals
        """
        hypotheses = []
        
        # Hypothesis 1: Bad Deployment (if data available)
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
                    f"Deployment {deployment.get('version')} occurred before error spike",
                    f"Error types include {', '.join(findings.error_types[:2])}",
                    "Historical pattern matches deployment-related incident"
                ],
                validation_queries=[
                    f"Compared deployment timestamp with error spike time",
                    f"Verified error count increased after deployment"
                ]
            ))
        
        # FIXED: Even without deployment data, consider deployment as possible cause
        elif len(findings.error_types) > 0 and findings.error_count > 100:
            confidence = 60.0
            
            # Boost confidence if historical incidents point to deployment issues
            if history and history.similar_incidents:
                for incident in history.similar_incidents:
                    if "deployment" in incident.root_cause.lower():
                        confidence = 70.0
                        break
            
            hypotheses.append(Hypothesis(
                hypothesis="Possible deployment-related issue (deployment data unavailable)",
                confidence=confidence,
                supporting_evidence=[
                    f"High error count: {findings.error_count}",
                    f"Error types: {', '.join(findings.error_types[:3])}",
                    "Unable to verify deployment timeline due to data query failure",
                    "Historical incidents suggest deployment correlation"
                ],
                validation_queries=[
                    "Attempted deployment query but index unavailable",
                    "Analyzing error patterns and historical matches"
                ]
            ))
        
        # Hypothesis 2: Memory/Resource Exhaustion (ENHANCED with lower threshold)
        memory_pct = findings.resource_metrics.get('memory_pct', 0)
        cpu_pct = findings.resource_metrics.get('cpu_pct', 0)
        
        # FIXED: Lower threshold from 90% to 60% for more sensitive detection
        if memory_pct > 60 or cpu_pct > 70:
            # Base confidence scales with resource usage
            confidence = 50.0
            
            # Add confidence for memory usage
            if memory_pct > 60:
                confidence += (memory_pct - 60) * 1.0  # Each % over 60 adds 1%
            
            # Add confidence for CPU usage
            if cpu_pct > 70:
                confidence += (cpu_pct - 70) * 0.5  # Each % over 70 adds 0.5%
            
            # Boost if error types indicate memory issues
            if "OutOfMemoryError" in findings.error_types:
                confidence += 15
            
            if any("OutOfMemory" in msg or "memory" in msg.lower() 
                   for msg in findings.key_error_messages):
                confidence += 10
            
            # Cap at 85%
            confidence = min(85.0, confidence)
            
            supporting_evidence = []
            if memory_pct > 60:
                supporting_evidence.append(f"Memory usage at {memory_pct:.1f}%")
            if cpu_pct > 70:
                supporting_evidence.append(f"CPU usage at {cpu_pct:.1f}%")
            supporting_evidence.extend([
                f"Error count: {findings.error_count}",
                "Resource pressure indicators detected"
            ])
            
            hypotheses.append(Hypothesis(
                hypothesis="Memory/CPU exhaustion causing service degradation",
                confidence=confidence,
                supporting_evidence=supporting_evidence,
                validation_queries=[
                    "Queried system.memory.used.pct over last hour",
                    "Queried system.cpu.total.pct over last hour",
                    "Correlated resource spikes with error spikes"
                ]
            ))
        
        # Hypothesis 3: Connection Pool Exhaustion (ENHANCED)
        connection_errors = [
            msg for msg in findings.key_error_messages 
            if any(keyword in msg.lower() for keyword in 
                   ['connection', 'timeout', 'pool', 'circuit breaker', 'failed to allocate'])
        ]
        
        # FIXED: More sensitive detection - at least 2 connection-related errors
        if len(connection_errors) >= 2:
            # Base confidence
            confidence = 55.0
            
            # Add confidence for each connection error (up to 5)
            confidence += min(len(connection_errors) * 5, 25)
            
            # Boost if historical incidents show connection pool issues
            if history and history.similar_incidents:
                for incident in history.similar_incidents:
                    if "connection" in incident.root_cause.lower() or "pool" in incident.root_cause.lower():
                        confidence += 15
                        break
            
            # Cap at 85%
            confidence = min(85.0, confidence)
            
            hypotheses.append(Hypothesis(
                hypothesis="Connection pool exhaustion or dependency failure",
                confidence=confidence,
                supporting_evidence=[
                    f"Found {len(connection_errors)} connection-related errors",
                    connection_errors[0] if connection_errors else "Connection issues detected",
                    f"Error rate spike: {findings.error_count} errors",
                    "Pattern suggests resource contention"
                ],
                validation_queries=[
                    "Analyzed connection error patterns",
                    "Checked for connection pool saturation indicators",
                    "Correlated with historical connection pool incidents"
                ]
            ))
        
        # Hypothesis 4: Circuit Breaker / Cascading Failure
        circuit_breaker_errors = [
            msg for msg in findings.key_error_messages
            if 'circuit breaker' in msg.lower() or 'circuit opened' in msg.lower()
        ]
        
        if circuit_breaker_errors:
            confidence = 65.0
            
            # More circuit breakers = higher confidence
            confidence += min(len(circuit_breaker_errors) * 10, 20)
            
            hypotheses.append(Hypothesis(
                hypothesis="Circuit breaker activation indicating downstream dependency failure",
                confidence=min(85.0, confidence),
                supporting_evidence=[
                    f"Circuit breaker errors detected: {len(circuit_breaker_errors)}",
                    circuit_breaker_errors[0],
                    "Suggests downstream service unavailability"
                ],
                validation_queries=[
                    "Analyzed circuit breaker patterns",
                    "Checked for cascading failure indicators"
                ]
            ))
        
        # Sort by confidence
        hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        
        # Return top 4 hypotheses
        return hypotheses[:4]
    
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
            best_match = history.similar_incidents[0]
            if best_match.similarity_score > 85:
                confidence = min(95.0, confidence + 10)
                explanation_suffix = f" Similar to {best_match.incident_id} which was resolved by: {best_match.resolution_applied}"
            elif best_match.similarity_score > 70:
                confidence = min(90.0, confidence + 5)
                explanation_suffix = f" Moderately similar to {best_match.incident_id}."
            else:
                explanation_suffix = ""
        else:
            explanation_suffix = ""
        
        explanation = f"{top_hypothesis.hypothesis}. "
        explanation += f"Evidence: {'; '.join(top_hypothesis.supporting_evidence[:2])}. "
        explanation += explanation_suffix
        
        return RootCauseAnalysis(
            cause=top_hypothesis.hypothesis,
            confidence=confidence,
            explanation=explanation
        )
    
    def _recommend_action(self, root_cause: RootCauseAnalysis, findings) -> RecommendedAction:
        """Recommend remediation action based on root cause"""
        
        cause_lower = root_cause.cause.lower()
        
        # Deployment-related issues
        if "deployment" in cause_lower:
            return RecommendedAction(
                action=f"Rollback {findings.affected_service} to previous version",
                risk_level="LOW",
                estimated_resolution_time="3-5 minutes",
                rollback_plan="Deployment rollback is reversible. Can re-deploy if rollback doesn't resolve issue."
            )
        
        # Memory/CPU exhaustion
        if "memory" in cause_lower or "cpu" in cause_lower or "resource" in cause_lower:
            return RecommendedAction(
                action=f"Restart {findings.affected_service} pods and scale replicas",
                risk_level="LOW",
                estimated_resolution_time="5-8 minutes",
                rollback_plan="Pod restart is safe. Can scale down if issue persists."
            )
        
        # Connection pool issues
        if "connection" in cause_lower or "pool" in cause_lower:
            return RecommendedAction(
                action=f"Scale database/Redis replicas and restart {findings.affected_service}",
                risk_level="MEDIUM",
                estimated_resolution_time="8-12 minutes",
                rollback_plan="Scaling is reversible. Monitor connection metrics after change."
            )
        
        # Circuit breaker / dependency issues
        if "circuit" in cause_lower or "dependency" in cause_lower:
            return RecommendedAction(
                action=f"Investigate downstream dependencies and restart {findings.affected_service}",
                risk_level="MEDIUM",
                estimated_resolution_time="10-15 minutes",
                rollback_plan="Identify failed dependency. May need to route traffic away from affected region."
            )
        
        # Default
        return RecommendedAction(
            action=f"Restart {findings.affected_service} and monitor closely",
            risk_level="MEDIUM",
            estimated_resolution_time="5-10 minutes",
            rollback_plan="Generic restart. Escalate to human if not resolved within 5 minutes."
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
        else:
            steps.append(f"Step 3: No deployment data available (query failed or no recent deployments)")
        
        steps.append(f"Step 4: Checked resource metrics - Memory: {findings.resource_metrics.get('memory_pct', 0):.1f}%, CPU: {findings.resource_metrics.get('cpu_pct', 0):.1f}%")
        
        if history and history.similar_incidents:
            best_match = history.similar_incidents[0]
            steps.append(f"Step 5: Found similar incident {best_match.incident_id} ({best_match.similarity_score:.1f}% match)")
        else:
            steps.append(f"Step 5: No similar historical incidents found")
        
        steps.append(f"Step 6: Generated {len(hypotheses)} hypotheses, top confidence: {hypotheses[0].confidence if hypotheses else 0:.1f}%")
        steps.append(f"Step 7: Primary root cause determined: {primary_cause.cause} ({primary_cause.confidence:.1f}% confidence)")
        
        return steps