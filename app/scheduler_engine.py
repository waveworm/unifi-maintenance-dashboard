import logging
import asyncio
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import pytz

from app.database import AsyncSessionLocal
from app.models import Schedule, JobRun, PoESchedule
from app.unifi_client import UniFiClient
from app.config import settings

logger = logging.getLogger(__name__)


class SchedulerEngine:
    """Background job scheduler for executing device maintenance tasks."""
    
    def __init__(self):
        # Use configured timezone
        timezone = pytz.timezone(settings.app_timezone)
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self.running = False
        self.timezone = timezone
    
    async def start(self):
        """Start the scheduler and load all enabled schedules."""
        if self.running:
            logger.warning("Scheduler already running")
            return
        
        logger.info("🚀 Starting scheduler engine...")
        self.scheduler.start()
        self.running = True
        
        # Load and schedule all enabled jobs
        await self.reload_schedules()
        logger.info("✅ Scheduler engine started")
    
    async def stop(self):
        """Stop the scheduler."""
        if not self.running:
            return
        
        logger.info("Stopping scheduler engine...")
        self.scheduler.shutdown()
        self.running = False
        logger.info("✅ Scheduler engine stopped")
    
    async def reload_schedules(self):
        """Reload all schedules from database."""
        logger.info("Reloading schedules from database...")
        
        # Clear existing jobs
        self.scheduler.remove_all_jobs()
        
        async with AsyncSessionLocal() as db:
            # Load device reboot schedules
            result = await db.execute(select(Schedule).where(Schedule.enabled == True))
            schedules = result.scalars().all()
            
            for schedule in schedules:
                await self._add_schedule_job(schedule)
            
            # Load PoE/port cycle schedules
            result = await db.execute(select(PoESchedule).where(PoESchedule.enabled == True))
            poe_schedules = result.scalars().all()
            
            for schedule in poe_schedules:
                await self._add_poe_schedule_job(schedule)
        
        logger.info(f"Loaded {len(schedules)} device schedules and {len(poe_schedules)} port schedules")
    
    async def _add_schedule_job(self, schedule: Schedule):
        """Add a device reboot schedule to the scheduler."""
        try:
            trigger = self._create_trigger(
                schedule.frequency,
                schedule.time_of_day,
                schedule.day_of_week,
                schedule.day_of_month
            )
            
            self.scheduler.add_job(
                self._execute_device_schedule,
                trigger=trigger,
                id=f"schedule_{schedule.id}",
                args=[schedule.id],
                replace_existing=True
            )
            
            logger.info(f"Added schedule job: {schedule.name} (ID: {schedule.id})")
        except Exception as e:
            logger.error(f"Failed to add schedule {schedule.id}: {e}")
    
    async def _add_poe_schedule_job(self, schedule: PoESchedule):
        """Add a PoE/port cycle schedule to the scheduler."""
        try:
            trigger = self._create_trigger(
                schedule.frequency,
                schedule.time_of_day,
                schedule.day_of_week,
                schedule.day_of_month
            )
            
            self.scheduler.add_job(
                self._execute_poe_schedule,
                trigger=trigger,
                id=f"poe_schedule_{schedule.id}",
                args=[schedule.id],
                replace_existing=True
            )
            
            logger.info(f"Added PoE schedule job: {schedule.name} (ID: {schedule.id})")
        except Exception as e:
            logger.error(f"Failed to add PoE schedule {schedule.id}: {e}")
    
    def _create_trigger(
        self,
        frequency: str,
        time_of_day: Optional[str],
        day_of_week: Optional[int],
        day_of_month: Optional[int]
    ) -> CronTrigger:
        """Create a cron trigger from schedule parameters."""
        hour, minute = 0, 0
        if time_of_day:
            parts = time_of_day.split(':')
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        
        if frequency == 'hourly':
            return CronTrigger(minute=minute)
        elif frequency == 'daily':
            return CronTrigger(hour=hour, minute=minute)
        elif frequency == 'weekly':
            return CronTrigger(day_of_week=day_of_week or 0, hour=hour, minute=minute)
        elif frequency == 'monthly':
            return CronTrigger(day=day_of_month or 1, hour=hour, minute=minute)
        else:
            raise ValueError(f"Unknown frequency: {frequency}")
    
    async def _execute_device_schedule(self, schedule_id: int):
        """Execute a device reboot schedule."""
        logger.info(f"Executing device schedule {schedule_id}")
        
        async with AsyncSessionLocal() as db:
            # Get schedule
            result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
            schedule = result.scalar_one_or_none()
            
            if not schedule or not schedule.enabled:
                logger.warning(f"Schedule {schedule_id} not found or disabled")
                return
            
            # Update last run time
            schedule.last_run_at = datetime.utcnow()
            await db.commit()
            
            # Execute reboots
            if schedule.rolling_mode:
                await self._execute_rolling_reboots(schedule, db)
            else:
                await self._execute_parallel_reboots(schedule, db)
    
    async def _execute_rolling_reboots(self, schedule: Schedule, db: AsyncSession):
        """Execute reboots one device at a time."""
        logger.info(f"Executing rolling reboots for schedule: {schedule.name}")

        async with UniFiClient() as client:
            site_name = await self._resolve_schedule_site(schedule, client)
            
            for device_id in schedule.device_ids:
                # Get device info first to set the name
                try:
                    device = await client.get_device_by_id(device_id, site_name)
                    if not device:
                        raise Exception(f"Device {device_id} not found")
                    
                    device_name = device.get("name", "Unknown")
                    device_mac = device.get("mac", device_id)
                except Exception as e:
                    logger.error(f"Failed to get device info for {device_id}: {e}")
                    device_name = device_id
                    device_mac = device_id
                
                # Create job run with device name
                job_run = JobRun(
                    schedule_id=schedule.id,
                    job_type="reboot",
                    device_id=device_id,
                    device_name=device_name,
                    started_at=datetime.utcnow(),
                    status="running"
                )
                db.add(job_run)
                await db.commit()
                await db.refresh(job_run)
                
                try:
                    # Reboot device
                    logger.info(f"Rebooting device: {device_name} ({device_mac})")
                    await client.reboot_device(device_mac, site_name)
                    
                    # Mark job as completed immediately after reboot command
                    job_run.status = "completed"
                    job_run.completed_at = datetime.utcnow()
                    job_run.duration_seconds = int((job_run.completed_at - job_run.started_at).total_seconds())
                    await db.commit()
                    
                    # Wait for device to come back online if configured (after marking complete)
                    if schedule.max_wait_time > 0:
                        logger.info(f"Waiting for {device_name} to come back online (max {schedule.max_wait_time}s)")
                        await asyncio.sleep(10)  # Initial wait for reboot to start
                        
                        online = await client.wait_for_device_online(
                            device_mac,
                            timeout=schedule.max_wait_time - 10,
                            site=site_name
                        )
                        
                        if not online:
                            logger.warning(f"Device {device_name} did not come back online within {schedule.max_wait_time}s")
                    
                    # Delay before next device
                    if schedule.delay_between_devices > 0:
                        logger.info(f"Waiting {schedule.delay_between_devices}s before next device")
                        await asyncio.sleep(schedule.delay_between_devices)
                    
                except Exception as e:
                    logger.error(f"Failed to reboot device {device_id}: {e}")
                    job_run.status = "failed"
                    job_run.error_message = str(e)
                    job_run.completed_at = datetime.utcnow()
                    await db.commit()
                    
                    if not schedule.continue_on_failure:
                        logger.error("Stopping rolling reboot due to failure")
                        break
    
    async def _execute_parallel_reboots(self, schedule: Schedule, db: AsyncSession):
        """Execute reboots for all devices in parallel."""
        logger.info(f"Executing parallel reboots for schedule: {schedule.name}")

        async with UniFiClient() as client:
            site_name = await self._resolve_schedule_site(schedule, client)
        
        tasks = []
        for device_id in schedule.device_ids:
            tasks.append(self._reboot_single_device(schedule.id, device_id, db, site_name))
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _reboot_single_device(self, schedule_id: int, device_id: str, db: AsyncSession, site_name: str = None):
        """Reboot a single device and log the job."""
        try:
            async with UniFiClient() as client:
                # Get device info first
                device = await client.get_device_by_id(device_id, site_name)
                if not device:
                    raise Exception(f"Device {device_id} not found")
                
                device_name = device.get("name", "Unknown")
                device_mac = device.get("mac", device_id)
        except Exception as e:
            logger.error(f"Failed to get device info for {device_id}: {e}")
            device_name = device_id
            device_mac = device_id
        
        # Create job run with device name
        job_run = JobRun(
            schedule_id=schedule_id,
            job_type="reboot",
            device_id=device_id,
            device_name=device_name,
            started_at=datetime.utcnow(),
            status="running"
        )
        db.add(job_run)
        await db.commit()
        await db.refresh(job_run)
        
        try:
            async with UniFiClient() as client:
                await client.reboot_device(device_mac, site_name)
                
                job_run.status = "completed"
                job_run.completed_at = datetime.utcnow()
                job_run.duration_seconds = int((job_run.completed_at - job_run.started_at).total_seconds())
                
        except Exception as e:
            logger.error(f"Failed to reboot device {device_id}: {e}")
            job_run.status = "failed"
            job_run.error_message = str(e)
            job_run.completed_at = datetime.utcnow()
        
        await db.commit()

    async def _resolve_schedule_site(self, schedule: Schedule, client: UniFiClient) -> Optional[str]:
        """Resolve site quickly, preferring stored schedule.site_name."""
        if schedule.site_name:
            return schedule.site_name

        if not schedule.device_ids:
            return None

        target_device_id = schedule.device_ids[0]
        sites = await client.get_sites()
        for site in sites:
            site_name = site.get("name")
            if not site_name:
                continue
            try:
                device = await client.get_device_by_id(target_device_id, site_name)
                if device:
                    logger.info(f"Detected site for schedule {schedule.id}: {site_name}")
                    return site_name
            except Exception:
                continue

        return None
    
    async def _execute_poe_schedule(self, schedule_id: int):
        """Execute a PoE/port cycle schedule."""
        logger.info(f"Executing PoE schedule {schedule_id}")
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(PoESchedule).where(PoESchedule.id == schedule_id))
            schedule = result.scalar_one_or_none()
            
            if not schedule or not schedule.enabled:
                logger.warning(f"PoE schedule {schedule_id} not found or disabled")
                return
            
            # Update last run time
            schedule.last_run_at = datetime.utcnow()
            await db.commit()
            
            # Create job run — resolve device name for display
            display_name = f"{schedule.name}"
            try:
                async with UniFiClient() as client:
                    site_name = await self._resolve_poe_schedule_site(schedule, client)
                    device = await client.get_device_by_id(schedule.device_id, site_name)
                    if device:
                        display_name = f"{device.get('name', schedule.device_id)} Port {schedule.port_idx}"
            except Exception:
                site_name = schedule.site_name
                display_name = f"{schedule.device_id} Port {schedule.port_idx}"

            # Resolve site display name for job log
            site_desc = site_name or ""
            if site_name:
                try:
                    async with UniFiClient() as client_sites:
                        sites_list = await client_sites.get_sites()
                        site_obj = next((s for s in sites_list if s.get("name") == site_name), None)
                        if site_obj:
                            site_desc = site_obj.get("desc") or site_obj.get("name") or site_name
                except Exception:
                    pass

            job_run = JobRun(
                schedule_id=None,
                job_type="port_cycle" if not schedule.poe_only else "poe_cycle",
                device_id=schedule.device_id,
                device_name=display_name,
                started_at=datetime.utcnow(),
                status="running",
                job_metadata={"port_idx": schedule.port_idx, "poe_only": schedule.poe_only, "source": "scheduled", "site_name": site_desc}
            )
            db.add(job_run)
            await db.commit()
            await db.refresh(job_run)
            
            try:
                async with UniFiClient() as client:
                    if not site_name:
                        site_name = await self._resolve_poe_schedule_site(schedule, client)

                    # Cycle the port
                    await client.cycle_port(
                        schedule.device_id,
                        schedule.port_idx,
                        schedule.off_duration,
                        site=site_name,
                        poe_only=schedule.poe_only
                    )
                    
                    job_run.status = "completed"
                    job_run.completed_at = datetime.utcnow()
                    job_run.duration_seconds = int((job_run.completed_at - job_run.started_at).total_seconds())
                    
            except Exception as e:
                logger.error(f"Failed to cycle port: {e}")
                job_run.status = "failed"
                job_run.error_message = str(e)
                job_run.completed_at = datetime.utcnow()
            
            await db.commit()

    async def _resolve_poe_schedule_site(self, schedule: PoESchedule, client: UniFiClient) -> Optional[str]:
        """Resolve site for a PoE schedule, with fallback auto-detection for older rows."""
        if schedule.site_name:
            return schedule.site_name

        sites = await client.get_sites()
        for site in sites:
            site_name = site.get("name")
            if not site_name:
                continue
            try:
                device = await client.get_device_by_id(schedule.device_id, site_name)
                if device:
                    logger.info(f"Detected site for PoE schedule {schedule.id}: {site_name}")
                    return site_name
            except Exception:
                continue

        return None


# Global scheduler instance
scheduler_engine = SchedulerEngine()
