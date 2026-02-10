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


def initialize_orchestrator(use_elasticsearch: bool = True) -> IncidentOrchestrator:
    """
    Initialize the incident response orchestrator with all agents
    
    Args:
        use_elasticsearch: If True, connect to Elasticsearch; if False, use simulation
    
    Returns:
        Configured IncidentOrchestrator instance
    """
    # Load environment variables
    load_dotenv()
    
    # Get configuration
    print(f"  - Elasticsearch: {'ENABLED' if use_elasticsearch else 'DISABLED (simulation mode)'}")
    
    # Initialize Elasticsearch tools if requested
    esql_tool = None
    search_tool = None
    
    if use_elasticsearch:
        try:
            from tools.elasticsearch import get_elasticsearch_client, ESQLTool, SearchTool
            
            print(f"  - Attempting to connect to Elasticsearch...")
            es_client = get_elasticsearch_client()
            esql_tool = ESQLTool(es_client)
            search_tool = SearchTool(es_client)
            
            
        except ImportError as e:
            print(f"  ⚠️  Elasticsearch tools not available: {str(e)}")
            print(f"  ⚠️  Make sure to install: pip install elasticsearch")
            print(f"  ⚠️  Falling back to simulation mode")
            use_elasticsearch = False
        except ConnectionError as e:
            print(f"  ⚠️  Could not connect to Elasticsearch: {str(e)}")
            print(f"  ℹ️  Is Elasticsearch running? Try: docker-compose up -d")
            print(f"  ⚠️  Falling back to simulation mode")
            use_elasticsearch = False
        except Exception as e:
            print(f"  ⚠️  Elasticsearch error: {str(e)}")
            print(f"  ⚠️  Falling back to simulation mode")
            use_elasticsearch = False
    
    # Initialize agents
    detective = DetectiveAgent(
        elasticsearch_tool=esql_tool,
        use_real_es=use_elasticsearch
    )
    
    historian = HistorianAgent(
        elasticsearch_tool=esql_tool,
        search_tool=search_tool,
        use_real_es=use_elasticsearch
    )
    
    analyzer = AnalyzerAgent(
        elasticsearch_tool=esql_tool
    )
    
    responder = ResponderAgent()
    
    # Create orchestrator
    orchestrator = IncidentOrchestrator(
        detective_agent=detective,
        historian_agent=historian,
        analyzer_agent=analyzer,
        responder_agent=responder
    )
    
    print(f"✅ Orchestrator initialized successfully\n")
    
    return orchestrator


def main():
    """
    Main application entry point
    For production use, this would listen to webhook alerts
    """
    import sys
    
    # Check for --no-es flag
    use_es = "--no-es" not in sys.argv
    
    # Initialize the orchestrator
    orchestrator = initialize_orchestrator(use_elasticsearch=use_es)
    
    print("Incident Response Orchestrator is running...")
    print("Waiting for alerts...")
    print("\nFor demo purposes, run demo.py to simulate an incident")
    print("  With Elasticsearch: python demo.py")
    print("  Without Elasticsearch: python demo.py --no-es\n")
    
    # In production, this would:
    # 1. Start a web server to receive webhook alerts
    # 2. For each alert, call: orchestrator.handle_alert(alert)
    # 3. Store results in Elasticsearch incident-reports index
    # 4. Send notifications via Slack/PagerDuty


if __name__ == "__main__":
    main()