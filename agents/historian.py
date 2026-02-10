"""
Historian Agent - Finds similar past incidents and their resolutions
"""

import time
from typing import Dict, Any, List
from datetime import datetime
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from agents.state import IncidentState, HistorianMatches, SimilarIncident
from langchain_google_genai import GoogleGenerativeAIEmbeddings


class HistorianAgent:
    """
    Historian Agent finds similar past incidents using hybrid search.
    Combines vector similarity with keyword matching.
    """
    
    SYSTEM_PROMPT = """You are a Historian Agent that finds similar past incidents.

Your job:
1. Take the current incident description from Detective Agent
2. Create a semantic search query combining symptoms, errors, and affected services
3. Search the incidents-history index using hybrid search (vector + keyword)
4. Return top 3 most similar incidents with their resolutions
5. Calculate similarity scores

Focus on finding incidents with:
- Similar error patterns
- Same affected services
- Similar symptoms (error spikes, resource exhaustion)
- Successful resolutions (not just any incident)

You will be provided with:
- Affected service: {service_name}
- Error types: {error_types}
- Symptoms: {symptoms}
- Resource metrics: {resource_metrics}

Your goal is to find the most relevant past incidents that can guide resolution.
"""

    USER_PROMPT = """Find similar past incidents for:

Service: {service_name}
Error Types: {error_types}
Error Count: {error_count}
Key Symptoms:
{key_symptoms}

Resource Metrics:
- CPU: {cpu_pct}%
- Memory: {memory_pct}%
- Disk: {disk_pct}%

Recent Deployment: {recent_deployment}

Search the incident history and return the top 3 most similar incidents with their resolutions.
Provide similarity scores (0-100) based on symptom match, service match, and error pattern match.
"""

    def __init__(self,  elasticsearch_tool=None, search_tool=None, use_real_es: bool = True):
        """
        Initialize the Historian Agent
        
        Args:
            model_name: GEMINI model to use
            elasticsearch_tool: Tool for querying Elasticsearch
            search_tool: Search tool for hybrid search
            use_real_es: If True, use real Elasticsearch; if False, use simulated data
        """
        self.llm = init_chat_model("gemini-2.5-flash-lite", model_provider="google_genai", temperature=0.7)
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        self.elasticsearch_tool = elasticsearch_tool
        self.search_tool = search_tool
        self.use_real_es = use_real_es and search_tool is not None
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("user", self.USER_PROMPT)
        ])
    
    def search_history(self, state: IncidentState) -> Dict[str, Any]:
        """
        Search for similar past incidents
        
        Args:
            state: Current incident state with detective findings
            
        Returns:
            Dictionary to update the state with historian matches
        """
        start_time = time.time()
        
        try:
            state.add_timeline_event(
                agent="historian",
                event="History search started",
                details={"service": state.detective_findings.affected_service}
            )
            
            # Create search query from detective findings
            search_query = self._create_search_query(state)
            
            # Search for similar incidents (real or simulated)
            if self.use_real_es:
                similar_incidents = self._real_history_search(state, search_query)
            else:
                similar_incidents = self._simulate_history_search(state)
            
            search_duration = time.time() - start_time
            
            matches = HistorianMatches(
                similar_incidents=similar_incidents,
                recommendation=self._generate_recommendation(similar_incidents),
                search_duration_seconds=search_duration
            )
            
            state.add_timeline_event(
                agent="historian",
                event="History search completed",
                details={
                    "duration_seconds": search_duration,
                    "matches_found": len(similar_incidents),
                    "top_similarity": similar_incidents[0].similarity_score if similar_incidents else 0
                }
            )
            
            return {
                "historian_matches": matches,
                "workflow_status": "analyzing"
            }
            
        except Exception as e:
            state.add_timeline_event(
                agent="historian",
                event="History search failed",
                details={"error": str(e)}
            )
            raise
    
    def _create_search_query(self, state: IncidentState) -> str:
        """Create a semantic search query from detective findings"""
        findings = state.detective_findings
        
        symptoms = [
            f"{findings.error_count} errors",
            f"Memory at {findings.resource_metrics.get('memory_pct', 0)}%",
            f"CPU at {findings.resource_metrics.get('cpu_pct', 0)}%"
        ]
        
        if findings.recent_deployments:
            symptoms.append(f"Recent deployment: {findings.recent_deployments[0].get('version', 'unknown')}")
        
        symptoms.extend(findings.error_types[:3])
        
        return " ".join(symptoms)
    
    def _real_history_search(self, state: IncidentState, search_query: str) -> List[SimilarIncident]:
        """
        Perform real history search using Elasticsearch hybrid search
        """
        findings = state.detective_findings
        
        try:
            print(f"  Searching for similar incidents...")
            print(f"  Query: {search_query[:100]}...")
            
            # Generate embedding for current incident
            query_embedding = self.embeddings.embed_query(search_query)
            
            # Perform hybrid search
            results = self.search_tool.hybrid_search(
                index="incidents-history",
                text_query=search_query,
                vector=query_embedding,
                text_fields=["symptoms", "root_cause", "error_types"],
                vector_field="incident_embedding",
                k=5,
                size=3
            )
            
            # Convert to SimilarIncident objects
            similar_incidents = []
            for hit in results:
                # Calculate similarity score (0-100)
                # ES score is typically 0-N, we normalize it
                similarity = min(100.0, (hit.get('_score', 0) / 10) * 100)
                
                similar_incidents.append(SimilarIncident(
                    incident_id=hit.get('incident_id', 'UNKNOWN'),
                    similarity_score=similarity,
                    occurred_at=datetime.fromisoformat(hit['@timestamp'].replace('Z', '+00:00')),
                    symptoms=hit.get('symptoms', ''),
                    root_cause=hit.get('root_cause', ''),
                    resolution_applied=', '.join(hit.get('resolution_steps', [])),
                    time_to_resolve=f"{hit.get('time_to_resolve_minutes', 0)} minutes",
                    success_rate="100% resolved" if hit.get('prevented_recurrence') else "Partial resolution"
                ))
            
            print(f"  ✅ Found {len(similar_incidents)} similar incidents")
            if similar_incidents:
                print(f"  🎯 Best match: {similar_incidents[0].incident_id} ({similar_incidents[0].similarity_score:.1f}% similar)")
            
            return similar_incidents
            
        except Exception as e:
            print(f"  ⚠️  Real search failed, using simulation: {str(e)}")
            return self._simulate_history_search(state)
    
    def _simulate_history_search(self, state: IncidentState) -> List[SimilarIncident]:
        """
        Simulate finding similar past incidents
        In production, this would use Elasticsearch hybrid search
        """
        findings = state.detective_findings
        
        # Simulate 3 similar incidents with varying similarity scores
        similar_incidents = [
            SimilarIncident(
                incident_id="INC-2847",
                similarity_score=87.5,
                occurred_at=datetime(2025, 12, 15, 3, 22, 0),
                symptoms=f"5xx errors spiked 340%, memory usage 98%, pod restarts every 2min in {findings.affected_service}",
                root_cause="Memory leak in Redis connection pool introduced in recent deployment",
                resolution_applied="Rolled back deployment and scaled Redis replicas",
                time_to_resolve="23 minutes",
                success_rate="100% resolved"
            ),
            SimilarIncident(
                incident_id="INC-2691",
                similarity_score=72.3,
                occurred_at=datetime(2025, 11, 28, 14, 45, 0),
                symptoms=f"Connection timeouts, high memory usage in {findings.affected_service}",
                root_cause="Database connection pool exhaustion after traffic spike",
                resolution_applied="Increased connection pool size and added circuit breaker",
                time_to_resolve="45 minutes",
                success_rate="95% resolved"
            ),
            SimilarIncident(
                incident_id="INC-2534",
                similarity_score=65.8,
                occurred_at=datetime(2025, 10, 12, 9, 30, 0),
                symptoms=f"Service degradation and high CPU in {findings.affected_service}",
                root_cause="Inefficient query after schema migration",
                resolution_applied="Optimized query and added database index",
                time_to_resolve="67 minutes",
                success_rate="100% resolved"
            )
        ]
        
        return similar_incidents
    
    def _generate_recommendation(self, similar_incidents: List[SimilarIncident]) -> str:
        """Generate a recommendation based on the best match"""
        if not similar_incidents:
            return "No similar past incidents found. Proceed with fresh analysis."
        
        best_match = similar_incidents[0]
        
        if best_match.similarity_score >= 85:
            return f"Strong match with {best_match.incident_id} ({best_match.similarity_score}% similar). " \
                   f"Previous resolution: {best_match.resolution_applied}. Recommend similar approach."
        elif best_match.similarity_score >= 70:
            return f"Moderate match with {best_match.incident_id} ({best_match.similarity_score}% similar). " \
                   f"Previous resolution may provide guidance: {best_match.resolution_applied}"
        else:
            return f"Weak match with past incidents (best: {best_match.similarity_score}%). " \
                   f"Recommend thorough analysis before action."
    
    def _hybrid_search(self, query_text: str, query_vector: List[float]) -> List[Dict[str, Any]]:
        """
        Perform hybrid search in Elasticsearch
        This is a placeholder - will be implemented when ES tools are ready
        """
        if self.elasticsearch_tool:
            search_body = {
                "query": {
                    "bool": {
                        "should": [
                            {
                                "match": {
                                    "symptoms": query_text
                                }
                            },
                            {
                                "match": {
                                    "error_types": query_text
                                }
                            }
                        ]
                    }
                },
                "knn": {
                    "field": "incident_embedding",
                    "query_vector": query_vector,
                    "k": 5,
                    "num_candidates": 50
                }
            }
            
            return self.elasticsearch_tool.search(
                index="incidents-history",
                body=search_body
            )
        
        return []