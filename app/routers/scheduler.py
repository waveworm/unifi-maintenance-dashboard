import logging
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime

from app.database import get_db
from app.models import Schedule, JobRun, PoESchedule, ScheduleTemplate
from app.schemas import (
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleResponse,
    JobRunResponse,
    PoEScheduleCreate,
    PoEScheduleUpdate,
    PoEScheduleResponse,
    ScheduleTemplateCreate,
    ScheduleTemplateResponse,
)
from app.scheduler_engine import scheduler_engine
from app.unifi_client import UniFiClient

logger = logging.getLogger(__name__)
router = APIRouter()


async def _build_schedule_details(schedules: List[Schedule]) -> List[dict]:
    """Attach switch names and site information to schedule responses."""
    if not schedules:
        return []

    schedule_payload = [
        ScheduleResponse.model_validate(schedule).model_dump()
        for schedule in schedules
    ]

    schedule_devices = {
        schedule.id: set(schedule.device_ids or [])
        for schedule in schedules
    }
    unresolved_device_ids = set().union(*schedule_devices.values()) if schedule_devices else set()
    if not unresolved_device_ids:
        return schedule_payload

    device_lookup = {}  # device_id -> display name
    site_lookup = {}    # device_id -> site name

    known_sites = {
        schedule.site_name
        for schedule in schedules
        if schedule.site_name
    }

    try:
        async with UniFiClient() as client:
            sites = await client.get_sites()
            site_names = [site.get("name") for site in sites if site.get("name")]

            prioritized_sites = [name for name in site_names if name in known_sites]
            fallback_sites = [name for name in site_names if name not in known_sites]

            for site_name in prioritized_sites + fallback_sites:
                if not unresolved_device_ids:
                    break

                try:
                    devices = await client.get_devices(site_name)
                except Exception:
                    continue

                for device in devices:
                    device_id = device.get("_id")
                    if device_id in unresolved_device_ids:
                        device_lookup[device_id] = device.get("name") or device_id
                        site_lookup[device_id] = site_name
                        unresolved_device_ids.remove(device_id)
    except Exception as e:
        logger.warning(f"Failed to resolve schedule device names: {e}")

    for payload in schedule_payload:
        device_ids = payload.get("device_ids") or []
        payload["device_names"] = [device_lookup.get(device_id, device_id) for device_id in device_ids]

        if payload.get("site_name"):
            continue

        resolved_sites = [
            site_lookup[device_id]
            for device_id in device_ids
            if device_id in site_lookup
        ]
        payload["site_name"] = resolved_sites[0] if resolved_sites else None

    return schedule_payload


@router.get("/schedules", response_model=List[ScheduleResponse])
async def list_schedules(db: AsyncSession = Depends(get_db)):
    """Get all device reboot schedules."""
    try:
        result = await db.execute(select(Schedule).order_by(Schedule.created_at.desc()))
        schedules = result.scalars().all()
        return await _build_schedule_details(schedules)
    except Exception as e:
        logger.error(f"Failed to list schedules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedules", response_model=ScheduleResponse)
async def create_schedule(
    schedule: ScheduleCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new device reboot schedule."""
    try:
        db_schedule = Schedule(
            name=schedule.name,
            description=schedule.description,
            frequency=schedule.frequency,
            time_of_day=schedule.time_of_day,
            day_of_week=schedule.day_of_week,
            day_of_month=schedule.day_of_month,
            device_ids=schedule.device_ids,
            site_name=schedule.site_name,
            rolling_mode=schedule.rolling_mode,
            delay_between_devices=schedule.delay_between_devices,
            max_wait_time=schedule.max_wait_time,
            continue_on_failure=schedule.continue_on_failure,
            enabled=schedule.enabled
        )
        
        db.add(db_schedule)
        await db.commit()
        await db.refresh(db_schedule)
        
        logger.info(f"Created schedule: {schedule.name}")
        
        # Reload scheduler to pick up new schedule
        await scheduler_engine.reload_schedules()
        
        return (await _build_schedule_details([db_schedule]))[0]
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create schedule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(schedule_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific schedule by ID."""
    try:
        result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
        schedule = result.scalar_one_or_none()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        return (await _build_schedule_details([schedule]))[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    schedule_update: ScheduleUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing schedule."""
    try:
        result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
        schedule = result.scalar_one_or_none()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Update fields
        update_data = schedule_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(schedule, field, value)
        
        schedule.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(schedule)
        
        logger.info(f"Updated schedule {schedule_id}")
        
        # Reload scheduler to pick up changes
        await scheduler_engine.reload_schedules()
        
        return (await _build_schedule_details([schedule]))[0]
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a schedule."""
    try:
        result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
        schedule = result.scalar_one_or_none()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        await db.delete(schedule)
        await db.commit()
        
        logger.info(f"Deleted schedule {schedule_id}")
        
        # Reload scheduler to remove deleted schedule
        await scheduler_engine.reload_schedules()
        
        return {"success": True, "message": f"Schedule {schedule_id} deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedules/{schedule_id}/toggle")
async def toggle_schedule(schedule_id: int, db: AsyncSession = Depends(get_db)):
    """Enable or disable a schedule."""
    try:
        result = await db.execute(select(Schedule).where(Schedule.id == schedule_id))
        schedule = result.scalar_one_or_none()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        schedule.enabled = not schedule.enabled
        schedule.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(schedule)
        
        status = "enabled" if schedule.enabled else "disabled"
        logger.info(f"Schedule {schedule_id} {status}")
        
        # Reload scheduler to enable/disable schedule
        await scheduler_engine.reload_schedules()
        
        return {"success": True, "enabled": schedule.enabled}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to toggle schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs", response_model=List[JobRunResponse])
async def list_jobs(
    limit: int = 100,
    schedule_id: int = None,
    db: AsyncSession = Depends(get_db)
):
    """Get job run history."""
    try:
        query = select(JobRun).order_by(JobRun.started_at.desc()).limit(limit)
        
        if schedule_id:
            query = query.where(JobRun.schedule_id == schedule_id)
        
        result = await db.execute(query)
        jobs = result.scalars().all()
        
        return jobs
        
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}", response_model=JobRunResponse)
async def get_job(job_id: int, db: AsyncSession = Depends(get_db)):
    """Get a specific job run by ID."""
    try:
        result = await db.execute(select(JobRun).where(JobRun.id == job_id))
        job = result.scalar_one_or_none()
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return job
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# PoE/Port Cycle Schedules

@router.get("/poe-schedules", response_model=List[PoEScheduleResponse])
async def list_poe_schedules(db: AsyncSession = Depends(get_db)):
    """Get all PoE/port cycle schedules."""
    try:
        result = await db.execute(select(PoESchedule).order_by(PoESchedule.created_at.desc()))
        schedules = result.scalars().all()
        return schedules
    except Exception as e:
        logger.error(f"Failed to list PoE schedules: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/poe-schedules", response_model=PoEScheduleResponse)
async def create_poe_schedule(
    schedule: PoEScheduleCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new PoE/port cycle schedule."""
    try:
        db_schedule = PoESchedule(
            name=schedule.name,
            description=schedule.description,
            frequency=schedule.frequency,
            time_of_day=schedule.time_of_day,
            day_of_week=schedule.day_of_week,
            day_of_month=schedule.day_of_month,
            device_id=schedule.device_id,
            site_name=schedule.site_name,
            port_idx=schedule.port_idx,
            poe_only=schedule.poe_only,
            off_duration=schedule.off_duration,
            enabled=schedule.enabled
        )
        
        db.add(db_schedule)
        await db.commit()
        await db.refresh(db_schedule)
        
        logger.info(f"Created PoE schedule: {schedule.name}")

        # Reload scheduler to pick up new PoE schedule
        await scheduler_engine.reload_schedules()

        return db_schedule
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create PoE schedule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/poe-schedules/{schedule_id}", response_model=PoEScheduleResponse)
async def update_poe_schedule(
    schedule_id: int,
    schedule_update: PoEScheduleUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing PoE/port cycle schedule."""
    try:
        result = await db.execute(select(PoESchedule).where(PoESchedule.id == schedule_id))
        schedule = result.scalar_one_or_none()

        if not schedule:
            raise HTTPException(status_code=404, detail="PoE schedule not found")

        update_data = schedule_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(schedule, field, value)

        schedule.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(schedule)

        logger.info(f"Updated PoE schedule {schedule_id}")

        # Reload scheduler to pick up updated PoE schedule
        await scheduler_engine.reload_schedules()

        return schedule

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update PoE schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/poe-schedules/run-site/{site_name}")
async def run_all_port_schedules_for_site(site_name: str, db: AsyncSession = Depends(get_db)):
    """Trigger all enabled port cycle schedules for a site to run now (in parallel)."""
    import asyncio
    from app.models import JobRun

    try:
        result = await db.execute(
            select(PoESchedule).where(
                PoESchedule.site_name == site_name,
                PoESchedule.enabled == True
            )
        )
        schedules = result.scalars().all()

        if not schedules:
            raise HTTPException(status_code=404, detail=f"No enabled port schedules found for site '{site_name}'")

        # Resolve device names and site display name
        device_names = {}
        site_desc = site_name
        try:
            async with UniFiClient() as client:
                sites = await client.get_sites()
                site_obj = next((s for s in sites if s.get("name") == site_name), None)
                if site_obj:
                    site_desc = site_obj.get("desc") or site_obj.get("name") or site_name
                for sched in schedules:
                    if sched.device_id not in device_names:
                        device = await client.get_device_by_id(sched.device_id, site_name)
                        if device:
                            device_names[sched.device_id] = device.get("name", sched.device_id)
        except Exception as e:
            logger.warning(f"Failed to resolve device names: {e}")

        # Create job_run entries for all schedules
        job_runs = []
        started_at = datetime.utcnow()
        for sched in schedules:
            dev_name = device_names.get(sched.device_id, sched.device_id)
            display_name = f"{dev_name} Port {sched.port_idx}"
            action = "port_cycle" if not sched.poe_only else "poe_cycle"
            job_run = JobRun(
                job_type=action,
                device_id=sched.device_id,
                device_name=display_name,
                started_at=started_at,
                status="running",
                job_metadata={
                    "port_idx": sched.port_idx,
                    "off_duration": sched.off_duration,
                    "poe_only": sched.poe_only,
                    "source": "manual_bulk",
                    "site_name": site_desc
                }
            )
            db.add(job_run)
            job_runs.append((sched, job_run))

        await db.commit()
        for _, jr in job_runs:
            await db.refresh(jr)

        # Run cycles with staggered starts (5s apart) to avoid controller congestion
        async def run_single(sched, job_run, delay):
            if delay > 0:
                await asyncio.sleep(delay)
            try:
                async with UniFiClient() as client:
                    await client.cycle_port(
                        sched.device_id,
                        sched.port_idx,
                        sched.off_duration,
                        site=site_name,
                        poe_only=sched.poe_only
                    )
                job_run.status = "success"
                job_run.completed_at = datetime.utcnow()
                job_run.duration_seconds = int((job_run.completed_at - job_run.started_at).total_seconds())
            except Exception as e:
                logger.error(f"Bulk cycle failed for {sched.device_id} port {sched.port_idx}: {e}")
                job_run.status = "failed"
                job_run.error_message = str(e)
                job_run.completed_at = datetime.utcnow()
                job_run.duration_seconds = int((job_run.completed_at - job_run.started_at).total_seconds())

        async def run_all():
            from app.database import AsyncSessionLocal
            stagger_seconds = 5
            tasks = [run_single(sched, jr, i * stagger_seconds) for i, (sched, jr) in enumerate(job_runs)]
            await asyncio.gather(*tasks, return_exceptions=True)
            # Commit all job_run updates in a fresh session
            async with AsyncSessionLocal() as commit_db:
                for _, jr in job_runs:
                    await commit_db.merge(jr)
                await commit_db.commit()

        # Fire and forget — don't block the HTTP response
        asyncio.create_task(run_all())

        return {
            "success": True,
            "message": f"Started {len(schedules)} port cycles for site '{site_desc}'",
            "count": len(schedules)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run bulk port cycles for site {site_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/poe-schedules/{schedule_id}")
async def delete_poe_schedule(schedule_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a PoE/port cycle schedule."""
    try:
        result = await db.execute(select(PoESchedule).where(PoESchedule.id == schedule_id))
        schedule = result.scalar_one_or_none()
        
        if not schedule:
            raise HTTPException(status_code=404, detail="PoE schedule not found")
        
        await db.delete(schedule)
        await db.commit()
        
        logger.info(f"Deleted PoE schedule {schedule_id}")

        # Reload scheduler to remove deleted PoE schedule
        await scheduler_engine.reload_schedules()

        return {"success": True, "message": f"PoE schedule {schedule_id} deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete PoE schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/poe-schedules/{schedule_id}/toggle")
async def toggle_poe_schedule(schedule_id: int, db: AsyncSession = Depends(get_db)):
    """Enable or disable a PoE schedule."""
    try:
        result = await db.execute(select(PoESchedule).where(PoESchedule.id == schedule_id))
        schedule = result.scalar_one_or_none()

        if not schedule:
            raise HTTPException(status_code=404, detail="PoE schedule not found")

        schedule.enabled = not schedule.enabled
        schedule.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(schedule)

        status = "enabled" if schedule.enabled else "disabled"
        logger.info(f"PoE schedule {schedule_id} {status}")

        # Reload scheduler to enable/disable PoE schedule
        await scheduler_engine.reload_schedules()

        return {"success": True, "enabled": schedule.enabled}

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to toggle PoE schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Schedule Templates

@router.get("/schedule-templates", response_model=List[ScheduleTemplateResponse])
async def list_schedule_templates(
    type: str = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all schedule templates, optionally filtered by type."""
    try:
        query = select(ScheduleTemplate).order_by(ScheduleTemplate.created_at.desc())
        if type:
            query = query.where(ScheduleTemplate.template_type == type)
        result = await db.execute(query)
        return result.scalars().all()
    except Exception as e:
        logger.error(f"Failed to list schedule templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/schedule-templates", response_model=ScheduleTemplateResponse)
async def create_schedule_template(
    template: ScheduleTemplateCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new schedule template."""
    try:
        db_template = ScheduleTemplate(**template.dict())
        db.add(db_template)
        await db.commit()
        await db.refresh(db_template)
        logger.info(f"Created schedule template: {template.name}")
        return db_template
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to create schedule template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/schedule-templates/{template_id}", response_model=ScheduleTemplateResponse)
async def update_schedule_template(
    template_id: int,
    template_update: ScheduleTemplateCreate,
    db: AsyncSession = Depends(get_db)
):
    """Update an existing schedule template."""
    try:
        result = await db.execute(select(ScheduleTemplate).where(ScheduleTemplate.id == template_id))
        template = result.scalar_one_or_none()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        for field, value in template_update.dict().items():
            setattr(template, field, value)
        template.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(template)
        logger.info(f"Updated schedule template {template_id}")
        return template
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to update schedule template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/schedule-templates/{template_id}")
async def delete_schedule_template(template_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a schedule template."""
    try:
        result = await db.execute(select(ScheduleTemplate).where(ScheduleTemplate.id == template_id))
        template = result.scalar_one_or_none()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        await db.delete(template)
        await db.commit()
        logger.info(f"Deleted schedule template {template_id}")
        return {"success": True, "message": f"Template {template_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Failed to delete schedule template {template_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
