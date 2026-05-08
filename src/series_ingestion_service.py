import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.library_episode_status import LibraryEpisodeStatusBuilder
from src.path_handler import PathHandler
from src.utils.logger_utils import setup_logging

logger = setup_logging(__name__)

ANALYSIS_STATES = {"idle", "ready", "running", "completed", "failed"}
AUTO_MATCH_PATTERN = re.compile(r"S(?P<season>\d{1,2})E(?P<episode>\d{1,2})", re.IGNORECASE)


class SeriesIngestionService:
    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        self.status_builder = LibraryEpisodeStatusBuilder(base_dir=base_dir)

    def list_series(self) -> List[Dict[str, Any]]:
        series_entries: List[Dict[str, Any]] = []
        base_path = Path(self.base_dir)
        if not base_path.exists():
            return []

        for series_dir in sorted([path for path in base_path.iterdir() if path.is_dir()]):
            metadata = self._read_metadata(series_dir.name)
            status = self.get_series_status(series_dir.name)
            series_entries.append(
                {
                    "code": series_dir.name,
                    "display_name": metadata.get("display_name", series_dir.name),
                    "analysis_state": status["analysis_state"],
                    "expected_episode_count": status["expected_episode_count"],
                    "uploaded_episode_count": status["uploaded_episode_count"],
                    "unmatched_upload_count": status["unmatched_upload_count"],
                }
            )
        return series_entries

    def create_series(self, code: str, display_name: str) -> Dict[str, Any]:
        normalized_code = self._normalize_series_code(code)
        series_path = Path(self.base_dir) / normalized_code
        series_path.mkdir(parents=True, exist_ok=True)

        metadata = self._default_metadata(normalized_code, display_name)
        existing = self._read_metadata(normalized_code)
        if existing:
            metadata.update(existing)
            metadata["display_name"] = display_name
        self._write_metadata(normalized_code, metadata)
        return self.get_series_status(normalized_code)

    def create_seasons(self, series_code: str, seasons: List[str]) -> Dict[str, Any]:
        normalized_series = self._normalize_series_code(series_code)
        metadata = self._read_metadata(normalized_series)
        for season in seasons:
            season_code = self._normalize_season(season)
            season_path = Path(self.base_dir) / normalized_series / season_code
            season_path.mkdir(parents=True, exist_ok=True)
            metadata.setdefault("seasons", {}).setdefault(season_code, {"episodes": []})
        self._write_metadata(normalized_series, metadata)
        return self.get_series_status(normalized_series)

    def create_episodes(self, series_code: str, season_code: str, episodes: List[str]) -> Dict[str, Any]:
        normalized_series = self._normalize_series_code(series_code)
        normalized_season = self._normalize_season(season_code)
        metadata = self._read_metadata(normalized_series)
        season_entry = metadata.setdefault("seasons", {}).setdefault(normalized_season, {"episodes": []})

        known_episodes = set(season_entry.get("episodes", []))
        for episode in episodes:
            episode_code = self._normalize_episode(episode)
            episode_path = Path(self.base_dir) / normalized_series / normalized_season / episode_code
            episode_path.mkdir(parents=True, exist_ok=True)
            known_episodes.add(episode_code)
        season_entry["episodes"] = sorted(known_episodes)
        self._write_metadata(normalized_series, metadata)
        return self.get_series_status(normalized_series)

    def register_uploads(self, series_code: str, uploads: List[Dict[str, str]]) -> Dict[str, Any]:
        normalized_series = self._normalize_series_code(series_code)
        metadata = self._read_metadata(normalized_series)
        unmatched_uploads = metadata.setdefault("unmatched_uploads", [])
        auto_matched: List[Dict[str, str]] = []

        for upload in uploads:
            filename = upload["filename"]
            content = upload["content"]
            matched = self._parse_upload_target(filename)
            if matched:
                saved = self.save_plot_file(normalized_series, matched["season"], matched["episode"], content)
                auto_matched.append(saved)
                self._ensure_episode_metadata(metadata, matched["season"], matched["episode"])
            else:
                unmatched_uploads.append({
                    "upload_id": self._build_upload_id(filename),
                    "filename": filename,
                    "content": content,
                })

        metadata["analysis_state"] = self._derive_analysis_state(metadata)
        self._write_metadata(normalized_series, metadata)
        status = self.get_series_status(normalized_series)
        status["auto_matched_uploads"] = auto_matched
        status["unmatched_uploads"] = [
            {"upload_id": item["upload_id"], "filename": item["filename"]}
            for item in self._read_metadata(normalized_series).get("unmatched_uploads", [])
        ]
        return status

    def assign_upload(self, series_code: str, upload_id: str, season_code: str, episode_code: str) -> Dict[str, Any]:
        normalized_series = self._normalize_series_code(series_code)
        normalized_season = self._normalize_season(season_code)
        normalized_episode = self._normalize_episode(episode_code)
        metadata = self._read_metadata(normalized_series)
        uploads = metadata.get("unmatched_uploads", [])

        matched_upload: Optional[Dict[str, str]] = None
        remaining_uploads: List[Dict[str, str]] = []
        for upload in uploads:
            if upload["upload_id"] == upload_id:
                matched_upload = upload
            else:
                remaining_uploads.append(upload)

        if matched_upload is None:
            raise ValueError(f"Upload {upload_id} not found")

        self.save_plot_file(normalized_series, normalized_season, normalized_episode, matched_upload["content"])
        metadata["unmatched_uploads"] = remaining_uploads
        self._ensure_episode_metadata(metadata, normalized_season, normalized_episode)
        metadata["analysis_state"] = self._derive_analysis_state(metadata)
        self._write_metadata(normalized_series, metadata)
        return self.get_series_status(normalized_series)

    def save_plot_file(self, series_code: str, season_code: str, episode_code: str, content: str) -> Dict[str, str]:
        normalized_series, normalized_season, normalized_episode, episode_path = self._normalize_episode_target(
            series_code,
            season_code,
            episode_code,
        )
        plot_path = PathHandler.get_episode_plot_path(self.base_dir, normalized_series, normalized_season, normalized_episode)
        with open(plot_path, "w", encoding="utf-8") as plot_file:
            plot_file.write(content)
        return {
            "season": normalized_season,
            "episode": normalized_episode,
            "path": plot_path,
        }

    def save_episode_source_file(self, series_code: str, season_code: str, episode_code: str, filename: str, content: str) -> Dict[str, str]:
        normalized_series, normalized_season, normalized_episode, episode_path = self._normalize_episode_target(
            series_code,
            season_code,
            episode_code,
        )

        lowered = filename.lower()
        if lowered.endswith('.txt'):
            saved = self.save_plot_file(normalized_series, normalized_season, normalized_episode, content)
            saved["source_type"] = "plot"
            return saved

        if lowered.endswith('.srt'):
            srt_path = episode_path / filename
            with open(srt_path, "w", encoding="utf-8") as srt_file:
                srt_file.write(content)
            return {
                "season": normalized_season,
                "episode": normalized_episode,
                "path": str(srt_path),
                "source_type": "srt",
            }

        raise ValueError("Only plot .txt files or subtitle .srt files are supported")

    def get_series_status(self, series_code: str) -> Dict[str, Any]:
        normalized_series = self._normalize_series_code(series_code)
        metadata = self._read_metadata(normalized_series)
        seasons = metadata.get("seasons", {})
        expected_episode_count = sum(len(season.get("episodes", [])) for season in seasons.values())
        uploaded_episode_count = 0
        episodes: List[Dict[str, Any]] = []

        for season_code in sorted(seasons.keys()):
            season = seasons[season_code]
            for episode_code in sorted(season.get("episodes", [])):
                episode_status = self.status_builder.build(
                    normalized_series,
                    season_code,
                    episode_code,
                    0,
                )
                if episode_status["has_plot_file"]:
                    uploaded_episode_count += 1
                episodes.append({
                    "season": season_code,
                    "episode": episode_code,
                    "has_plot": episode_status["has_plot_file"],
                })

        analysis_state = metadata.get("analysis_state", "idle")
        if analysis_state not in ANALYSIS_STATES:
            analysis_state = "idle"

        return {
            "code": normalized_series,
            "display_name": metadata.get("display_name", normalized_series),
            "analysis_state": analysis_state,
            "expected_episode_count": expected_episode_count,
            "uploaded_episode_count": uploaded_episode_count,
            "unmatched_upload_count": len(metadata.get("unmatched_uploads", [])),
            "episodes": episodes,
            "unmatched_uploads": [
                {"upload_id": item["upload_id"], "filename": item["filename"]}
                for item in metadata.get("unmatched_uploads", [])
            ],
        }

    def set_analysis_state(self, series_code: str, state: str, error: Optional[str] = None) -> None:
        if state not in ANALYSIS_STATES:
            raise ValueError(f"Invalid analysis state: {state}")
        normalized_series = self._normalize_series_code(series_code)
        metadata = self._read_metadata(normalized_series)
        metadata["analysis_state"] = state
        if error:
            metadata["analysis_error"] = error
        else:
            metadata.pop("analysis_error", None)
        self._write_metadata(normalized_series, metadata)

    def list_expected_episodes(self, series_code: str) -> List[Dict[str, str]]:
        metadata = self._read_metadata(self._normalize_series_code(series_code))
        episodes: List[Dict[str, str]] = []
        for season_code in sorted(metadata.get("seasons", {}).keys()):
            for episode_code in sorted(metadata["seasons"][season_code].get("episodes", [])):
                episodes.append({"season": season_code, "episode": episode_code})
        return episodes

    def _metadata_path(self, series_code: str) -> Path:
        return Path(self.base_dir) / series_code / "series_metadata.json"

    def _read_metadata(self, series_code: str) -> Dict[str, Any]:
        metadata_path = self._metadata_path(series_code)
        if not metadata_path.exists():
            return self._default_metadata(series_code, series_code)
        with open(metadata_path, "r", encoding="utf-8") as metadata_file:
            return json.load(metadata_file)

    def _write_metadata(self, series_code: str, metadata: Dict[str, Any]) -> None:
        metadata_path = self._metadata_path(series_code)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(metadata_path, "w", encoding="utf-8") as metadata_file:
            json.dump(metadata, metadata_file, indent=2, ensure_ascii=False)

    def _default_metadata(self, code: str, display_name: str) -> Dict[str, Any]:
        return {
            "code": code,
            "display_name": display_name,
            "seasons": {},
            "unmatched_uploads": [],
            "analysis_state": "idle",
        }

    def _normalize_series_code(self, code: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9_-]", "", code.strip().upper())
        if not normalized:
            raise ValueError("Series code cannot be empty")
        return normalized

    def _normalize_season(self, season: str) -> str:
        season_num = int(str(season).upper().replace("S", ""))
        return f"S{season_num:02d}"

    def _normalize_episode(self, episode: str) -> str:
        episode_num = int(str(episode).upper().replace("E", ""))
        return f"E{episode_num:02d}"

    def _parse_upload_target(self, filename: str) -> Optional[Dict[str, str]]:
        match = AUTO_MATCH_PATTERN.search(filename)
        if not match:
            return None
        return {
            "season": self._normalize_season(match.group("season")),
            "episode": self._normalize_episode(match.group("episode")),
        }

    def _normalize_episode_target(self, series_code: str, season_code: str, episode_code: str) -> tuple[str, str, str, Path]:
        normalized_series = self._normalize_series_code(series_code)
        normalized_season = self._normalize_season(season_code)
        normalized_episode = self._normalize_episode(episode_code)
        episode_path = Path(self.base_dir) / normalized_series / normalized_season / normalized_episode
        episode_path.mkdir(parents=True, exist_ok=True)
        return normalized_series, normalized_season, normalized_episode, episode_path

    def _build_upload_id(self, filename: str) -> str:
        stem = Path(filename).stem.lower()
        cleaned = re.sub(r"[^a-z0-9]+", "-", stem).strip("-") or "upload"
        return f"{cleaned}-{uuid.uuid4().hex[:8]}"

    def _ensure_episode_metadata(self, metadata: Dict[str, Any], season_code: str, episode_code: str) -> None:
        season_entry = metadata.setdefault("seasons", {}).setdefault(season_code, {"episodes": []})
        if episode_code not in season_entry["episodes"]:
            season_entry["episodes"] = sorted([*season_entry["episodes"], episode_code])

    def _derive_analysis_state(self, metadata: Dict[str, Any]) -> str:
        expected_episode_count = sum(len(season.get("episodes", [])) for season in metadata.get("seasons", {}).values())
        unmatched_count = len(metadata.get("unmatched_uploads", []))
        uploaded_episode_count = 0
        for season_code, season in metadata.get("seasons", {}).items():
            for episode_code in season.get("episodes", []):
                plot_path = PathHandler.get_episode_plot_path(self.base_dir, metadata["code"], season_code, episode_code)
                if os.path.exists(plot_path):
                    uploaded_episode_count += 1
        if expected_episode_count and uploaded_episode_count == expected_episode_count and unmatched_count == 0:
            return "ready"
        return metadata.get("analysis_state", "idle")
