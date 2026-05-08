from typing import Any, Optional, Dict, List
import asyncio
from typing import Dict, Optional
import asyncio
from .prompts import PRESENT_SEASON_ARCS_IDENTIFIER_PROMPT
from src.utils.llm_utils import clean_llm_json_response

from src.utils.logger_utils import setup_logging

logger = setup_logging(__name__)

class BaseAsyncProcessor:
    """Base class for async LLM processors."""
    
    def __init__(
        self,
        max_concurrent: int = 5,
        timeout: float = 30.0,
        retry_attempts: int = 3
    ):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.tasks = []
        self.timeout = timeout
        self.retry_attempts = retry_attempts

    async def _process_with_retries(
        self,
        process_func: callable,
        *args,
        **kwargs
    ) -> Optional[Dict]:
        """Generic retry logic for processing tasks."""
        async with self.semaphore:
            for attempt in range(self.retry_attempts):
                try:
                    async with asyncio.timeout(self.timeout):
                        return await process_func(*args, **kwargs)
                except asyncio.TimeoutError:
                    if attempt == self.retry_attempts - 1:
                        logger.error(f"Timeout after {self.retry_attempts} attempts")
                        return None
                    await asyncio.sleep(2 ** attempt)
                except Exception as e:
                    if attempt == self.retry_attempts - 1:
                        logger.error(f"Failed after {self.retry_attempts} attempts: {e}")
                        return None
                    await asyncio.sleep(2 ** attempt)
        return None

    async def process_all(self) -> List[Dict]:
        """Process all tasks and return results."""
        results = await asyncio.gather(*self.tasks, return_exceptions=True)
        return [r for r in results if r is not None and not isinstance(r, Exception)]

class PresentSeasonArcsProcessor(BaseAsyncProcessor):
    """Async processor specifically for identifying present season arcs."""

    async def process_season_arc(
        self,
        arc: Dict,
        episode_plot: str,
        llm: Any
    ) -> Optional[Dict]:
        """Process a single season arc."""
        async def _process():
            if arc['arc_type'] == "Anthology Arc":
                return None

            response = await llm.ainvoke(
                PRESENT_SEASON_ARCS_IDENTIFIER_PROMPT.format_messages(
                    episode_plot=episode_plot,
                    arc_title=arc['title'],
                    arc_description=arc['description']
                )
            )

            arc_data = clean_llm_json_response(response.content)
            if isinstance(arc_data, list):
                arc_data = arc_data[0]

            if arc_data['is_present']:
                return {
                    "title": arc_data['title'],
                    "description": arc_data['description'],
                    "presence_explanation": arc_data['explanation']
                }
            return None

        return await self._process_with_retries(_process)

    def add_task(self, arc: Dict, episode_plot: str, llm: Any):
        """Add a task to process a season arc."""
        task = asyncio.create_task(
            self.process_season_arc(arc, episode_plot, llm)
        )
        self.tasks.append(task)