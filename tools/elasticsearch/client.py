"""
Elasticsearch client for Incident Response Orchestrator
Handles connection and basic operations
"""

import os
from typing import Optional, Dict, Any, List
from elasticsearch import Elasticsearch, helpers


class ElasticsearchClient:
    """
    Manages Elasticsearch connection and provides basic operations
    """
    
    def __init__(self):

        # Initialize client
        self.client = self._create_client()
    
    def _create_client(self) -> Elasticsearch:
        """Create Elasticsearch client instance"""

        from elasticsearch import Elasticsearch, helpers

        client = Elasticsearch(
            os.getenv("ELASTICSEARCH_URL"),
            api_key=os.getenv("ELASTIC_API_KEY"),
        )
        
        return client
 
    
    def health(self) -> Dict[str, Any]:
        """Get cluster health"""
        return self.client.cluster.health()
    
    def index_exists(self, index_name: str) -> bool:
        """Check if an index exists"""
        return self.client.indices.exists(index=index_name)
    
    def create_index(self, index_name: str, mappings: Dict[str, Any]) -> bool:
        """
        Create an index with mappings
        
        Args:
            index_name: Name of the index
            mappings: Mapping configuration
            
        Returns:
            True if created successfully
        """
        try:
            if not self.index_exists(index_name):
                self.client.indices.create(
                    index=index_name
                )
                self.client.indices.put_mapping(
                    index=index_name,
                    body=mappings
                )
                print(f"Created index: {index_name}")
                return True
            else:
                print(f"Index already exists: {index_name}")
                return False
        except Exception as e:
            print(f"Failed to create index {index_name}: {str(e)}")
            raise
    
    def delete_index(self, index_name: str) -> bool:
        """Delete an index"""
        try:
            if self.index_exists(index_name):
                self.client.indices.delete(index=index_name)
                print(f"Deleted index: {index_name}")
                return True
            return False
        except Exception as e:
            print(f"Failed to delete index {index_name}: {str(e)}")
            raise
    
    def index_document(self, index_name: str, document: Dict[str, Any], doc_id: str = None) -> Dict[str, Any]:
        """
        Index a single document
        
        Args:
            index_name: Index name
            document: Document to index
            doc_id: Optional document ID
            
        Returns:
            Indexing result
        """
        try:
            result = self.client.index(
                index=index_name,
                document=document,
                id=doc_id,
                refresh=True  # Make immediately searchable
            )
            return result
        except Exception as e:
            print(f"Failed to index document: {str(e)}")
            raise
    
    def bulk_index(self, index_name: str, documents: List[Dict[str, Any]]) -> tuple:
        """
        Bulk index multiple documents
        
        Args:
            index_name: Index name
            documents: List of documents
            
        Returns:
            (success_count, errors)
        """
        try:
            ingestion_timeout=300 # Allow time for semantic ML model to load
            success, errors  = helpers.bulk(
                self.client.options(request_timeout=ingestion_timeout),
                documents,
                index=index_name,
                refresh="wait_for" # Wait until indexed documents are visible for search before returning the response
            )
            print(f"Bulk indexed {success} documents into {index_name}")
            
            if errors:
                print(f"{len(errors)} errors occurred during bulk indexing")
            
            return success, errors
            
        except Exception as e:
            print(f"Failed to bulk index: {str(e)}")
            raise
    
    def search(self, index_name: str, query: Dict[str, Any], size: int = 10) -> Dict[str, Any]:
        """
        Search an index
        
        Args:
            index_name: Index name
            query: Elasticsearch query DSL
            size: Number of results
            
        Returns:
            Search results
        """
        try:

            result = self.client.search(
                index=index_name,
                body=query,
                size=size
            )
            return result
        except Exception as e:
            print(f"Search failed: {str(e)}")
            raise
    
    def count(self, index_name: str, query: Dict[str, Any] = None) -> int:
        """Count documents matching a query"""
        try:
            result = self.client.count(
                index=index_name,
                body={"query": query} if query else None
            )
            return result['count']
        except Exception as e:
            print(f"❌ Count failed: {str(e)}")
            raise
    
    def get_document(self, index_name: str, doc_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID"""
        try:
            result = self.client.get(index=index_name, id=doc_id)
            return result['_source']
        except Exception as e:
            return None
    
    def close(self):
        """Close the client connection"""
        self.client.close()
        print("✅ Elasticsearch connection closed")


# Singleton instance
_es_client: Optional[ElasticsearchClient] = None


def get_elasticsearch_client() -> ElasticsearchClient:
    """Get or create the global Elasticsearch client"""
    global _es_client
    
    if _es_client is None:
        _es_client = ElasticsearchClient()
    
    return _es_client