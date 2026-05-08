import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  VStack,
  HStack,
  Button,
  useDisclosure,
  useToast,
  Text,
  AlertDialog,
  AlertDialogBody,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogContent,
  AlertDialogOverlay,
} from '@chakra-ui/react';
import { AddIcon } from '@chakra-ui/icons';
import { ArcTimeline } from './ArcTimeline';
import { NewArcModal } from '../modals/NewArcModal';
import { ArcMergeModal } from '../modals/ArcMergeModal';
import { ArcFilters } from '../filters/ArcFilters';
import { useApi } from '@/hooks/useApi';
import { ApiClient } from '@/services/api/ApiClient';
import type { 
  NarrativeArc, 
  Episode, 
  ArcProgression, 
  Character, 
  ProgressionMapping,
  CreateArcData
} from '@/architecture/types';
import { ArcProgressionEditModal } from '../modals/ArcProgressionEditModal';
import { ArcType } from '@/architecture/types/arc';
import { ArcEditModal } from '../modals/ArcEditModal';

interface NarrativeArcManagerProps {
  series: string;
  arcs: NarrativeArc[];
  episodes: Episode[];
  onArcUpdated: () => void;
}

export const NarrativeArcManager: React.FC<NarrativeArcManagerProps> = ({
  series,
  arcs,
  episodes,
  onArcUpdated,
}) => {
  // State
  const [selectedSeason, setSelectedSeason] = useState('');
  const [isMergeMode, setIsMergeMode] = useState(false);
  const [selectedForMerge, setSelectedForMerge] = useState<NarrativeArc[]>([]);
  const [selectedCharacters, setSelectedCharacters] = useState<string[]>([]);
  const [includeInterferingCharacters, setIncludeInterferingCharacters] = useState(false);
  const [selectedArcTypes, setSelectedArcTypes] = useState<ArcType[]>([]);
  const [selectedProgression, setSelectedProgression] = useState<ProgressionMapping | null>(null);
  const [selectedArc, setSelectedArc] = useState<NarrativeArc | null>(null);
  const [selectedEpisode, setSelectedEpisode] = useState('');
  const [editingArc, setEditingArc] = useState<NarrativeArc | null>(null);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [isGenerateAllDialogOpen, setIsGenerateAllDialogOpen] = useState(false);
  const [selectedArcForGeneration, setSelectedArcForGeneration] = useState<NarrativeArc | null>(null);
  const cancelRef = React.useRef<HTMLButtonElement>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  // Modal disclosures
  const {
    isOpen: isProgressionModalOpen,
    onOpen: onProgressionModalOpen,
    onClose: onProgressionModalClose
  } = useDisclosure();

  const {
    isOpen: isNewArcModalVisible,
    onOpen: openNewArcModal,
    onClose: closeNewArcModal
  } = useDisclosure();

  const {
    isOpen: isMergeModalOpen,
    onOpen: openMergeModal,
    onClose: closeMergeModal
  } = useDisclosure();

  const {
    isOpen: isArcEditModalOpen,
    onOpen: onArcEditModalOpen,
    onClose: onArcEditModalClose
  } = useDisclosure();

  const toast = useToast();
  const { request } = useApi();
  const api = new ApiClient();

  // Get unique seasons from episodes
  const seasons = React.useMemo(() => {
    const uniqueSeasons = new Set(episodes.map(ep => ep.season));
    return Array.from(uniqueSeasons).sort();
  }, [episodes]);

  // Set initial season
  useEffect(() => {
    if (seasons.length > 0 && !selectedSeason) {
      setSelectedSeason(seasons[0]);
    }
  }, [seasons, selectedSeason]);

  // Fetch characters when component mounts
  useEffect(() => {
    const fetchCharacters = async () => {
      try {
        const response = await request(() => api.getCharacters(series));
        if (response) {
          // Make sure we're getting an array of characters
          const characterList = Array.isArray(response) ? response : [];
          setCharacters(characterList);
        }
      } catch (error) {
        console.error('Error fetching characters:', error);
        // Set empty array on error to prevent map errors
        setCharacters([]);
      }
    };

    if (series) {
      fetchCharacters();
    }
  }, [series]);

  // Update the filteredArcs useMemo to include arc type filtering
  const filteredArcs = useMemo(() => {
    let filtered = arcs;

    // Filter by arc type if any are selected
    if (selectedArcTypes.length > 0) {
      filtered = filtered.filter(arc => selectedArcTypes.includes(arc.arc_type as ArcType));
    }

    // Filter by characters if any are selected
    if (selectedCharacters.length > 0) {
      filtered = filtered.filter(arc => {
        // Check main characters
        const hasMainCharacter = arc.main_characters.some(char => 
          selectedCharacters.includes(char)
        );

        if (hasMainCharacter) return true;

        // Check interfering characters if enabled
        if (includeInterferingCharacters) {
          return arc.progressions.some(prog => 
            prog.interfering_characters.some(char => 
              selectedCharacters.includes(char)
            )
          );
        }

        return false;
      });
    }

    // Filter by episode if selected
    if (selectedSeason && selectedEpisode) {
      filtered = filtered.filter(arc => 
        arc.progressions.some(prog => 
          prog.season === selectedSeason && prog.episode === selectedEpisode
        )
      );
    }

    return filtered;
  }, [
    arcs, 
    selectedCharacters, 
    includeInterferingCharacters, 
    selectedArcTypes,  // Add this dependency
    selectedSeason,
    selectedEpisode
  ]);

  const handleCreateArc = async (arcData: CreateArcData) => {
    try {
      const response = await request(() => api.createArc(arcData));
      if (response) {
        toast({
          title: 'Arc created',
          status: 'success',
          duration: 3000,
        });
        onArcUpdated();
        closeNewArcModal();
      }
    } catch (error) {
      toast({
        title: 'Error creating arc',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const handleMergeArcs = async (mergedArcData: Partial<NarrativeArc>) => {
    if (selectedForMerge.length !== 2) return;

    try {
      const response = await request(() => api.mergeArcs(
        selectedForMerge[0].id,
        selectedForMerge[1].id,
        mergedArcData
      ));

      if (response) {
        toast({
          title: 'Arcs merged successfully',
          status: 'success',
          duration: 3000,
        });
        setIsMergeMode(false);
        setSelectedForMerge([]);
        onArcUpdated();
        closeMergeModal();
      }
    } catch (error) {
      toast({
        title: 'Error merging arcs',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const handleToggleMerge = (arc: NarrativeArc) => {
    setSelectedForMerge(prev => {
      if (prev.includes(arc)) {
        return prev.filter(a => a.id !== arc.id);
      }
      if (prev.length < 2) {
        return [...prev, arc];
      }
      return prev;
    });
  };

  const handleEditArc = (arc: NarrativeArc) => {
    setEditingArc(arc);
    onArcEditModalOpen();
  };

  const handleDeleteArc = async () => {
    if (!editingArc) return;

    try {
      await request(() => api.deleteArc(editingArc.id));
      toast({
        title: 'Arc deleted',
        status: 'success',
        duration: 3000,
      });
      onArcUpdated();
      onArcEditModalClose();
    } catch (error) {
      toast({
        title: 'Error deleting arc',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const handleCellClick = async (arc: NarrativeArc, season: string, episode: string) => {
    const existingProgression = arc.progressions.find(
      (p: ArcProgression) => p.season === season && p.episode === episode
    );

    const progressionData: ProgressionMapping = {
      season,
      episode,
      content: existingProgression?.content || '',
      interfering_characters: existingProgression?.interfering_characters || [],
      arc_id: arc.id,
      series: series
    };

    setSelectedProgression(progressionData);
    setSelectedArc(arc);
    onProgressionModalOpen();
  };

  const handleProgressionSave = async (updatedProgression: ProgressionMapping) => {
    if (!selectedArc) return;

    try {
      const existingProgression = selectedArc.progressions.find(
        (p: ArcProgression) => p.season === updatedProgression.season && p.episode === updatedProgression.episode
      );

      if (existingProgression) {
        // Update existing progression
        await request(() =>
          api.updateProgression(existingProgression.id, {
            content: updatedProgression.content,
            interfering_characters: updatedProgression.interfering_characters
          })
        );
      } else {
        // Create new progression
        await request(() =>
          api.createProgression({
            arc_id: selectedArc.id,
            content: updatedProgression.content,
            series: series,
            season: updatedProgression.season,
            episode: updatedProgression.episode,
            interfering_characters: updatedProgression.interfering_characters.join(';')
          })
        );
      }

      onArcUpdated();
      onProgressionModalClose();
      toast({
        title: 'Success',
        description: `Progression ${existingProgression ? 'updated' : 'created'} successfully`,
        status: 'success',
        duration: 3000,
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to save progression',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const handleProgressionDelete = async () => {
    if (!selectedArc || !selectedProgression) return;

    try {
      const existingProgression = selectedArc.progressions.find(
        (p: ArcProgression) => p.season === selectedProgression.season && p.episode === selectedProgression.episode
      );

      if (!existingProgression) {
        onProgressionModalClose();
        return;
      }

      await request(() => api.deleteProgression(existingProgression.id));

      onArcUpdated();
      onProgressionModalClose();
      toast({
        title: 'Success',
        description: 'Progression deleted successfully',
        status: 'success',
        duration: 3000,
      });
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof Error ? error.message : 'Failed to delete progression',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const handleUpdateArc = async (updatedArc: Partial<NarrativeArc>) => {
    try {
      await request(() => api.updateArc(updatedArc.id!, updatedArc));
      onArcUpdated();
      onArcEditModalClose();
      toast({
        title: 'Arc updated',
        status: 'success',
        duration: 3000,
      });
    } catch (error) {
      toast({
        title: 'Error updating arc',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const handleGenerateAllClick = (arc: NarrativeArc) => {
    setSelectedArcForGeneration(arc);
    setIsGenerateAllDialogOpen(true);
  };

  const handleGenerateAll = async (overwriteExisting: boolean = false) => {
    if (!selectedArcForGeneration) return;
    
    setIsGenerating(true);
    
    const arc = selectedArcForGeneration;
    const allEpisodes = episodes
      .filter(ep => ep.season === selectedSeason)
      .sort((a, b) => {
        const epA = parseInt(a.episode.replace('E', ''));
        const epB = parseInt(b.episode.replace('E', ''));
        return epA - epB;
      });

    try {
      const loadingToastId = toast({
        title: `Generating progressions for "${arc.title}"`,
        description: 'Starting generation...',
        status: 'info',
        duration: null,
        isClosable: true,
      });

      let generatedCount = 0;
      let skippedCount = 0;
      let noProgressionCount = 0;

      console.log(`Starting generation for arc: ${arc.title}`);
      console.log(`Total episodes to process: ${allEpisodes.length}`);

      for (const ep of allEpisodes) {
        // Update toast with current episode
        toast.update(loadingToastId, {
          description: `Processing S${ep.season.replace('S', '').padStart(2, '0')}E${ep.episode.replace('E', '').padStart(2, '0')} (${generatedCount + skippedCount + noProgressionCount + 1}/${allEpisodes.length})`,
        });
        
        console.log(`Processing S${ep.season}E${ep.episode}`);
        
        // Skip if progression already exists and we're not overwriting
        const existingProgression = arc.progressions.find(
          p => p.season === ep.season && p.episode === ep.episode
        );
        if (existingProgression && !overwriteExisting) {
          console.log(`Skipping existing progression for S${ep.season}E${ep.episode}`);
          skippedCount++;
          continue;
        }

        // Generate progression
        console.log(`Generating progression for S${ep.season}E${ep.episode}`);
        const response = await api.generateProgression(
          arc.id,
          series,
          ep.season,
          ep.episode,
          arc.title,
          arc.description
        );

        if (response.content && response.content !== "NO_PROGRESSION") {
          try {
            if (existingProgression) {
              // Update existing progression
              await request(() =>
                api.updateProgression(existingProgression.id, {
                  content: response.content,
                  interfering_characters: response.interfering_characters || []
                })
              );
            } else {
              // Create new progression
              await request(() =>
                api.createProgression({
                  arc_id: arc.id,
                  content: response.content,
                  series: series,
                  season: ep.season,
                  episode: ep.episode,
                  interfering_characters: Array.isArray(response.interfering_characters)
                    ? response.interfering_characters.join(';')
                    : response.interfering_characters || ''
                })
              );
            }
            generatedCount++;
          } catch (error) {
            console.error(`Error ${existingProgression ? 'updating' : 'creating'} progression for S${ep.season}E${ep.episode}:`, error);
          }
        } else if (response.content === "NO_PROGRESSION") {
          noProgressionCount++;
        }
      }

      toast.close(loadingToastId);
      toast({
        title: 'Generation Complete',
        description: `Generated ${generatedCount} progressions, skipped ${skippedCount} existing, ${noProgressionCount} episodes had no progression`,
        status: 'success',
        duration: 5000,
      });

      onArcUpdated();

    } catch (error) {
      console.error('Error in handleGenerateAll:', error);
      toast({
        title: 'Error generating progressions',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsGenerating(false);
      setIsGenerateAllDialogOpen(false);
      setSelectedArcForGeneration(null);
    }
  };

  return (
    <Box>
      <VStack spacing={4} align="stretch">
        {/* Arc Filters */}
        <ArcFilters
          seasons={seasons}
          selectedSeason={selectedSeason}
          onSeasonChange={setSelectedSeason}
          selectedEpisode={selectedEpisode}
          onEpisodeChange={setSelectedEpisode}
          allCharacters={characters?.map(c => c.best_appellation) || []}
          selectedCharacters={selectedCharacters}
          setSelectedCharacters={setSelectedCharacters}
          includeInterferingCharacters={includeInterferingCharacters}
          setIncludeInterferingCharacters={setIncludeInterferingCharacters}
          episodes={episodes}
          selectedArcTypes={selectedArcTypes}
          setSelectedArcTypes={setSelectedArcTypes}
        />

        {/* Timeline Header with Actions */}
        <HStack justify="space-between" align="center" mb={2}>
          <Text fontSize="lg" fontWeight="bold">Narrative Arcs Timeline</Text>
          <HStack spacing={4}>
            <Button
              colorScheme={isMergeMode ? "orange" : "gray"}
              onClick={() => {
                setIsMergeMode(!isMergeMode);
                if (!isMergeMode) {
                  setSelectedForMerge([]);
                }
              }}
            >
              {isMergeMode ? "Cancel Merge" : "Merge Arcs"}
            </Button>
            {isMergeMode && (
              <Button
                colorScheme="blue"
                isDisabled={selectedForMerge.length !== 2}
                onClick={openMergeModal}
              >
                Merge Selected ({selectedForMerge.length}/2)
              </Button>
            )}
            <Button
              leftIcon={<AddIcon />}
              colorScheme="green"
              onClick={openNewArcModal}
            >
              New Arc
            </Button>
          </HStack>
        </HStack>

        {/* Timeline */}
        <ArcTimeline
          arcs={filteredArcs}
          episodes={episodes}
          selectedSeason={selectedSeason}
          selectedEpisode={selectedEpisode}
          onCellClick={handleCellClick}
          isMergeMode={isMergeMode}
          selectedForMerge={selectedForMerge}
          onToggleMerge={handleToggleMerge}
          onEditArc={handleEditArc}
          onGenerateAll={handleGenerateAllClick}
        />

        {/* Modals */}
        <NewArcModal
          isOpen={isNewArcModalVisible}
          onClose={closeNewArcModal}
          onSubmit={handleCreateArc}
          availableCharacters={characters.map(c => c.best_appellation)}
          series={series}
          episodes={episodes}
        />

        {selectedForMerge.length === 2 && (
          <ArcMergeModal
            isOpen={isMergeModalOpen}
            onClose={closeMergeModal}
            arc1={selectedForMerge[0]}
            arc2={selectedForMerge[1]}
            onMergeComplete={handleMergeArcs}
          />
        )}

        <ArcProgressionEditModal
          isOpen={isProgressionModalOpen}
          onClose={onProgressionModalClose}
          progression={selectedProgression}
          onSave={handleProgressionSave}
          onDelete={handleProgressionDelete}
          availableCharacters={characters.map(c => c.best_appellation)}
          arcId={selectedArc?.id || ''}
          series={series}
        />

        <ArcEditModal
          isOpen={isArcEditModalOpen}
          onClose={onArcEditModalClose}
          arc={editingArc}
          onSave={handleUpdateArc}
          onDelete={handleDeleteArc}
          availableCharacters={characters.map(c => c.best_appellation)}
        />

        {/* Add the AlertDialog */}
        <AlertDialog
          isOpen={isGenerateAllDialogOpen}
          leastDestructiveRef={cancelRef}
          onClose={() => setIsGenerateAllDialogOpen(false)}
        >
          <AlertDialogOverlay>
            <AlertDialogContent>
              <AlertDialogHeader fontSize="lg" fontWeight="bold">
                Generate All Progressions
              </AlertDialogHeader>

              <AlertDialogBody>
                Do you want to overwrite existing progressions? If you choose "No", only missing progressions will be generated.
              </AlertDialogBody>

              <AlertDialogFooter>
                <Button 
                  ref={cancelRef} 
                  onClick={() => setIsGenerateAllDialogOpen(false)}
                  isDisabled={isGenerating}
                >
                  Cancel
                </Button>
                <Button
                  colorScheme="blue"
                  onClick={() => handleGenerateAll(false)}
                  ml={3}
                  isDisabled={isGenerating}
                  isLoading={isGenerating}
                >
                  No, Skip Existing
                </Button>
                <Button
                  colorScheme="red"
                  onClick={() => handleGenerateAll(true)}
                  ml={3}
                  isDisabled={isGenerating}
                  isLoading={isGenerating}
                >
                  Yes, Overwrite All
                </Button>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialogOverlay>
        </AlertDialog>
      </VStack>
    </Box>
  );
};