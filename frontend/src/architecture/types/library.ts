export interface LibrarySeriesSummary {
  code: string;
  display_name: string;
  analysis_state: 'idle' | 'ready' | 'running' | 'completed' | 'failed';
  expected_episode_count: number;
  uploaded_episode_count: number;
  unmatched_upload_count: number;
}

export interface LibraryEpisodeStatus {
  season: string;
  episode: string;
  has_plot: boolean;
}

export interface LibraryUpload {
  upload_id: string;
  filename: string;
}

export interface LibrarySeriesStatus extends LibrarySeriesSummary {
  episodes: LibraryEpisodeStatus[];
  unmatched_uploads: LibraryUpload[];
  auto_matched_uploads?: Array<{
    season: string;
    episode: string;
    path: string;
  }>;
}
