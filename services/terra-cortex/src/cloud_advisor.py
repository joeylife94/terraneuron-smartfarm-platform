"""
Cloud LLM Advisor
Provides detailed AI-powered recommendations using OpenAI API
Triggered ONLY when local analyzer detects ANOMALY
"""
import os
import logging
from typing import Optional
from openai import AsyncOpenAI
from src.models import SensorData, Insight

logger = logging.getLogger(__name__)


class CloudAdvisor:
    """
    Cloud-based LLM advisor for detailed anomaly analysis.
    Uses OpenAI API to provide expert recommendations.
    """
    
    def __init__(self):
        """Initialize OpenAI client"""
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Cost-effective model
        self.enabled = bool(self.api_key)
        
        if self.enabled:
            self.client = AsyncOpenAI(api_key=self.api_key)
            logger.info(f"✅ Cloud Advisor enabled with model: {self.model}")
        else:
            self.client = None
            logger.warning("⚠️ Cloud Advisor disabled (OPENAI_API_KEY not set)")
        
        self.recommendation_count = 0
    
    async def get_recommendation(
        self, 
        sensor_data: SensorData, 
        local_insight: Insight
    ) -> Optional[str]:
        """
        Get detailed recommendation from LLM for anomaly.
        
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
            
            # Prepare context for LLM
            prompt = self._build_prompt(sensor_data, local_insight)
            
            # Call OpenAI API
            logger.info(f"🤖 Requesting LLM recommendation for {sensor_data.farmId}...")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert agricultural AI assistant specialized in smart farm management. "
                            "Provide concise, actionable recommendations for farmers when sensor anomalies are detected. "
                            "Focus on immediate actions, root causes, and preventive measures. "
                            "Keep responses under 200 words."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            recommendation = response.choices[0].message.content.strip()
            
            logger.info(f"✅ LLM recommendation received ({len(recommendation)} chars)")
            
            return recommendation
        
        except Exception as e:
            logger.error(f"❌ Cloud Advisor API error: {e}", exc_info=True)
            return None
    
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
