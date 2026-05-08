import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from sqlmodel import select

from src.ai_models.ai_models import LLMType, get_llm
from src.analysis_service import AnalysisService
from src.library_episode_status import LibraryEpisodeStatusBuilder
from src.narrative_storage_management.narrative_models import ArcProgression
from src.narrative_storage_management.repositories import DatabaseSessionManager
from src.path_handler import PathHandler
from src.plot_processing.plot_summarizing import summarize_plot
from src.utils.logger_utils import setup_logging

logger = setup_logging(__name__)


class LibraryExplorerService:
    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        self.db_manager = DatabaseSessionManager()
        self.analysis_service = AnalysisService(base_dir=base_dir)
        self.status_builder = LibraryEpisodeStatusBuilder(base_dir=base_dir)

    def get_library_overview(self) -> List[Dict[str, Any]]:
        progressions = self._load_progression_counts()
        base_path = Path(self.base_dir)
        if not base_path.exists():
            return []

        series_payload: List[Dict[str, Any]] = []
        for series_dir in sorted(path for path in base_path.iterdir() if path.is_dir()):
            seasons_payload: List[Dict[str, Any]] = []
            for season_dir in sorted(path for path in series_dir.iterdir() if path.is_dir() and path.name.startswith("S")):
                episodes_payload: List[Dict[str, Any]] = []
                for episode_dir in sorted(path for path in season_dir.iterdir() if path.is_dir() and path.name.startswith("E")):
                    episodes_payload.append(
                        self._build_episode_status(
                            series_dir.name,
                            season_dir.name,
                            episode_dir.name,
                            progressions,
                        )
                    )
                seasons_payload.append(
                    {
                        "season": season_dir.name,
                        "episodes": episodes_payload,
                    }
                )
            series_payload.append(
                {
                    "code": series_dir.name,
                    "display_name": self._display_name_for_series(series_dir.name),
                    "seasons": seasons_payload,
                }
            )
        return series_payload

    def get_series_overview(self, series_code: str) -> Dict[str, Any]:
        normalized_series = series_code.upper()
        for series in self.get_library_overview():
            if series["code"] == normalized_series:
                return series
        raise ValueError(f"Series {normalized_series} not found")

    def generate_plot_from_srt(self, series_code: str, season_code: str, episode_code: str) -> Dict[str, Any]:
        normalized_series = series_code.upper()
        normalized_season = season_code.upper()
        normalized_episode = episode_code.upper()
        episode_dir = Path(self.base_dir) / normalized_series / normalized_season / normalized_episode
        srt_path = self.status_builder.find_srt_path(episode_dir)
        if srt_path is None:
            raise ValueError("No SRT file found for this episode")

        with open(srt_path, "r", encoding="utf-8") as srt_file:
            dialogue_text = srt_file.read()
        if not dialogue_text.strip():
            raise ValueError("SRT file does not contain usable text")

        output_path = PathHandler.get_episode_plot_path(self.base_dir, normalized_series, normalized_season, normalized_episode)
        llm = get_llm(LLMType.INTELLIGENT)
        summarize_plot(dialogue_text, llm, output_path)
        return self._build_episode_status(
            normalized_series,
            normalized_season,
            normalized_episode,
            self._load_progression_counts(),
        )

    def generate_missing_plots_for_season(self, series_code: str, season_code: str) -> Dict[str, Any]:
        normalized_series = series_code.upper()
        normalized_season = season_code.upper()
        season_path = Path(self.base_dir) / normalized_series / normalized_season
        if not season_path.exists():
            raise ValueError(f"Season {normalized_season} not found for {normalized_series}")

        generated_episodes: List[str] = []
        progression_counts = self._load_progression_counts()
        for episode_dir in sorted(path for path in season_path.iterdir() if path.is_dir() and path.name.startswith("E")):
            status = self._build_episode_status(
                normalized_series,
                normalized_season,
                episode_dir.name,
                progression_counts,
            )
            if status["analysis_status"] == "subtitle_only":
                self.generate_plot_from_srt(normalized_series, normalized_season, episode_dir.name)
                generated_episodes.append(episode_dir.name)

        return {
            "series": normalized_series,
            "season": normalized_season,
            "generated_episodes": generated_episodes,
        }

    def analyze_episode(self, series_code: str, season_code: str, episode_code: str) -> Dict[str, Any]:
        normalized_series = series_code.upper()
        normalized_season = season_code.upper()
        normalized_episode = episode_code.upper()
        status = self._build_episode_status(
            normalized_series,
            normalized_season,
            normalized_episode,
            self._load_progression_counts(),
        )
        if status["analysis_status"] != "plot_ready":
            raise ValueError("Episode is not ready for analysis")

        self.analysis_service.analyze_episode(normalized_series, normalized_season, normalized_episode)
        return self._build_episode_status(
            normalized_series,
            normalized_season,
            normalized_episode,
            self._load_progression_counts(),
        )

    def analyze_ready_episodes_for_season(self, series_code: str, season_code: str) -> Dict[str, Any]:
        normalized_series = series_code.upper()
        normalized_season = season_code.upper()
        season_path = Path(self.base_dir) / normalized_series / normalized_season
        if not season_path.exists():
            raise ValueError(f"Season {normalized_season} not found for {normalized_series}")

        processed_episodes: List[str] = []
        progression_counts = self._load_progression_counts()
        for episode_dir in sorted(path for path in season_path.iterdir() if path.is_dir() and path.name.startswith("E")):
            status = self._build_episode_status(
                normalized_series,
                normalized_season,
                episode_dir.name,
                progression_counts,
            )
            if status["analysis_status"] == "plot_ready":
                self.analysis_service.analyze_episode(normalized_series, normalized_season, episode_dir.name)
                processed_episodes.append(episode_dir.name)

        return {
            "series": normalized_series,
            "season": normalized_season,
            "processed_episodes": processed_episodes,
        }

    def _build_episode_status(
        self,
        series_code: str,
        season_code: str,
        episode_code: str,
        progression_counts: Dict[tuple[str, str, str], int],
    ) -> Dict[str, Any]:
        progression_count = progression_counts.get((series_code, season_code, episode_code), 0)
        return self.status_builder.build(series_code, season_code, episode_code, progression_count)

    def _load_progression_counts(self) -> Dict[tuple[str, str, str], int]:
        counts: Dict[tuple[str, str, str], int] = defaultdict(int)
        with self.db_manager.session_scope() as session:
            progressions = session.exec(select(ArcProgression)).all()
            for progression in progressions:
                counts[(progression.series, progression.season, progression.episode)] += 1
        return counts

    def _display_name_for_series(self, code: str) -> str:
        if code == "GA":
            return "Grey's Anatomy"
        return code
