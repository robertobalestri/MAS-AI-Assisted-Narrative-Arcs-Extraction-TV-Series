from pathlib import Path
from typing import Dict, List

from sqlmodel import select

from src.narrative_storage_management.narrative_arc_service import NarrativeArcService
from src.narrative_storage_management.character_service import CharacterService
from src.narrative_storage_management.llm_service import LLMService
from src.narrative_storage_management.narrative_models import ArcProgression
from src.narrative_storage_management.repositories import ArcProgressionRepository, DatabaseSessionManager, NarrativeArcRepository, CharacterRepository
from src.narrative_storage_management.vector_store_service import VectorStoreService
from src.path_handler import PathHandler
from src.utils.logger_utils import setup_logging

logger = setup_logging(__name__)


class EpisodeResetService:
    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir
        self.db_manager = DatabaseSessionManager()
        self.vector_store_service = VectorStoreService()

    def reset_episode(self, series: str, season: str, episode: str) -> Dict[str, List[str]]:
        derived_files_deleted = self._delete_episode_artifacts(series, season, episode)

        with self.db_manager.session_scope() as session:
            progression_repo = ArcProgressionRepository(session)
            arc_repo = NarrativeArcRepository(session)
            character_repo = CharacterRepository(session)
            character_service = CharacterService(character_repo)
            llm_service = LLMService()
            narrative_arc_service = NarrativeArcService(
                arc_repository=arc_repo,
                progression_repository=progression_repo,
                character_service=character_service,
                llm_service=llm_service,
                vector_store_service=self.vector_store_service,
                session=session,
            )

            target_progressions = session.exec(
                select(ArcProgression).where(
                    ArcProgression.series == series,
                    ArcProgression.season == season,
                    ArcProgression.episode == episode,
                )
            ).all()

            affected_arc_ids = sorted({progression.main_arc_id for progression in target_progressions})
            removed_progression_ids = [progression.id for progression in target_progressions if progression.id]
            deleted_arc_ids: List[str] = []
            updated_arc_ids: List[str] = []

            for progression in target_progressions:
                if progression.id:
                    progression.interfering_characters.clear()
                    self.vector_store_service.collection.delete(ids=[progression.id])
                    progression_repo.delete(progression.id)

            session.flush()

            for arc_id in affected_arc_ids:
                remaining_progressions = session.exec(
                    select(ArcProgression).where(ArcProgression.main_arc_id == arc_id)
                ).all()
                if not remaining_progressions:
                    narrative_arc_service.delete_arc(arc_id)
                    deleted_arc_ids.append(arc_id)
                else:
                    arc = arc_repo.get_by_id(arc_id)
                    if arc:
                        narrative_arc_service.update_embeddings(arc)
                        updated_arc_ids.append(arc_id)

        return {
            "removed_progression_ids": removed_progression_ids,
            "deleted_arc_ids": deleted_arc_ids,
            "updated_arc_ids": updated_arc_ids,
            "deleted_artifacts": derived_files_deleted,
        }

    def _delete_episode_artifacts(self, series: str, season: str, episode: str) -> List[str]:
        path_handler = PathHandler(series, season, episode, base_dir=self.base_dir)
        candidate_paths = [
            path_handler.get_named_plot_file_path(),
            path_handler.get_entity_substituted_plot_file_path(),
            path_handler.get_entity_normalized_plot_file_path(),
            path_handler.get_semantic_segments_path(),
            path_handler.get_episode_raw_spacy_entities_path(),
            path_handler.get_episode_refined_entities_path(),
            path_handler.get_suggested_episode_arc_path(),
            path_handler.get_episode_narrative_analysis_path(),
            path_handler.get_episode_narrative_arcs_path(),
        ]

        deleted: List[str] = []
        for artifact_path in candidate_paths:
            artifact = Path(artifact_path)
            if artifact.exists():
                artifact.unlink()
                deleted.append(str(artifact))
        return deleted
