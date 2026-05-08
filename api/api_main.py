from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Union
from pydantic import BaseModel, ValidationError
from src.narrative_storage_management.repositories import DatabaseSessionManager
from src.narrative_storage_management.narrative_arc_service import NarrativeArcService
from src.narrative_storage_management.repositories import NarrativeArcRepository, ArcProgressionRepository, CharacterRepository
from src.narrative_storage_management.character_service import CharacterService
from src.narrative_storage_management.vector_store_service import VectorStoreService
from src.narrative_storage_management.narrative_models import NarrativeArc, ArcProgression, Character
from src.utils.logger_utils import setup_logging
from sqlmodel import Session, select
from src.plot_processing.plot_processing_models import EntityLink
import sys
from pathlib import Path
from src.narrative_storage_management.llm_service import LLMService
from src.path_handler import PathHandler
from api.library_routes import router as library_router, ingestion_service

# Set up logging at the very beginning
logger = setup_logging(__name__)

# Also set up root logger to catch all logs
root_logger = setup_logging("root")

# Disable uvicorn access log to avoid duplicate logging
import logging
logging.getLogger("uvicorn.access").handlers = []

app = FastAPI(title="Narrative Arcs Dashboard API")
app.include_router(library_router)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

db_manager = DatabaseSessionManager()

class ArcProgressionResponse(BaseModel):
    id: str
    content: str
    series: str
    season: str
    episode: str
    ordinal_position: int
    interfering_characters: List[str]

    class Config:
        from_attributes = True

    @classmethod
    def from_progression(cls, prog: ArcProgression):
        return cls(
            id=prog.id,
            content=prog.content,
            series=prog.series,
            season=prog.season,
            episode=prog.episode,
            ordinal_position=prog.ordinal_position,
            interfering_characters=[char.best_appellation for char in prog.interfering_characters]
        )

class NarrativeArcResponse(BaseModel):
    id: str
    title: str
    description: str
    arc_type: str
    main_characters: List[str]
    series: str
    progressions: List[ArcProgressionResponse]

    class Config:
        from_attributes = True

    @classmethod
    def from_arc(cls, arc: NarrativeArc):
        return cls(
            id=arc.id,
            title=arc.title,
            description=arc.description,
            arc_type=arc.arc_type,
            main_characters=[char.best_appellation for char in arc.main_characters],
            series=arc.series,
            progressions=[ArcProgressionResponse.from_progression(prog) for prog in sorted(
                arc.progressions,
                key=lambda x: (x.season, x.episode)
            )]
        )

class ArcUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    arc_type: Optional[str] = None
    main_characters: Optional[List[str]] = None

class ProgressionUpdateRequest(BaseModel):
    content: str
    interfering_characters: List[str]

class ProgressionCreateRequest(BaseModel):
    content: str
    arc_id: str
    series: str
    season: str
    episode: str
    interfering_characters: Union[str, List[str]]  # Accept either string or list

class VectorStoreEntry(BaseModel):
    id: str
    content: str
    metadata: dict
    embedding: Optional[List[float]] = None
    distance: Optional[float] = None

class ProgressionMapping(BaseModel):
    season: str
    episode: str
    content: str
    interfering_characters: List[str]

class ArcMergeRequest(BaseModel):
    arc_id_1: str
    arc_id_2: str
    merged_title: str
    merged_description: str
    merged_arc_type: str
    main_characters: List[str]
    progression_mappings: List[ProgressionMapping]

class InitialProgressionData(BaseModel):
    content: str
    season: str
    episode: str
    interfering_characters: List[str]

class ArcCreateRequest(BaseModel):
    title: str
    description: str
    arc_type: str
    main_characters: str  # Comma-separated string
    series: str
    initial_progression: Optional[InitialProgressionData] = None

class CharacterResponse(BaseModel):
    entity_name: str
    best_appellation: str
    series: str
    appellations: List[str]

    class Config:
        from_attributes = True

    @classmethod
    def from_character(cls, character: Character):
        return cls(
            entity_name=character.entity_name,
            best_appellation=character.best_appellation,
            series=character.series,
            appellations=[app.appellation for app in character.appellations]
        )

class CharacterCreateRequest(BaseModel):
    entity_name: str
    best_appellation: str
    series: str
    appellations: List[str]

    class Config:
        from_attributes = True

class CharacterMergeRequest(BaseModel):
    character1_id: str
    character2_id: str
    keep_character: str  # 'character1' or 'character2'

def normalize_season_episode(season: str, episode: str) -> tuple[str, str]:
    """Normalize season and episode format to S01, E01."""
    # Remove any S/SS or E/EE prefix and leading zeros
    season_num = int(season.replace('S', '').replace('s', ''))
    episode_num = int(episode.replace('E', '').replace('e', ''))
    
    # Format with leading zeros
    return f"S{season_num:02d}", f"E{episode_num:02d}"

def pad_number(num_str: str) -> str:
    """Pad a number string to at least 2 digits."""
    if len(num_str) == 1:
        return f"0{num_str}"
    return num_str

@app.get("/api/series", response_model=List[str])
async def get_series():
    """Get all unique series names."""
    try:
        with db_manager.session_scope() as session:
            result = session.exec(select(NarrativeArc.series).distinct())
            database_series = set(result)
        library_series = {item["code"] for item in ingestion_service.list_series()}
        return sorted(database_series.union(library_series))
    except Exception as e:
        logger.error(f"Error getting series: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/arcs/series/{series}", response_model=List[NarrativeArcResponse])
async def get_arcs_by_series(series: str):
    """Get all narrative arcs for a specific series."""
    try:
        with db_manager.session_scope() as session:
            logger.info(f"Fetching arcs for series: {series}")
            query = select(NarrativeArc).where(NarrativeArc.series == series)
            arcs = session.exec(query).all()
            logger.info(f"Found {len(arcs)} arcs")
            
            # Normalize season/episode format in progressions
            for arc in arcs:
                for prog in arc.progressions:
                    normalized_season, normalized_episode = normalize_season_episode(prog.season, prog.episode)
                    prog.season = normalized_season
                    prog.episode = normalized_episode
            
            return [NarrativeArcResponse.from_arc(arc) for arc in arcs]
    except Exception as e:
        logger.error(f"Error getting arcs for series {series}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/episodes/{series}", response_model=List[dict])
async def get_episodes(series: str):
    """Get all episodes for a series."""
    try:
        with db_manager.session_scope() as session:
            query = select(ArcProgression.season, ArcProgression.episode)\
                .where(ArcProgression.series == series)\
                .distinct()
            episodes = session.exec(query).all()
            
            # Convert to list of dicts and normalize format
            episode_list = [
                {
                    "season": normalized_season,
                    "episode": normalized_episode
                }
                for season, episode in episodes
                for normalized_season, normalized_episode in [normalize_season_episode(season, episode)]
            ]
            return sorted(
                episode_list,
                key=lambda x: (x["season"], x["episode"])
            )
    except Exception as e:
        logger.error(f"Error getting episodes for series {series}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/arcs/{series}/{season}/{episode}", response_model=List[NarrativeArcResponse])
async def get_arcs_by_episode(series: str, season: str, episode: str):
    """Get all narrative arcs that have progressions in a specific episode."""
    try:
        normalized_episode = f"E{episode.zfill(2)}"
        logger.debug(f"Fetching arcs for {series} {season} {normalized_episode}")
        
        with db_manager.session_scope() as session:
            # Get arcs that have progressions in this episode
            query = select(NarrativeArc)\
                .join(ArcProgression)\
                .where(
                    ArcProgression.series == series,
                    ArcProgression.season == season,
                    ArcProgression.episode == normalized_episode
                )\
                .distinct()
            
            arcs = session.exec(query).all()
            
            if not arcs:
                logger.warning(f"No arcs found for {series} {season} {normalized_episode}")
                return []
            
            return [NarrativeArcResponse.from_arc(arc) for arc in arcs]
            
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/arcs/{arc_id}")
async def delete_arc(arc_id: str):
    """Delete a narrative arc and its progressions."""
    try:
        with db_manager.session_scope() as session:
            arc_repository = NarrativeArcRepository(session)
            progression_repository = ArcProgressionRepository(session)
            character_service = CharacterService(CharacterRepository(session))
            vector_store_service = VectorStoreService()
            
            narrative_arc_service = NarrativeArcService(
                arc_repository=arc_repository,
                progression_repository=progression_repository,
                character_service=character_service,
                llm_service=None,  # Not needed for deletion
                vector_store_service=vector_store_service,
                session=session
            )
            
            result = narrative_arc_service.delete_arc(arc_id)
            if not result:
                raise HTTPException(status_code=404, detail="Arc not found")
            return {"message": "Arc deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting arc: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/arcs/{arc_id}")
async def update_arc(arc_id: str, update_data: ArcUpdateRequest):
    """Update arc details."""
    try:
        with db_manager.session_scope() as session:
            arc_repository = NarrativeArcRepository(session)
            progression_repository = ArcProgressionRepository(session)
            character_service = CharacterService(CharacterRepository(session))
            vector_store_service = VectorStoreService()
            
            narrative_arc_service = NarrativeArcService(
                arc_repository=arc_repository,
                progression_repository=progression_repository,
                character_service=character_service,
                llm_service=None,  # Not needed for update
                vector_store_service=vector_store_service,
                session=session
            )
            
            updated_arc = narrative_arc_service.update_arc_details(
                arc_id=arc_id,
                title=update_data.title,
                description=update_data.description,
                arc_type=update_data.arc_type,
                main_characters=update_data.main_characters
            )
            if not updated_arc:
                raise HTTPException(status_code=404, detail="Arc not found")
            return NarrativeArcResponse.from_arc(updated_arc)
    except Exception as e:
        logger.error(f"Error updating arc: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/progressions/{progression_id}", response_model=ArcProgressionResponse)
async def update_progression(progression_id: str, progression_data: ProgressionUpdateRequest):
    """Update a progression."""
    try:
        with db_manager.session_scope() as session:
            progression_repository = ArcProgressionRepository(session)
            character_service = CharacterService(CharacterRepository(session))
            vector_store_service = VectorStoreService()
            
            # Get the progression
            progression = progression_repository.get_by_id(progression_id)
            if not progression:
                raise HTTPException(status_code=404, detail="Progression not found")
            
            # Update the progression
            progression.content = progression_data.content
            
            # Update interfering characters
            # Split the characters if they're in a string format
            character_names = (
                progression_data.interfering_characters.split(';') 
                if isinstance(progression_data.interfering_characters, str) 
                else progression_data.interfering_characters
            )
            
            # Get characters from the database
            interfering_characters = character_service.get_characters_by_appellations(
                character_names,
                progression.series
            )
            
            progression.interfering_characters = interfering_characters
            
            # Save changes
            session.commit()
            session.refresh(progression)
            
            # Update vector store
            narrative_arc_service = NarrativeArcService(
                arc_repository=NarrativeArcRepository(session),
                progression_repository=progression_repository,
                character_service=character_service,
                llm_service=None,
                vector_store_service=vector_store_service,
                session=session
            )
            narrative_arc_service.update_embeddings(progression.narrative_arc)
            
            return ArcProgressionResponse.from_progression(progression)
            
    except Exception as e:
        logger.error(f"Error updating progression: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/progressions", response_model=ArcProgressionResponse)
async def create_progression(progression: ProgressionCreateRequest):
    """Create a new progression."""
    try:
        with db_manager.session_scope() as session:
            # Format season and episode numbers
            season = f"S{pad_number(progression.season.replace('S', ''))}"
            episode = f"E{pad_number(progression.episode.replace('E', ''))}"

            progression_repository = ArcProgressionRepository(session)
            arc_repository = NarrativeArcRepository(session)
            character_service = CharacterService(CharacterRepository(session))
            vector_store_service = VectorStoreService()
            
            narrative_arc_service = NarrativeArcService(
                arc_repository=arc_repository,
                progression_repository=progression_repository,
                character_service=character_service,
                llm_service=None,
                vector_store_service=vector_store_service,
                session=session
            )
            
            # Handle interfering_characters as either string or list
            character_names = (
                progression.interfering_characters.split(';') 
                if isinstance(progression.interfering_characters, str) 
                else progression.interfering_characters
            )

            # Create progression
            new_progression = narrative_arc_service.add_progression(
                arc_id=progression.arc_id,
                content=progression.content,
                series=progression.series,
                season=season,
                episode=episode,
                interfering_characters=character_names  # Pass as list
            )
            
            if not new_progression:
                raise HTTPException(status_code=404, detail="Arc not found")
                
            return ArcProgressionResponse.from_progression(new_progression)
            
    except Exception as e:
        logger.error(f"Error creating progression: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vector-store/{series}", response_model=List[VectorStoreEntry])
async def get_vector_store_entries(series: str, query: Optional[str] = None):
    """Get vector store entries for a series, optionally filtered by similarity to a query."""
    try:
        vector_store_service = VectorStoreService()
        
        if query:
            # If query provided, return similar documents
            results = vector_store_service.find_similar_documents(
                query=query,
                series=series,
                n_results=10
            )
            return results
        else:
            # If no query, return all documents for the series
            results = vector_store_service.get_all_documents(
                series=series,
                include_embeddings=True
            )
            return results
    except Exception as e:
        logger.error(f"Error getting vector store entries: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/arcs/merge", response_model=NarrativeArcResponse)
async def merge_arcs(merge_data: ArcMergeRequest):
    """Merge two arcs into a new one."""
    try:
        logger.info(f"Received merge request for arcs: {merge_data.arc_id_1} and {merge_data.arc_id_2}")
        logger.info(f"Merge data: {merge_data.dict()}")
        
        with db_manager.session_scope() as session:
            arc_repository = NarrativeArcRepository(session)
            progression_repository = ArcProgressionRepository(session)
            character_service = CharacterService(CharacterRepository(session))
            vector_store_service = VectorStoreService()
            
            narrative_arc_service = NarrativeArcService(
                arc_repository=arc_repository,
                progression_repository=progression_repository,
                character_service=character_service,
                llm_service=None,
                vector_store_service=vector_store_service,
                session=session
            )
            
            # Verify both arcs exist before attempting merge
            arc1 = arc_repository.get_by_id(merge_data.arc_id_1)
            arc2 = arc_repository.get_by_id(merge_data.arc_id_2)
            
            if not arc1 or not arc2:
                raise HTTPException(
                    status_code=404,
                    detail="One or both arcs not found"
                )
            
            # Normalize season/episode in progression mappings
            normalized_mappings = []
            for prog in merge_data.progression_mappings:
                if not prog.content.strip():  # Skip empty progressions
                    continue
                    
                season = f"S{pad_number(prog.season.replace('S', ''))}"
                episode = f"E{pad_number(prog.episode.replace('E', ''))}"
                
                normalized_mappings.append({
                    "season": season,
                    "episode": episode,
                    "content": prog.content,
                    "interfering_characters": prog.interfering_characters
                })
            
            merged_arc = narrative_arc_service.merge_arcs(
                arc_id_1=merge_data.arc_id_1,
                arc_id_2=merge_data.arc_id_2,
                merged_title=merge_data.merged_title,
                merged_description=merge_data.merged_description,
                merged_arc_type=merge_data.merged_arc_type,
                main_characters=merge_data.main_characters,
                progression_mappings=normalized_mappings
            )
            
            if not merged_arc:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to merge arcs"
                )
            
            logger.info(f"Successfully merged arcs into '{merged_arc.title}'")
            return NarrativeArcResponse.from_arc(merged_arc)
            
    except Exception as e:
        logger.error(f"Error merging arcs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/progressions/{progression_id}")
async def delete_progression(progression_id: str):
    """Delete a progression."""
    try:
        with db_manager.session_scope() as session:
            arc_repository = NarrativeArcRepository(session)
            progression_repository = ArcProgressionRepository(session)
            character_service = CharacterService(CharacterRepository(session))
            vector_store_service = VectorStoreService()
            
            narrative_arc_service = NarrativeArcService(
                arc_repository=arc_repository,
                progression_repository=progression_repository,
                character_service=character_service,
                llm_service=None,
                vector_store_service=vector_store_service,
                session=session
            )
            
            # Get the progression to find its arc
            progression = progression_repository.get_by_id(progression_id)
            if not progression:
                raise HTTPException(status_code=404, detail="Progression not found")
            
            # Delete the progression
            progression_repository.delete(progression_id)
            
            # Update the vector store for the arc
            narrative_arc_service.update_embeddings(progression.narrative_arc)
            
            return {"message": "Progression deleted successfully"}
            
    except Exception as e:
        logger.error(f"Error deleting progression: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class InitialProgressionRequest(BaseModel):
    content: str
    season: str
    episode: str
    interfering_characters: str  # Comma-separated string

class ArcCreateRequest(BaseModel):
    title: str
    description: str
    arc_type: str
    main_characters: str  # Comma-separated string
    series: str
    initial_progression: InitialProgressionRequest

@app.post("/api/arcs", response_model=NarrativeArcResponse)
async def create_arc(arc_data: ArcCreateRequest):
    """Create a new narrative arc."""
    try:
        # Log the raw request data
        logger.info("=== Raw Request Data ===")
        logger.info(f"Type of arc_data: {type(arc_data)}")
        logger.info(f"Raw arc_data: {arc_data.dict()}")
        
        with db_manager.session_scope() as session:
            arc_repository = NarrativeArcRepository(session)
            progression_repository = ArcProgressionRepository(session)
            character_service = CharacterService(CharacterRepository(session))
            vector_store_service = VectorStoreService()
            
            narrative_arc_service = NarrativeArcService(
                arc_repository=arc_repository,
                progression_repository=progression_repository,
                character_service=character_service,
                llm_service=None,
                vector_store_service=vector_store_service,
                session=session
            )
            
            # Create arc data dict with initial progression data
            arc_dict = {
                'title': arc_data.title,
                'description': arc_data.description,
                'arc_type': arc_data.arc_type,
                'main_characters': arc_data.main_characters,  # Already semicolon-separated string
                'single_episode_progression_string': arc_data.initial_progression.content if arc_data.initial_progression else None,
                'interfering_episode_characters': arc_data.initial_progression.interfering_characters if arc_data.initial_progression else None
            }

            # Create the arc with its initial progression
            new_arc = narrative_arc_service.add_arc(
                arc_data=arc_dict,
                series=arc_data.series,
                season=arc_data.initial_progression.season if arc_data.initial_progression else "",
                episode=arc_data.initial_progression.episode if arc_data.initial_progression else "",
                initial_progression=None  # We're using the fields in arc_dict instead
            )
            
            logger.info(f"Created new arc with ID: {new_arc.id}")
            if arc_data.initial_progression:
                logger.info(f"Initial progression data: {arc_data.initial_progression}")
            
            return NarrativeArcResponse.from_arc(new_arc)
            
    except Exception as e:
        logger.error(f"Error creating arc: {e}")
        logger.error("Full error details:", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/characters/{series}", response_model=List[CharacterResponse])
async def get_characters(series: str):
    """Get all characters for a series."""
    try:
        with db_manager.session_scope() as session:
            character_repository = CharacterRepository(session)
            characters = character_repository.get_by_series(series)
            return [
                CharacterResponse(
                    entity_name=char.entity_name,
                    best_appellation=char.best_appellation,
                    series=char.series,
                    appellations=[app.appellation for app in char.appellations]
                )
                for char in characters
            ]
    except Exception as e:
        logger.error(f"Error getting characters: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/characters/{series}", response_model=CharacterResponse)
async def create_character(series: str, character_data: CharacterCreateRequest):
    """Create a new character."""
    try:
        with db_manager.session_scope() as session:
            character_service = CharacterService(CharacterRepository(session))
            character = character_service.add_or_update_character(
                EntityLink(
                    entity_name=character_data.entity_name,
                    best_appellation=character_data.best_appellation,
                    appellations=character_data.appellations
                ),
                series=series
            )
            if not character:
                raise HTTPException(status_code=400, detail="Failed to create character")
            return CharacterResponse(
                entity_name=character.entity_name,
                best_appellation=character.best_appellation,
                series=character.series,
                appellations=[app.appellation for app in character.appellations]
            )
    except Exception as e:
        logger.error(f"Error creating character: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/characters/{series}", response_model=CharacterResponse)
async def update_character(series: str, character_data: CharacterCreateRequest):
    """Update an existing character."""
    try:
        with db_manager.session_scope() as session:
            character_service = CharacterService(CharacterRepository(session))
            
            # Create EntityLink with all the data
            entity = EntityLink(
                entity_name=character_data.entity_name,
                best_appellation=character_data.best_appellation,
                appellations=character_data.appellations,
                entity_type="PERSON"  # Default type for characters
            )
            
            # Update character
            character = character_service.add_or_update_character(entity, series)
            if not character:
                raise HTTPException(status_code=404, detail="Character not found")
            
            # Refresh the character to get updated data
            session.refresh(character)
            
            return CharacterResponse(
                entity_name=character.entity_name,
                best_appellation=character.best_appellation,
                series=character.series,
                appellations=[app.appellation for app in character.appellations]
            )
    except Exception as e:
        logger.error(f"Error updating character: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/characters/{series}/{entity_name}")
async def delete_character(series: str, entity_name: str):
    """Delete a character."""
    try:
        with db_manager.session_scope() as session:
            character_repository = CharacterRepository(session)
            character = character_repository.get_by_entity_name(entity_name, series)
            if not character:
                raise HTTPException(status_code=404, detail="Character not found")
            character_repository.delete(character)
            return {"message": "Character deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting character: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/characters/{series}/merge", response_model=dict)
async def merge_characters(series: str, merge_data: CharacterMergeRequest):
    """Merge two characters."""
    try:
        logger.info(f"Attempting to merge characters in series {series}. Request data: {merge_data.dict()}")
        
        with db_manager.session_scope() as session:
            character_service = CharacterService(CharacterRepository(session))
            
            success = character_service.merge_characters(
                merge_data.character1_id,
                merge_data.character2_id,
                series,
                keep_character=merge_data.keep_character
            )
            
            if not success:
                error_msg = f"Failed to merge characters. One or both characters not found: {merge_data.character1_id}, {merge_data.character2_id}"
                logger.error(error_msg)
                raise HTTPException(
                    status_code=400, 
                    detail=error_msg
                )
            
            logger.info(f"Successfully merged characters {merge_data.character1_id} and {merge_data.character2_id}")
            return {"message": "Characters merged successfully"}
            
    except Exception as e:
        error_msg = f"Error merging characters: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

@app.post("/api/vector-store/compare", response_model=Dict)
async def compare_arcs(arc_ids: List[str]):
    """Calculate cosine distance between two arcs."""
    try:
        if len(arc_ids) != 2:
            raise HTTPException(
                status_code=400,
                detail="Exactly two arc IDs must be provided"
            )

        vector_store_service = VectorStoreService()
        result = vector_store_service.calculate_arcs_cosine_distances(arc_ids)
        return result

    except Exception as e:
        logger.error(f"Error comparing arcs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vector-store/{series}/clusters", response_model=List[Dict])
async def get_arc_clusters(
    series: str,
    threshold: float = 0.5,  # Similarity threshold (1 - distance)
    min_cluster_size: int = 2,
    max_clusters: int = 5  # New parameter to limit number of clusters
):
    """Get clusters of similar arcs using HDBSCAN."""
    try:
        # Convert similarity threshold to distance threshold
        cluster_selection_epsilon = 1 - threshold
        
        vector_store_service = VectorStoreService()
        clusters = vector_store_service.find_similar_arcs_clusters(
            series=series,
            min_cluster_size=min_cluster_size,
            min_samples=1,  # Keep this low for more flexible clustering
            cluster_selection_epsilon=cluster_selection_epsilon
        )
        
        # Sort clusters by size and probability, then limit to max_clusters
        sorted_clusters = sorted(
            clusters,
            key=lambda x: (x['size'], x['average_probability']),
            reverse=True
        )[:max_clusters]
        
        return sorted_clusters
        
    except Exception as e:
        logger.error(f"Error getting arc clusters: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/arcs/by-id/{arc_id}", response_model=NarrativeArcResponse)
async def get_arc_by_id(arc_id: str):
    """Get a single arc by ID with all its details."""
    try:
        with db_manager.session_scope() as session:
            arc_repository = NarrativeArcRepository(session)
            arc = arc_repository.get_by_id(arc_id)
            
            if not arc:
                raise HTTPException(status_code=404, detail=f"Arc with ID {arc_id} not found")
            
            # Ensure the arc is fully loaded with its relationships
            session.refresh(arc, ['main_characters', 'progressions'])
            
            # Normalize season/episode format in progressions
            for prog in arc.progressions:
                normalized_season, normalized_episode = normalize_season_episode(prog.season, prog.episode)
                prog.season = normalized_season
                prog.episode = normalized_episode
            
            # Create response using the model
            response = NarrativeArcResponse.from_arc(arc)
            logger.info(f"Retrieved arc '{arc.title}' with {len(arc.progressions)} progressions")
            return response
            
    except Exception as e:
        logger.error(f"Error getting arc by ID {arc_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/progressions/generate")
async def generate_progression(
    series: str = Query(...),
    season: str = Query(...),
    episode: str = Query(...),
    data: dict = Body(...)
):
    """Generate progression content for an arc in a specific episode."""
    try:
        logger.info(f"Generating progression for series: {series}, S{season}E{episode}")
        logger.info(f"Request data: {data}")
        
        with db_manager.session_scope() as session:
            arc_repository = NarrativeArcRepository(session)
            progression_repository = ArcProgressionRepository(session)
            character_repository = CharacterRepository(session)
            character_service = CharacterService(character_repository)
            llm_service = LLMService()

            # Get arc details
            arc = None
            arc_title = None
            arc_description = None
            arc_id = None
            
            if data.get('arc_id'):
                arc = arc_repository.get_by_id(data['arc_id'])
                if arc:
                    arc_title = arc.title
                    arc_description = arc.description
                    arc_id = arc.id
                    logger.info(f"Found arc by ID: {arc.title}")
            else:
                arc_title = data.get('arc_title')
                arc_description = data.get('arc_description')
                logger.info(f"Using provided arc title: {arc_title}")

            if not arc_title or not arc_description:
                logger.error("Missing required arc information")
                return {
                    "content": "",
                    "interfering_characters": []
                }

            # Get episode plot path and generate content
            path_handler = PathHandler(series, season, episode)
            episode_plot_path = path_handler.get_entity_normalized_plot_file_path()
            
            logger.info(f"Generating content using plot file: {episode_plot_path}")
            content = llm_service.generate_progression_content(
                arc_title=arc_title,
                arc_description=arc_description,
                episode_plot_path=episode_plot_path
            )
            
            # If content is NO_PROGRESSION and we have an arc, delete any existing progression
            if content == "NO_PROGRESSION" and arc and data.get('delete_existing', False):
                existing_progression = progression_repository.get_single(
                    arc_id=arc.id,
                    series=series,
                    season=season,
                    episode=episode
                )
                if existing_progression:
                    logger.info(f"Deleting existing progression for S{season}E{episode} due to NO_PROGRESSION")
                    progression_repository.delete(existing_progression.id)

                return {
                    "content": "NO_PROGRESSION",
                    "interfering_characters": []
                }

            # If we have valid content, process it
            if content != "NO_PROGRESSION":
                # Get all characters for the series
                all_characters = character_repository.get_by_series(series)
                
                # Find mentioned characters in the content
                mentioned_appellations = []
                for character in all_characters:
                    for appellation in character.appellations:
                        if appellation.appellation in content:
                            mentioned_appellations.append(character.best_appellation)
                            break  # Only add each character once

                logger.info(f"Found interfering characters: {mentioned_appellations}")
                return {
                    "content": content,
                    "interfering_characters": mentioned_appellations
                }

    except Exception as e:
        logger.error(f"Error generating progression: {str(e)}")
        logger.exception("Full error details:")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/arcs/{arc_id}", response_model=NarrativeArcResponse)
async def get_arc_by_id(arc_id: str):
    """Get a single arc by ID with all its details."""
    try:
        with db_manager.session_scope() as session:
            arc_repository = NarrativeArcRepository(session)
            arc = arc_repository.get_by_id(arc_id)
            
            if not arc:
                raise HTTPException(status_code=404, detail=f"Arc with ID {arc_id} not found")
            
            # Ensure the arc is fully loaded with its relationships
            session.refresh(arc, ['main_characters', 'progressions'])
            
            # Normalize season/episode format in progressions
            for prog in arc.progressions:
                normalized_season, normalized_episode = normalize_season_episode(prog.season, prog.episode)
                prog.season = normalized_season
                prog.episode = normalized_episode
            
            # Create response using the model
            response = NarrativeArcResponse.from_arc(arc)
            logger.info(f"Retrieved arc '{arc.title}' with {len(arc.progressions)} progressions")
            return response
            
    except Exception as e:
        logger.error(f"Error getting arc by ID {arc_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))