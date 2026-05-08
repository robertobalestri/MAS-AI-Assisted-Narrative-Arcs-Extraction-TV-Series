export enum ArcType {
  SoapArc = 'Soap Arc',
  GenreSpecificArc = 'Genre-Specific Arc',
  AnthologyArc = 'Anthology Arc'
}

export interface ArcProgression {
  id: string;
  content: string;
  series: string;
  season: string;
  episode: string;
  ordinal_position: number;
  interfering_characters: string[];
}

export interface NarrativeArc {
  id: string;
  title: string;
  description: string;
  arc_type: ArcType;
  main_characters: string[];
  series: string;
  progressions: ArcProgression[];
}

export interface ArcCluster {
  cluster_id: number;
  arcs: Array<{
    id: string;
    title: string;
    type: string;
    metadata: Record<string, unknown>;
    cluster_probability: number;
  }>;
  average_distance: number;
  size: number;
  average_probability: number;
  cluster_persistence?: number;
}

export interface ProgressionMapping {
  season: string;
  episode: string;
  content: string;
  interfering_characters: string[];
  arc_id?: string;
  arc_title?: string;
  series?: string;
}

// Add a new type for creating arcs
export interface CreateArcData extends Omit<Partial<NarrativeArc>, 'progressions'> {
  progressions?: Omit<Partial<ArcProgression>, 'id'>[];
} 