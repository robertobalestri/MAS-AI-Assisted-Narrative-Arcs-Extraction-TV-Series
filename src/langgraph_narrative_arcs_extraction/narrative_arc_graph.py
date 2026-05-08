# narrative_arc_graph.py

import asyncio
from typing import Dict, List, TypedDict
from langgraph.graph import StateGraph, END
import os
import json
from datetime import datetime
from pathlib import Path

from src.utils.llm_utils import clean_llm_json_response
from src.utils.logger_utils import setup_logging
from src.utils.text_utils import load_text, save_json
from src.ai_models.ai_models import get_llm, LLMType
from src.plot_processing.plot_ner_entity_extraction import EntityLink, normalize_names
# Import the new repositories and models
from src.narrative_storage_management.repositories import (
    DatabaseSessionManager,
    NarrativeArcRepository,
)
from src.narrative_storage_management.narrative_models import NarrativeArc, ArcProgression
import logging

logger = setup_logging(__name__)
llm = get_llm(LLMType.INTELLIGENT)
cheap_llm = get_llm(LLMType.CHEAP)
from pydantic import BaseModel, Field

# Define your prompts and guidelines (ensure these are defined in your code)
from .prompts import (
     EXTRACTOR_OUTPUT_JSON_FORMAT,
     PRESENT_SEASON_ARCS_IDENTIFIER_PROMPT,
     ARC_VERIFIER_PROMPT,
     NARRATIVE_ARC_GUIDELINES,
     ARC_PROGRESSION_VERIFIER_PROMPT,
     DETAILED_OUTPUT_JSON_FORMAT,
     CHARACTER_VERIFIER_PROMPT,
     ARC_DEDUPLICATOR_PROMPT,
     ANTHOLOGY_ARC_EXTRACTOR_PROMPT,
     ARC_ENHANCER_PROMPT,
     BRIEF_OUTPUT_JSON_FORMAT,
     PRESENT_SEASON_ARCS_OUTPUT_JSON_FORMAT,
     SOAP_AND_GENRE_ARC_EXTRACTOR_PROMPT,
     SEASONAL_ARC_OPTIMIZER_PROMPT
 )

class IntermediateNarrativeArc(BaseModel):
    """Model representing an intermediate narrative arc during extraction process."""
    title: str = Field(..., description="The title of the narrative arc")
    arc_type: str = Field(..., description="Type of the arc such as 'Soap Arc'/'Genre-Specific Arc'/'Anthology Arc'")
    description: str = Field(..., description="A brief description of the narrative arc")
    main_characters: str = Field(..., description="Main characters involved in this arc")
    interfering_episode_characters: str = Field(..., description="Interfering characters involved in this arc")
    single_episode_progression_string: str = Field("", description="The progression of the arc for the current episode")

    class Config:
        populate_by_name = True

class NarrativeArcsExtractionState(TypedDict):
    """State representation for the narrative analysis process."""
    soap_arcs: List[IntermediateNarrativeArc]
    genre_arcs: List[IntermediateNarrativeArc]
    anthology_arcs: List[IntermediateNarrativeArc]
    episode_arcs: List[IntermediateNarrativeArc]
    present_season_arcs: List[Dict]
    season_arcs: List[Dict]  # Added to store serialized season arcs
    file_paths: Dict[str, str]
    series: str
    season: str
    episode: str
    existing_season_entities: List[EntityLink]
    episode_plot: str
    season_plot: str
    optimized_arcs: List[IntermediateNarrativeArc]

class ExtractedArcBase(BaseModel):
    """Basic model for initially extracted arcs before enhancement."""
    title: str = Field(..., description="The title of the narrative arc")
    description: str = Field(..., description="A brief description of the narrative arc")
    arc_type: str = Field(..., description="Type of the arc")

async def process_with_semaphore(items, process_func, max_concurrent=5):
    """Helper function to process a list of items concurrently with a semaphore."""
    semaphore = asyncio.Semaphore(max_concurrent)
    async def sem_task(item):
        async with semaphore:
            return await process_func(item)
    return await asyncio.gather(*(sem_task(item) for item in items), return_exceptions=True)

def initialize_state(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Initialize the state by loading necessary data from files."""
    logger.info("Initializing state with data from files.")


    # Load existing season entities
    if os.path.exists(state['file_paths']['season_entities_path']):
        with open(state['file_paths']['season_entities_path'], 'r') as f:
            season_entities_data = json.load(f)
            state['existing_season_entities'] = [EntityLink(**entity) for entity in season_entities_data]

    if os.path.exists(state['file_paths']['episode_plot_path']):
        state['episode_plot'] = load_text(state['file_paths']['episode_plot_path'])


    if os.path.exists(state['file_paths']['season_plot_path']):
        state['season_plot'] = load_text(state['file_paths']['season_plot_path'])

    if os.path.exists(state['file_paths']['suggested_episode_arc_path']):
        state['suggested_episode_arc'] = load_text(state['file_paths']['suggested_episode_arc_path'])

    logger.info(f"Loaded {len(state['existing_season_entities'])} existing entities from season file.")

    return state

def log_agent_output(agent_name: str, output_data: dict, log_dir: str = "agent_logs") -> None:
    """Log agent output to a file with timestamp."""
    # Create logs directory if it doesn't exist
    log_dir_path = Path(log_dir)
    log_dir_path.mkdir(parents=True, exist_ok=True)
    
    # Create a timestamp for the current run if it doesn't exist
    timestamp_file = log_dir_path / "current_run_timestamp.txt"
    if not timestamp_file.exists():
        current_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamp_file.write_text(current_timestamp)
    else:
        current_timestamp = timestamp_file.read_text().strip()
    
    # Create log file path
    log_file = log_dir_path / f"run_{current_timestamp}.jsonl"
    
    # Prepare log entry with proper formatting
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "agent": agent_name,
        "output": output_data
    }
    
    # Format the JSON with proper indentation and ensure_ascii=False for proper character handling
    formatted_json = json.dumps(
        log_entry,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        default=str  # Handles any non-serializable objects
    )
    
    # Add a newline after each formatted JSON entry
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(formatted_json + "\n\n")  # Add extra newline for better readability
    
    logger.info(f"Logged output from {agent_name}")

async def identify_present_season_arcs(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Identify which existing season arcs are clearly present in the current episode."""
    logger.info("Identifying present season arcs in the episode.")

    # Initialize the database session manager and repositories
    db_manager = DatabaseSessionManager()
    serialized_season_arcs = []

    try:
        with db_manager.session_scope() as session:
            # Initialize repositories
            arc_repository = NarrativeArcRepository(session)

            # Get all narrative arcs for the series
            season_arcs = arc_repository.get_all(series=state['series'])

            # Filter arcs that have progressions in the current season
            filtered_arcs = []
            for arc in season_arcs:
                progressions_in_season = [prog for prog in arc.progressions if prog.season == state['season']]
                if progressions_in_season:
                    arc.progressions = progressions_in_season
                    filtered_arcs.append(arc)

            state['season_arcs'] = [arc.dict() for arc in filtered_arcs]
            logger.info(f"Retrieved {len(filtered_arcs)} arcs for {state['series']} season {state['season']}.")

    except Exception as e:
        logger.error(f"Error managing season arcs: {e}")
        state['season_arcs'] = []
        return state

    if not state['season_arcs']:
        logger.warning("No existing season arcs found. Skipping present season arcs identification.")
        state['present_season_arcs'] = []
        return state

    async def _process_arc(arc):
        if arc['arc_type'] == "Anthology Arc":
            return None
        response = await llm.ainvoke(PRESENT_SEASON_ARCS_IDENTIFIER_PROMPT.format_messages(
            episode_plot=state['episode_plot'],
            arc_title=arc['title'],
            arc_description=arc['description']
        ))
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

    results = await process_with_semaphore(state['season_arcs'], _process_arc, max_concurrent=5)

    present_arcs = []
    for arc, result in zip(state['season_arcs'], results):
        if isinstance(result, Exception):
            logger.error(f"Error processing arc '{arc['title']}': {result}")
        elif result is not None:
            present_arcs.append(result)
            logger.warning(f"Arc '{arc['title']}' identified as present in episode.")
        else:
            if arc['arc_type'] != "Anthology Arc":
                logger.info(f"Arc '{arc['title']}' not present in episode.")

    state['present_season_arcs'] = present_arcs
    logger.info(f"Identified {len(present_arcs)} season arcs present in the episode.")

    # Add logging before returning
    log_agent_output("identify_present_season_arcs", {
        "present_season_arcs": state['present_season_arcs'],
        "season_arcs": state['season_arcs']
    })
    
    return state

async def extract_anthology_arcs(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Extract self-contained anthology arcs from the episode plot."""
    logger.info("Extracting anthology arcs.")

    response = await llm.ainvoke(ANTHOLOGY_ARC_EXTRACTOR_PROMPT.format_messages(
        episode_plot=state['episode_plot'],
        season_plot=state['season_plot'],
        output_json_format=BRIEF_OUTPUT_JSON_FORMAT,
    ))

    try:
        arcs_data = clean_llm_json_response(response.content)
        arcs = []
        for arc in arcs_data:
            new_arc = ExtractedArcBase(
                title=arc['title'],
                description=arc['description'],
                arc_type="Anthology Arc"
            )
            arcs.append(new_arc)
        state['anthology_arcs'] = arcs
        logger.info(f"Extracted {len(arcs)} anthology arcs.")
    except Exception as e:
        logger.error(f"Error extracting anthology arcs: {e}")
        state['anthology_arcs'] = []

    # Add logging before returning
    log_agent_output("extract_anthology_arcs", {
        "anthology_arcs": [arc.model_dump() for arc in state['anthology_arcs']]
    })
    
    return state

async def extract_soap_and_genre_arcs(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Extract both soap and genre-specific arcs from the episode plot."""
    logger.info("Extracting soap and genre-specific arcs.")

    response = await llm.ainvoke(SOAP_AND_GENRE_ARC_EXTRACTOR_PROMPT.format_messages(
        episode_plot=state['episode_plot'],
        present_season_arcs_summaries=json.dumps(state['present_season_arcs'], indent=2),
        anthology_arcs=json.dumps([arc.model_dump() for arc in state['anthology_arcs']], indent=2),
        output_json_format=EXTRACTOR_OUTPUT_JSON_FORMAT
    ))

    try:
        arcs_data = clean_llm_json_response(response.content)
        soap_arcs = []
        genre_arcs = []
        
        for arc in arcs_data:
            new_arc = ExtractedArcBase(
                title=arc['title'],
                description=arc['description'],
                arc_type=arc['arc_type']
            )
            if arc['arc_type'] == "Soap Arc":
                soap_arcs.append(new_arc)
            else:  # Genre-Specific Arc
                genre_arcs.append(new_arc)
                
        state['soap_arcs'] = soap_arcs
        state['genre_arcs'] = genre_arcs
        logger.info(f"Extracted {len(soap_arcs)} soap arcs and {len(genre_arcs)} genre-specific arcs.")
    except Exception as e:
        logger.error(f"Error extracting soap and genre arcs: {e}")
        state['soap_arcs'] = []
        state['genre_arcs'] = []

    # Add logging before returning
    log_agent_output("extract_soap_and_genre_arcs", {
        "soap_arcs": [arc.model_dump() for arc in state['soap_arcs']],
        "genre_arcs": [arc.model_dump() for arc in state['genre_arcs']]
    })
    
    return state

async def verify_arc_progression(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Verify and adjust the progression and description of each arc."""
    logger.info("Verifying arc progressions.")

    async def _process_arc(arc):
        response = await llm.ainvoke(ARC_PROGRESSION_VERIFIER_PROMPT.format_messages(
            episode_plot=state['episode_plot'],
            arc_to_verify=arc.model_dump(),
            output_json_format=DETAILED_OUTPUT_JSON_FORMAT
        ))
        verified_arc_data = clean_llm_json_response(response.content)
        if isinstance(verified_arc_data, list):
            verified_arc_data = verified_arc_data[0]
        return IntermediateNarrativeArc(
            title=verified_arc_data['title'],
            arc_type=verified_arc_data['arc_type'],
            description=verified_arc_data['description'],
            main_characters=verified_arc_data.get('main_characters', ''),
            interfering_episode_characters=verified_arc_data.get('interfering_episode_characters', ''),
            single_episode_progression_string=verified_arc_data['single_episode_progression_string']
        )

    results = await process_with_semaphore(state['episode_arcs'], _process_arc, max_concurrent=5)

    verified_arcs = []
    for arc, result in zip(state['episode_arcs'], results):
        if isinstance(result, Exception):
            logger.error(f"Error verifying arc progression: {result}")
            verified_arcs.append(arc)
        else:
            verified_arcs.append(result)

    state['episode_arcs'] = verified_arcs
    logger.info(f"Verified progressions for {len(verified_arcs)} arcs.")

    # Add logging before returning
    log_agent_output("verify_arc_progression", {
        "verified_arcs": [arc.model_dump() for arc in state['episode_arcs']]
    })
    
    return state

async def verify_character_roles(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Verify and correctly categorize characters as either main or interfering for each arc."""
    logger.info("Verifying character roles in arcs.")

    async def _process_arc(arc):
        response = await llm.ainvoke(CHARACTER_VERIFIER_PROMPT.format_messages(
            episode_plot=state['episode_plot'],
            arc_to_verify=arc.model_dump(),
            output_json_format=DETAILED_OUTPUT_JSON_FORMAT
        ))
        verified_arc_data = clean_llm_json_response(response.content)
        if isinstance(verified_arc_data, list):
            verified_arc_data = verified_arc_data[0]
        return IntermediateNarrativeArc(
            title=verified_arc_data['title'],
            arc_type=verified_arc_data['arc_type'],
            description=verified_arc_data['description'],
            main_characters=verified_arc_data['main_characters'],
            interfering_episode_characters=verified_arc_data['interfering_episode_characters'],
            single_episode_progression_string=verified_arc_data['single_episode_progression_string']
        )

    results = await process_with_semaphore(state['episode_arcs'], _process_arc, max_concurrent=5)

    verified_arcs = []
    for arc, result in zip(state['episode_arcs'], results):
        if isinstance(result, Exception):
            logger.error(f"Error verifying character roles: {result}")
            verified_arcs.append(arc)
        else:
            verified_arcs.append(result)

    state['episode_arcs'] = verified_arcs
    logger.info(f"Verified character roles for {len(verified_arcs)} arcs.")

    # Add logging before returning
    log_agent_output("verify_character_roles", {
        "verified_arcs": [arc.model_dump() for arc in state['episode_arcs']]
    })
    
    return state

async def deduplicate_arcs(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Deduplicate and merge similar arcs from different extraction methods."""
    logger.info("Deduplicating and merging similar arcs from different extraction methods.")

    # Separate anthology arcs
    non_anthology_arcs = [arc for arc in state['optimized_arcs'] if arc.arc_type != "Anthology Arc"]
    anthology_arcs = [arc for arc in state['optimized_arcs'] if arc.arc_type == "Anthology Arc"]

    response = await llm.ainvoke(ARC_DEDUPLICATOR_PROMPT.format_messages(
        episode_plot=state['episode_plot'],
        arcs_to_deduplicate=[arc.model_dump() for arc in non_anthology_arcs],
        anthology_arcs=[arc.model_dump() for arc in anthology_arcs],  # Added anthology arcs as context
        guidelines=NARRATIVE_ARC_GUIDELINES,
        output_json_format=EXTRACTOR_OUTPUT_JSON_FORMAT
    ))

    try:
        deduplicated_arcs_data = clean_llm_json_response(response.content)
        deduplicated_arcs = []
        for arc in deduplicated_arcs_data:
            new_arc = ExtractedArcBase(
                title=arc['title'],
                arc_type=arc['arc_type'],
                description=arc['description']
            )
            deduplicated_arcs.append(new_arc)
        
        # Combine anthology arcs with deduplicated arcs
        state['episode_arcs'] = anthology_arcs + deduplicated_arcs
        logger.info(f"Deduplicated to {len(deduplicated_arcs)} unique arcs + {len(anthology_arcs)} anthology arcs.")
    except Exception as e:
        logger.error(f"Error deduplicating arcs: {e}")
        state['episode_arcs'] = anthology_arcs + non_anthology_arcs

    # Add logging before returning
    log_agent_output("deduplicate_arcs", {
        "deduplicated_arcs": [arc.model_dump() for arc in state['episode_arcs']],
        "anthology_arcs_count": len(anthology_arcs),
        "other_arcs_count": len(deduplicated_arcs)
    })
    
    return state

async def enhance_arc_details(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Enhance deduplicated arcs with additional details."""
    logger.info("Enhancing arcs with additional details.")

    async def _process_arc(arc):
        response = await llm.ainvoke(ARC_ENHANCER_PROMPT.format_messages(
            episode_plot=state['episode_plot'],
            arc_to_enhance=arc.model_dump(),
            guidelines=NARRATIVE_ARC_GUIDELINES,
            output_json_format=DETAILED_OUTPUT_JSON_FORMAT
        ))
        enhanced_arc_data = clean_llm_json_response(response.content)
        if isinstance(enhanced_arc_data, list):
            enhanced_arc_data = enhanced_arc_data[0]
        return IntermediateNarrativeArc(
            title=arc.title,
            arc_type=arc.arc_type,
            description=arc.description,
            main_characters=enhanced_arc_data['main_characters'],
            interfering_episode_characters=enhanced_arc_data['interfering_episode_characters'],
            single_episode_progression_string=enhanced_arc_data['single_episode_progression_string']
        )

    results = await process_with_semaphore(state['episode_arcs'], _process_arc, max_concurrent=5)

    enhanced_arcs = []
    for arc, result in zip(state['episode_arcs'], results):
        if isinstance(result, Exception):
            logger.error(f"Error enhancing arc details: {result}")
            enhanced_arcs.append(IntermediateNarrativeArc(
                title=arc.title,
                arc_type=arc.arc_type,
                description=arc.description,
                main_characters="",
                interfering_episode_characters="",
                single_episode_progression_string=""
            ))
        else:
            enhanced_arcs.append(result)

    state['episode_arcs'] = enhanced_arcs
    logger.info(f"Enhanced {len(enhanced_arcs)} arcs with additional details.")

    # Add logging before returning
    log_agent_output("enhance_arc_details", {
        "enhanced_arcs": [arc.model_dump() for arc in state['episode_arcs']]
    })
    
    return state

async def verify_arcs(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Verify the arcs to ensure they are consistent with the episode plot and present season arcs."""
    logger.info("Verifying arcs.")

    response = await llm.ainvoke(ARC_VERIFIER_PROMPT.format_messages(
        episode_plot=state['episode_plot'],
        season_plot=state['season_plot'],
        arcs_to_verify=json.dumps([arc.model_dump() for arc in state['episode_arcs']], indent=2),
        present_season_arcs_summaries=json.dumps(state['present_season_arcs'], indent=2), 
        guidelines=NARRATIVE_ARC_GUIDELINES,
        output_json_format=DETAILED_OUTPUT_JSON_FORMAT
    ))

    try:
        verified_arcs_data = clean_llm_json_response(response.content)
        verified_arcs = []
        
        for arc_data in verified_arcs_data:
            try:
                # Ensure all required fields are present with defaults if missing
                new_arc = IntermediateNarrativeArc(
                    title=arc_data['title'],
                    arc_type=arc_data['arc_type'],
                    description=arc_data['description'],
                    main_characters=arc_data.get('main_characters', ''),
                    interfering_episode_characters=arc_data.get('interfering_episode_characters', ''),
                    single_episode_progression_string=arc_data.get('single_episode_progression_string', '')
                )
                verified_arcs.append(new_arc)
            except Exception as e:
                logger.error(f"Error processing verified arc: {e}")
                logger.error(f"Problematic arc data: {arc_data}")
                continue

        if verified_arcs:
            state['episode_arcs'] = verified_arcs
            logger.info(f"Successfully verified {len(verified_arcs)} arcs.")
        else:
            logger.warning("No arcs were successfully verified. Keeping original arcs.")
            
    except Exception as e:
        logger.error(f"Error during arc verification: {e}")
        # Keep original arcs if verification completely fails
        logger.warning("Verification failed. Keeping original arcs.")

    # Add logging before returning
    log_agent_output("verify_arcs", {
        "final_verified_arcs": [arc.model_dump() for arc in state['episode_arcs']]
    })
    
    return state

async def optimize_arcs_with_season_context(state: NarrativeArcsExtractionState) -> NarrativeArcsExtractionState:
    """Optimize arc titles and descriptions based on seasonal context and merge related arcs."""
    logger.info("Starting seasonal arc optimization.")

    # Combine soap and genre arcs for optimization
    arcs_to_optimize = state['soap_arcs'] + state['genre_arcs']

    if not arcs_to_optimize:
        logger.info("No arcs to optimize.")
        return state

    response = await llm.ainvoke(SEASONAL_ARC_OPTIMIZER_PROMPT.format_messages(
        season_plot=state['season_plot'],
        present_season_arcs=json.dumps(state['present_season_arcs'], indent=2),
        new_arcs=json.dumps([arc.model_dump() for arc in arcs_to_optimize], indent=2),
        output_json_format=EXTRACTOR_OUTPUT_JSON_FORMAT
    ))

    try:
        optimized_arcs_data = clean_llm_json_response(response.content)
        optimized_arcs = []
        
        for arc_data in optimized_arcs_data:
            optimized_arc = ExtractedArcBase(
                title=arc_data['title'],
                arc_type=arc_data['arc_type'],
                description=arc_data['description']
            )
            optimized_arcs.append(optimized_arc)

        # Store optimized arcs in episode_arcs along with anthology arcs
        state['optimized_arcs'] = state['anthology_arcs'] + optimized_arcs
        logger.info(f"Optimized arcs into {len(optimized_arcs)} arcs + {len(state['anthology_arcs'])} anthology arcs.")
        
    except Exception as e:
        logger.error(f"Error during arc optimization: {e}")
        # If optimization fails, use original arcs along with anthology arcs
        state['optimized_arcs'] = state['anthology_arcs'] + arcs_to_optimize
        
    # Add logging before returning
    log_agent_output("optimize_arcs", {
        "optimized_arcs": [arc.model_dump() for arc in state['optimized_arcs']]
    })
    
    return state

def create_narrative_arc_graph():
    """Create and configure the state graph for narrative arc extraction."""
    workflow = StateGraph(NarrativeArcsExtractionState)

    # Add nodes
    workflow.add_node("initialize_state_node", initialize_state)
    workflow.add_node("identify_present_season_arcs_node", identify_present_season_arcs)
    workflow.add_node("extract_anthology_arcs_node", extract_anthology_arcs)
    workflow.add_node("extract_soap_and_genre_arcs_node", extract_soap_and_genre_arcs)
    workflow.add_node("optimize_arcs_node", optimize_arcs_with_season_context)
    workflow.add_node("deduplicate_arcs_node", deduplicate_arcs)
    workflow.add_node("enhance_arc_details_node", enhance_arc_details)
    workflow.add_node("verify_arc_progression_node", verify_arc_progression)
    workflow.add_node("verify_character_roles_node", verify_character_roles)
    workflow.add_node("verify_arcs_node", verify_arcs)

    # Set up the workflow
    workflow.set_entry_point("initialize_state_node")
    workflow.add_edge("initialize_state_node", "identify_present_season_arcs_node")
    workflow.add_edge("identify_present_season_arcs_node", "extract_anthology_arcs_node")
    workflow.add_edge("extract_anthology_arcs_node", "extract_soap_and_genre_arcs_node")
    workflow.add_edge("extract_soap_and_genre_arcs_node", "optimize_arcs_node")
    workflow.add_edge("optimize_arcs_node", "deduplicate_arcs_node")
    workflow.add_edge("deduplicate_arcs_node", "enhance_arc_details_node")
    workflow.add_edge("enhance_arc_details_node", "verify_arc_progression_node")
    workflow.add_edge("verify_arc_progression_node", "verify_character_roles_node")
    workflow.add_edge("verify_character_roles_node", "verify_arcs_node")
    workflow.add_edge("verify_arcs_node", END)

    return workflow.compile()

async def extract_narrative_arcs(file_paths: Dict[str, str], series: str, season: str, episode: str):
    """
    Entry point for extracting narrative arcs using LangGraph.
    """
    logger.info("Starting extract_narrative_arcs function")
    # Create a unique timestamp for this run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = Path("agent_logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "current_run_timestamp.txt").write_text(timestamp)
    
    graph = create_narrative_arc_graph()

    initial_state = NarrativeArcsExtractionState(
        soap_arcs=[],
        genre_arcs=[],
        anthology_arcs=[],
        episode_arcs=[],
        present_season_arcs=[],
        season_arcs=[],  # Initialize season_arcs
        file_paths=file_paths,
        series=series,
        season=season,
        episode=episode,
        existing_season_entities=[],
        episode_plot="",
        season_plot="",
        optimized_arcs=[]
    )
    logger.info("Invoking the graph")
    result = await graph.ainvoke(initial_state)
    logger.info("Graph execution completed")

    # Save the results to a JSON file
    suggested_arcs = [arc.dict() for arc in result['episode_arcs']]

    save_json(suggested_arcs, file_paths['suggested_episode_arc_path'])

    logger.info(f"Suggested episode arcs saved to {file_paths['suggested_episode_arc_path']}")
