import React, { useMemo, useState } from 'react';
import {
  Box,
  Button,
  FormControl,
  FormLabel,
  HStack,
  Input,
  SimpleGrid,
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

interface SeriesManagerPanelProps {
  seriesData: ExplorerSeries | null;
  onRefresh: () => Promise<void>;
}

const api = new ApiClient();

export const SeriesManagerPanel: React.FC<SeriesManagerPanelProps> = ({ seriesData, onRefresh }) => {
  const toast = useToast();
  const [newSeason, setNewSeason] = useState('');
  const [newEpisodes, setNewEpisodes] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const orderedSeasons = useMemo(() => seriesData?.seasons ?? [], [seriesData]);

  const handleAddSeason = async () => {
    if (!seriesData || !newSeason.trim()) {
      return;
    }

    setIsSubmitting(true);
    const response = await api.createLibrarySeasons(seriesData.code, [newSeason]);
    setIsSubmitting(false);

    if (!isApiSuccess(response)) {
      toast({ title: 'Unable to add season', description: response.error, status: 'error' });
      return;
    }

    setNewSeason('');
    toast({ title: 'Season added', status: 'success' });
    await onRefresh();
  };

  const handleAddEpisode = async (season: string) => {
    const episodeValue = newEpisodes[season]?.trim();
    if (!seriesData || !episodeValue) {
      return;
    }

    setIsSubmitting(true);
    const response = await api.createLibraryEpisodes(seriesData.code, season, [episodeValue]);
    setIsSubmitting(false);

    if (!isApiSuccess(response)) {
      toast({ title: 'Unable to add episode', description: response.error, status: 'error' });
      return;
    }

    setNewEpisodes((prev) => ({ ...prev, [season]: '' }));
    toast({ title: 'Episode added', status: 'success' });
    await onRefresh();
  };

  const handleEpisodeUpload = async (season: string, episode: string, file: File) => {
    if (!seriesData) {
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    setIsSubmitting(true);
    const response = await api.request<{ source_type: string }>(
      `/library/series/${seriesData.code}/${season}/${episode}/upload`,
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

    toast({ title: `Uploaded ${response.data.source_type} file`, status: 'success' });
    await onRefresh();
  };

  if (!seriesData) {
    return (
      <Box bg="white" p={6} borderRadius="lg" shadow="sm">
        <Text color="gray.600">Select a series from the library explorer to manage seasons and episode files.</Text>
      </Box>
    );
  }

  return (
    <VStack align="stretch" spacing={6}>
      <Box bg="white" p={6} borderRadius="lg" shadow="sm">
        <Text fontSize="xl" fontWeight="bold">Series Manager</Text>
        <Text color="gray.600">{seriesData.display_name} ({seriesData.code})</Text>

        <HStack mt={4} spacing={3} align="end">
          <FormControl maxW="220px">
            <FormLabel>New season number</FormLabel>
            <Input value={newSeason} onChange={(event) => setNewSeason(event.target.value)} placeholder="1" />
          </FormControl>
          <Button onClick={handleAddSeason} isLoading={isSubmitting}>Add season</Button>
        </HStack>
      </Box>

      {orderedSeasons.map((season) => (
        <Box key={season.season} bg="white" p={6} borderRadius="lg" shadow="sm">
          <HStack justify="space-between" mb={4}>
            <Text fontSize="lg" fontWeight="bold">{season.season}</Text>
            <HStack spacing={3} align="end">
              <FormControl maxW="180px">
                <FormLabel>Add episode</FormLabel>
                <Input
                  value={newEpisodes[season.season] ?? ''}
                  onChange={(event) => setNewEpisodes((prev) => ({ ...prev, [season.season]: event.target.value }))}
                  placeholder="1"
                />
              </FormControl>
              <Button onClick={() => handleAddEpisode(season.season)} isLoading={isSubmitting}>Add episode</Button>
            </HStack>
          </HStack>

          <SimpleGrid columns={{ base: 1, md: 2, xl: 3 }} spacing={4}>
            {season.episodes.map((episode) => (
              <Box key={`${season.season}-${episode.episode}`} borderWidth="1px" borderRadius="md" p={4}>
                <Text fontWeight="medium" mb={2}>{episode.episode}</Text>
                <Text fontSize="sm" color="gray.600" mb={3}>Status: {episode.analysis_status}</Text>
                <Box
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
                      await handleEpisodeUpload(season.season, episode.episode, file);
                    }
                  }}
                >
                  <Text fontSize="sm" mb={2}>Drop plot.txt or .srt here</Text>
                  <Input
                    type="file"
                    accept=".txt,.srt"
                    onChange={async (event) => {
                      const file = event.target.files?.[0];
                      if (file) {
                        await handleEpisodeUpload(season.season, episode.episode, file);
                      }
                      event.target.value = '';
                    }}
                  />
                </Box>
              </Box>
            ))}
          </SimpleGrid>
        </Box>
      ))}
    </VStack>
  );
};
