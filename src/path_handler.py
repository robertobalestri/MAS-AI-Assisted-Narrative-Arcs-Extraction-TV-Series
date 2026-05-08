import os
from typing import List

class PathHandler:
    def __init__(self, series: str, season: str, episode: str, base_dir: str = "data"):
        self.series = series
        self.season = season
        self.episode = episode
        self.base_dir = base_dir

    # Define methods to get file paths
    def get_raw_plot_file_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode, f"{self.series}{self.season}{self.episode}_plot.txt")

    def get_full_dialogues_file_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode, f"{self.series}{self.season}{self.episode}_full_dialogues.json")

    def get_simplified_plot_file_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode, f"{self.series}{self.season}{self.episode}_plot_simplified.txt")

    def get_named_plot_file_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode, f"{self.series}{self.season}{self.episode}_plot_named.txt")
    
    def get_entity_substituted_plot_file_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode, f"{self.series}{self.season}{self.episode}_plot_entities_substituted.txt")

    def get_entity_normalized_plot_file_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode, f"{self.series}{self.season}{self.episode}_plot_entities_normalized.txt")

    def get_season_plot_file_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, f"{self.series}{self.season}_season_plot.txt")

    def get_semantic_segments_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode, f"{self.series}{self.season}{self.episode}_plot_semantic_segments.json")

    def get_episode_narrative_arcs_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode, f"{self.series}{self.season}{self.episode}_multiagent_episode_narrative_arcs.json")

    def get_season_narrative_arcs_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, f"{self.series}{self.season}_multiagent_season_narrative_arcs.json")

    def get_episode_narrative_analysis_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode, f"{self.series}{self.season}{self.episode}_multiagent_episode_narrative_analysis.txt")

    def get_season_narrative_analysis_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, f"{self.series}{self.season}_multiagent_season_narrative_analysis.txt")

    def get_episode_refined_entities_path(self) -> str:
        """Path for saving refined entities for the episode."""
        return os.path.join(self.base_dir, self.series, self.season, self.episode, f"{self.series}{self.season}{self.episode}_refined_entities.json")

    def get_episode_raw_spacy_entities_path(self) -> str:
        """Path for saving raw spaCy entities for the episode."""
        return os.path.join(self.base_dir, self.series, self.season, self.episode, f"{self.series}{self.season}{self.episode}_raw_spacy_entities.json")
    
    def get_season_extracted_refined_entities_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, f"{self.series}{self.season}_extracted_entities.json")
    
    def get_plot_localized_sentences_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode, f"{self.series}{self.season}{self.episode}_plot_localized_sentences.json")
    
    def get_summarized_plot_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode, f"{self.series}{self.season}{self.episode}_summarized_plot.txt")
    
    def get_suggested_episode_arc_path(self) -> str:
        return os.path.join(self.base_dir, self.series, self.season, self.episode, f"{self.series}{self.season}{self.episode}_multiagent_suggested_episode_arcs.json")

    @staticmethod
    def get_episode_plot_path(base_dir: str, series: str, season: str, episode: str) -> str:
        """Get the path for an episode's plot file."""
        return os.path.join(base_dir, series, season, episode, f"{series}{season}{episode}_plot.txt")
    
    @staticmethod
    def get_episode_summary_path(base_dir: str, series: str, season: str, episode: str) -> str:
        """Get the path for an episode's summary file."""
        return os.path.join(base_dir, series, season, episode, f"{series}{season}{episode}_summarized_plot.txt")
    
    @staticmethod
    def get_season_plot_path(base_dir: str, series: str, season: str) -> str:
        """Get the path for a season's plot file."""
        return os.path.join(base_dir, series, season, f"{series}{season}_season_plot.txt")
    
    @staticmethod
    def list_episode_folders(base_dir: str, series: str, season: str) -> List[str]:
        """List all episode folders in a season directory."""
        season_path = os.path.join(base_dir, series, season)
        if not os.path.exists(season_path):
            return []
        return sorted([d for d in os.listdir(season_path)
                      if os.path.isdir(os.path.join(season_path, d)) and d.startswith('E')])

    @staticmethod
    def file_exists(path: str) -> bool:
        return os.path.exists(path)
