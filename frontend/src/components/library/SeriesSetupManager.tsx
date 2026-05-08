import React, { useEffect, useMemo, useState } from 'react';
import {
  Badge,
  Box,
  Button,
  Divider,
  FormControl,
  FormLabel,
  Grid,
  HStack,
  Input,
  Select,
  SimpleGrid,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  VStack,
  useToast,
} from '@chakra-ui/react';
import { isApiSuccess } from '@/architecture/types/api';
import { ApiClient } from '@/services/api/ApiClient';
import type { LibrarySeriesStatus, LibrarySeriesSummary } from '@/architecture/types';

interface SeriesSelectorOption extends LibrarySeriesSummary {
  isLibrarySeries: boolean;
}

interface SeriesSetupManagerProps {
  selectedSeries: string;
  onSelectSeries: (series: string) => void;
  onStatusChange: (status: LibrarySeriesStatus | null) => void;
}

const api = new ApiClient();

export const SeriesSetupManager: React.FC<SeriesSetupManagerProps> = ({
  selectedSeries,
  onSelectSeries,
  onStatusChange,
}) => {
  const toast = useToast();
  const [seriesList, setSeriesList] = useState<SeriesSelectorOption[]>([]);
  const [status, setStatus] = useState<LibrarySeriesStatus | null>(null);
  const [seriesCode, setSeriesCode] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [seasonInput, setSeasonInput] = useState('1');
  const [episodeInput, setEpisodeInput] = useState('1');
  const [assignmentSeason, setAssignmentSeason] = useState('S01');
  const [assignmentEpisode, setAssignmentEpisode] = useState('E01');
  const [isDragging, setIsDragging] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const seasonCodes = useMemo(() => {
    const seasons = new Set<string>(status?.episodes.map((episode) => episode.season) ?? []);
    return Array.from(seasons).sort();
  }, [status]);

  const episodeCodes = useMemo(() => {
    if (!status) {
      return [];
    }
    return status.episodes
      .filter((episode) => episode.season === assignmentSeason)
      .map((episode) => episode.episode)
      .sort();
  }, [assignmentSeason, status]);

  const refreshSeries = async (nextSelectedSeries?: string) => {
    const [libraryResponse, allSeriesResponse] = await Promise.all([
      api.getLibrarySeries(),
      api.getSeries(),
    ]);

    if (!isApiSuccess<LibrarySeriesSummary[]>(libraryResponse)) {
      return;
    }

    const librarySeries = libraryResponse.data.map((series) => ({
      ...series,
      isLibrarySeries: true,
    }));

    if (!isApiSuccess<string[]>(allSeriesResponse)) {
      setSeriesList(librarySeries);
      const targetSeries = nextSelectedSeries ?? selectedSeries;
      if (!targetSeries && librarySeries[0]) {
        onSelectSeries(librarySeries[0].code);
      }
      return;
    }

    const knownLibraryCodes = new Set(librarySeries.map((series) => series.code));
    const mergedSeries = [
      ...librarySeries,
      ...allSeriesResponse.data
        .filter((code) => !knownLibraryCodes.has(code))
        .map((code) => ({
          code,
          display_name: code,
          analysis_state: 'completed' as const,
          expected_episode_count: 0,
          uploaded_episode_count: 0,
          unmatched_upload_count: 0,
          isLibrarySeries: false,
        })),
    ];

    setSeriesList(mergedSeries);
    const targetSeries = nextSelectedSeries ?? selectedSeries;
    if (!targetSeries && mergedSeries[0]) {
      onSelectSeries(mergedSeries[0].code);
    }
  };

  const refreshStatus = async (seriesCodeToLoad: string) => {
    const selectedOption = seriesList.find((series) => series.code === seriesCodeToLoad);
    if (selectedOption && !selectedOption.isLibrarySeries) {
      setStatus(null);
      onStatusChange(null);
      return;
    }

    const response = await api.getLibrarySeriesStatus(seriesCodeToLoad);
    if (isApiSuccess<LibrarySeriesStatus>(response)) {
      setStatus(response.data);
      onStatusChange(response.data);
      return;
    }

    setStatus(null);
    onStatusChange(null);
  };

  useEffect(() => {
    refreshSeries();
  }, []);

  useEffect(() => {
    if (selectedSeries) {
      refreshStatus(selectedSeries);
    } else {
      setStatus(null);
      onStatusChange(null);
    }
  }, [selectedSeries, seriesList]);

  useEffect(() => {
    if (seasonCodes[0] && !seasonCodes.includes(assignmentSeason)) {
      setAssignmentSeason(seasonCodes[0]);
    }
  }, [assignmentSeason, seasonCodes]);

  useEffect(() => {
    if (episodeCodes[0] && !episodeCodes.includes(assignmentEpisode)) {
      setAssignmentEpisode(episodeCodes[0]);
    }
  }, [assignmentEpisode, episodeCodes]);

  const handleCreateSeries = async () => {
    setIsSubmitting(true);
    const response = await api.createLibrarySeries(seriesCode, displayName);
    setIsSubmitting(false);

    if (!isApiSuccess<LibrarySeriesStatus>(response)) {
      toast({ title: 'Unable to create series', description: response.error, status: 'error' });
      return;
    }

    setSeriesCode('');
    setDisplayName('');
    onSelectSeries(response.data.code);
    setStatus(response.data);
    onStatusChange(response.data);
    await refreshSeries(response.data.code);
    toast({ title: 'Series created', status: 'success' });
  };

  const handleAddSeason = async () => {
    if (!selectedSeries) {
      return;
    }
    setIsSubmitting(true);
    const response = await api.createLibrarySeasons(selectedSeries, [seasonInput]);
    setIsSubmitting(false);

    if (!isApiSuccess<LibrarySeriesStatus>(response)) {
      toast({ title: 'Unable to add season', description: response.error, status: 'error' });
      return;
    }

    setStatus(response.data);
    onStatusChange(response.data);
    setAssignmentSeason(response.data.episodes[0]?.season ?? 'S01');
    toast({ title: 'Season added', status: 'success' });
  };

  const handleAddEpisode = async () => {
    if (!selectedSeries || !assignmentSeason) {
      return;
    }
    setIsSubmitting(true);
    const response = await api.createLibraryEpisodes(selectedSeries, assignmentSeason, [episodeInput]);
    setIsSubmitting(false);

    if (!isApiSuccess<LibrarySeriesStatus>(response)) {
      toast({ title: 'Unable to add episode', description: response.error, status: 'error' });
      return;
    }

    setStatus(response.data);
    onStatusChange(response.data);
    toast({ title: 'Episode added', status: 'success' });
  };

  const uploadFiles = async (files: File[]) => {
    if (!selectedSeries || files.length === 0) {
      return;
    }
    setIsSubmitting(true);
    const response = await api.uploadLibraryPlots(selectedSeries, files);
    setIsSubmitting(false);

    if (!isApiSuccess<LibrarySeriesStatus>(response)) {
      toast({ title: 'Upload failed', description: response.error, status: 'error' });
      return;
    }

    setStatus(response.data);
    onStatusChange(response.data);
    toast({ title: 'Files uploaded', status: 'success' });
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!event.target.files) {
      return;
    }
    await uploadFiles(Array.from(event.target.files));
    event.target.value = '';
  };

  const handleAssignUpload = async (uploadId: string) => {
    if (!selectedSeries) {
      return;
    }
    setIsSubmitting(true);
    const response = await api.assignLibraryUpload(selectedSeries, uploadId, assignmentSeason, assignmentEpisode);
    setIsSubmitting(false);

    if (!isApiSuccess<LibrarySeriesStatus>(response)) {
      toast({ title: 'Assignment failed', description: response.error, status: 'error' });
      return;
    }

    setStatus(response.data);
    onStatusChange(response.data);
    toast({ title: 'Upload assigned', status: 'success' });
  };

  const handleAnalyze = async () => {
    if (!selectedSeries) {
      return;
    }
    setIsSubmitting(true);
    const response = await api.analyzeLibrarySeries(selectedSeries);
    setIsSubmitting(false);

    if (!isApiSuccess<LibrarySeriesStatus>(response)) {
      toast({ title: 'Analysis failed to start', description: response.error, status: 'error' });
      return;
    }

    setStatus(response.data);
    onStatusChange(response.data);
    toast({ title: 'Analysis started', status: 'success' });
  };

  useEffect(() => {
    if (!selectedSeries || status?.analysis_state !== 'running') {
      return;
    }

    const interval = window.setInterval(() => {
      refreshStatus(selectedSeries);
    }, 5000);

    return () => window.clearInterval(interval);
  }, [selectedSeries, status?.analysis_state]);

  return (
    <VStack align="stretch" spacing={6}>
      <Box bg="white" p={6} borderRadius="lg" shadow="sm">
        <Text fontSize="xl" fontWeight="bold" mb={4}>Series library</Text>
        <SimpleGrid columns={{ base: 1, md: 3 }} spacing={4}>
          <FormControl>
            <FormLabel>Series code</FormLabel>
            <Input value={seriesCode} onChange={(event) => setSeriesCode(event.target.value)} placeholder="GA" />
          </FormControl>
          <FormControl>
            <FormLabel>Display name</FormLabel>
            <Input value={displayName} onChange={(event) => setDisplayName(event.target.value)} placeholder="Grey's Anatomy" />
          </FormControl>
          <FormControl alignSelf="end">
            <Button onClick={handleCreateSeries} isLoading={isSubmitting} colorScheme="blue" width="100%">
              Create series
            </Button>
          </FormControl>
        </SimpleGrid>

        <Divider my={6} />

        <FormControl>
          <FormLabel>Current series</FormLabel>
          <Select value={selectedSeries} onChange={(event) => onSelectSeries(event.target.value)} placeholder="Select a series">
            {seriesList.map((series) => (
              <option key={series.code} value={series.code}>
                {series.display_name} ({series.code})
              </option>
            ))}
          </Select>
        </FormControl>
      </Box>

      {status?.episodes?.length ? (
        <>
          <Grid templateColumns={{ base: '1fr', md: 'repeat(3, 1fr)' }} gap={4}>
            <Box bg="white" p={4} borderRadius="lg" shadow="sm">
              <Text fontSize="sm" color="gray.500">Analysis state</Text>
              <Badge mt={2} colorScheme={status.analysis_state === 'completed' ? 'green' : status.analysis_state === 'running' ? 'blue' : status.analysis_state === 'failed' ? 'red' : 'yellow'}>
                {status.analysis_state}
              </Badge>
            </Box>
            <Box bg="white" p={4} borderRadius="lg" shadow="sm">
              <Text fontSize="sm" color="gray.500">Uploaded episodes</Text>
              <Text mt={2} fontSize="2xl" fontWeight="bold">{status.uploaded_episode_count}/{status.expected_episode_count}</Text>
            </Box>
            <Box bg="white" p={4} borderRadius="lg" shadow="sm">
              <Text fontSize="sm" color="gray.500">Unmatched uploads</Text>
              <Text mt={2} fontSize="2xl" fontWeight="bold">{status.unmatched_upload_count}</Text>
            </Box>
          </Grid>

          <Box bg="white" p={6} borderRadius="lg" shadow="sm">
            <Text fontSize="lg" fontWeight="bold" mb={4}>Structure</Text>
            <HStack align="end" spacing={4} mb={4}>
              <FormControl>
                <FormLabel>Add season</FormLabel>
                <Input value={seasonInput} onChange={(event) => setSeasonInput(event.target.value)} placeholder="1" />
              </FormControl>
              <Button onClick={handleAddSeason} isLoading={isSubmitting}>Add season</Button>
            </HStack>
            <HStack align="end" spacing={4}>
              <FormControl>
                <FormLabel>Season for new episode</FormLabel>
                <Select value={assignmentSeason} onChange={(event) => setAssignmentSeason(event.target.value)}>
                  {seasonCodes.map((season) => (
                    <option key={season} value={season}>{season}</option>
                  ))}
                </Select>
              </FormControl>
              <FormControl>
                <FormLabel>Add episode</FormLabel>
                <Input value={episodeInput} onChange={(event) => setEpisodeInput(event.target.value)} placeholder="1" />
              </FormControl>
              <Button onClick={handleAddEpisode} isLoading={isSubmitting}>Add episode</Button>
            </HStack>

            <Table mt={6} size="sm">
              <Thead>
                <Tr>
                  <Th>Season</Th>
                  <Th>Episode</Th>
                  <Th>Plot</Th>
                </Tr>
              </Thead>
              <Tbody>
                {status.episodes.map((episode) => (
                  <Tr key={`${episode.season}-${episode.episode}`}>
                    <Td>{episode.season}</Td>
                    <Td>{episode.episode}</Td>
                    <Td>{episode.has_plot ? 'Uploaded' : 'Missing'}</Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </Box>

          <Box bg="white" p={6} borderRadius="lg" shadow="sm">
            <Text fontSize="lg" fontWeight="bold" mb={4}>Plot uploads</Text>
            <Box
              border="2px dashed"
              borderColor={isDragging ? 'blue.400' : 'gray.200'}
              borderRadius="lg"
              p={8}
              textAlign="center"
              bg={isDragging ? 'blue.50' : 'gray.50'}
              onDragOver={(event) => {
                event.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={async (event) => {
                event.preventDefault();
                setIsDragging(false);
                await uploadFiles(Array.from(event.dataTransfer.files));
              }}
            >
              <Text mb={3}>Drag and drop plot files here</Text>
              <Input type="file" multiple accept=".txt" onChange={handleFileChange} />
            </Box>

            {status.unmatched_uploads.length > 0 && (
              <Box mt={6}>
                <Text fontWeight="bold" mb={3}>Manual assignment required</Text>
                <VStack align="stretch" spacing={3}>
                  {status.unmatched_uploads.map((upload) => (
                    <Box key={upload.upload_id} borderWidth="1px" borderRadius="md" p={4}>
                      <Text fontWeight="medium">{upload.filename}</Text>
                      <HStack mt={3} spacing={4} align="end">
                        <FormControl>
                          <FormLabel>Season</FormLabel>
                          <Select value={assignmentSeason} onChange={(event) => setAssignmentSeason(event.target.value)}>
                            {seasonCodes.map((season) => (
                              <option key={season} value={season}>{season}</option>
                            ))}
                          </Select>
                        </FormControl>
                        <FormControl>
                          <FormLabel>Episode</FormLabel>
                          <Select value={assignmentEpisode} onChange={(event) => setAssignmentEpisode(event.target.value)}>
                            {episodeCodes.map((episode) => (
                              <option key={episode} value={episode}>{episode}</option>
                            ))}
                          </Select>
                        </FormControl>
                        <Button onClick={() => handleAssignUpload(upload.upload_id)} isLoading={isSubmitting}>Assign</Button>
                      </HStack>
                    </Box>
                  ))}
                </VStack>
              </Box>
            )}
          </Box>

          <Box bg="white" p={6} borderRadius="lg" shadow="sm">
            <HStack justify="space-between">
              <Box>
                <Text fontSize="lg" fontWeight="bold">Analyze series</Text>
                <Text color="gray.600">Runs the current processing pipeline for every episode that has a plot file.</Text>
              </Box>
              <Button colorScheme="teal" onClick={handleAnalyze} isLoading={isSubmitting || status.analysis_state === 'running'}>
                Analyze series
              </Button>
            </HStack>
          </Box>
        </>
      ) : selectedSeries ? (
        <Box bg="white" p={6} borderRadius="lg" shadow="sm">
          <Text color="gray.600">
            This series is available in the existing dashboard, but it does not have editable library metadata yet.
          </Text>
        </Box>
      ) : null}
    </VStack>
  );
};
