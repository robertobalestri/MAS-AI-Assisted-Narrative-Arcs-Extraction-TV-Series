import React, { useEffect, useMemo, useState } from 'react';
import {
  Badge,
  Box,
  Button,
  Divider,
  FormControl,
  HStack,
  Input,
  SimpleGrid,
  Spinner,
  Text,
  VStack,
  useToast,
} from '@chakra-ui/react';
import { ApiClient } from '@/services/api/ApiClient';
import { isApiSuccess } from '@/architecture/types/api';

interface ExplorerEpisodeStatus {
  series: string;
  season: string;
  episode: string;
  has_plot_file: boolean;
  has_srt_file: boolean;
  has_dialogue_json: boolean;
  has_analysis_artifacts: boolean;
  progression_count: number;
  analysis_status: 'processed' | 'plot_ready' | 'subtitle_only' | 'empty';
}

interface ExplorerSeason {
  season: string;
  episodes: ExplorerEpisodeStatus[];
}

interface ExplorerSeries {
  code: string;
  display_name: string;
  seasons: ExplorerSeason[];
}

interface LibraryExplorerProps {
  selectedSeries: string;
  onSelectSeries: (series: string) => void;
  onDataChange?: (series: ExplorerSeries[]) => void;
  refreshKey?: number;
  onSelectAnalysisEngine?: () => void;
}

const normalizeCode = (value: string) => value.trim().toUpperCase().replace(/[^A-Z0-9_-]/g, '');

const api = new ApiClient();

export const LibraryExplorer: React.FC<LibraryExplorerProps> = ({
  selectedSeries,
  onSelectSeries,
  onDataChange,
  refreshKey,
}) => {
  const toast = useToast();
  const [series, setSeries] = useState<ExplorerSeries[]>([]);
  const [selectedEpisode, setSelectedEpisode] = useState<ExplorerEpisodeStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [newSeriesCode, setNewSeriesCode] = useState('');
  const [newSeriesName, setNewSeriesName] = useState('');
  const [newSeasonBySeries, setNewSeasonBySeries] = useState<Record<string, string>>({});
  const [newEpisodeBySeason, setNewEpisodeBySeason] = useState<Record<string, string>>({});

  const selectedSeriesData = useMemo(
    () => series.find((item) => item.code === selectedSeries) ?? null,
    [selectedSeries, series]
  );

  const refreshExplorer = async () => {
    setIsLoading(true);
    const response = await api.request<ExplorerSeries[]>('/library/explorer');
    setIsLoading(false);

    if (!isApiSuccess<ExplorerSeries[]>(response)) {
      toast({ title: 'Unable to load library explorer', description: response.error, status: 'error' });
      return;
    }

    setSeries(response.data);
    onDataChange?.(response.data);
    if (!selectedSeries && response.data[0]) {
      onSelectSeries(response.data[0].code);
    }
  };

  useEffect(() => {
    refreshExplorer();
  }, [refreshKey]);

  useEffect(() => {
    if (!selectedSeriesData) {
      setSelectedEpisode(null);
      return;
    }

    const firstEpisode = selectedSeriesData.seasons[0]?.episodes[0] ?? null;
    if (!selectedEpisode || selectedEpisode.series !== selectedSeries) {
      setSelectedEpisode(firstEpisode);
    }
  }, [selectedEpisode, selectedSeries, selectedSeriesData]);

  const handleCreateSeries = async () => {
    const code = normalizeCode(newSeriesCode);
    const displayName = newSeriesName.trim();
    if (!code || !displayName) {
      return;
    }

    setIsSubmitting(true);
    const response = await api.createLibrarySeries(code, displayName);
    setIsSubmitting(false);

    if (!isApiSuccess(response)) {
      toast({ title: 'Unable to create series', description: response.error, status: 'error' });
      return;
    }

    setNewSeriesCode('');
    setNewSeriesName('');
    onSelectSeries(response.data.code);
    await refreshExplorer();
  };

  const handleAddSeason = async (seriesCode: string) => {
    const seasonValue = newSeasonBySeries[seriesCode]?.trim();
    if (!seasonValue) {
      return;
    }

    setIsSubmitting(true);
    const response = await api.createLibrarySeasons(seriesCode, [seasonValue]);
    setIsSubmitting(false);

    if (!isApiSuccess(response)) {
      toast({ title: 'Unable to add season', description: response.error, status: 'error' });
      return;
    }

    setNewSeasonBySeries((prev) => ({ ...prev, [seriesCode]: '' }));
    await refreshExplorer();
  };

  const handleAddEpisode = async (seriesCode: string, seasonCode: string) => {
    const key = `${seriesCode}-${seasonCode}`;
    const episodeValue = newEpisodeBySeason[key]?.trim();
    if (!episodeValue) {
      return;
    }

    setIsSubmitting(true);
    const response = await api.createLibraryEpisodes(seriesCode, seasonCode, [episodeValue]);
    setIsSubmitting(false);

    if (!isApiSuccess(response)) {
      toast({ title: 'Unable to add episode', description: response.error, status: 'error' });
      return;
    }

    setNewEpisodeBySeason((prev) => ({ ...prev, [key]: '' }));
    await refreshExplorer();
  };

  const handleUpload = async (kind: 'plot' | 'srt', file: File) => {
    if (!selectedEpisode) {
      return;
    }

    const expectedExtension = kind === 'plot' ? '.txt' : '.srt';
    if (!file.name.toLowerCase().endsWith(expectedExtension)) {
      toast({ title: `Please upload a ${expectedExtension} file in the ${kind.toUpperCase()} box.`, status: 'warning' });
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    setIsSubmitting(true);
    const response = await api.request<{ source_type: string }>(
      `/library/series/${selectedEpisode.series}/${selectedEpisode.season}/${selectedEpisode.episode}/upload`,
      {
        method: 'POST',
        body: formData,
      }
    );
    setIsSubmitting(false);

    if (!isApiSuccess(response)) {
      toast({ title: 'Unable to upload file', description: response.error, status: 'error' });
      return;
    }

    await refreshExplorer();
  };

  const handleGeneratePlot = async () => {
    if (!selectedEpisode) {
      return;
    }

    setIsSubmitting(true);
    const response = await api.request<ExplorerEpisodeStatus>(
      `/library/explorer/${selectedEpisode.series}/${selectedEpisode.season}/${selectedEpisode.episode}/generate-plot`,
      { method: 'POST' }
    );
    setIsSubmitting(false);

    if (!isApiSuccess<ExplorerEpisodeStatus>(response)) {
      toast({ title: 'Unable to generate plot', description: response.error, status: 'error' });
      return;
    }

    toast({ title: 'Plot generated', status: 'success' });
    await refreshExplorer();
    setSelectedEpisode(response.data);
  };


  const handleResetEpisode = async () => {
    if (!selectedEpisode) {
      return;
    }

    setIsSubmitting(true);
    const response = await api.request<{ episode: ExplorerEpisodeStatus }>(
      `/library/explorer/${selectedEpisode.series}/${selectedEpisode.season}/${selectedEpisode.episode}/reset`,
      { method: 'POST' }
    );
    setIsSubmitting(false);

    if (!isApiSuccess<{ episode: ExplorerEpisodeStatus }>(response)) {
      toast({ title: 'Unable to reset episode', description: response.error, status: 'error' });
      return;
    }

    toast({ title: 'Episode reset completed', status: 'success' });
    await refreshExplorer();
    setSelectedEpisode(response.data.episode);
  };

  const statusColor = (status: ExplorerEpisodeStatus['analysis_status']) => {
    if (status === 'processed') return 'green';
    if (status === 'plot_ready') return 'blue';
    if (status === 'subtitle_only') return 'yellow';
    return 'gray';
  };

  return (
    <SimpleGrid columns={{ base: 1, lg: 3 }} spacing={6} alignItems="start">
      <Box bg="white" p={4} borderRadius="lg" shadow="sm">
        <Text fontSize="lg" fontWeight="bold" mb={4}>Library Explorer</Text>
        {isLoading ? (
          <Spinner />
        ) : (
          <VStack align="stretch" spacing={4}>
            {series.map((seriesItem) => (
              <Box key={seriesItem.code} borderWidth="1px" borderRadius="md" p={3}>
                <Button variant="ghost" width="100%" justifyContent="space-between" onClick={() => onSelectSeries(seriesItem.code)}>
                  <Text fontWeight="bold">{seriesItem.display_name}</Text>
                  <Text color="gray.500">{seriesItem.code}</Text>
                </Button>
                {selectedSeries === seriesItem.code && (
                  <VStack align="stretch" mt={3} spacing={3}>
                    {seriesItem.seasons.map((seasonItem) => {
                      const seasonKey = `${seriesItem.code}-${seasonItem.season}`;
                      return (
                        <Box key={seasonItem.season}>
                          <HStack justify="space-between" mb={2}>
                            <Text fontWeight="medium">{seasonItem.season}</Text>
                          </HStack>
                          <VStack align="stretch" spacing={2}>
                            {seasonItem.episodes.map((episodeItem) => (
                              <Button
                                key={`${episodeItem.season}-${episodeItem.episode}`}
                                variant={selectedEpisode?.season === episodeItem.season && selectedEpisode?.episode === episodeItem.episode ? 'solid' : 'outline'}
                                justifyContent="space-between"
                                onClick={() => setSelectedEpisode(episodeItem)}
                                size="sm"
                              >
                                <Text>{episodeItem.episode}</Text>
                                <Badge colorScheme={statusColor(episodeItem.analysis_status)}>{episodeItem.analysis_status}</Badge>
                              </Button>
                            ))}
                            <HStack>
                              <FormControl>
                                <Input
                                  size="sm"
                                  placeholder="Episode number"
                                  value={newEpisodeBySeason[seasonKey] ?? ''}
                                  onChange={(event) => setNewEpisodeBySeason((prev) => ({ ...prev, [seasonKey]: event.target.value }))}
                                />
                              </FormControl>
                              <Button size="sm" onClick={() => handleAddEpisode(seriesItem.code, seasonItem.season)} isLoading={isSubmitting}>
                                + Add Episode
                              </Button>
                            </HStack>
                          </VStack>
                        </Box>
                      );
                    })}
                    <HStack>
                      <FormControl>
                        <Input
                          size="sm"
                          placeholder="Season number"
                          value={newSeasonBySeries[seriesItem.code] ?? ''}
                          onChange={(event) => setNewSeasonBySeries((prev) => ({ ...prev, [seriesItem.code]: event.target.value }))}
                        />
                      </FormControl>
                      <Button size="sm" onClick={() => handleAddSeason(seriesItem.code)} isLoading={isSubmitting}>
                        + Add Season
                      </Button>
                    </HStack>
                  </VStack>
                )}
              </Box>
            ))}
            <Box borderWidth="1px" borderRadius="md" p={3}>
              <VStack align="stretch" spacing={3}>
                <Text fontWeight="bold">Add new series</Text>
                <FormControl>
                  <Input
                    size="sm"
                    placeholder="Series code"
                    value={newSeriesCode}
                    onChange={(event) => setNewSeriesCode(event.target.value)}
                  />
                </FormControl>
                <FormControl>
                  <Input
                    size="sm"
                    placeholder="Display name"
                    value={newSeriesName}
                    onChange={(event) => setNewSeriesName(event.target.value)}
                  />
                </FormControl>
                <Button onClick={handleCreateSeries} isLoading={isSubmitting}>Add new series</Button>
              </VStack>
            </Box>
          </VStack>
        )}
      </Box>

      <Box bg="white" p={6} borderRadius="lg" shadow="sm" gridColumn={{ lg: 'span 2' }}>
        {selectedEpisode ? (
          <VStack align="stretch" spacing={4}>
            <HStack justify="space-between">
              <Box>
                <Text fontSize="lg" fontWeight="bold">{selectedEpisode.series} {selectedEpisode.season}{selectedEpisode.episode}</Text>
                <Text color="gray.600">Episode processing status from filesystem and database.</Text>
              </Box>
              <Badge colorScheme={statusColor(selectedEpisode.analysis_status)}>{selectedEpisode.analysis_status}</Badge>
            </HStack>

            <Divider />

            <SimpleGrid columns={{ base: 1, md: 2 }} spacing={4}>
              <Box borderWidth="1px" borderRadius="md" p={4}>
                <Text fontWeight="medium">Plot file</Text>
                <Text color={selectedEpisode.has_plot_file ? 'green.600' : 'gray.500'}>{selectedEpisode.has_plot_file ? 'Present' : 'Missing'}</Text>
                <Box
                  mt={3}
                  border="2px dashed"
                  borderColor="gray.200"
                  borderRadius="md"
                  p={4}
                  textAlign="center"
                  bg="gray.50"
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={async (event) => {
                    event.preventDefault();
                    const file = event.dataTransfer.files[0];
                    if (file) {
                      await handleUpload('plot', file);
                    }
                  }}
                >
                  <Text fontSize="sm" mb={2}>Drop plot .txt here</Text>
                  <Input
                    type="file"
                    accept=".txt"
                    onChange={async (event) => {
                      const file = event.target.files?.[0];
                      if (file) {
                        await handleUpload('plot', file);
                      }
                      event.target.value = '';
                    }}
                  />
                </Box>
              </Box>
              <Box borderWidth="1px" borderRadius="md" p={4}>
                <Text fontWeight="medium">SRT subtitles</Text>
                <Text color={selectedEpisode.has_srt_file ? 'green.600' : 'gray.500'}>{selectedEpisode.has_srt_file ? 'Present' : 'Missing'}</Text>
                <Box
                  mt={3}
                  border="2px dashed"
                  borderColor="gray.200"
                  borderRadius="md"
                  p={4}
                  textAlign="center"
                  bg="gray.50"
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={async (event) => {
                    event.preventDefault();
                    const file = event.dataTransfer.files[0];
                    if (file) {
                      await handleUpload('srt', file);
                    }
                  }}
                >
                  <Text fontSize="sm" mb={2}>Drop subtitle .srt here</Text>
                  <Input
                    type="file"
                    accept=".srt"
                    onChange={async (event) => {
                      const file = event.target.files?.[0];
                      if (file) {
                        await handleUpload('srt', file);
                      }
                      event.target.value = '';
                    }}
                  />
                </Box>
              </Box>
            </SimpleGrid>

            <Box>
              <Text fontWeight="medium" mb={2}>Actions</Text>
              <HStack spacing={3}>
                <Button
                  onClick={handleGeneratePlot}
                  isLoading={isSubmitting}
                  isDisabled={!selectedEpisode.has_srt_file || selectedEpisode.has_plot_file}
                >
                  Generate detailed plot from SRT
                </Button>
                <Button
                  onClick={handleResetEpisode}
                  isLoading={isSubmitting}
                  isDisabled={!selectedEpisode.has_analysis_artifacts && selectedEpisode.progression_count === 0}
                >
                  Reset episode analysis
                </Button>
              </HStack>
            </Box>
          </VStack>
        ) : (
          <Text color="gray.600">Select a series and episode from the library explorer.</Text>
        )}
      </Box>
    </SimpleGrid>
  );
};
