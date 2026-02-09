"""
Script to set up all required Elasticsearch indices
"""

from tools.elasticsearch.client import ElasticsearchClient


# Index mappings
INDICES = {
    "logs-app": {
        "properties": {
            "@timestamp": {"type": "date"},
            "service.name": {"type": "keyword"},
            "log.level": {"type": "keyword"},
            "message": {"type": "text"},
            "error.stack_trace": {"type": "text"},
            "error.type": {"type": "keyword"},
            "host.name": {"type": "keyword"},
            "host.region": {"type": "keyword"},
            "http.request.method": {"type": "keyword"},
            "http.response.status_code": {"type": "integer"}
        }
    },
    
    "metrics-system": {
        "properties": {
            "@timestamp": {"type": "date"},
            "metricset.name": {"type": "keyword"},
            "host.name": {"type": "keyword"},
            "host.region": {"type": "keyword"},
            "system.cpu.total.pct": {"type": "float"},
            "system.memory.used.pct": {"type": "float"},
            "system.disk.used.pct": {"type": "float"},
            "system.network.in.bytes": {"type": "long"},
            "service.name": {"type": "keyword"}
        }
    },
    
    "deployments": {
        "properties": {
            "@timestamp": {"type": "date"},
            "service.name": {"type": "keyword"},
            "deployment.version": {"type": "keyword"},
            "deployment.previous_version": {"type": "keyword"},
            "deployment.deployed_by": {"type": "keyword"},
            "deployment.commit_sha": {"type": "keyword"},
            "deployment.status": {"type": "keyword"}
        }
    },
    
    "incidents-history": {
        "properties": {
            "incident_id": {"type": "keyword"},
            "@timestamp": {"type": "date"},
            "service.name": {"type": "keyword"},
            "symptoms": {"type": "text"},
            "error_types": {"type": "keyword"},
            "affected_regions": {"type": "keyword"},
            "root_cause": {"type": "text"},
            "root_cause_category": {"type": "keyword"},
            "resolution_steps": {"type": "text"},
            "time_to_detect_minutes": {"type": "integer"},
            "time_to_resolve_minutes": {"type": "integer"},
            "downtime_minutes": {"type": "integer"},
            "resolved_by": {"type": "keyword"},
            "prevented_recurrence": {"type": "boolean"},
            "incident_embedding": {
                "type": "dense_vector",
                "dims": 1536,
                "index": True,
                "similarity": "cosine"
            },
            "tags": {"type": "keyword"}
        }
    },
    
    "incident-reports": {
        "properties": {
            "incident_id": {"type": "keyword"},
            "@timestamp": {"type": "date"},
            "status": {"type": "keyword"},
            "alert_payload": {"type": "object", "enabled": False},
            "detective_findings": {"type": "object", "enabled": False},
            "historian_matches": {"type": "object", "enabled": False},
            "analyzer_diagnosis": {"type": "object", "enabled": False},
            "responder_actions": {"type": "object", "enabled": False},
            "timeline": {"type": "object", "enabled": False},
            "resolution_time_seconds": {"type": "float"},
            "was_auto_resolved": {"type": "boolean"}
        }
    }
}


def setup_indices(es_client: ElasticsearchClient, recreate: bool = False):
    """
    Set up all required indices
    
    Args:
        es_client: Elasticsearch client
        recreate: If True, delete and recreate existing indices
    """
    print("\n" + "="*80)
    print("ELASTICSEARCH INDEX SETUP")
    print("="*80 + "\n")
    
    for index_name, mappings in INDICES.items():
        print(f"Setting up index: {index_name}")
        
        if recreate and es_client.index_exists(index_name):
            print(f"  - Deleting existing index...")
            es_client.delete_index(index_name)
        
        if not es_client.index_exists(index_name):
            es_client.create_index(index_name, mappings)
        else:
            print(f"  - Index already exists, skipping")
        
        print()
    
    print("="*80)
    print("✅ Index setup complete!")
    print("="*80 + "\n")


def main():
    """Main function to run index setup"""
    import sys
    
    # Check for recreate flag
    recreate = "--recreate" in sys.argv
    
    if recreate:
        print("⚠️  WARNING: This will delete and recreate all indices!")
        response = input("Are you sure? (yes/no): ")
        if response.lower() != "yes":
            print("Cancelled.")
            return
    
    try:
        # Create client
        es_client = ElasticsearchClient()
        
        # Check health
        health = es_client.health()
        print(f"Cluster status: {health.get('status', 'unknown')}")
        print()
        
        # Setup indices
        setup_indices(es_client, recreate)
        
        # Show summary
        print("\nIndex Summary:")
        print("-" * 80)
        for index_name in INDICES.keys():
            doc_count = es_client.count(index_name)
            print(f"  {index_name}: {doc_count} documents")
        
        print("\n✅ Setup complete! You can now run the sample data loader.")
        print("   Run: python tools/elasticsearch/load_sample_data.py")
        
    except Exception as e:
        print(f"\n❌ Setup failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()