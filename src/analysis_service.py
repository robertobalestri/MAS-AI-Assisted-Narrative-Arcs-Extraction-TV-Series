from typing import Dict, List

from src.analysis_pipeline import analyze_episode
from src.path_handler import PathHandler
from src.series_ingestion_service import SeriesIngestionService
from src.utils.logger_utils import setup_logging

logger = setup_logging(__name__)


class AnalysisService:
    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        self.ingestion_service = SeriesIngestionService(base_dir=base_dir)

    def analyze_episode(self, series_code: str, season_code: str, episode_code: str) -> None:
        analyze_episode(series_code, season_code, episode_code, base_dir=self.base_dir)

    def analyze_series(self, series_code: str) -> Dict[str, List[str]]:
        expected_episodes = self.ingestion_service.list_expected_episodes(series_code)
        processed: List[str] = []
        for item in expected_episodes:
            plot_path = PathHandler.get_episode_plot_path(self.base_dir, series_code, item["season"], item["episode"])
            if not PathHandler.file_exists(plot_path):
                logger.warning(f"Skipping {item['season']} {item['episode']} because no plot file exists")
                continue
            self.analyze_episode(series_code, item["season"], item["episode"])
            processed.append(f"{item['season']}{item['episode']}")
        return {"processed_episodes": processed}
