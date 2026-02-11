"""
Load sample data into Elasticsearch for testing
Creates realistic production-like data
"""

import random
from datetime import datetime, timedelta
from client import ElasticsearchClient


def generate_sample_logs(service_name: str, start_time: datetime, num_docs: int = 1000) -> list:
    """Generate sample application logs"""
    
    logs = []
    error_types = [
        "ConnectionTimeoutException",
        "OutOfMemoryError",
        "NullPointerException",
        "IOException",
        "ServiceUnavailableException"
    ]
    
    error_messages = [
        "Connection timeout to Redis after 5000ms",
        "OutOfMemoryError: Java heap space exceeded",
        "Failed to allocate connection from pool",
        "HTTP 503: Service temporarily unavailable",
        "Circuit breaker opened for redis-connection",
        "Database connection timeout after 30s",
        "Failed to serialize response object",
        "Rate limit exceeded for API key"
    ]
    
    hosts = [f"pod-{service_name}-{i:04d}" for i in range(1, 6)]
    regions = ["us-west-2", "us-east-1", "eu-west-1"]
    log_levels = ["INFO", "WARN", "ERROR", "FATAL", "DEBUG"]
    
    # Create a spike of errors around 25 minutes after start
    spike_time = start_time + timedelta(minutes=25)
    
    for i in range(num_docs):
        # Calculate time - more errors during spike
        time_offset = random.randint(0, 60)  # 60 minutes range
        timestamp = start_time + timedelta(minutes=time_offset)
        
        # Determine if this is during error spike
        is_spike = abs((timestamp - spike_time).total_seconds()) < 600  # Within 10 min of spike
        
        # Higher chance of errors during spike
        if is_spike:
            level = random.choices(
                log_levels,
                weights=[20, 20, 40, 15, 5]  # More errors
            )[0]
        else:
            level = random.choices(
                log_levels,
                weights=[60, 20, 10, 2, 8]  # Normal distribution
            )[0]
        
        log = {
            "@timestamp": timestamp.isoformat(),
            "service.name": service_name,
            "log.level": level,
            "host.name": random.choice(hosts),
            "host.region": random.choice(regions)
        }
        
        if level in ["ERROR", "FATAL"]:
            log["message"] = random.choice(error_messages)
            log["error.type"] = random.choice(error_types)
            log["error.stack_trace"] = f"Stack trace for {log['error.type']}"
            log["http.response.status_code"] = random.choice([500, 503, 504])
        else:
            log["message"] = f"Request processed successfully for endpoint /api/v1/{random.choice(['users', 'orders', 'products'])}"
            log["http.response.status_code"] = random.choice([200, 201, 204])
        
        log["http.request.method"] = random.choice(["GET", "POST", "PUT", "DELETE"])
        
        logs.append(log)
    
    return logs


def generate_sample_metrics(service_name: str, start_time: datetime, num_docs: int = 360) -> list:
    """Generate sample system metrics (one per minute for 6 hours)"""
    
    metrics = []
    hosts = [f"pod-{service_name}-{i:04d}" for i in range(1, 6)]
    regions = ["us-west-2", "us-east-1", "eu-west-1"]
    
    # Create memory spike around 25 minutes after start
    spike_time = start_time + timedelta(minutes=25)
    
    for i in range(num_docs):
        timestamp = start_time + timedelta(minutes=i)
        
        for host in hosts:
            # Calculate if we're near the spike
            time_diff = (timestamp - spike_time).total_seconds() / 60  # in minutes
            
            # Base CPU and memory
            base_cpu = random.uniform(0.3, 0.5)
            base_memory = random.uniform(0.5, 0.7)
            
            # Add spike effect
            if -10 <= time_diff <= 5:  # Spike from -10 to +5 minutes
                spike_factor = 1 - (abs(time_diff) / 10)  # Peak at spike_time
                base_cpu += spike_factor * 0.4
                base_memory += spike_factor * 0.35
            
            metrics.append({
                "@timestamp": timestamp.isoformat(),
                "metricset.name": "cpu",
                "host.name": host,
                "host.region": random.choice(regions),
                "system.cpu.total.pct": min(0.99, base_cpu + random.uniform(-0.05, 0.05)),
                "system.memory.used.pct": min(0.98, base_memory + random.uniform(-0.05, 0.05)),
                "system.disk.used.pct": random.uniform(0.4, 0.6),
                "system.network.in.bytes": random.randint(1000000, 5000000),
                "service.name": service_name
            })
    
    return metrics


def generate_sample_deployments(service_name: str, start_time: datetime) -> list:
    """Generate sample deployment events"""
    
    # Deployment happened 25 minutes before spike (which is at +25 min from start)
    # So deployment is at start_time
    deployment_time = start_time
    
    deployments = [
        {
            "@timestamp": (deployment_time - timedelta(hours=24)).isoformat(),
            "service.name": service_name,
            "deployment.version": "v2.3.8",
            "deployment.previous_version": "v2.3.7",
            "deployment.deployed_by": "jenkins-ci",
            "deployment.commit_sha": "abc123old",
            "deployment.status": "completed"
        },
        {
            "@timestamp": deployment_time.isoformat(),
            "service.name": service_name,
            "deployment.version": "v2.4.1",
            "deployment.previous_version": "v2.3.8",
            "deployment.deployed_by": "jenkins-ci",
            "deployment.commit_sha": "def456new",
            "deployment.status": "completed"
        }
    ]
    
    return deployments


def generate_historical_incidents() -> list:
    """Generate historical incident data"""
    
    incidents = [
        {
            "incident_id": "INC-2847",
            "@timestamp": "2025-12-15T03:22:00Z",
            "service.name": "checkout-api",
            "symptoms": "5xx errors spiked 340%, memory usage 98%, pod restarts every 2min",
            "error_types": ["OutOfMemoryError", "ConnectionTimeoutException"],
            "affected_regions": ["us-west-2"],
            "root_cause": "Memory leak in Redis connection pool introduced in v2.3.0",
            "root_cause_category": "memory-leak",
            "resolution_steps": [
                "Rolled back from v2.3.0 to v2.2.8",
                "Scaled Redis from 4 to 6 replicas",
                "Added connection pool max size limit in config"
            ],
            "time_to_detect_minutes": 5,
            "time_to_resolve_minutes": 23,
            "downtime_minutes": 28,
            "resolved_by": "john.doe",
            "prevented_recurrence": True,
            "tags": ["deployment", "memory-leak", "redis", "auto-resolved"]
        },
        {
            "incident_id": "INC-2691",
            "@timestamp": "2025-11-28T14:45:00Z",
            "service.name": "checkout-api",
            "symptoms": "Connection timeouts spiking, high memory usage, service degradation",
            "error_types": ["ConnectionTimeoutException", "SocketTimeoutException"],
            "affected_regions": ["us-west-2", "us-east-1"],
            "root_cause": "Database connection pool exhaustion after traffic spike",
            "root_cause_category": "connection-pool",
            "resolution_steps": [
                "Increased connection pool size from 50 to 100",
                "Added circuit breaker with 10s timeout",
                "Enabled connection pool monitoring"
            ],
            "time_to_detect_minutes": 8,
            "time_to_resolve_minutes": 45,
            "downtime_minutes": 53,
            "resolved_by": "sarah.smith",
            "prevented_recurrence": True,
            "tags": ["connection-pool", "database", "traffic-spike"]
        },
        {
            "incident_id": "INC-2534",
            "@timestamp": "2025-10-12T09:30:00Z",
            "service.name": "checkout-api",
            "symptoms": "High CPU usage, slow response times, service degradation",
            "error_types": ["SlowQueryException"],
            "affected_regions": ["us-west-2"],
            "root_cause": "Inefficient query after database schema migration",
            "root_cause_category": "performance",
            "resolution_steps": [
                "Optimized query with proper JOIN",
                "Added database index on user_id column",
                "Enabled query caching"
            ],
            "time_to_detect_minutes": 15,
            "time_to_resolve_minutes": 67,
            "downtime_minutes": 82,
            "resolved_by": "mike.jones",
            "prevented_recurrence": True,
            "tags": ["performance", "database", "query-optimization"]
        },
        {
            "incident_id": "INC-2401",
            "@timestamp": "2025-09-20T18:12:00Z",
            "service.name": "user-service",
            "symptoms": "Authentication failures, Redis connection errors, user login issues",
            "error_types": ["ConnectionRefusedException", "AuthenticationException"],
            "affected_regions": ["eu-west-1"],
            "root_cause": "Redis cluster failover caused connection pool drain",
            "root_cause_category": "infrastructure",
            "resolution_steps": [
                "Restarted Redis connection pool",
                "Scaled Redis cluster from 3 to 5 nodes",
                "Implemented connection retry logic"
            ],
            "time_to_detect_minutes": 3,
            "time_to_resolve_minutes": 18,
            "downtime_minutes": 21,
            "resolved_by": "automated",
            "prevented_recurrence": True,
            "tags": ["redis", "infrastructure", "auto-resolved"]
        }
    ]
    
    return incidents


def main():
    """Load all sample data"""
    print("\n" + "="*80)
    print("LOADING SAMPLE DATA")
    print("="*80 + "\n")
    
    try:
        # Create client
        es_client = ElasticsearchClient()
        
        # Set base time (1 hour ago)
        base_time = datetime.utcnow() - timedelta(hours=1)
        service_name = "checkout-api"
        
        # 1. Load logs
        print("Loading application logs...")
        logs = generate_sample_logs(service_name, base_time, num_docs=2000)
        success, errors = es_client.bulk_index("logs-app", logs)
        print(f"  ✅ Indexed {success} log documents\n")
        
        # 2. Load metrics
        print("Loading system metrics...")
        metrics = generate_sample_metrics(service_name, base_time, num_docs=360)
        success, errors = es_client.bulk_index("metrics-system", metrics)
        print(f"  ✅ Indexed {success} metric documents\n")
        
        # 3. Load deployments
        print("Loading deployment events...")
        deployments = generate_sample_deployments(service_name, base_time)
        success, errors = es_client.bulk_index("deployments", deployments)
        print(f"  ✅ Indexed {success} deployment documents\n")
        
        # 4. Load historical incidents
        print("Loading historical incidents...")
        incidents = generate_historical_incidents()
        for incident in incidents:
            es_client.index_document("incidents-history", incident, incident["incident_id"])
        print(f"  ✅ Indexed {len(incidents)} historical incidents\n")
        
        # Summary
        print("="*80)
        print("DATA LOADING SUMMARY")
        print("="*80)
        print(f"  logs-app: {es_client.count('logs-app')} documents")
        print(f"  metrics-system: {es_client.count('metrics-system')} documents")
        print(f"  deployments: {es_client.count('deployments')} documents")
        print(f"  incidents-history: {es_client.count('incidents-history')} documents")
        print()
        
        print("✅ Sample data loaded successfully!")
        print("\n📝 Data timeline:")
        print(f"  - Base time: {base_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  - Deployment at: {base_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  - Error spike at: {(base_time + timedelta(minutes=25)).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  - Data range: 1 hour window")
        print()
        print("🚀 You can now run the demo with real Elasticsearch data!")
        print("   Run: python demo.py")
        
    except Exception as e:
        print(f"\n❌ Failed to load sample data: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()