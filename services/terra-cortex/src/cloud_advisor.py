"""
Cloud LLM Advisor
Provides detailed AI-powered recommendations using OpenAI API
Triggered ONLY when local analyzer detects ANOMALY
Enhanced with RAG (Retrieval-Augmented Generation) for agricultural expertise
"""
import os
import logging
from typing import Optional
from openai import AsyncOpenAI
from src.models import SensorData, Insight
from src.rag_advisor import get_rag_advisor

logger = logging.getLogger(__name__)


class CloudAdvisor:
    """
    Cloud-based LLM advisor for detailed anomaly analysis.
    Uses OpenAI API to provide expert recommendations.
    """
    
    def __init__(self):
        """Initialize OpenAI client (supports both OpenAI and Ollama) + RAG"""
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Default model
        self.base_url = os.getenv("OPENAI_BASE_URL")  # For Ollama: http://host.docker.internal:11434/v1
        self.enabled = bool(self.api_key)
        
        if self.enabled:
            # Initialize client with optional base_url (for Ollama)
            if self.base_url:
                self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
                logger.info(f"✅ Cloud Advisor enabled with LOCAL LLM: {self.model} (base_url: {self.base_url})")
            else:
                self.client = AsyncOpenAI(api_key=self.api_key)
                logger.info(f"✅ Cloud Advisor enabled with OpenAI: {self.model}")
        else:
            self.client = None
            logger.warning("⚠️ Cloud Advisor disabled (OPENAI_API_KEY not set)")
        
        # Initialize RAG advisor
        self.rag_advisor = get_rag_advisor()
        if self.rag_advisor.enabled:
            logger.info(f"✅ RAG Advisor enabled: {self.rag_advisor.get_stats()['document_count']} documents")
        else:
            logger.warning("⚠️ RAG Advisor disabled (no knowledge base found)")
        
        self.recommendation_count = 0
    
    async def get_recommendation(
        self, 
        sensor_data: SensorData, 
        local_insight: Insight
    ) -> Optional[str]:
        """
        Get detailed recommendation from LLM for anomaly.
        Enhanced with RAG - retrieves relevant context from agricultural PDFs.
        
        Args:
            sensor_data: Original sensor data
            local_insight: Insight from local analyzer (with ANOMALY status)
            
        Returns:
            Detailed recommendation string from LLM, or None if API unavailable
        """
        if not self.enabled:
            logger.debug("Cloud Advisor disabled, skipping LLM call")
            return None
        
        try:
            self.recommendation_count += 1
            
            # Step 1: Retrieve relevant context from RAG (if enabled)
            rag_contexts = []
            if self.rag_advisor.enabled:
                search_query = f"{sensor_data.sensorType} anomaly {sensor_data.value} agricultural risk management best practices"
                rag_contexts = self.rag_advisor.retrieve_context(search_query)
            
            # Step 2: Build RAG-enhanced prompt
            if rag_contexts:
                # Use RAG prompt with retrieved context
                prompt = self._build_rag_prompt(sensor_data, rag_contexts)
                logger.info(f"🤖 Requesting RAG-enhanced LLM recommendation for {sensor_data.farmId}...")
            else:
                # Fallback to simple prompt if no RAG context
                prompt = self._build_simple_prompt(sensor_data)
                logger.info(f"🤖 Requesting LLM recommendation for {sensor_data.farmId}...")
            
            # Step 3: Call LLM with enhanced prompt
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Agronomist for a Smart Farm. Provide actionable, evidence-based advice."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=200,
                timeout=10.0  # 10 second timeout for Ollama
            )
            
            recommendation = response.choices[0].message.content.strip()
            
            logger.info(f"✅ LLM recommendation received ({len(recommendation)} chars)")
            
            return recommendation
        
        except Exception as e:
            logger.error(f"❌ Cloud Advisor API error: {e}", exc_info=True)
            # Return fallback error message
            return "AI Error: Check Local LLM connection. Ensure Ollama is running on host machine."
    
    
    def _build_rag_prompt(self, sensor_data: SensorData, contexts: list) -> str:
        """
        Build RAG-enhanced prompt with retrieved agricultural knowledge
        
        Args:
            sensor_data: Original sensor data
            contexts: Retrieved context chunks from RAG
            
        Returns:
            RAG-enhanced prompt string
        """
        context_section = "\n\n".join([
            f"**Context {i+1}:**\n{ctx[:500]}..."  # Limit context length
            for i, ctx in enumerate(contexts[:3])  # Top 3 contexts
        ])
        
        prompt = f"""Based on agricultural best practices and the following context from expert manuals:

{context_section}

**Current Situation:**
- Sensor Type: {sensor_data.sensorType}
- Reading: {sensor_data.value} {self._get_unit(sensor_data.sensorType)}
- Status: ANOMALY detected

**Question:** What immediate action should the farmer take? Provide a specific, actionable recommendation in 2-3 sentences based on the context above."""
        
        return prompt
    
    def _build_simple_prompt(self, sensor_data: SensorData) -> str:
        """
        Build simple prompt without RAG context (fallback)
        
        Args:
            sensor_data: Original sensor data
            
        Returns:
            Simple prompt string
        """
        return f"Sensor {sensor_data.sensorType} shows {sensor_data.value} {self._get_unit(sensor_data.sensorType)}. This is an ANOMALY. Suggest immediate action in 1-2 sentences."
    
    def _build_prompt(self, sensor_data: SensorData, local_insight: Insight) -> str:
        """
        Build detailed prompt for LLM with sensor context.
        
        Args:
            sensor_data: Original sensor data
            local_insight: Local analyzer's insight
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""Smart Farm Anomaly Alert:

**Farm ID:** {sensor_data.farmId}
**Sensor Type:** {sensor_data.sensorType}
**Current Reading:** {sensor_data.value} {self._get_unit(sensor_data.sensorType)}
**Status:** {local_insight.status} (Severity: {local_insight.severity})
**Local Analysis:** {local_insight.message}

Please provide:
1. **Immediate Action:** What should the farmer do right now?
2. **Root Cause:** What likely caused this anomaly?
3. **Prevention:** How to avoid this in the future?

Keep your response concise, practical, and focused on actionable steps."""
        
        return prompt
    
    def _get_unit(self, sensor_type: str) -> str:
        """Get measurement unit for sensor type"""
        units = {
            "temperature": "°C",
            "humidity": "%",
            "co2": "ppm",
            "soilmoisture": "%",
            "light": "lux"
        }
        return units.get(sensor_type.lower(), "")
    
    def get_stats(self) -> dict:
        """Get advisor statistics"""
        return {
            "total_recommendations": self.recommendation_count,
            "advisor_type": "cloud_llm",
            "model": self.model if self.enabled else None,
            "enabled": self.enabled
        }
