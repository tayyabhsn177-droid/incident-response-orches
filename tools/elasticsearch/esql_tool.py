"""
ES|QL query tool for executing Elasticsearch Query Language queries
FIXED VERSION - Corrected deployment index name from deployments-* to deployments
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from tools.elasticsearch.client import ElasticsearchClient


class ESQLTool:
    """
    Tool for executing ES|QL queries
    ES|QL is Elasticsearch's query language similar to SQL
    """
    
    def __init__(self, es_client: ElasticsearchClient):
        """
        Initialize ES|QL tool
        
        Args:
            es_client: Elasticsearch client instance
        """
        self.es_client = es_client
    
    def execute(self, query: str, format: str = "json") -> Dict[str, Any]:
        """
        Execute an ES|QL query
        
        Args:
            query: ES|QL query string
            format: Response format (json, csv, txt)
            
        Returns:
            Query results
        """
        try:
            # Use the ES|QL API - correct method according to Python client docs
            response = self.es_client.client.esql.query(
                query=query
            )
            
            # The response is an ObjectApiResponse, access the body
            return response.body
            
        except Exception as e:
            print(f"❌ ES|QL query failed: {str(e)}")
            print(f"Query: {query}")
            raise
    
    def get_error_timeline(
        self,
        service_name: str,
        start_time: datetime,
        end_time: datetime,
        error_levels: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get error timeline for a service
        
        Args:
            service_name: Service name
            start_time: Start time
            end_time: End time
            error_levels: Error levels to filter (ERROR, FATAL, CRITICAL)
            
        Returns:
            List of error counts by time bucket
        """
        if error_levels is None:
            error_levels = ["ERROR", "FATAL", "CRITICAL"]
        
        levels_str = ", ".join([f'"{level}"' for level in error_levels])
        
        # ES|QL requires backticks around field names with dots
        query = f"""
        FROM logs-*
        | WHERE @timestamp >= "{start_time.isoformat()}"
        | WHERE @timestamp <= "{end_time.isoformat()}"
        | WHERE `service.name` == "{service_name}"
        | WHERE `log.level` IN ({levels_str})
        | STATS error_count = COUNT(*) BY bucket = BUCKET(@timestamp, 1 minute)
        | SORT bucket
        """
        
        try:
            result = self.execute(query)
            
            # Parse results - ES|QL returns columns and values
            timeline = []
            if 'values' in result:
                for row in result['values']:
                    timeline.append({
                        'timestamp': row[1],  # bucket
                        'error_count': row[0]  # error_count
                    })
            
            return timeline
            
        except Exception as e:
            print(f"⚠️  Could not get error timeline: {str(e)}")
            return []
    
    def get_resource_metrics(
        self,
        host_names: List[str],
        start_time: datetime,
        metric_types: List[str] = None
    ) -> Dict[str, Dict[str, float]]:
        """
        Get resource metrics for hosts
        
        Args:
            host_names: List of host names
            start_time: Start time
            metric_types: Metric types (cpu, memory, disk)
            
        Returns:
            Dictionary of host -> metrics
        """
        if metric_types is None:
            metric_types = ["cpu", "memory"]
        
        hosts_str = ", ".join([f'"{host}"' for host in host_names])
        metrics_str = ", ".join([f'"{m}"' for m in metric_types])
        
        # ES|QL requires backticks around field names with dots
        query = f"""
        FROM metrics-*
        | WHERE @timestamp >= "{start_time.isoformat()}"
        | WHERE `host.name` IN ({hosts_str})
        | WHERE `metricset.name` IN ({metrics_str})
        | STATS avg_cpu = AVG(`system.cpu.total.pct`),
                avg_memory = AVG(`system.memory.used.pct`)
          BY `host.name`
        """
        
        try:
            result = self.execute(query)
            
            # Parse results
            metrics = {}
            if 'values' in result:
                for row in result['values']:
                    host_name = row[2]  # host.name
                    metrics[host_name] = {
                        'cpu_pct': row[0] * 100 if row[0] else 0,  # avg_cpu
                        'memory_pct': row[1] * 100 if row[1] else 0  # avg_memory
                    }
            
            return metrics
            
        except Exception as e:
            print(f"⚠️  Could not get resource metrics: {str(e)}")
            return {}
    
    def get_recent_deployments(
        self,
        service_name: str,
        start_time: datetime,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get recent deployments for a service
        
        Args:
            service_name: Service name
            start_time: Look back from this time
            limit: Maximum number of deployments
            
        Returns:
            List of deployments
        """
        # FIXED: Changed from 'deployments-*' to 'deployments' (no wildcard)
        # The actual index is named 'deployments', not a pattern
        query = f"""
        FROM deployments
        | WHERE @timestamp >= "{start_time.isoformat()}"
        | WHERE `service.name` == "{service_name}"
        | SORT @timestamp DESC
        | LIMIT {limit}
        """
        
        try:
            result = self.execute(query)
            
            # Parse results
            deployments = []
            if 'values' in result:
                # Note: Column order depends on the fields selected
                for row in result['values']:
                    deployments.append({
                        'timestamp': row[0],  # @timestamp
                        'service_name': row[1],  # service.name
                        'version': row[2] if len(row) > 2 else None,
                        'deployed_by': row[3] if len(row) > 3 else None,
                        'commit_sha': row[4] if len(row) > 4 else None
                    })
            
            return deployments
            
        except Exception as e:
            print(f"⚠️  Could not get deployments: {str(e)}")
            return []
    
    def get_error_messages(
        self,
        service_name: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 10
    ) -> List[str]:
        """
        Get top error messages for a service
        
        Args:
            service_name: Service name
            start_time: Start time
            end_time: End time
            limit: Number of messages to return
            
        Returns:
            List of error messages
        """
        # ES|QL requires backticks around field names with dots
        query = f"""
        FROM logs-*
        | WHERE @timestamp >= "{start_time.isoformat()}"
        | WHERE @timestamp <= "{end_time.isoformat()}"
        | WHERE `service.name` == "{service_name}"
        | WHERE `log.level` IN ("ERROR", "FATAL", "CRITICAL")
        | STATS count = COUNT(*) BY message
        | SORT count DESC
        | LIMIT {limit}
        """
        
        try:
            result = self.execute(query)
            
            # Parse results
            messages = []
            if 'values' in result:
                for row in result['values']:
                    messages.append(row[1])  # message
            
            return messages
            
        except Exception as e:
            print(f"⚠️  Could not get error messages: {str(e)}")
            return []


class SearchTool:
    """
    Tool for executing regular Elasticsearch queries (DSL)
    FIXED VERSION - Corrects parameter passing to avoid conflicts
    """
    
    def __init__(self, es_client: ElasticsearchClient):
        """
        Initialize search tool
        
        Args:
            es_client: Elasticsearch client instance
        """
        self.es_client = es_client
    
    def search(
        self,
        index: str,
        query: Dict[str, Any],
        size: int = 10,
        sort: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a search query
        
        Args:
            index: Index name or pattern
            query: Elasticsearch query DSL
            size: Number of results
            sort: Sort configuration
            
        Returns:
            Search results
        """
        body = {"query": query, "size": size}
        
        if sort:
            body["sort"] = sort
        
        # Call the client's search method with just body parameter
        return self.es_client.search(index, body, size)
    
    def hybrid_search(
        self,
        index: str,
        text_query: str,
        vector: List[float],
        text_fields: List[str],
        vector_field: str = "incident_embedding",
        k: int = 5,
        size: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search (keyword + vector)
        
        Args:
            index: Index name
            text_query: Text to search
            vector: Query vector
            text_fields: Fields to search with text
            vector_field: Field containing vectors
            k: Number of nearest neighbors
            size: Total results to return
            
        Returns:
            Search results
        """
        # Build query body - don't pass size as separate parameter
        query_body = {
            "query": {
                "bool": {
                    "should": [
                        {
                            "multi_match": {
                                "query": text_query,
                                "fields": text_fields
                            }
                        }
                    ]
                }
            },
            "knn": {
                "field": vector_field,
                "query_vector": vector,
                "k": k,
                "num_candidates": 50
            },
            "size": size  # size is in the body, not a separate parameter
        }
        
        # Call ES client search with only index and body
        result = self.es_client.client.search(
            index=index,
            body=query_body
        )
        
        # Extract hits
        hits = []
        if 'hits' in result and 'hits' in result['hits']:
            for hit in result['hits']['hits']:
                doc = hit['_source']
                doc['_score'] = hit['_score']
                hits.append(doc)
        
        return hits