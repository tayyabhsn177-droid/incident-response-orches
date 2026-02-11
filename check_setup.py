"""
Quick verification: Are indices set up?
"""
import os
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

load_dotenv()

client = Elasticsearch(
    os.getenv("ELASTICSEARCH_URL"),
    api_key=os.getenv("ELASTIC_API_KEY"),
)

print("\n" + "="*80)
print("QUICK ELASTICSEARCH CHECK")
print("="*80 + "\n")

# Check if required indices exist
required = {
    'logs-app': 'Application logs',
    'metrics-system': 'System metrics',
    'deployments': 'Deployment history',
    'incidents-history': 'Historical incidents'
}

missing = []
for index, desc in required.items():
    try:
        exists = client.indices.exists(index=index)
        count = client.count(index=index)['count'] if exists else 0
        
        if exists and count > 0:
            print(f"✅ {index:<20} {count:>6} docs  ({desc})")
        elif exists:
            print(f"⚠️  {index:<20} {count:>6} docs  ({desc}) - NO DATA!")
            missing.append(index)
        else:
            print(f"❌ {index:<20}         MISSING  ({desc})")
            missing.append(index)
    except Exception as e:
        print(f"❌ {index:<20}         ERROR: {e}")
        missing.append(index)

print("\n" + "="*80)

if missing:
    print("\n🚨 SETUP REQUIRED!\n")
    print("Missing or empty indices detected. Run these commands:\n")
    print("1. Create indices:")
    print("   python tools/elasticsearch/setup_indices.py\n")
    print("2. Load sample data:")
    print("   python tools/elasticsearch/load_sample_data.py\n")
    print("3. Re-run demo:")
    print("   python demo.py 1\n")
else:
    print("\n✅ All indices present and have data!")
    print("\nYou should be able to run: python demo.py 1")
    
print("="*80 + "\n")