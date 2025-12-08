"""
RAG (Retrieval-Augmented Generation) Advisor
Retrieves relevant context from agricultural knowledge base (ChromaDB)
and enhances LLM prompts with domain-specific information
"""
import os
import logging
from pathlib import Path
from typing import List, Optional

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

logger = logging.getLogger(__name__)


class RAGAdvisor:
    """
    RAG system for agricultural expertise
    Retrieves relevant context from PDFs to enhance LLM recommendations
    """
    
    def __init__(
        self,
        chroma_db_path: str = "/app/data/chroma_db",
        embedding_model: str = "all-MiniLM-L6-v2",
        top_k: int = 3
    ):
        """
        Initialize RAG advisor with ChromaDB retriever
        
        Args:
            chroma_db_path: Path to ChromaDB vector database
            embedding_model: HuggingFace model for embeddings (must match ingestion)
            top_k: Number of relevant chunks to retrieve
        """
        self.chroma_db_path = Path(chroma_db_path)
        self.embedding_model = embedding_model
        self.top_k = top_k
        self.vector_db = None
        self.enabled = False
        
        try:
            # Check if ChromaDB exists
            if not self.chroma_db_path.exists():
                logger.warning(f"⚠️ ChromaDB not found at {chroma_db_path}")
                logger.warning("   Run ingestion script first: python -m src.ingest_knowledge")
                return
            
            # Initialize embeddings (same model used for ingestion)
            logger.info(f"🔄 Loading RAG embedding model: {embedding_model}...")
            self.embeddings = HuggingFaceEmbeddings(
                model_name=embedding_model,
                model_kwargs={'device': 'cpu'},
                encode_kwargs={'normalize_embeddings': True}
            )
            
            # Load ChromaDB
            logger.info(f"🔄 Loading ChromaDB from {chroma_db_path}...")
            self.vector_db = Chroma(
                persist_directory=str(self.chroma_db_path),
                embedding_function=self.embeddings,
                collection_name="agri_knowledge"
            )
            
            # Verify DB has documents
            collection_count = self.vector_db._collection.count()
            if collection_count == 0:
                logger.warning("⚠️ ChromaDB is empty (0 documents)")
                self.enabled = False
            else:
                logger.info(f"✅ RAG Advisor enabled: {collection_count} chunks loaded")
                self.enabled = True
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize RAG Advisor: {e}", exc_info=True)
            self.enabled = False
    
    def retrieve_context(self, query: str) -> List[str]:
        """
        Retrieve relevant context chunks from knowledge base
        
        Args:
            query: Search query (e.g., "High temperature risk for tomato")
            
        Returns:
            List of relevant text chunks (top_k results)
        """
        if not self.enabled:
            logger.debug("RAG disabled, returning empty context")
            return []
        
        try:
            # Perform similarity search
            logger.info(f"🔍 RAG search: '{query[:50]}...'")
            
            results = self.vector_db.similarity_search(
                query,
                k=self.top_k
            )
            
            # Extract text content from Document objects
            contexts = [doc.page_content for doc in results]
            
            logger.info(f"✅ Retrieved {len(contexts)} context chunks")
            
            return contexts
            
        except Exception as e:
            logger.error(f"❌ RAG retrieval failed: {e}", exc_info=True)
            return []
    
    def build_rag_prompt(
        self,
        query: str,
        sensor_type: str,
        sensor_value: float,
        contexts: Optional[List[str]] = None
    ) -> str:
        """
        Build RAG-enhanced prompt with retrieved context
        
        Args:
            query: User query/anomaly description
            sensor_type: Type of sensor (temperature, humidity, etc.)
            sensor_value: Current sensor reading
            contexts: Retrieved context chunks (optional, will retrieve if None)
            
        Returns:
            RAG-enhanced prompt string
        """
        # Retrieve context if not provided
        if contexts is None:
            search_query = f"{sensor_type} anomaly {sensor_value} agricultural risk management"
            contexts = self.retrieve_context(search_query)
        
        # Build context section
        if contexts:
            context_section = "\n\n".join([
                f"**Context {i+1}:**\n{ctx}"
                for i, ctx in enumerate(contexts)
            ])
            
            prompt = f"""System: You are an expert Agronomist for a Smart Farm. Use the following context from GlobalG.A.P. manuals and agricultural best practices to advise the farmer. If the context is not directly relevant, combine it with your general knowledge to provide the best recommendation.

Context:
{context_section}

Question: Sensor {sensor_type} shows a reading of {sensor_value}. This is an ANOMALY. Based on the context above, suggest immediate action in 1-2 sentences.

Answer:"""
        else:
            # Fallback to non-RAG prompt if no context available
            prompt = f"""System: You are an expert Agronomist for a Smart Farm. Be concise and actionable.

Question: Sensor {sensor_type} shows a reading of {sensor_value}. This is an ANOMALY. Suggest immediate action in 1 sentence.

Answer:"""
        
        return prompt
    
    def get_stats(self) -> dict:
        """Get RAG advisor statistics"""
        stats = {
            "enabled": self.enabled,
            "vector_db_path": str(self.chroma_db_path),
            "embedding_model": self.embedding_model,
            "top_k": self.top_k
        }
        
        if self.enabled and self.vector_db:
            try:
                stats["document_count"] = self.vector_db._collection.count()
            except:
                stats["document_count"] = 0
        else:
            stats["document_count"] = 0
        
        return stats


# Global instance (singleton pattern)
_rag_advisor_instance = None


def get_rag_advisor() -> RAGAdvisor:
    """Get or create global RAG advisor instance"""
    global _rag_advisor_instance
    if _rag_advisor_instance is None:
        _rag_advisor_instance = RAGAdvisor()
    return _rag_advisor_instance
