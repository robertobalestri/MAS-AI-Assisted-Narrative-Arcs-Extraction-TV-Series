import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  Text,
  Spinner,
  HStack,
  FormControl,
  FormLabel,
  Select,
  Checkbox,
  Button,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
  Badge,
  useColorModeValue,
  Grid,
  GridItem,
} from '@chakra-ui/react';
import Plot from 'react-plotly.js';
import { PCA } from 'ml-pca';
import type { VectorStoreEntry } from '@/architecture/types';
import { ArcType } from '@/architecture/types/arc';

interface VectorStoreExplorerProps {
  entries: VectorStoreEntry[];
  isLoading: boolean;
}

export const VectorStoreExplorer: React.FC<VectorStoreExplorerProps> = ({
  entries,
  isLoading,
}) => {
  // 1. First, all useContext hooks
  const plotBgColor = useColorModeValue('white', 'gray.800');
  const progressionBgColor = useColorModeValue('gray.50', 'gray.700');
  const filtersBgColor = useColorModeValue('white', 'gray.800');

  // 2. All useState hooks
  const [visualizationData, setVisualizationData] = useState<any>(null);
  const [selectedSeason, setSelectedSeason] = useState<string>('S01');
  const [selectedEpisode, setSelectedEpisode] = useState<string>('');
  const [availableSeasons, setAvailableSeasons] = useState<string[]>([]);
  const [availableEpisodes, setAvailableEpisodes] = useState<string[]>([]);
  const [showOnlyMainArcs, setShowOnlyMainArcs] = useState<boolean>(true);

  // 3. All useEffect hooks
  useEffect(() => {
    if (entries.length > 0) {
      const seasons = new Set<string>();
      const episodes = new Set<string>();

      entries.forEach((entry) => {
        if (entry.metadata.season) {
          seasons.add(entry.metadata.season);
        }
        if (entry.metadata.episode) {
          episodes.add(entry.metadata.episode);
        }
      });

      setAvailableSeasons(Array.from(seasons).sort());
      setAvailableEpisodes(Array.from(episodes).sort());
    }
  }, [entries]);

  useEffect(() => {
    if (selectedSeason && entries.length > 0) {
      const episodesInSeason = new Set<string>();
      entries.forEach((entry) => {
        if (entry.metadata.season === selectedSeason && entry.metadata.episode) {
          episodesInSeason.add(entry.metadata.episode);
        }
      });
      setAvailableEpisodes(Array.from(episodesInSeason).sort());
    }
  }, [selectedSeason, entries]);

  useEffect(() => {
    if (entries.length > 0) {
      calculateVisualization(entries, showOnlyMainArcs, selectedSeason, selectedEpisode);
    }
  }, [entries, showOnlyMainArcs, selectedSeason, selectedEpisode]);

  // Helper functions and constants
  const getArcTypeColor = (arcType: ArcType): string => {
    const colors = {
      [ArcType.SoapArc]: 'pink',
      [ArcType.GenreSpecificArc]: 'orange',
      [ArcType.AnthologyArc]: 'green',
    };
    return colors[arcType] || 'gray';
  };

  const initializeWebGL = (canvas: HTMLCanvasElement) => {
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (gl && gl instanceof WebGLRenderingContext) {
      gl.getExtension('WEBGL_color_buffer_float');
      gl.getExtension('EXT_float_blend');
      gl.getExtension('OES_texture_float');
      gl.getExtension('OES_texture_float_linear');
    }
  };

  const plotConfig = {
    displayModeBar: true,
    responsive: true,
    scrollZoom: true,
    displaylogo: false,
    webgl: {
      preserveDrawingBuffer: true,
      extensions: [
        'WEBGL_color_buffer_float',
        'EXT_float_blend',
        'OES_texture_float',
        'OES_texture_float_linear',
      ],
    },
  };

  // Visualization calculations
  const calculateVisualization = (
    data: VectorStoreEntry[],
    hideProgressions?: boolean,
    filterSeason?: string,
    filterEpisode?: string
  ) => {
    if (!data || data.length < 3) {
      setVisualizationData(null);
      return;
    }

    try {
      // Separate main arcs and progressions
      const mainArcs = data.filter((entry) => entry.metadata.doc_type === 'main');
      let progressions = data.filter((entry) => entry.metadata.doc_type !== 'main');

      // Apply season/episode filters to progressions
      if (filterSeason || filterEpisode) {
        progressions = progressions.filter((entry) => {
          const seasonMatch = !filterSeason || entry.metadata.season === filterSeason;
          const episodeMatch = !filterEpisode || entry.metadata.episode === filterEpisode;
          return seasonMatch && episodeMatch;
        });

        // Get main arcs that have filtered progressions
        const mainArcIds = new Set(progressions.map((prog) => prog.metadata.main_arc_id));
        const relevantMainArcs = mainArcs.filter((arc) => mainArcIds.has(arc.id));

        // Create visualization data
        const traces: any[] = [];

        // Add main arcs trace
        if (relevantMainArcs.length > 0) {
          const mainArcsEmbeddings = relevantMainArcs.map((arc) => arc.embedding!);
          const mainArcsPca = new PCA(mainArcsEmbeddings);
          const mainArcsResult = mainArcsPca.predict(mainArcsEmbeddings, { nComponents: 3 });
          const mainArcsPcaResult = Array.from(mainArcsResult.to2DArray());

          traces.push({
            type: 'scatter3d',
            mode: 'markers',
            x: mainArcsPcaResult.map((p) => p[0]),
            y: mainArcsPcaResult.map((p) => p[1]),
            z: mainArcsPcaResult.map((p) => p[2]),
            text: relevantMainArcs.map(
              (arc) =>
                `Title: ${arc.metadata.title}<br>` +
                `Type: ${arc.metadata.arc_type}<br>` +
                `Characters: ${arc.metadata.main_characters || 'None'}`
            ),
            marker: {
              size: 12,
              symbol: 'circle',
              color: relevantMainArcs.map((arc) =>
                getArcTypeColor(arc.metadata.arc_type as ArcType)
              ),
              opacity: 0.8,
            },
            name: 'Main Arcs',
            hoverinfo: 'text',
          });
        }

        // Add progressions trace if not hidden
        if (!hideProgressions && progressions.length > 0) {
          const progressionsEmbeddings = progressions.map((prog) => prog.embedding!);
          const progressionsPca = new PCA(progressionsEmbeddings);
          const progressionsResult = progressionsPca.predict(progressionsEmbeddings, {
            nComponents: 3,
          });
          const progressionsPcaResult = Array.from(progressionsResult.to2DArray());

          traces.push({
            type: 'scatter3d',
            mode: 'markers',
            x: progressionsPcaResult.map((p) => p[0]),
            y: progressionsPcaResult.map((p) => p[1]),
            z: progressionsPcaResult.map((p) => p[2]),
            text: progressions.map(
              (prog) =>
                `Progression: ${prog.metadata.progression_title}<br>` +
                `Arc: ${prog.metadata.arc_title}<br>` +
                `Type: ${prog.metadata.arc_type}<br>` +
                `Characters: ${prog.metadata.interfering_characters || 'None'}`
            ),
            marker: {
              size: 8,
              symbol: 'square',
              color: progressions.map((prog) =>
                getArcTypeColor(prog.metadata.arc_type as ArcType)
              ),
              opacity: 0.6,
            },
            name: 'Progressions',
            hoverinfo: 'text',
          });
        }

        setVisualizationData(traces);
      } else {
        // If no filters, show all data
        const allData = hideProgressions ? mainArcs : [...mainArcs, ...progressions];
        const embeddings = allData.map((entry) => entry.embedding!);
        const pca = new PCA(embeddings);
        const result = pca.predict(embeddings, { nComponents: 3 });
        const pcaResult = Array.from(result.to2DArray());

        const traces: any[] = [];

        // Add main arcs trace
        if (mainArcs.length > 0) {
          traces.push({
            type: 'scatter3d',
            mode: 'markers',
            x: mainArcs.map((_, i) => pcaResult[i][0]),
            y: mainArcs.map((_, i) => pcaResult[i][1]),
            z: mainArcs.map((_, i) => pcaResult[i][2]),
            text: mainArcs.map(
              (arc) =>
                `Title: ${arc.metadata.title}<br>` +
                `Type: ${arc.metadata.arc_type}<br>` +
                `Characters: ${arc.metadata.main_characters || 'None'}`
            ),
            marker: {
              size: 12,
              symbol: 'circle',
              color: mainArcs.map((arc) => getArcTypeColor(arc.metadata.arc_type as ArcType)),
              opacity: 0.8,
            },
            name: 'Main Arcs',
            hoverinfo: 'text',
          });
        }

        // Add progressions trace if not hidden
        if (!hideProgressions && progressions.length > 0) {
          traces.push({
            type: 'scatter3d',
            mode: 'markers',
            x: progressions.map((_, i) => pcaResult[mainArcs.length + i][0]),
            y: progressions.map((_, i) => pcaResult[mainArcs.length + i][1]),
            z: progressions.map((_, i) => pcaResult[mainArcs.length + i][2]),
            text: progressions.map(
              (prog) =>
                `Progression: ${prog.metadata.progression_title}<br>` +
                `Arc: ${prog.metadata.arc_title}<br>` +
                `Type: ${prog.metadata.arc_type}<br>` +
                `Characters: ${prog.metadata.interfering_characters || 'None'}`
            ),
            marker: {
              size: 8,
              symbol: 'square',
              color: progressions.map((prog) =>
                getArcTypeColor(prog.metadata.arc_type as ArcType)
              ),
              opacity: 0.6,
            },
            name: 'Progressions',
            hoverinfo: 'text',
          });
        }

        setVisualizationData(traces);
      }
    } catch (error) {
      console.error('Error calculating visualization:', error);
      setVisualizationData(null);
    }
  };

  // Handle filter changes
  const handleFilterChange = (newSeason?: string, newEpisode?: string) => {
    calculateVisualization(entries, showOnlyMainArcs, newSeason, newEpisode);
  };

  return (
    <Grid templateColumns="1fr 600px" gap={4}>
      {/* Entry List */}
      <GridItem>
        <VStack spacing={4} align="stretch">
          <Accordion allowMultiple defaultIndex={[]}>
            {entries
              .filter((entry) => entry.metadata.doc_type === 'main')
              .map((mainArc: VectorStoreEntry) => (
                <AccordionItem key={mainArc.id}>
                  <AccordionButton>
                    <Box flex="1" textAlign="left">
                      <HStack spacing={2}>
                        <Badge colorScheme={getArcTypeColor(mainArc.metadata.arc_type as ArcType)}>
                          {mainArc.metadata.arc_type}
                        </Badge>
                        <Text fontWeight="bold">{mainArc.metadata.title}</Text>
                        {mainArc.metadata.main_characters &&
                          Array.isArray(mainArc.metadata.main_characters) && (
                            <Text fontSize="sm" color="gray.500">
                              Main Characters: {mainArc.metadata.main_characters.join(', ')}
                            </Text>
                          )}
                      </HStack>
                    </Box>
                    <AccordionIcon />
                  </AccordionButton>
                  <AccordionPanel pb={4}>
                    <VStack align="stretch" spacing={4}>
                      {/* Main Arc Content */}
                      <Box pl={4} borderLeft="2px" borderColor="gray.200">
                        <Text>{mainArc.content}</Text>
                        {mainArc.metadata.main_characters &&
                          Array.isArray(mainArc.metadata.main_characters) && (
                            <HStack mt={2}>
                              <Text fontWeight="bold">Main Characters:</Text>
                              <Text>{mainArc.metadata.main_characters.join(', ')}</Text>
                            </HStack>
                          )}
                      </Box>

                      {/* Progressions */}
                      <Box>
                        <Text fontWeight="bold" mb={2}>
                          Progressions:
                        </Text>
                        <VStack align="stretch" spacing={2}>
                          {entries
                            .filter(
                              (entry) =>
                                entry.metadata.doc_type !== 'main' &&
                                entry.metadata.main_arc_id === mainArc.id
                            )
                            .sort((a, b) => {
                              const seasonA = parseInt(
                                a.metadata.season?.replace('S', '') || '0'
                              );
                              const seasonB = parseInt(
                                b.metadata.season?.replace('S', '') || '0'
                              );
                              if (seasonA !== seasonB) return seasonA - seasonB;

                              const episodeA = parseInt(
                                a.metadata.episode?.replace('E', '') || '0'
                              );
                              const episodeB = parseInt(
                                b.metadata.episode?.replace('E', '') || '0'
                              );
                              return episodeA - episodeB;
                            })
                            .map((progression: VectorStoreEntry) => (
                              <Box
                                key={progression.id}
                                p={3}
                                borderWidth={1}
                                borderRadius="md"
                                bg={progressionBgColor}
                              >
                                <VStack align="stretch" spacing={2}>
                                  <HStack justify="space-between">
                                    <Badge colorScheme="purple">
                                      S{progression.metadata.season?.replace('S', '')}-
                                      E{progression.metadata.episode?.replace('E', '')}
                                    </Badge>
                                    {progression.distance !== undefined && (
                                      <Badge colorScheme="green">
                                        {((1 - progression.distance) * 100).toFixed(1)}% similarity
                                      </Badge>
                                    )}
                                  </HStack>
                                  <Text>{progression.content}</Text>
                                  {progression.metadata.interfering_characters &&
                                    Array.isArray(
                                      progression.metadata.interfering_characters
                                    ) &&
                                    progression.metadata.interfering_characters.length > 0 && (
                                      <HStack>
                                        <Text fontWeight="bold" fontSize="sm">
                                          Interfering Characters:
                                        </Text>
                                        <Text fontSize="sm">
                                          {progression.metadata.interfering_characters.join(', ')}
                                        </Text>
                                      </HStack>
                                    )}
                                </VStack>
                              </Box>
                            ))}
                        </VStack>
                      </Box>
                    </VStack>
                  </AccordionPanel>
                </AccordionItem>
              ))}
          </Accordion>
        </VStack>
      </GridItem>

      {/* 3D Visualization with Filters Above */}
      <GridItem>
        <VStack spacing={4} align="stretch">
          {/* Filters */}
          <Box
            bg={filtersBgColor}
            borderRadius="md"
            borderWidth={1}
            p={4}
            shadow="sm"
            width="100%"
          >
            <VStack spacing={4} align="stretch">
              <HStack spacing={4} align="flex-end">
                <FormControl size="sm" flex={1}>
                  <FormLabel fontSize="sm">Season</FormLabel>
                  <Select
                    size="sm"
                    value={selectedSeason}
                    onChange={(e) => {
                      const newSeason = e.target.value;
                      setSelectedSeason(newSeason);
                      setSelectedEpisode('');
                      handleFilterChange(newSeason, '');
                    }}
                  >
                    {availableSeasons.map((season) => (
                      <option key={season} value={season}>
                        Season {season.replace('S', '')}
                      </option>
                    ))}
                  </Select>
                </FormControl>

                <FormControl size="sm" flex={1}>
                  <FormLabel fontSize="sm">Episode</FormLabel>
                  <Select
                    size="sm"
                    value={selectedEpisode}
                    onChange={(e) => {
                      const newEpisode = e.target.value;
                      setSelectedEpisode(newEpisode);
                      handleFilterChange(selectedSeason, newEpisode);
                    }}
                    isDisabled={!selectedSeason}
                  >
                    <option value="">All Episodes</option>
                    {availableEpisodes.map((episode) => (
                      <option key={episode} value={episode}>
                        Episode {episode.replace('E', '')}
                      </option>
                    ))}
                  </Select>
                </FormControl>

                <FormControl flex={0}>
                  <Checkbox
                    size="sm"
                    isChecked={showOnlyMainArcs}
                    onChange={(e) => {
                      const hideProgressions = e.target.checked;
                      setShowOnlyMainArcs(hideProgressions);
                      calculateVisualization(
                        entries,
                        hideProgressions,
                        selectedSeason,
                        selectedEpisode
                      );
                    }}
                  >
                    Hide Progressions
                  </Checkbox>
                </FormControl>

                <Button
                  size="sm"
                  onClick={() => {
                    setSelectedSeason('S01');
                    setSelectedEpisode('');
                    setShowOnlyMainArcs(true);
                    handleFilterChange('S01', '');
                  }}
                  variant="outline"
                >
                  Reset Filters
                </Button>
              </HStack>
            </VStack>
          </Box>

          {/* 3D Visualization */}
          <Box
            height="calc(100vh - 280px)" // Adjusted height to account for filters
            borderWidth={1}
            borderRadius="lg"
            position="sticky"
            top="20px"
          >
            {isLoading ? (
              <VStack justify="center" height="100%">
                <Spinner />
                <Text>Loading visualization...</Text>
              </VStack>
            ) : visualizationData ? (
              <Plot
                data={visualizationData}
                layout={{
                  title: '3D PCA of Narrative Arc Embeddings',
                  autosize: true,
                  scene: {
                    xaxis: { title: 'PC1' },
                    yaxis: { title: 'PC2' },
                    zaxis: { title: 'PC3' },
                    aspectmode: 'cube',
                    aspectratio: { x: 1, y: 1, z: 1 },
                    camera: {
                      eye: { x: 1.5, y: 1.5, z: 1.5 },
                    },
                  },
                  margin: { l: 0, r: 0, t: 30, b: 0 },
                  showlegend: true,
                  legend: {
                    x: 0.9,
                    y: 0.9,
                    bgcolor: 'rgba(255, 255, 255, 0.8)',
                  },
                  paper_bgcolor: plotBgColor,
                  plot_bgcolor: plotBgColor,
                }}
                style={{ width: '100%', height: '100%' }}
                useResizeHandler
                config={plotConfig}
                onUpdate={() => {
                  const canvas = document.querySelector('.plotly canvas');
                  if (canvas) {
                    initializeWebGL(canvas as HTMLCanvasElement);
                  }
                }}
              />
            ) : (
              <VStack justify="center" height="100%">
                <Text>No data available for visualization</Text>
              </VStack>
            )}
          </Box>
        </VStack>
      </GridItem>
    </Grid>
  );
};
