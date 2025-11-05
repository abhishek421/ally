"""
Vector store with Qdrant for hybrid search (embeddings + BM25) with recency priority
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import os
import logging
from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
import numpy as np
from config.settings import (
    CONTEXT_K_RECENT, 
    CONTEXT_R_RETRIEVED,
    QDRANT_COLLECTION_NAME,
    EMBEDDING_MODEL_NAME,
    QDRANT_VECTOR_SIZE,
    QDRANT_SCORE_THRESHOLD
)

logger = logging.getLogger(__name__)

# Initialize clients
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
COLLECTION_NAME = QDRANT_COLLECTION_NAME

# Global instances (lazy loaded)
_qdrant_client: Optional[QdrantClient] = None
_embedding_model: Optional[SentenceTransformer] = None


def get_qdrant_client() -> QdrantClient:
    """Get or create Qdrant client instance"""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
        )
        _ensure_collection_exists()
    return _qdrant_client


def get_embedding_model() -> SentenceTransformer:
    """Get or create embedding model instance"""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logger.info(f"Loaded embedding model: {EMBEDDING_MODEL_NAME}")
    return _embedding_model


def _ensure_collection_exists():
    """Ensure Qdrant collection exists with proper configuration"""
    client = get_qdrant_client()
    
    try:
        collections = client.get_collections().collections
        if COLLECTION_NAME in [c.name for c in collections]:
            logger.info(f"Collection '{COLLECTION_NAME}' already exists")
            return
    except Exception:
        pass
    
    # Create collection with vector configuration
    try:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=QDRANT_VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )
        
        # Create indexes for faster filtering
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="conversation_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name="timestamp",
            field_schema=models.PayloadSchemaType.DATETIME,
        )
        
        logger.info(f"Created collection '{COLLECTION_NAME}' with indexes")
    except Exception as e:
        logger.error(f"Error creating collection: {e}")


async def embed_text(text: str) -> List[float]:
    """Generate embeddings for text using sentence-transformers"""
    try:
        model = get_embedding_model()
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        # Fallback to zero vector
        return [0.0] * QDRANT_VECTOR_SIZE


def calculate_bm25_scores(query: str, documents: List[str]) -> List[float]:
    """Calculate BM25 scores for keyword matching"""
    try:
        # Tokenize
        tokenized_docs = [doc.lower().split() for doc in documents]
        tokenized_query = query.lower().split()
        
        # BM25
        bm25 = BM25Okapi(tokenized_docs)
        scores = bm25.get_scores(tokenized_query)
        
        # Normalize to 0-1
        max_score = max(scores) if max(scores) > 0 else 1.0
        return [score / max_score for score in scores]
    except Exception as e:
        logger.error(f"Error calculating BM25 scores: {e}")
        return [0.0] * len(documents)


def calculate_recency_score(timestamp: datetime) -> float:
    """Calculate recency score with exponential decay"""
    try:
        hours_ago = (datetime.utcnow() - timestamp).total_seconds() / 3600
        # Exponential decay: recent=1.0, 1hr=0.7, 6hr=0.3, 24hr=0.1
        return float(np.exp(-0.15 * hours_ago))
    except Exception:
        return 0.5


async def upsert_message_embedding(
    message_id: str,
    conversation_id: str,
    workspace_id: Optional[str],
    user_id: Optional[str],
    role: str,
    content: str,
    created_at: str,
):
    """Store message embedding in Qdrant"""
    try:
        client = get_qdrant_client()
        
        # Generate embedding
        embedding = await embed_text(content)
        
        # Parse timestamp
        try:
            timestamp = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        except Exception:
            timestamp = datetime.utcnow()
        
        # Create point
        point = PointStruct(
            id=message_id,
            vector=embedding,
            payload={
                "message_id": message_id,
                "conversation_id": conversation_id,
                "workspace_id": workspace_id,
                "user_id": user_id,
                "role": role,
                "content": content,
                "timestamp": timestamp.isoformat(),
            }
        )
        
        # Upsert to Qdrant
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[point],
        )
        
        logger.debug(f"Stored embedding for message {message_id}")
    except Exception as e:
        logger.error(f"Error storing embedding: {e}")
        # Don't raise - fail gracefully


async def get_recent_messages_from_db(
    conversation_id: str,
    limit: int = 3
) -> List[Dict[str, Any]]:
    """Get recent messages from PostgreSQL (not vector DB)"""
    try:
        from database.prisma_client import prisma_client
        
        client = await prisma_client.get_client()
        messages = await client.conversationmessage.find_many(
            where={"conversationId": conversation_id},
            order={"timestamp": "desc"},
            take=limit,
        )
        
        # Reverse to get chronological order
        return [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
            }
            for msg in reversed(messages)
        ]
    except Exception as e:
        logger.error(f"Error fetching recent messages: {e}")
        return []


async def retrieve_conversation_context(
    conversation_id: str,
    current_query: str,
    k_recent: int = CONTEXT_K_RECENT,
    r_retrieved: int = CONTEXT_R_RETRIEVED,
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant context from conversation history with hybrid search + recency priority
    
    Strategy:
    1. Always include last k_recent messages (immediate context)
    2. Semantic search for additional r_retrieved messages
    3. Apply BM25 for keyword matching
    4. Boost recent messages with recency score
    """
    try:
        # Step 1: Get last k_recent messages (always included)
        recent_messages = await get_recent_messages_from_db(
            conversation_id=conversation_id,
            limit=k_recent
        )
        recent_ids = {msg["id"] for msg in recent_messages}
        
        # If we already have enough context, return
        if len(recent_messages) >= (k_recent + r_retrieved):
            return recent_messages[:k_recent]
        
        # Step 2: Semantic search for additional context
        client = get_qdrant_client()
        query_embedding = await embed_text(current_query)
        
        # Search with conversation filter and recency boost
        search_results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_embedding,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="conversation_id",
                        match=models.MatchValue(value=conversation_id)
                    )
                ]
            ),
            limit=max(r_retrieved * 3, 10),  # Get more candidates for reranking
            score_threshold=QDRANT_SCORE_THRESHOLD,  # Minimum similarity
        )
        
        # Step 3: Rerank with hybrid scoring (semantic + BM25 + recency)
        candidates = []
        for hit in search_results:
            if hit.id in recent_ids:
                continue  # Skip already included recent messages
            
            payload = hit.payload
            timestamp = datetime.fromisoformat(payload["timestamp"])
            
            # Calculate scores
            semantic_score = hit.score
            recency_score = calculate_recency_score(timestamp)
            
            # Hybrid score: 50% semantic, 30% recency, 20% for BM25 (computed per-query)
            hybrid_score = 0.5 * semantic_score + 0.3 * recency_score
            
            candidates.append({
                "id": hit.id,
                "role": payload["role"],
                "content": payload["content"],
                "timestamp": payload["timestamp"],
                "score": hybrid_score,
            })
        
        # Step 4: Apply BM25 scoring to candidates
        if candidates:
            candidate_contents = [c["content"] for c in candidates]
            bm25_scores = calculate_bm25_scores(current_query, candidate_contents)
            
            for i, candidate in enumerate(candidates):
                candidate["score"] += 0.2 * bm25_scores[i]
        
        # Step 5: Sort by hybrid score and take top results
        candidates.sort(key=lambda x: x["score"], reverse=True)
        # Take only up to r_retrieved items
        # Also ensure we don't include any of the recent_ids
        additional_context = []
        for c in candidates:
            if c["id"] in recent_ids:
                continue
            additional_context.append(c)
            if len(additional_context) >= r_retrieved:
                break
        
        # Combine: recent messages first, then semantically relevant
        return recent_messages + additional_context
        
    except Exception as e:
        logger.error(f"Error retrieving context: {e}")
        # Fallback: return just recent messages
        return recent_messages if 'recent_messages' in locals() else []


# Health check
def health_check() -> bool:
    """Check if Qdrant is accessible"""
    try:
        client = get_qdrant_client()
        client.get_collections()
        return True
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
        return False
