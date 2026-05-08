from typing import List, Dict
from textwrap import dedent
from langchain_litellm import ChatLiteLLM
from langchain_core.messages import HumanMessage
from src.utils.logger_utils import setup_logging
from src.utils.text_utils import load_text
from src.utils.llm_utils import clean_llm_text_response
import os

logger = setup_logging(__name__)

def summarize_plot(text: str, llm: ChatLiteLLM, output_path: str) -> str:
    """
    Summarize the plot of a series using the LLM.
    
    Args:
        text (str): The text to summarize
        llm (ChatLiteLLM): The LLM to use
        output_path (str): Where to save the summary
        
    Returns:
        str: The summarized text
    """
    prompt = dedent(f"""You are an expert at summarizing the main narrative arcs and plot progression of TV series.
    You will receive a plot description for a TV series and need to summarize it, focusing on the key narrative arcs and progression, while preserving the storyline without extraneous details.
    Your summary should be linear, capturing the primary events and shifts in the plot in a detailed, chronological manner without skipping around the text or adding commentary.
    Avoid conclusions or personal interpretation.
    Please summarize the following text:\n{text}""")
    
    response = llm.invoke([HumanMessage(content=prompt)])
    summary = clean_llm_text_response(response.content.strip())
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, "w") as output_file:
        output_file.write(summary)
    
    return summary

def create_season_summary(episode_plots_paths: List[str], llm: ChatLiteLLM, season_summary_path: str) -> str:
    """
    Create a season summary directly from individual episode plots.
    
    Args:
        episode_plots_paths (List[str]): List of paths to episode plot files
        llm (ChatLiteLLM): The LLM to use
        season_summary_path (str): Where to save the season summary
        
    Returns:
        str: The season summary
    """
    episode_plots: List[str] = []
    for i, plot_path in enumerate(episode_plots_paths):
        if not os.path.exists(plot_path):
            logger.warning(f"Plot file not found: {plot_path}")
            continue
            
        plot_text = load_text(plot_path)
        # Enumerate episodes for clarity in the prompt
        episode_plots.append(f"EPISODE #{i+1}:\n{plot_text}")
    
    if not episode_plots:
        logger.warning("No episode plots found")
        return ""
    
    combined_plots = "\n\n--- EPISODE BREAK ---\n\n".join(episode_plots)
    
    prompt = dedent(f"""You are an expert at creating cohesive season summaries for TV series by focusing on the primary narrative arcs and plot evolution. You also love spoilers, so you don't keep secrets on the plot.
    You will receive multiple episode plots, separated by 'EPISODE BREAK,' and are to create a season summary that preserves the chronological development of the main storyline.
    Each episode's plot should remain in order without mixing events from different episodes.
    You will focus on the narrative arcs that spans multiple episodes, not the episodic arcs that only happen in a single episode.
    Emphasize key developments and character arcs without adding extraneous details, conclusions, or commentary.
    Please create a season summary from these episode plots:\n\n{combined_plots}""")
    
    response = llm.invoke([HumanMessage(content=prompt)])
    season_summary = clean_llm_text_response(response.content.strip())
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(season_summary_path), exist_ok=True)
    
    with open(season_summary_path, "w", encoding="utf-8") as season_file:
        season_file.write(season_summary)
        
    return season_summary
