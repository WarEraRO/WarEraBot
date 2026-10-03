import asyncio
import functools
import inspect
import logging
import time
from typing import List

import discord
from discord import app_commands
from discord.ext import commands, tasks
from config import config

logger = logging.getLogger(__name__)

TASKS_MODULE_PREFIX = "cogs.tasks."
DEVELOPER_ROLE_ID = config.get("roles", {}).get("developer")


def _format_interval(loop: tasks.Loop) -> str:
    parts = []
    if loop.hours:
        parts.append(f"{loop.hours:g}h")
    if loop.minutes:
        parts.append(f"{loop.minutes:g}m")
    if loop.seconds:
        parts.append(f"{loop.seconds:g}s")
    return " ".join(parts) or "scheduled"


class RunJob(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # job names currently being executed through /run_job
        self._forced_running: set[str] = set()

    def _member_is_developer(self, member: discord.abc.User) -> bool:
        return any(r.id == DEVELOPER_ROLE_ID for r in getattr(member, "roles", []))

    def _get_jobs(self) -> dict[str, tasks.Loop]:
        """Collect every tasks.Loop exposed by the cogs loaded from cogs/tasks/*.py, keyed by job name."""
        jobs: dict[str, tasks.Loop] = {}
        for cog in self.bot.cogs.values():
            if not type(cog).__module__.startswith(TASKS_MODULE_PREFIX):
                continue
            for attr in dir(type(cog)):
                if isinstance(inspect.getattr_static(type(cog), attr, None), tasks.Loop):
                    # instance access returns the bound per-cog copy that the scheduler is running
                    loop = getattr(cog, attr)
                    jobs[loop.coro.__name__] = loop
        return jobs

    def _is_scheduled_iteration_running(self, loop: tasks.Loop) -> bool:
        """True while the loop's own scheduler is inside the job body (not sleeping between iterations)."""
        task = loop.get_task()
        if task is None or task.done():
            return False
        # Loop._loop awaits self.coro(...) directly, so during an iteration the loop task's
        # coroutine is suspended on the job coroutine itself.
        awaiting = getattr(task.get_coro(), "cr_await", None)
        job_codes = {loop.coro.__code__, getattr(loop.coro, "__run_job_original__", loop.coro).__code__}
        return getattr(awaiting, "cr_code", None) in job_codes

    def _install_guard(self, name: str, loop: tasks.Loop):
        """Make the loop's own scheduler skip an iteration that would start while a forced run is in progress."""
        if hasattr(loop.coro, "__run_job_original__"):
            return
        original = loop.coro

        @functools.wraps(original)
        async def guarded(*args, **kwargs):
            # only the loop's own task is skipped; the forced run calls through here from the interaction task
            if name in self._forced_running and asyncio.current_task() is loop.get_task():
                logger.info("Skipping scheduled run of job %s: a forced run is in progress", name)
                return
            return await original(*args, **kwargs)

        guarded.__run_job_original__ = original
        # Loop._loop looks up self.coro on every iteration, so this takes effect from the next one
        loop.coro = guarded

    async def job_name_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        if not self._member_is_developer(interaction.user):
            return []
        lower = (current or "").lower()
        choices = []
        for name, loop in sorted(self._get_jobs().items()):
            if lower and lower not in name.lower():
                continue
            choices.append(app_commands.Choice(name=f"{name} (every {_format_interval(loop)})", value=name))
            if len(choices) >= 25:
                break
        return choices

    @app_commands.command(name="run_job", description="Force a background job to run now, outside its loop timer (developers only).")
    @app_commands.describe(job_name="Background job to execute")
    @app_commands.autocomplete(job_name=job_name_autocomplete)
    async def run_job(self, interaction: discord.Interaction, job_name: str):
        if not self._member_is_developer(interaction.user):
            await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
            return

        jobs = self._get_jobs()
        loop = jobs.get(job_name.strip())
        if loop is None:
            available = ", ".join(f"`{name}`" for name in sorted(jobs)) or "none"
            await interaction.response.send_message(f"Unknown job `{job_name}`. Available jobs: {available}", ephemeral=True)
            return

        name = loop.coro.__name__
        if name in self._forced_running or self._is_scheduled_iteration_running(loop):
            await interaction.response.send_message(f"Job `{name}` is already running. Try again once it finishes.", ephemeral=True)
            return

        # claim the job before the first await so neither another /run_job nor the scheduler can start it meanwhile
        self._install_guard(name, loop)
        self._forced_running.add(name)
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            logger.info("Job %s forced by %s (%s)", name, interaction.user, interaction.user.id)
            started = time.monotonic()
            try:
                # Loop.__call__ runs the job body once without touching the loop's schedule
                await loop()
            except Exception as exc:
                logger.exception("Forced run of job %s failed", name)
                await self._safe_followup(interaction, f"Job `{name}` failed after {time.monotonic() - started:.1f}s: `{type(exc).__name__}: {exc}`")
                return
            await self._safe_followup(interaction, f"Job `{name}` finished in {time.monotonic() - started:.1f}s.")
        finally:
            self._forced_running.discard(name)

    async def _safe_followup(self, interaction: discord.Interaction, content: str):
        # the interaction token expires after 15 minutes; long jobs may outlive it
        try:
            await interaction.followup.send(content[:2000], ephemeral=True)
        except discord.HTTPException:
            logger.warning("Could not deliver /run_job result: %s", content)


async def setup(bot: commands.Bot):
    await bot.add_cog(RunJob(bot))
