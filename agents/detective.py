"""
Detective Agent - Rapidly gathers context about the incident
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from agents.state import IncidentState, DetectiveFindings


class DetectiveAgent:
    """
    Detective Agent specializes in production incident investigation.
    Collects error logs, system metrics, deployment history, and geographic scope.
    """
    
    SYSTEM_PROMPT = """You are a Detective Agent specializing in production incident investigation.

Your job:
1. Collect error logs from the affected service in the ±30 minute window around the alert time
2. Query system metrics (CPU, memory, network, disk) for the affected hosts
3. Check recent deployments (last 2 hours)
4. Identify geographic scope (which regions/data centers affected)
5. Check external dependency status
6. Summarize findings in structured JSON

Use ES|QL for precise time-windowed queries. Be thorough but fast - aim for 60-90 seconds investigation time.

You will be provided with:
- Service name: {service_name}
- Alert timestamp: {alert_timestamp}
- Alert message: {alert_message}
- Severity: {severity}

Based on the alert, you need to:
1. Query error logs to find the error spike pattern
2. Get system metrics for affected hosts
3. Check for recent deployments
4. Identify affected regions
5. Extract key error messages

Think step-by-step and be precise with your time windows.
"""

    USER_PROMPT = """Investigate this incident:

Service: {service_name}
Alert Time: {alert_timestamp}
Severity: {severity}
Message: {alert_message}

Provide your findings in JSON format with these fields:
- affected_service
- error_spike_time
- error_count
- error_types (list)
- affected_hosts (list)
- affected_regions (list)
- resource_metrics (dict with cpu_pct, memory_pct, disk_pct)
- recent_deployments (list of dicts)
- key_error_messages (list of top 5-10 error messages)
"""

    def __init__(self, model_name: str = "gpt-4o", elasticsearch_tool=None, use_real_es: bool = True):
        """
        Initialize the Detective Agent
        
        Args:
            model_name: OpenAI model to use
            elasticsearch_tool: Tool for querying Elasticsearch
            use_real_es: If True, use real Elasticsearch; if False, use simulated data
        """
        self.llm = ChatOpenAI(model=model_name, temperature=0)
        self.elasticsearch_tool = elasticsearch_tool
        self.use_real_es = use_real_es and elasticsearch_tool is not None
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("user", self.USER_PROMPT)
        ])
    
    def investigate(self, state: IncidentState) -> Dict[str, Any]:
        """
        Main investigation method
        
        Args:
            state: Current incident state
            
        Returns:
            Dictionary to update the state with detective findings
        """
        start_time = time.time()
        
        try:
            state.add_timeline_event(
                agent="detective",
                event="Investigation started",
                details={"service": state.alert.service}
            )
            
            # Prepare the prompt
            prompt_input = {
                "service_name": state.alert.service,
                "alert_timestamp": state.alert.timestamp.isoformat(),
                "severity": state.alert.severity,
                "alert_message": state.alert.message
            }
            
            # Query Elasticsearch or use simulation
            if self.use_real_es:
                findings = self._real_investigation(state)
            else:
                findings = self._simulate_investigation(state)
            
            investigation_duration = time.time() - start_time
            findings.investigation_duration_seconds = investigation_duration
            
            state.add_timeline_event(
                agent="detective",
                event="Investigation completed",
                details={
                    "duration_seconds": investigation_duration,
                    "error_count": findings.error_count,
                    "affected_hosts": len(findings.affected_hosts)
                }
            )
            
            return {
                "detective_findings": findings,
                "workflow_status": "investigating"
            }
            
        except Exception as e:
            state.add_timeline_event(
                agent="detective",
                event="Investigation failed",
                details={"error": str(e)}
            )
            raise
    
    def _real_investigation(self, state: IncidentState) -> DetectiveFindings:
        """
        Perform real investigation using Elasticsearch
        """
        alert_time = state.alert.timestamp
        service_name = state.alert.service
        
        # Time windows
        start_time = alert_time - timedelta(minutes=30)
        end_time = alert_time + timedelta(minutes=30)
        
        print(f"  🔍 Querying logs from {start_time.strftime('%H:%M')} to {end_time.strftime('%H:%M')}")
        
        # 1. Get error timeline
        try:
            error_timeline = self.elasticsearch_tool.get_error_timeline(
                service_name=service_name,
                start_time=start_time,
                end_time=end_time
            )
            
            # Calculate total errors
            error_count = sum(entry['error_count'] for entry in error_timeline)
            
            # Find spike time (max errors)
            if error_timeline:
                spike_entry = max(error_timeline, key=lambda x: x['error_count'])
                error_spike_time = datetime.fromisoformat(spike_entry['timestamp'])
            else:
                error_spike_time = alert_time
            
            print(f"  📊 Found {error_count} errors")
            
        except Exception as e:
            print(f"  ⚠️  Could not query error timeline: {str(e)}")
            error_count = 0
            error_spike_time = alert_time
        
        # 2. Get error messages
        try:
            error_messages = self.elasticsearch_tool.get_error_messages(
                service_name=service_name,
                start_time=start_time,
                end_time=end_time,
                limit=10
            )
            print(f"  📝 Extracted {len(error_messages)} unique error messages")
        except Exception as e:
            print(f"  ⚠️  Could not get error messages: {str(e)}")
            error_messages = ["Error data unavailable"]
        
        # 3. Get deployments
        try:
            recent_deployments = self.elasticsearch_tool.get_recent_deployments(
                service_name=service_name,
                start_time=alert_time - timedelta(hours=2),
                limit=5
            )
            print(f"  🚀 Found {len(recent_deployments)} recent deployments")
        except Exception as e:
            print(f"  ⚠️  Could not get deployments: {str(e)}")
            recent_deployments = []
        
        # 4. Determine affected hosts from logs (simplified - would query)
        affected_hosts = [f"pod-{service_name}-{i:04d}" for i in range(1, 4)]
        
        # 5. Determine affected regions (simplified - would query)
        affected_regions = ["us-west-2", "us-east-1"]
        
        # 6. Get resource metrics (if we have affected hosts)
        try:
            if affected_hosts:
                metrics_result = self.elasticsearch_tool.get_resource_metrics(
                    host_names=affected_hosts[:3],  # Query first 3 hosts
                    start_time=start_time
                )
                
                # Average across hosts
                if metrics_result:
                    avg_cpu = sum(m['cpu_pct'] for m in metrics_result.values()) / len(metrics_result)
                    avg_memory = sum(m['memory_pct'] for m in metrics_result.values()) / len(metrics_result)
                    resource_metrics = {
                        "cpu_pct": avg_cpu,
                        "memory_pct": avg_memory,
                        "disk_pct": 45.0  # Default
                    }
                    print(f"  💻 Resource usage - CPU: {avg_cpu:.1f}%, Memory: {avg_memory:.1f}%")
                else:
                    resource_metrics = {"cpu_pct": 50.0, "memory_pct": 70.0, "disk_pct": 45.0}
            else:
                resource_metrics = {"cpu_pct": 50.0, "memory_pct": 70.0, "disk_pct": 45.0}
        except Exception as e:
            print(f"  ⚠️  Could not get resource metrics: {str(e)}")
            resource_metrics = {"cpu_pct": 50.0, "memory_pct": 70.0, "disk_pct": 45.0}
        
        # Extract error types from messages
        error_types = []
        for msg in error_messages[:5]:
            if "OutOfMemory" in msg:
                error_types.append("OutOfMemoryError")
            elif "Connection" in msg or "timeout" in msg:
                error_types.append("ConnectionTimeoutException")
            elif "503" in msg or "unavailable" in msg:
                error_types.append("ServiceUnavailableException")
        
        if not error_types:
            error_types = ["UnknownException"]
        
        return DetectiveFindings(
            affected_service=service_name,
            error_spike_time=error_spike_time,
            error_count=error_count,
            error_types=list(set(error_types)),  # Unique types
            affected_hosts=affected_hosts,
            affected_regions=affected_regions,
            resource_metrics=resource_metrics,
            recent_deployments=recent_deployments,
            key_error_messages=error_messages[:10],
            investigation_duration_seconds=0.0
        )
    
    def _simulate_investigation(self, state: IncidentState) -> DetectiveFindings:
        """
        Simulate investigation results for testing
        In production, this would query Elasticsearch
        """
        # Calculate time windows
        alert_time = state.alert.timestamp
        
        return DetectiveFindings(
            affected_service=state.alert.service,
            error_spike_time=alert_time,
            error_count=1247,
            error_types=[
                "ConnectionTimeoutException",
                "OutOfMemoryError",
                "503 Service Unavailable"
            ],
            affected_hosts=[
                f"pod-{state.alert.service}-7f8d9c-abc12",
                f"pod-{state.alert.service}-7f8d9c-def34",
                f"pod-{state.alert.service}-7f8d9c-ghi56"
            ],
            affected_regions=["us-west-2", "us-east-1"],
            resource_metrics={
                "cpu_pct": 87.5,
                "memory_pct": 94.2,
                "disk_pct": 45.3
            },
            recent_deployments=[
                {
                    "version": "v2.4.1",
                    "timestamp": (alert_time - timedelta(minutes=25)).isoformat(),
                    "deployed_by": "jenkins-ci",
                    "commit_sha": "abc123def"
                }
            ],
            key_error_messages=[
                "Connection timeout to Redis after 5000ms",
                "OutOfMemoryError: Java heap space exceeded",
                "Failed to allocate connection from pool",
                "HTTP 503: Service temporarily unavailable",
                "Circuit breaker opened for redis-connection"
            ],
            investigation_duration_seconds=0.0  # Will be set by investigate()
        )
    
    def _query_error_logs(self, service: str, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """
        Query Elasticsearch for error logs
        This is a placeholder - will be implemented when ES tools are ready
        """
        if self.elasticsearch_tool:
            query = f"""
            FROM logs-*
            | WHERE @timestamp >= "{start_time.isoformat()}"
            | WHERE @timestamp <= "{end_time.isoformat()}"
            | WHERE service.name == "{service}"
            | WHERE log.level IN ("ERROR", "FATAL", "CRITICAL")
            | STATS error_count = COUNT(*) BY BUCKET(@timestamp, 1 minute)
            | SORT @timestamp
            """
            return self.elasticsearch_tool.execute_esql(query)
        
        return {}
    
    def _query_system_metrics(self, hosts: list, start_time: datetime) -> Dict[str, Any]:
        """
        Query system metrics from Elasticsearch
        This is a placeholder - will be implemented when ES tools are ready
        """
        if self.elasticsearch_tool:
            hosts_str = ", ".join([f'"{h}"' for h in hosts])
            query = f"""
            FROM metrics-*
            | WHERE @timestamp >= "{start_time.isoformat()}"
            | WHERE host.name IN ({hosts_str})
            | WHERE metricset.name IN ("cpu", "memory")
            | STATS avg_cpu = AVG(system.cpu.total.pct),
                    avg_memory = AVG(system.memory.used.pct)
              BY host.name
            """
            return self.elasticsearch_tool.execute_esql(query)
        
        return {}