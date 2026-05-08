from pathlib import Path
from typing import Any, Dict

from src.path_handler import PathHandler


class LibraryEpisodeStatusBuilder:
    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir

    def build(
        self,
        series_code: str,
        season_code: str,
        episode_code: str,
        progression_count: int,
    ) -> Dict[str, Any]:
        episode_dir = Path(self.base_dir) / series_code / season_code / episode_code
        path_handler = PathHandler(series_code, season_code, episode_code, base_dir=self.base_dir)

        plot_path = Path(path_handler.get_raw_plot_file_path())
        full_dialogues_path = Path(path_handler.get_full_dialogues_file_path())
        srt_path = self.find_srt_path(episode_dir)
        has_analysis_artifacts = Path(path_handler.get_semantic_segments_path()).exists() or Path(path_handler.get_suggested_episode_arc_path()).exists()

        if plot_path.exists() and progression_count > 0:
            analysis_status = "processed"
        elif plot_path.exists():
            analysis_status = "plot_ready"
        elif srt_path is not None:
            analysis_status = "subtitle_only"
        else:
            analysis_status = "empty"

        return {
            "series": series_code,
            "season": season_code,
            "episode": episode_code,
            "has_plot_file": plot_path.exists(),
            "has_srt_file": srt_path is not None,
            "has_dialogue_json": full_dialogues_path.exists(),
            "has_analysis_artifacts": has_analysis_artifacts,
            "progression_count": progression_count,
            "analysis_status": analysis_status,
        }

    def find_srt_path(self, episode_dir: Path) -> Path | None:
        if not episode_dir.exists():
            return None
        srt_files = sorted(episode_dir.glob("*.srt"))
        return srt_files[0] if srt_files else None
