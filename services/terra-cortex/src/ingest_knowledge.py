"""
Knowledge Base Ingestion Script
Loads PDF documents from /app/data/knowledge_base and creates vector embeddings
for RAG (Retrieval-Augmented Generation)
"""
import os
import logging
from pathlib import Path
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KnowledgeBaseIngester:
    """Ingests agricultural PDFs into ChromaDB vector database"""
    
    def __init__(
        self,
        knowledge_base_path: str = "/app/data/knowledge_base",
        chroma_db_path: str = "/app/data/chroma_db",
        embedding_model: str = "all-MiniLM-L6-v2"
    ):
        """
        Initialize the ingester
        
        Args:
            knowledge_base_path: Path to directory containing PDF files
            chroma_db_path: Path to persist ChromaDB vector database
            embedding_model: HuggingFace model for embeddings (runs locally on CPU)
        """
        self.knowledge_base_path = Path(knowledge_base_path)
        self.chroma_db_path = Path(chroma_db_path)
        self.embedding_model = embedding_model
        
        # Initialize embeddings (all-MiniLM-L6-v2 is lightweight, CPU-friendly)
        logger.info(f"🔄 Loading embedding model: {embedding_model}...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=embedding_model,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        logger.info("✅ Embedding model loaded")
        
        # Text splitter configuration
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            separators=["\n\n", "\n", ".", "!", "?", ",", " ", ""]
        )
    
    def load_pdfs(self) -> List:
        """
        Load all PDF files from knowledge base directory
        
        Returns:
            List of Document objects from all PDFs
        """
        if not self.knowledge_base_path.exists():
            logger.warning(f"⚠️ Knowledge base path does not exist: {self.knowledge_base_path}")
            self.knowledge_base_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Created knowledge base directory: {self.knowledge_base_path}")
            return []
        
        pdf_files = list(self.knowledge_base_path.glob("*.pdf"))
        
        if not pdf_files:
            logger.warning(f"⚠️ No PDF files found in {self.knowledge_base_path}")
            return []
        
        logger.info(f"📚 Found {len(pdf_files)} PDF files")
        
        all_documents = []
        
        for pdf_file in pdf_files:
            try:
                logger.info(f"   📄 Loading: {pdf_file.name}")
                loader = PyPDFLoader(str(pdf_file))
                documents = loader.load()
                all_documents.extend(documents)
                logger.info(f"      ✅ Loaded {len(documents)} pages")
            except Exception as e:
                logger.error(f"      ❌ Failed to load {pdf_file.name}: {e}")
        
        logger.info(f"✅ Total pages loaded: {len(all_documents)}")
        return all_documents
    
    def chunk_documents(self, documents: List) -> List:
        """
        Split documents into smaller chunks for better retrieval
        
        Args:
            documents: List of Document objects
            
        Returns:
            List of chunked Document objects
        """
        if not documents:
            return []
        
        logger.info(f"🔄 Chunking {len(documents)} documents...")
        chunks = self.text_splitter.split_documents(documents)
        logger.info(f"✅ Created {len(chunks)} chunks (chunk_size=1000, overlap=200)")
        
        return chunks
    
    def create_vector_db(self, chunks: List) -> Chroma:
        """
        Create ChromaDB vector database from document chunks
        
        Args:
            chunks: List of chunked Document objects
            
        Returns:
            Chroma vector store
        """
        if not chunks:
            logger.warning("⚠️ No chunks to process, skipping vector DB creation")
            return None
        
        logger.info(f"🔄 Creating ChromaDB vector database at {self.chroma_db_path}...")
        
        # Ensure chroma_db directory exists
        self.chroma_db_path.mkdir(parents=True, exist_ok=True)
        
        # Create Chroma vector store with persistence
        vector_db = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=str(self.chroma_db_path),
            collection_name="agri_knowledge"
        )
        
        logger.info("✅ ChromaDB vector database created and persisted")
        
        return vector_db
    
    def ingest(self) -> bool:
        """
        Main ingestion pipeline: Load PDFs → Chunk → Create Vector DB
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info("=" * 60)
            logger.info("🌾 Starting Knowledge Base Ingestion Pipeline")
            logger.info("=" * 60)
            
            # Step 1: Load PDFs
            documents = self.load_pdfs()
            if not documents:
                logger.warning("⚠️ No documents to process. Place PDF files in:")
                logger.warning(f"   📂 {self.knowledge_base_path}")
                return False
            
            # Step 2: Chunk documents
            chunks = self.chunk_documents(documents)
            
            # Step 3: Create vector database
            vector_db = self.create_vector_db(chunks)
            
            if vector_db:
                logger.info("=" * 60)
                logger.info(f"✅ Knowledge Base Ingested: {len(documents)} documents processed")
                logger.info(f"   📚 Total chunks: {len(chunks)}")
                logger.info(f"   💾 Vector DB: {self.chroma_db_path}")
                logger.info("=" * 60)
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"❌ Ingestion failed: {e}", exc_info=True)
            return False


def main():
    """Run the ingestion script"""
    ingester = KnowledgeBaseIngester()
    success = ingester.ingest()
    
    if not success:
        logger.error("❌ Ingestion failed or no documents found")
        exit(1)
    
    logger.info("✅ Ingestion complete! RAG system ready.")


if __name__ == "__main__":
    main()
