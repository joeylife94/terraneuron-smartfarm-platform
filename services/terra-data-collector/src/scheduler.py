"""
Terra Data Collector - Scheduler
APScheduler 기반 주기적 데이터 수집 스케줄링
"""
import logging
from typing import Dict, Any, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.collector import Collector

logger = logging.getLogger(__name__)


class CollectionScheduler:
    """
    주기적 데이터 수집 스케줄러.
    실시간 수집과 일괄(historical) 수집 작업을 분리하여 관리.
    """

    def __init__(self, collector: Collector, scheduler_config: Dict[str, Any]):
        self.collector = collector
        self.config = scheduler_config
        self.scheduler = AsyncIOScheduler(
            timezone=scheduler_config.get("timezone", "Asia/Seoul")
        )

    def setup(self):
        """스케줄러 작업 등록"""
        # 실시간 수집 작업
        realtime_jobs = self.config.get("realtime_jobs", [])
        for job in realtime_jobs:
            provider = job.get("provider")
            cron = job.get("cron")
            if provider and cron:
                self.scheduler.add_job(
                    self._realtime_job,
                    CronTrigger.from_crontab(cron),
                    args=[provider],
                    id=f"realtime_{provider}",
                    name=f"Realtime collection: {provider}",
                    replace_existing=True,
                )
                logger.info(f"  ⏰ Scheduled realtime job: {provider} [{cron}]")

        # 일괄 수집 작업 (AI 학습 데이터)
        batch_jobs = self.config.get("batch_jobs", [])
        for job in batch_jobs:
            provider = job.get("provider")
            cron = job.get("cron")
            job_type = job.get("type", "historical")
            if provider and cron:
                self.scheduler.add_job(
                    self._batch_job,
                    CronTrigger.from_crontab(cron),
                    args=[provider],
                    id=f"batch_{provider}_{job_type}",
                    name=f"Batch {job_type}: {provider}",
                    replace_existing=True,
                )
                logger.info(f"  ⏰ Scheduled batch job: {provider} [{cron}]")

    async def _realtime_job(self, provider_name: str):
        """실시간 수집 작업 실행"""
        logger.info(f"🔄 [scheduler] Running realtime collection: {provider_name}")
        try:
            await self.collector.collect_and_export(
                provider_names=[provider_name],
                historical=False,
            )
        except Exception as e:
            logger.error(f"❌ [scheduler] Realtime job failed: {e}")

    async def _batch_job(self, provider_name: str):
        """일괄 수집 작업 실행"""
        logger.info(f"🔄 [scheduler] Running batch collection: {provider_name}")
        try:
            await self.collector.collect_and_export(
                provider_names=[provider_name],
                historical=True,
            )
        except Exception as e:
            logger.error(f"❌ [scheduler] Batch job failed: {e}")

    def start(self):
        """스케줄러 시작"""
        self.setup()
        self.scheduler.start()
        logger.info("⏰ Collection scheduler started")

    def stop(self):
        """스케줄러 중지"""
        self.scheduler.shutdown()
        logger.info("⏰ Collection scheduler stopped")

    def get_jobs(self):
        """등록된 작업 목록"""
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            }
            for job in self.scheduler.get_jobs()
        ]
