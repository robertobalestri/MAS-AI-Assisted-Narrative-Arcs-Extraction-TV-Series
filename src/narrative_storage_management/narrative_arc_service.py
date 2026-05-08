# narrative_arc_service.py

from typing import List, Optional, Dict, Union
from src.narrative_storage_management.narrative_models import NarrativeArc, ArcProgression, Character
from src.narrative_storage_management.repositories import NarrativeArcRepository, ArcProgressionRepository, CharacterRepository
from src.narrative_storage_management.llm_service import LLMService
from src.narrative_storage_management.vector_store_service import VectorStoreService
from src.narrative_storage_management.character_service import CharacterService
from src.narrative_storage_management.arc_progression_service import ArcProgressionService
from langchain_core.documents import Document
import uuid
import logging
from contextlib import contextmanager
from sqlmodel import Session, select
from src.plot_processing.plot_processing_models import EntityLink

from src.utils.logger_utils import setup_logging
logger = setup_logging(__name__)

class NarrativeArcService:
    """Service to manage narrative arcs."""

    def __init__(
        self,
        arc_repository: NarrativeArcRepository,
        progression_repository: ArcProgressionRepository,
        character_service: CharacterService,
        llm_service: LLMService,
        vector_store_service: VectorStoreService,
        session: Session
    ):
        self.arc_repository = arc_repository
        self.progression_service = ArcProgressionService(progression_repository, character_service)
        self.character_service = character_service
        self.llm_service = llm_service
        self.vector_store_service = vector_store_service
        self.session = session

    @contextmanager
    def transaction(self):
        """Provide a transactional scope around a series of operations."""
        try:
            yield
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Transaction rollback due to: {e}")
            raise

    def add_arc(
        self,
        arc_data: Dict,
        series: str,
        season: str,
        episode: str,
        initial_progression: Optional[Dict] = None
    ) -> NarrativeArc:
        """
        Add a new narrative arc, handling deduplication and updating the vector store.
        Only uses existing characters from the database.
        """
        with self.transaction():
            try:
                # Get main characters from the database
                main_character_names = []
                if 'main_characters' in arc_data and isinstance(arc_data['main_characters'], str):
                    main_character_names = [
                        name.strip() 
                        for name in arc_data['main_characters'].split(';') 
                        if name.strip()
                    ]
                    
                # Check for existing arc by title
                title_normalized = arc_data['title'].strip().lower()
                existing_arc = self.arc_repository.get_by_title(title_normalized, series)

                if existing_arc:
                    logger.info(f"Arc with title '{arc_data['title']}' already exists. Updating existing arc.")
                    return self.update_arc(existing_arc.id, arc_data, series, season, episode)

                # If no exact title match, check for similar arcs using vector store
                similar_arcs = self.vector_store_service.find_similar_arcs(
                    query=f"{arc_data['title']}\n{arc_data['description']}",
                    n_results=5,
                    series=series,
                    exclude_anthology=True
                )

                # Filter arcs by similarity threshold
                SIMILARITY_THRESHOLD = 0.35
                similar_arcs = [
                    arc for arc in similar_arcs 
                    if arc['cosine_distance'] < SIMILARITY_THRESHOLD
                ]

                if similar_arcs:
                    # Get the most similar arc
                    most_similar = similar_arcs[0]
                    existing_arc = self.arc_repository.get_by_id(most_similar['metadata']['id'])

                    if existing_arc:
                        # Use LLM to decide if arcs should be merged
                        merge_decision = self.llm_service.decide_arc_merging(
                            new_arc=NarrativeArc(
                                id=str(uuid.uuid4()),
                                title=arc_data['title'],
                                description=arc_data['description'],
                                arc_type=arc_data['arc_type'],
                                series=series
                            ),
                            existing_arc=existing_arc
                        )

                        if merge_decision.get('same_arc', False):
                            logger.info(f"LLM decided arcs are the same. Updating existing arc.")
                            return self.update_arc(
                                existing_arc.id, 
                                arc_data, 
                                series, 
                                season, 
                                episode,
                                merge_decision=merge_decision
                            )

                elif existing_arc:
                    # If exact title match, use LLM to merge identical arcs
                    merge_decision = self.llm_service.merge_identical_arcs(
                        new_arc=NarrativeArc(
                            id=str(uuid.uuid4()),
                            title=arc_data['title'],
                            description=arc_data['description'],
                            arc_type=arc_data['arc_type'],
                            series=series
                        ),
                        existing_arc=existing_arc
                    )
                    return self.update_arc(
                        existing_arc.id, 
                        arc_data, 
                        series, 
                        season, 
                        episode,
                        merge_decision=merge_decision
                    )

                # If no similar arcs found or LLM decided they're different, create new arc
                # Create new arc
                new_arc = self._construct_narrative_arc(arc_data, series)
                self.arc_repository.add_or_update(new_arc)

                # Link main characters to arc (only existing ones)
                if main_character_names:
                    main_characters = self.character_service.get_characters_by_appellations(
                        main_character_names, 
                        series
                    )
                    if main_characters:
                        self.character_service.link_characters_to_arc(main_characters, new_arc)
                        logger.info(f"Linked {len(main_characters)} main characters to arc '{new_arc.title}'")
                    else:
                        logger.warning(f"No existing characters found for main characters: {main_character_names}")

                # Handle progression
                progression_data = arc_data.get('single_episode_progression_string')
                if progression_data:
                    # Get interfering characters from the database
                    interfering_chars = []
                    if 'interfering_episode_characters' in arc_data:
                        interfering_chars = [
                            name.strip() 
                            for name in arc_data['interfering_episode_characters'].split(';') 
                            if name.strip()
                        ]

                    # Create and add progression
                    progression = ArcProgression(
                        id=str(uuid.uuid4()),
                        main_arc_id=new_arc.id,
                        content=progression_data,
                        series=series,
                        season=season,
                        episode=episode
                    )

                    # Link interfering characters to progression (only existing ones)
                    if interfering_chars:
                        interfering_characters = self.character_service.get_characters_by_appellations(
                            interfering_chars, 
                            series
                        )
                        if interfering_characters:
                            self.character_service.link_characters_to_progression(
                                interfering_characters, 
                                progression
                            )
                            logger.info(f"Linked {len(interfering_characters)} interfering characters to progression")
                        else:
                            logger.warning(f"No existing characters found for interfering characters: {interfering_chars}")

                    # Add progression
                    self.progression_service.add_or_update_progression(
                        arc=new_arc,
                        progression=progression,
                        series=series,
                        season=season,
                        episode=episode
                    )
                    logger.info(f"Added progression to arc '{new_arc.title}'")

                # Update embeddings
                self.update_embeddings(new_arc)
                logger.info(f"Added new arc '{new_arc.title}' to the database and vector store.")
                return new_arc

            except Exception as e:
                logger.error(f"Error in add_arc: {e}")
                raise

    def update_arc(
        self,
        arc_id: str,
        arc_data: Dict,
        series: str,
        season: str,
        episode: str,
        merge_decision: Optional[Dict] = None
    ) -> NarrativeArc:
        """
        Update an existing narrative arc, including merging if necessary.

        Args:
            arc_id: The ID of the arc to update.
            arc_data: Dictionary containing updated arc details.
            series: The series name.
            season: The season number.
            episode: The episode number.
            merge_decision: Optional dictionary with merge details.

        Returns:
            The updated NarrativeArc object.
        """
        with self.transaction():
            try:
                existing_arc = self.arc_repository.get_by_id(arc_id)
                if not existing_arc:
                    logger.warning(f"No arc found with ID {arc_id}. Cannot update.")
                    raise ValueError(f"No arc found with ID {arc_id}.")

                # Update fields based on merge decision if provided
                if merge_decision:
                    existing_arc.description = merge_decision.get('merged_description', existing_arc.description)
                    if 'merged_title' in merge_decision:
                        existing_arc.title = merge_decision['merged_title']

                # Normalize title
                existing_arc.title = existing_arc.title.strip().title()

                # Update the arc
                self.arc_repository.update_fields(existing_arc, existing_arc.__dict__)
                logger.info(f"Updated arc '{existing_arc.title}' with ID {arc_id}.")

                # Update main characters if provided in arc_data
                if 'main_characters' in arc_data:
                    main_character_names = [
                        name.strip() 
                        for name in arc_data['main_characters'].split(';') 
                        if name.strip()
                    ]
                    main_characters = self.character_service.get_characters_by_appellations(
                        main_character_names, 
                        series
                    )
                    if main_characters:
                        # Clear existing main characters and add new ones
                        existing_arc.main_characters.clear()
                        self.character_service.link_characters_to_arc(main_characters, existing_arc)
                        logger.info(f"Updated main characters for arc '{existing_arc.title}'")
                    else:
                        logger.warning(f"No main characters found for updated arc: {existing_arc.title}")

                # Handle progressions
                self._handle_progressions(existing_arc, arc_data, series, season, episode)

                # Update embeddings
                self.update_embeddings(existing_arc)
                logger.info(f"Updated embeddings for arc '{existing_arc.title}'.")

                return existing_arc

            except Exception as e:
                logger.error(f"Error in update_arc: {e}")
                raise

    def _construct_narrative_arc(self, arc_data: Dict, series: str) -> NarrativeArc:
        """Helper method to construct a NarrativeArc object from arc_data."""
        return NarrativeArc(
            id=str(uuid.uuid4()),
            title=arc_data['title'].strip().title(),
            arc_type=arc_data.get('arc_type', 'default_type'),  # Default type if not provided
            description=arc_data['description'],
            series=series
        )

    def _handle_progressions(
        self,
        arc: NarrativeArc,
        arc_data: Dict,
        series: str,
        season: str,
        episode: str
    ):
        """Handle adding or updating arc progressions."""
        progression_data = arc_data.get('single_episode_progression_string')
        if progression_data:
            progression = ArcProgression(
                id=str(uuid.uuid4()),
                content=progression_data,
                series=series,
                season=season,
                episode=episode
            )

            # Handle interfering characters
            if interfering_chars := arc_data.get('interfering_episode_characters'):
                # Split interfering characters string into a list
                interfering_names = [
                    name.strip() 
                    for name in interfering_chars.split(';') 
                    if name.strip()
                ]
                # Get the actual character objects
                interfering_characters = self.character_service.get_characters_by_appellations(
                    interfering_names, 
                    series
                )
                if interfering_characters:
                    self.character_service.link_characters_to_progression(
                        interfering_characters, 
                        progression
                    )
                else:
                    logger.warning(f"No interfering characters found for progression in {season}{episode}")

            # Add or update progression
            self.progression_service.add_or_update_progression(
                arc=arc,
                progression=progression,
                series=series,
                season=season,
                episode=episode
            )

    def update_embeddings(self, arc: NarrativeArc):
        """Update the vector store embeddings for the arc."""
        main_characters_str = ', '.join([char.best_appellation for char in arc.main_characters])

        # Create main document for the arc itself
        main_doc = Document(
            page_content=f"{arc.title}\n{arc.description}",
            metadata={
                "title": arc.title,
                "arc_type": arc.arc_type,
                "description": arc.description,
                "main_characters": main_characters_str,
                "series": arc.series,
                "doc_type": "main",
                "id": arc.id,
            }
        )

        # Create documents for each progression
        docs = [main_doc]
        ids = [arc.id]
        for progression in arc.progressions:
            # Get interfering characters for this progression
            interfering_chars_str = ', '.join([
                char.best_appellation 
                for char in progression.interfering_characters
            ])
            
            # Create progression title - include series, arc title, episode and interfering characters
            progression_title = f"{arc.series} | {arc.title} | S{progression.season.replace('S', '')}E{progression.episode.replace('E', '')}"
            if interfering_chars_str:
                progression_title += f" | {interfering_chars_str}"
                
            # Create progression document with enhanced metadata
            prog_doc = Document(
                page_content=f"{progression.content}",
                metadata={
                    "progression_title": progression_title,
                    "arc_type": arc.arc_type,
                    "interfering_characters": interfering_chars_str,
                    "series": arc.series,
                    "doc_type": "progression",
                    "id": progression.id,
                    "main_arc_id": arc.id,
                    "parent_arc_title": arc.title,
                    "season": progression.season,
                    "episode": progression.episode,
                    "ordinal_position": progression.ordinal_position
                }
            )
            docs.append(prog_doc)
            ids.append(progression.id)

        # Update vector store
        try:
            # First delete existing documents
            self.vector_store_service.delete_documents_by_arc(arc.id)
            # Then add new/updated documents
            self.vector_store_service.add_documents(docs, ids)
            logger.info(f"Updated vector store entries for arc '{arc.title}' with {len(docs)} documents")
        except Exception as e:
            logger.error(f"Error updating vector store for arc {arc.id}: {e}")
            raise

    def add_arc_to_vector_store(self, arc: NarrativeArc):
        """Optional helper if you want to separately add arcs to vector store."""
        self.update_embeddings(arc)

    def delete_arc(self, arc_id: str) -> bool:
        """
        Delete a narrative arc and its progressions.
        Also removes related entries from the vector store.
        """
        with self.transaction():
            try:
                arc = self.arc_repository.get_by_id(arc_id)
                if not arc:
                    logger.warning(f"No arc found with ID {arc_id}")
                    return False

                # Delete from vector store first
                self.vector_store_service.delete_documents_by_arc(arc_id)

                # Delete from database
                self.arc_repository.delete(arc_id)
                logger.info(f"Successfully deleted arc '{arc.title}' with ID {arc_id}")
                return True

            except Exception as e:
                logger.error(f"Error deleting arc {arc_id}: {e}")
                raise

    def update_arc_details(
        self,
        arc_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        arc_type: Optional[str] = None,
        main_characters: Optional[List[str]] = None
    ) -> Optional[NarrativeArc]:
        """
        Update specific details of a narrative arc.
        Updates vector store embeddings if title or description changes.
        """
        with self.transaction():
            try:
                arc = self.arc_repository.get_by_id(arc_id)
                if not arc:
                    logger.warning(f"No arc found with ID {arc_id}")
                    return None

                update_fields = {}
                if title is not None:
                    update_fields["title"] = title.strip().title()
                if description is not None:
                    update_fields["description"] = description
                if arc_type is not None:
                    update_fields["arc_type"] = arc_type

                if update_fields:
                    self.arc_repository.update_fields(arc, update_fields)

                # Update main characters if provided
                if main_characters is not None:
                    # Get character objects for the new main characters
                    characters = self.character_service.get_characters_by_appellations(
                        main_characters, arc.series
                    )
                    # Clear existing main characters and add new ones
                    arc.main_characters = characters
                    logger.info(f"Updated main characters for arc '{arc.title}'")

                # Update embeddings if title or description changed
                if "title" in update_fields or "description" in update_fields:
                    self.update_embeddings(arc)
                    logger.info(f"Updated embeddings for arc '{arc.title}'")

                return arc

            except Exception as e:
                logger.error(f"Error updating arc {arc_id}: {e}")
                raise

    def update_progression(
        self,
        progression_id: str,
        content: str,
        interfering_characters: List[str]
    ) -> Optional[ArcProgression]:
        """Update the content and interfering characters of a progression."""
        with self.transaction():
            try:
                progression = self.progression_service.get_progression_by_id(progression_id)
                if not progression:
                    logger.warning(f"No progression found with ID {progression_id}")
                    return None

                # Update progression content
                progression.content = content

                # Update interfering characters
                characters = self.character_service.get_characters_by_appellations(
                    interfering_characters, 
                    progression.series
                )
                progression.interfering_characters = characters

                # Add or update progression
                self.progression_service.add_or_update_progression(
                    arc=progression.narrative_arc,
                    progression=progression,
                    series=progression.series,
                    season=progression.season,
                    episode=progression.episode
                )

                # Update embeddings for the entire arc
                self.update_embeddings(progression.narrative_arc)
                
                logger.info(f"Updated progression {progression_id} with {len(characters)} interfering characters")
                return progression

            except Exception as e:
                logger.error(f"Error updating progression {progression_id}: {e}")
                raise

    def add_progression(
        self,
        arc_id: str,
        content: str,
        series: str,
        season: str,
        episode: str,
        interfering_characters: Union[str, List[str]]
    ) -> Optional[ArcProgression]:
        """Add a new progression to an existing arc."""
        with self.transaction():
            try:
                # Convert interfering_characters to list if it's a string
                character_names = (
                    interfering_characters.split(';') 
                    if isinstance(interfering_characters, str) 
                    else interfering_characters
                )
                
                arc = self.arc_repository.get_by_id(arc_id)
                if not arc:
                    logger.warning(f"No arc found with ID {arc_id}")
                    return None

                # Normalize season and episode format
                normalized_season = f"S{season.replace('S', '').replace('s', '').zfill(2)}"
                normalized_episode = f"E{episode.replace('E', '').replace('e', '').zfill(2)}"

                # Create new progression
                progression = ArcProgression(
                    id=str(uuid.uuid4()),
                    content=content,
                    series=series,
                    season=normalized_season,
                    episode=normalized_episode
                )

                # Get and link interfering characters
                if character_names:
                    characters = self.character_service.get_characters_by_appellations(
                        character_names, 
                        series
                    )
                    if characters:
                        self.character_service.link_characters_to_progression(
                            characters, 
                            progression
                        )
                        logger.info(f"Linked {len(characters)} interfering characters to new progression")

                # Add progression using progression service
                updated_progression = self.progression_service.add_or_update_progression(
                    arc=arc,
                    progression=progression,
                    series=series,
                    season=normalized_season,
                    episode=normalized_episode
                )

                # Refresh the arc to get the updated progressions
                self.session.refresh(arc, ['progressions'])

                # Update embeddings for the entire arc
                self.update_embeddings(arc)
                
                logger.info(f"Added new progression to arc '{arc.title}' in {normalized_season}{normalized_episode}")
                return updated_progression

            except Exception as e:
                logger.error(f"Error adding progression to arc {arc_id}: {e}")
                raise

    def merge_arcs(
        self,
        arc_id_1: str,
        arc_id_2: str,
        merged_title: str,
        merged_description: str,
        merged_arc_type: str,
        main_characters: List[str],
        progression_mappings: List[Dict[str, Union[str, List[str]]]]
    ) -> Optional[NarrativeArc]:
        """Merge two arcs into a new one."""
        with self.transaction():
            try:
                # Get both arcs
                arc1 = self.arc_repository.get_by_id(arc_id_1)
                arc2 = self.arc_repository.get_by_id(arc_id_2)
                
                if not arc1 or not arc2:
                    logger.warning("One or both arcs not found")
                    return None

                logger.info(f"Starting merge of arcs: '{arc1.title}' and '{arc2.title}'")

                # Delete both arcs from vector store first
                self.vector_store_service.delete_documents_by_arc(arc_id_1)
                self.vector_store_service.delete_documents_by_arc(arc_id_2)

                # Update first arc with merged details
                arc1.title = merged_title
                arc1.description = merged_description
                arc1.arc_type = merged_arc_type

                # Update main characters
                characters = self.character_service.get_characters_by_appellations(
                    main_characters, 
                    arc1.series
                )
                arc1.main_characters = characters

                # Clear existing progressions
                arc1.progressions = []

                # Create new progressions from the mappings
                for mapping in progression_mappings:
                    if mapping['content'].strip():  # Only create progression if content exists
                        progression = ArcProgression(
                            id=str(uuid.uuid4()),
                            content=mapping['content'],
                            series=arc1.series,
                            season=mapping['season'],
                            episode=mapping['episode'],
                            main_arc_id=arc1.id
                        )

                        # Handle interfering characters
                        if mapping.get('interfering_characters'):
                            interfering_chars = self.character_service.get_characters_by_appellations(
                                mapping['interfering_characters'],
                                arc1.series
                            )
                            if interfering_chars:
                                self.character_service.link_characters_to_progression(
                                    interfering_chars,
                                    progression
                                )

                        # Add progression
                        self.progression_service.add_or_update_progression(
                            arc=arc1,
                            progression=progression,
                            series=arc1.series,
                            season=mapping['season'],
                            episode=mapping['episode']
                        )

                # Update the merged arc in database
                self.arc_repository.add_or_update(arc1)

                # Resequence all progressions
                self.progression_service.resequence_ordinal_positions(arc1.id)

                # Update vector store with new merged arc
                self.update_embeddings(arc1)

                # Delete second arc from database
                self.arc_repository.delete(arc_id_2)

                logger.info(f"Successfully merged arcs into '{arc1.title}'")
                return arc1

            except Exception as e:
                logger.error(f"Error merging arcs: {e}")
                raise
