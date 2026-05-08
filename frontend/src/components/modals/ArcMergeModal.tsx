import React, { useState, useEffect, useMemo } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  Button,
  VStack,
  FormControl,
  FormLabel,
  Input,
  Textarea,
  Select,
  Box,
  Text,
  Grid,
  Badge,
  useColorModeValue,
  Tooltip,
} from '@chakra-ui/react';
import { ArcType } from '@/architecture/types/arc';
import type { NarrativeArc, ArcProgression } from '@/architecture/types';
import { ArcProgressionEditModal } from './ArcProgressionEditModal';

interface ArcMergeModalProps {
  isOpen: boolean;
  onClose: () => void;
  arc1: NarrativeArc;
  arc2: NarrativeArc;
  onMergeComplete: (mergedData: Partial<NarrativeArc>) => void;
}

interface ProgressionMapping {
  season: string;
  episode: string;
  content: string;
  interfering_characters: string[];
}

export const ArcMergeModal: React.FC<ArcMergeModalProps> = ({
  isOpen,
  onClose,
  arc1,
  arc2,
  onMergeComplete,
}) => {
  // State
  const [mergedTitle, setMergedTitle] = useState<string>(arc1.title);
  const [mergedDescription, setMergedDescription] = useState<string>(arc1.description);
  const [mergedArcType, setMergedArcType] = useState<ArcType>(arc1.arc_type as ArcType);
  const [mainCharacters, setMainCharacters] = useState<string[]>([]);
  const [progressionMappings, setProgressionMappings] = useState<Record<string, ProgressionMapping>>({});
  const [selectedProgression, setSelectedProgression] = useState<ProgressionMapping | null>(null);
  const [isProgressionModalOpen, setIsProgressionModalOpen] = useState(false);

  // Colors
  const arc1Color = useColorModeValue('blue.50', 'blue.900');
  const arc2Color = useColorModeValue('green.50', 'green.900');
  const mergedColor = useColorModeValue('purple.50', 'purple.900');

  // Get all episodes from both arcs
  const allEpisodes = useMemo(() => {
    const episodes = new Set<string>();
    [...arc1.progressions, ...arc2.progressions].forEach(prog => {
      episodes.add(`${prog.season}-${prog.episode}`);
    });
    return Array.from(episodes).sort((a, b) => {
      const [s1, e1] = a.split('-').map(x => parseInt(x.replace(/[SE]/g, '')));
      const [s2, e2] = b.split('-').map(x => parseInt(x.replace(/[SE]/g, '')));
      return s1 === s2 ? e1 - e2 : s1 - s2;
    });
  }, [arc1, arc2]);

  // Calculate episode width
  const episodeWidth = useMemo(() => {
    return `${100 / (allEpisodes.length + 1)}%`;
  }, [allEpisodes]);

  // Initialize state when modal opens
  useEffect(() => {
    if (isOpen) {
      // Combine main characters
      const uniqueCharacters = [...new Set([...arc1.main_characters, ...arc2.main_characters])];
      setMainCharacters(uniqueCharacters);

      // Initialize progression mappings
      const mappings: Record<string, ProgressionMapping> = {};
      allEpisodes.forEach(episode => {
        const [season, ep] = episode.split('-');
        const prog1 = arc1.progressions.find((p: ArcProgression) => p.season === season && p.episode === ep);
        const prog2 = arc2.progressions.find((p: ArcProgression) => p.season === season && p.episode === ep);
        
        if (prog1 || prog2) {
          mappings[episode] = {
            season,
            episode: ep,
            content: prog1?.content || prog2?.content || '',
            interfering_characters: [
              ...(prog1?.interfering_characters || []),
              ...(prog2?.interfering_characters || [])
            ]
          };
        }
      });
      setProgressionMappings(mappings);
    }
  }, [isOpen, arc1, arc2]);

  const handleMerge = () => {
    // Convert all progressions from both arcs into progression mappings
    const allProgressions = new Map<string, ProgressionMapping>();

    // Helper function to add progression to the map
    const addProgression = (prog: ArcProgression) => {
      const key = `${prog.season}-${prog.episode}`;
      if (!allProgressions.has(key)) {
        allProgressions.set(key, {
          season: prog.season,
          episode: prog.episode,
          content: prog.content,
          interfering_characters: prog.interfering_characters || []
        });
      }
    };

    // Add progressions from both arcs
    arc1.progressions.forEach(addProgression);
    arc2.progressions.forEach(addProgression);

    // Convert map to array and sort by season/episode
    const progressionMappingsArray = Array.from(allProgressions.values())
      .filter(mapping => mapping.content.trim() !== '')
      .sort((a, b) => {
        const seasonA = parseInt(a.season.replace('S', ''));
        const seasonB = parseInt(b.season.replace('S', ''));
        if (seasonA !== seasonB) return seasonA - seasonB;
        
        const episodeA = parseInt(a.episode.replace('E', ''));
        const episodeB = parseInt(b.episode.replace('E', ''));
        return episodeA - episodeB;
      });

    const mergedData = {
      arc_id_1: arc1.id,
      arc_id_2: arc2.id,
      merged_title: mergedTitle.trim(),
      merged_description: mergedDescription.trim(),
      merged_arc_type: mergedArcType,
      main_characters: mainCharacters,
      series: arc1.series,
      progression_mappings: progressionMappingsArray
    };

    onMergeComplete(mergedData);
  };

  const handleProgressionEdit = (episode: string) => {
    const [season, ep] = episode.split('-');
    const existingMapping = progressionMappings[episode];
    setSelectedProgression(existingMapping || {
      season,
      episode: ep,
      content: '',
      interfering_characters: []
    });
    setIsProgressionModalOpen(true);
  };

  const handleProgressionSave = (updatedProgression: ProgressionMapping) => {
    setProgressionMappings(prev => ({
      ...prev,
      [`${updatedProgression.season}-${updatedProgression.episode}`]: updatedProgression
    }));
    setIsProgressionModalOpen(false);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="6xl">
      <ModalOverlay />
      <ModalContent maxH="90vh" overflowY="auto">
        <ModalHeader>Merge Arcs</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <VStack spacing={6}>
            {/* Arc Details Section */}
            <Grid templateColumns="repeat(3, 1fr)" gap={4} width="100%">
              {/* Arc 1 */}
              <Box p={4} bg={arc1Color} borderRadius="md">
                <Text fontWeight="bold">{arc1.title}</Text>
                <Text fontSize="sm" mt={2}>{arc1.description}</Text>
                <Badge mt={2}>{arc1.arc_type}</Badge>
              </Box>

              {/* Merged Arc */}
              <Box p={4} bg={mergedColor} borderRadius="md">
                <FormControl>
                  <FormLabel>Title</FormLabel>
                  <Input
                    value={mergedTitle}
                    onChange={(e) => setMergedTitle(e.target.value)}
                  />
                </FormControl>

                <FormControl mt={4}>
                  <FormLabel>Description</FormLabel>
                  <Textarea
                    value={mergedDescription}
                    onChange={(e) => setMergedDescription(e.target.value)}
                    rows={3}
                  />
                </FormControl>

                <FormControl mt={4}>
                  <FormLabel>Arc Type</FormLabel>
                  <Select
                    value={mergedArcType}
                    onChange={(e) => setMergedArcType(e.target.value as ArcType)}
                  >
                    {Object.values(ArcType).map(type => (
                      <option key={type} value={type}>{type}</option>
                    ))}
                  </Select>
                </FormControl>
              </Box>

              {/* Arc 2 */}
              <Box p={4} bg={arc2Color} borderRadius="md">
                <Text fontWeight="bold">{arc2.title}</Text>
                <Text fontSize="sm" mt={2}>{arc2.description}</Text>
                <Badge mt={2}>{arc2.arc_type}</Badge>
              </Box>
            </Grid>

            {/* Timeline Section */}
            <Box width="100%" overflowX="auto">
              <Grid templateColumns={`200px repeat(${allEpisodes.length}, ${episodeWidth})`} gap={1}>
                {/* Header */}
                <Box p={2} bg="gray.100">Arc</Box>
                {allEpisodes.map(episode => {
                  const [season, ep] = episode.split('-');
                  return (
                    <Box key={episode} p={2} bg="gray.100" textAlign="center">
                      {season}-{ep}
                    </Box>
                  );
                })}

                {/* Arc 1 Row */}
                <Box p={2} bg={arc1Color}>
                  <Text fontWeight="bold">{arc1.title}</Text>
                </Box>
                {allEpisodes.map(episode => {
                  const [season, ep] = episode.split('-');
                  const prog = arc1.progressions.find((p: ArcProgression) => 
                    p.season === season && p.episode === ep
                  );
                  return (
                    <Box 
                      key={`arc1-${episode}`}
                      p={2}
                      bg={prog ? arc1Color : 'transparent'}
                      borderWidth={1}
                      minH="100px"
                    >
                      {prog && (
                        <Tooltip label={prog.content}>
                          <Text fontSize="xs" noOfLines={3}>
                            {prog.content}
                          </Text>
                        </Tooltip>
                      )}
                    </Box>
                  );
                })}

                {/* Arc 2 Row */}
                <Box p={2} bg={arc2Color}>
                  <Text fontWeight="bold">{arc2.title}</Text>
                </Box>
                {allEpisodes.map(episode => {
                  const [season, ep] = episode.split('-');
                  const prog = arc2.progressions.find((p: ArcProgression) => 
                    p.season === season && p.episode === ep
                  );
                  return (
                    <Box 
                      key={`arc2-${episode}`}
                      p={2}
                      bg={prog ? arc2Color : 'transparent'}
                      borderWidth={1}
                      minH="100px"
                    >
                      {prog && (
                        <Tooltip label={prog.content}>
                          <Text fontSize="xs" noOfLines={3}>
                            {prog.content}
                          </Text>
                        </Tooltip>
                      )}
                    </Box>
                  );
                })}

                {/* Merged Row */}
                <Box p={2} bg={mergedColor}>
                  <Text fontWeight="bold">Merged</Text>
                </Box>
                {allEpisodes.map(episode => {
                  const mapping = progressionMappings[episode];
                  return (
                    <Box 
                      key={`merged-${episode}`}
                      p={2}
                      bg={mapping ? mergedColor : 'transparent'}
                      borderWidth={1}
                      minH="100px"
                      cursor="pointer"
                      onClick={() => handleProgressionEdit(episode)}
                    >
                      {mapping && (
                        <Tooltip label={mapping.content}>
                          <Text fontSize="xs" noOfLines={3}>
                            {mapping.content}
                          </Text>
                        </Tooltip>
                      )}
                    </Box>
                  );
                })}
              </Grid>
            </Box>
          </VStack>
        </ModalBody>

        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={onClose}>
            Cancel
          </Button>
          <Button 
            colorScheme="blue" 
            onClick={handleMerge}
            isDisabled={!mergedTitle.trim() || !mergedDescription.trim()}
          >
            Merge Arcs
          </Button>
        </ModalFooter>
      </ModalContent>

      {/* Progression Edit Modal */}
      <ArcProgressionEditModal
        isOpen={isProgressionModalOpen}
        onClose={() => setIsProgressionModalOpen(false)}
        progression={selectedProgression}
        onSave={handleProgressionSave}
        availableCharacters={[...new Set([...arc1.main_characters, ...arc2.main_characters])]}
        arcId={arc1.id}
        series={arc1.series}
      />
    </Modal>
  );
}; 