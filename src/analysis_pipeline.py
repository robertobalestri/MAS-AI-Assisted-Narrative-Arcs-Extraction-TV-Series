import asyncio
import json
import os
import threading

from dotenv import load_dotenv

from src.ai_models.ai_models import LLMType, get_llm
from src.langgraph_narrative_arcs_extraction.narrative_arc_graph import extract_narrative_arcs
from src.path_handler import PathHandler
from src.plot_processing.plot_ner_entity_extraction import (
    extract_and_refine_entities,
    normalize_entities_names_to_best_appellation,
    substitute_appellations_with_names,
)
from src.plot_processing.plot_processing_models import EntityLink
from src.plot_processing.plot_semantic_processing import semantic_split
from src.plot_processing.plot_summarizing import create_season_summary
from src.plot_processing.plot_text_processing import replace_pronouns_with_names
from src.plot_processing.process_suggested_arcs import process_suggested_arcs
from src.utils.logger_utils import setup_logging
from src.utils.text_utils import clean_text, load_text

load_dotenv(override=True)
logger = setup_logging(__name__)


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result = {}
    error = {}

    def runner():
        try:
            result["value"] = asyncio.run(coro)
        except Exception as exc:
            error["value"] = exc

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()

    if "value" in error:
        raise error["value"]
    return result.get("value")


def process_text(path_handler: PathHandler) -> None:
    series = path_handler.series
    season = path_handler.season
    episode = path_handler.episode
    try:
        logger.info("Initializing language models.")
        llm_intelligent = get_llm(LLMType.INTELLIGENT)
        llm_cheap = get_llm(LLMType.CHEAP)

        season_plot_path = path_handler.get_season_plot_file_path()
        if not os.path.exists(season_plot_path):
            logger.info("Season summary not found. Creating season summary from episode plots.")
            episode_folders = PathHandler.list_episode_folders(
                path_handler.base_dir,
                path_handler.series,
                path_handler.season,
            )
            episode_plots = []
            for ep_folder in episode_folders:
                ep_plot_path = PathHandler.get_episode_plot_path(
                    path_handler.base_dir,
                    path_handler.series,
                    path_handler.season,
                    ep_folder,
                )
                if os.path.exists(ep_plot_path):
                    episode_plots.append(ep_plot_path)
            if episode_plots:
                logger.info(f"Found {len(episode_plots)} episode plots to summarize")
                create_season_summary(episode_plots, llm_cheap, season_plot_path)
            else:
                logger.warning("No episode plots found to create season summary.")
        else:
            logger.info(f"Season summary already exists at: {season_plot_path}")

        input_file = path_handler.get_raw_plot_file_path()
        logger.info(f"Loading raw plot from: {input_file}")
        if not os.path.exists(input_file):
            logger.error(f"Raw plot file not found: {input_file}")
            return

        raw_plot = load_text(input_file)
        cleaned_plot = clean_text(raw_plot)
        logger.info("Cleaning plot text completed.")

        named_file_path = path_handler.get_named_plot_file_path()
        if not os.path.exists(named_file_path):
            logger.info(f"Replacing pronouns with names and saving to: {named_file_path}")
            named_plot = replace_pronouns_with_names(text=cleaned_plot, intelligent_llm=llm_intelligent, cheap_llm=llm_cheap)
            with open(named_file_path, "w", encoding="utf-8") as named_file:
                named_file.write(named_plot)
        else:
            logger.info(f"Loading named plot from: {named_file_path}")
            with open(named_file_path, "r", encoding="utf-8") as named_file:
                named_plot = named_file.read()

        episode_extracted_refined_entities_path = path_handler.get_episode_refined_entities_path()
        season_extracted_refined_entities_path = path_handler.get_season_extracted_refined_entities_path()
        if not os.path.exists(episode_extracted_refined_entities_path):
            logger.info("Extracting and refining entities from named plot.")
            entities = extract_and_refine_entities(
                named_plot,
                series,
                llm_intelligent,
                episode_extracted_refined_entities_path,
                path_handler.get_episode_raw_spacy_entities_path(),
                season_extracted_refined_entities_path,
            )
        else:
            logger.info(f"Loading existing entities from: {episode_extracted_refined_entities_path}")
            with open(episode_extracted_refined_entities_path, "r") as episode_extracted_refined_entities_file:
                entities_data = json.load(episode_extracted_refined_entities_file)
                entities = [EntityLink(**entity) for entity in entities_data]

        entity_substituted_plot_path = path_handler.get_entity_substituted_plot_file_path()
        entity_normalized_plot_path = path_handler.get_entity_normalized_plot_file_path()
        if not os.path.exists(entity_substituted_plot_path):
            entity_substituted_plot = substitute_appellations_with_names(named_plot, entities, llm_intelligent)
            with open(entity_substituted_plot_path, "w", encoding="utf-8") as entity_substituted_plot_file:
                entity_substituted_plot_file.write(entity_substituted_plot)
        else:
            logger.info(f"Loading entity substituted plot from: {entity_substituted_plot_path}")
            with open(entity_substituted_plot_path, "r", encoding="utf-8") as entity_substituted_plot_file:
                entity_substituted_plot = entity_substituted_plot_file.read()

        if not os.path.exists(entity_normalized_plot_path):
            entity_normalized_plot = normalize_entities_names_to_best_appellation(entity_substituted_plot, entities)
            with open(entity_normalized_plot_path, "w", encoding="utf-8") as entity_normalized_plot_file:
                entity_normalized_plot_file.write(entity_normalized_plot)
        else:
            logger.info(f"Loading entity normalized plot from: {entity_normalized_plot_path}")
            with open(entity_normalized_plot_path, "r", encoding="utf-8") as entity_normalized_plot_file:
                entity_normalized_plot = entity_normalized_plot_file.read()

        semantic_segments_path = path_handler.get_semantic_segments_path()
        if not os.path.exists(semantic_segments_path):
            logger.info("Performing semantic splitting.")
            semantic_segments = semantic_split(text=entity_normalized_plot, llm=llm_intelligent)
            with open(semantic_segments_path, "w", encoding="utf-8") as semantic_segments_file:
                json.dump(semantic_segments, semantic_segments_file, indent=2, ensure_ascii=False)
                logger.info(f"Semantic splitting complete. Results saved to {semantic_segments_path}")
        else:
            logger.info(f"Loading semantic segments from: {semantic_segments_path}")
            with open(semantic_segments_path, "r") as semantic_segments_file:
                semantic_segments = json.load(semantic_segments_file)

        suggested_episode_arc_path = path_handler.get_suggested_episode_arc_path()
        if not os.path.exists(suggested_episode_arc_path):
            file_paths_for_graph = {
                "season_plot_path": path_handler.get_season_plot_file_path(),
                "episode_plot_path": path_handler.get_entity_normalized_plot_file_path(),
                "seasonal_narrative_analysis_output_path": path_handler.get_season_narrative_analysis_path(),
                "episode_narrative_analysis_output_path": path_handler.get_episode_narrative_analysis_path(),
                "season_entities_path": path_handler.get_season_extracted_refined_entities_path(),
                "suggested_episode_arc_path": suggested_episode_arc_path,
            }
            logger.info("Extracting narrative arcs.")
            _run_async(extract_narrative_arcs(file_paths_for_graph, series, season, episode))

        logger.info("Processing suggested arcs and updating database.")
        updated_arcs = process_suggested_arcs(
            suggested_episode_arc_path,
            series,
            season,
            episode,
        )
        logger.info(f"Updated {len(updated_arcs)} arcs in the database.")
        logger.info("Processing complete.")
    except Exception as e:
        logger.error(f"An error occurred during processing: {e}")
        raise


def analyze_episode(series: str, season: str, episode: str, base_dir: str = "data") -> None:
    logger.warning(f"Starting text processing for episode {episode}")
    process_text(PathHandler(series, season, episode, base_dir=base_dir))


def analyze_series(series: str, season: str, episodes: range | None = None, base_dir: str = "data") -> None:
    logger.info("Starting text processing.")
    for ep in episodes or range(1, 10):
        analyze_episode(series, season, f"E{ep:02d}", base_dir=base_dir)
