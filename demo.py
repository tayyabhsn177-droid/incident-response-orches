"""
Demo script to test the Incident Response Orchestrator
Simulates a production incident and shows the full workflow
"""

import json
from datetime import datetime
from agents.state import AlertPayload
from main import initialize_orchestrator


def demo_scenario_1_bad_deployment():
    """
    Scenario 1: Bad deployment causing 5xx errors
    - Memory leak introduced in v2.4.1
    - High similarity to past incident
    - Should trigger auto-rollback
    """
    print("\n" + "="*100)
    print("DEMO SCENARIO 1: Bad Deployment Causing Memory Leak")
    print("="*100 + "\n")
    
    alert = AlertPayload(
        alert_id="ALERT-20260203-001",
        severity="critical",
        service="checkout-api",
        timestamp=datetime.utcnow(),
        message="5xx error rate increased by 340% in the last 5 minutes",
        tags=["production", "checkout", "http-errors"]
    )
    
    return alert


def demo_scenario_2_connection_timeout():
    """
    Scenario 2: Database connection pool exhaustion
    - Connection timeouts spiking
    - Medium similarity to past incidents
    - Should request approval for scaling
    """
    print("\n" + "="*100)
    print("DEMO SCENARIO 2: Connection Pool Exhaustion")
    print("="*100 + "\n")
    
    alert = AlertPayload(
        alert_id="ALERT-20260203-002",
        severity="critical",
        service="user-service",
        timestamp=datetime.utcnow(),
        message="Database connection timeout rate exceeded threshold",
        tags=["production", "database", "timeouts"]
    )
    
    return alert


def demo_scenario_3_unknown_issue():
    """
    Scenario 3: Unknown issue with low confidence
    - New type of error
    - No historical matches
    - Should alert human
    """
    print("\n" + "="*100)
    print("DEMO SCENARIO 3: Unknown Issue - Low Confidence")
    print("="*100 + "\n")
    
    alert = AlertPayload(
        alert_id="ALERT-20260203-003",
        severity="warning",
        service="notification-service",
        timestamp=datetime.utcnow(),
        message="Unusual error pattern detected in notification delivery",
        tags=["production", "notifications", "anomaly"]
    )
    
    return alert


def run_demo(scenario_num: int = 1, use_elasticsearch: bool = True):
    """
    Run a demo scenario
    
    Args:
        scenario_num: Which scenario to run (1, 2, or 3)
        use_elasticsearch: If True, use real Elasticsearch; if False, simulate
    """
    # Initialize the orchestrator
    orchestrator = initialize_orchestrator(use_elasticsearch=use_elasticsearch)
    
    # Select scenario
    scenarios = {
        1: demo_scenario_1_bad_deployment,
        2: demo_scenario_2_connection_timeout,
        3: demo_scenario_3_unknown_issue
    }
    
    if scenario_num not in scenarios:
        print(f"Invalid scenario number. Choose 1, 2, or 3.")
        return
    
    # Get the alert for this scenario
    alert = scenarios[scenario_num]()
    
    # Handle the incident
    try:
        final_state = orchestrator.handle_alert(alert)
        
        # Generate and display the final report
        print("\n" + "="*100)
        print("INCIDENT REPORT")
        print("="*100 + "\n")
        
        report = orchestrator.generate_report(final_state)
        print(json.dumps(report, indent=2, default=str))
        
        # Summary
        print("\n" + "="*100)
        print("SUMMARY")
        print("="*100)
        print(f"Incident ID: {final_state.incident_id}")
        print(f"Total Duration: {final_state.total_duration_seconds:.2f} seconds")
        print(f"Status: {final_state.workflow_status}")
        
        if final_state.responder_action:
            print(f"Decision: {final_state.responder_action.decision}")
            print(f"Action Taken: {final_state.responder_action.action_taken}")
            print(f"Execution Status: {final_state.responder_action.execution_status}")
        
        print("="*100 + "\n")
        
        # Metrics that would be tracked
        print("\nMETRICS (would be stored in Elasticsearch):")
        print(f"  - Detection Time: < 5 seconds")
        print(f"  - Investigation Time: {final_state.detective_findings.investigation_duration_seconds:.2f}s")
        print(f"  - Analysis Time: {final_state.analyzer_diagnosis.analysis_duration_seconds:.2f}s")
        print(f"  - Response Time: {final_state.responder_action.execution_duration_seconds:.2f}s")
        print(f"  - Total MTTR: {final_state.total_duration_seconds:.2f}s")
        
        if final_state.analyzer_diagnosis:
            print(f"  - Root Cause Confidence: {final_state.analyzer_diagnosis.primary_root_cause.confidence:.1f}%")
        
        if final_state.responder_action and final_state.responder_action.decision == "AUTO_EXECUTE":
            print(f"  - Auto-Resolution: YES ✅")
        else:
            print(f"  - Auto-Resolution: NO (human approval needed)")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {str(e)}")
        raise


def run_all_scenarios():
    """Run all demo scenarios"""
    for scenario_num in [1, 2, 3]:
        run_demo(scenario_num)
        print("\n" + "*"*100 + "\n")
        input("Press Enter to continue to next scenario...")


if __name__ == "__main__":
    import sys
    
    # Check for --no-es flag
    use_es = "--no-es" not in sys.argv
    
    # Remove --no-es from args if present
    args = [arg for arg in sys.argv[1:] if arg != "--no-es"]
    
    # Check command line arguments
    if len(args) > 0:
        if args[0] == "all":
            for scenario_num in [1, 2, 3]:
                run_demo(scenario_num, use_elasticsearch=use_es)
                print("\n" + "*"*100 + "\n")
                input("Press Enter to continue to next scenario...")
        else:
            try:
                scenario = int(args[0])
                run_demo(scenario, use_elasticsearch=use_es)
            except ValueError:
                print("Usage: python demo.py [scenario_number | all] [--no-es]")
                print("  scenario_number: 1, 2, or 3")
                print("  all: Run all scenarios")
                print("  --no-es: Run without Elasticsearch (simulation mode)")
    else:
        # Default: run scenario 1
        print("Running default scenario (Bad Deployment)")
        print("Usage: python demo.py [1|2|3|all] [--no-es] to run other scenarios")
        if use_es:
            print("Mode: Using Elasticsearch (real data)\n")
        else:
            print("Mode: Simulation (no Elasticsearch)\n")
        run_demo(1, use_elasticsearch=use_es)