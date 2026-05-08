# repositories.py

from typing import List, Optional, Dict
from sqlmodel import SQLModel, Session, select
from sqlalchemy.orm import selectinload
from src.narrative_storage_management.narrative_models import NarrativeArc, ArcProgression, Character, CharacterAppellation
from contextlib import contextmanager
import os
from sqlmodel import create_engine
from sqlalchemy import func, UniqueConstraint
from sqlalchemy.exc import IntegrityError

from src.utils.logger_utils import setup_logging
logger = setup_logging(__name__)

class DatabaseSessionManager:
    """Manages the database session."""

    def __init__(self, db_url: str = None):
        if db_url is None:
            db_path = os.getenv("DATABASE_NAME", "narrative_db.sqlite")
            db_url = f'sqlite:///{db_path}'
            # Ensure the directory for the SQLite database exists
            db_dir = os.path.dirname(db_path)
            if db_dir:
                os.makedirs(db_dir, exist_ok=True)

        self.engine = create_engine(
            db_url,
            echo=False,
            connect_args={"timeout": 60},
            pool_size=5,
            max_overflow=10
        )
        self.create_tables()

    def create_tables(self):
        """Create database tables if they don't exist."""
        SQLModel.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        """Get a new session."""
        return Session(self.engine)

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Session rollback due to exception: {e}")
            raise
        finally:
            session.close()

class BaseRepository:
    """Base repository class with session management."""
    def __init__(self, session: Session):
        self.session = session

class NarrativeArcRepository(BaseRepository):
    """Repository for NarrativeArc operations."""

    def add_or_update(self, arc: NarrativeArc):
        existing_arc = self.session.get(NarrativeArc, arc.id)
        if existing_arc:
            existing_arc.title = arc.title
            existing_arc.description = arc.description
            existing_arc.arc_type = arc.arc_type
            existing_arc.series = arc.series
            logger.info(f"Updated NarrativeArc: {arc.title}")
        else:
            self.session.add(arc)
            logger.info(f"Added new NarrativeArc: {arc.title}")

    def update_fields(self, arc: NarrativeArc, updated_fields: Dict):
        """Update specific fields of the arc."""
        for field, value in updated_fields.items():
            if hasattr(arc, field):
                setattr(arc, field, value)
                logger.debug(f"Set {field} to {value} for arc ID {arc.id}")
            else:
                logger.warning(f"Field '{field}' does not exist on NarrativeArc.")
        self.session.add(arc)  # SQLAlchemy tracks changes

    def get_by_id(self, arc_id: str) -> Optional[NarrativeArc]:
        arc = self.session.get(NarrativeArc, arc_id)
        if arc:
            self.session.refresh(arc, ['main_characters', 'progressions'])
        return arc

    def get_by_title(self, title: str, series: str) -> Optional[NarrativeArc]:
        """Get a narrative arc by its exact title, case-insensitive."""
        return self.session.query(NarrativeArc)\
            .filter(func.lower(NarrativeArc.title) == title.lower())\
            .filter(NarrativeArc.series == series)\
            .first()

    def get_all(self, series: Optional[str] = None) -> List[NarrativeArc]:
        query = select(NarrativeArc).options(
            selectinload(NarrativeArc.main_characters),
            selectinload(NarrativeArc.progressions)
        )
        if series:
            query = query.where(NarrativeArc.series == series)
        return self.session.exec(query).all()

    def delete(self, arc_id: str):
        """Delete a narrative arc and its progressions."""
        arc = self.session.get(NarrativeArc, arc_id)
        if arc:
            self.session.delete(arc)
            logger.info(f"Deleted NarrativeArc: {arc.title}")

class ArcProgressionRepository(BaseRepository):
    """Repository for ArcProgression operations."""

    def add_or_update(self, progression: ArcProgression):
        existing_progression = self.session.exec(
            select(ArcProgression).where(
                ArcProgression.main_arc_id == progression.main_arc_id,
                ArcProgression.series == progression.series,
                ArcProgression.season == progression.season,
                ArcProgression.episode == progression.episode
            )
        ).first()

        if existing_progression:
            existing_progression.content = progression.content
            existing_progression.ordinal_position = progression.ordinal_position
            logger.info(f"Updated ArcProgression in S{progression.season}E{progression.episode}")
        else:
            self.session.add(progression)
            logger.info(f"Added new ArcProgression in S{progression.season}E{progression.episode}")

    def get_by_arc_id(self, arc_id: str) -> List[ArcProgression]:
        query = select(ArcProgression).where(
            ArcProgression.main_arc_id == arc_id
        ).options(
            selectinload(ArcProgression.narrative_arc),
            selectinload(ArcProgression.interfering_characters)
        )
        return self.session.exec(query).all()

    def get_single(self, arc_id: str, series: str, season: str, episode: str) -> Optional[ArcProgression]:
        query = select(ArcProgression).where(
            ArcProgression.main_arc_id == arc_id,
            ArcProgression.series == series,
            ArcProgression.season == season,
            ArcProgression.episode == episode
        ).options(
            selectinload(ArcProgression.interfering_characters)
        )
        return self.session.exec(query).first()

    def get_by_id(self, progression_id: str) -> Optional[ArcProgression]:
        """Get a progression by its ID."""
        return self.session.get(ArcProgression, progression_id)

    def delete(self, progression_id: str):
        """Delete a progression."""
        progression = self.session.get(ArcProgression, progression_id)
        if progression:
            self.session.delete(progression)
            logger.info(f"Deleted progression {progression_id}")

class CharacterRepository(BaseRepository):
    """Repository for Character operations."""

    def get_by_entity_name(self, entity_name: str, series: str) -> Optional[Character]:
        """Get a character by entity_name and series."""
        query = select(Character).where(
            Character.entity_name == entity_name,
            Character.series == series
        ).options(
            selectinload(Character.appellations),
            selectinload(Character.main_narrative_arcs),
            selectinload(Character.interfering_progressions)
        )
        return self.session.exec(query).first()

    def get_by_appellations(self, appellations: List[str], series: str) -> List[Character]:
        """Get characters by matching their appellations."""
        if not appellations:
            return []

        query = select(Character).join(CharacterAppellation).where(
            Character.series == series,
            CharacterAppellation.appellation.in_(appellations)
        ).options(
            selectinload(Character.appellations),
            selectinload(Character.main_narrative_arcs),
            selectinload(Character.interfering_progressions)
        ).distinct()

        return self.session.exec(query).all()

    def get_character_by_appellation(self, appellation: str, series: str) -> Optional[Character]:
        """Get a character by an appellation and series."""
        query = select(Character).join(CharacterAppellation).where(
            Character.series == series,
            CharacterAppellation.appellation == appellation
        ).options(
            selectinload(Character.appellations)
        )
        return self.session.exec(query).first()

    def add(self, character: Character):
        """Add a new character to the database."""
        self.session.add(character)
        self.session.flush()  # Ensure the character is persisted

    def update(self, character: Character):
        """Update an existing character in the database."""
        self.session.add(character)  # Add or update the character
        self.session.flush()

    def get_by_series(self, series: str) -> List[Character]:
        """Get all characters for a series."""
        query = select(Character).where(Character.series == series).options(
            selectinload(Character.appellations)
        )
        return self.session.exec(query).all()

    def delete(self, character: Character):
        """Delete a character from the database."""
        try:
            # Delete all appellations first
            for appellation in character.appellations:
                self.session.delete(appellation)
            
            # Remove character from all arcs and progressions
            for arc in character.main_narrative_arcs:
                arc.main_characters.remove(character)
            
            for progression in character.interfering_progressions:
                progression.interfering_characters.remove(character)
            
            # Finally delete the character
            self.session.delete(character)
            self.session.flush()
            logger.info(f"Successfully deleted character {character.entity_name}")
        except Exception as e:
            logger.error(f"Error deleting character {character.entity_name}: {e}")
            raise