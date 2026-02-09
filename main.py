"""
Main application for Incident Response Orchestrator
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from agents.state import AlertPayload
from agents.detective import DetectiveAgent
from agents.historian import HistorianAgent
from agents.analyzer import AnalyzerAgent
from agents.responder import ResponderAgent
from agents.orchestrator import IncidentOrchestrator


def initialize_orchestrator() -> IncidentOrchestrator:
    """
    Initialize the incident response orchestrator with all agents
    
    Returns:
        Configured IncidentOrchestrator instance
    """
    # Load environment variables
    load_dotenv()
    
    # Get configuration
    model_name = os.getenv("DEFAULT_MODEL", "gpt-4o")
    analyzer_model = os.getenv("ANALYZER_MODEL", "gpt-4o")
    
    print(f"Initializing Incident Response Orchestrator...")
    print(f"  - Default Model: {model_name}")
    print(f"  - Analyzer Model: {analyzer_model}")
    
    # Initialize agents
    detective = DetectiveAgent(model_name=model_name)
    historian = HistorianAgent(model_name=model_name)
    analyzer = AnalyzerAgent(model_name=analyzer_model)
    responder = ResponderAgent(model_name=model_name)
    
    # Create orchestrator
    orchestrator = IncidentOrchestrator(
        detective_agent=detective,
        historian_agent=historian,
        analyzer_agent=analyzer,
        responder_agent=responder
    )
    
    print(f"Orchestrator initialized successfully\n")
    
    return orchestrator


def main():
    """
    Main application entry point
    For production use, this would listen to webhook alerts
    """
    # Initialize the orchestrator
    orchestrator = initialize_orchestrator()
    
    print("Incident Response Orchestrator is running...")
    print("Waiting for alerts...")
    print("\nFor demo purposes, run demo.py to simulate an incident\n")
    
    # In production, this would:
    # 1. Start a web server to receive webhook alerts
    # 2. For each alert, call: orchestrator.handle_alert(alert)
    # 3. Store results in Elasticsearch incident-reports index
    # 4. Send notifications via Slack/PagerDuty


if __name__ == "__main__":
    main()