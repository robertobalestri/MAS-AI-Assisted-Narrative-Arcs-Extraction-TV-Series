import React, { useState } from 'react';
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
  HStack,
  Tag,
  TagLabel,
  TagCloseButton,
  useToast,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
} from '@chakra-ui/react';
import { ArcType } from '@/architecture/types';
import type { ArcProgression, Episode, CreateArcData } from '@/architecture/types';
import { StarIcon } from '@chakra-ui/icons';
import { ApiClient } from '@/services/api/ApiClient';

interface NewArcModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (arcData: CreateArcData) => void;
  availableCharacters: string[];
  series: string;
  episodes: Episode[];
}

export const NewArcModal: React.FC<NewArcModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  availableCharacters,
  series,
  episodes,
}) => {
  const toast = useToast();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [arcType, setArcType] = useState<ArcType>(ArcType.SoapArc);
  const [mainCharacters, setMainCharacters] = useState<string[]>([]);
  const [progressionContent, setProgressionContent] = useState('');
  const [progressionSeason, setProgressionSeason] = useState('');
  const [progressionEpisode, setProgressionEpisode] = useState('');
  const [interferingCharacters, setInterferingCharacters] = useState<string[]>([]);
  const [isGeneratingAll, setIsGeneratingAll] = useState(false);
  const api = new ApiClient();
  const [, setActiveTab] = useState(0);

  const handleSubmit = () => {
    const initialProgression: Omit<Partial<ArcProgression>, 'id'> = {
      content: progressionContent,
      season: `S${progressionSeason.padStart(2, '0')}`,
      episode: `E${progressionEpisode.padStart(2, '0')}`,
      interfering_characters: interferingCharacters,
      series: series,
      ordinal_position: parseInt(progressionEpisode)
    };

    const arcData: CreateArcData = {
      title: title.trim(),
      description: description.trim(),
      arc_type: arcType,
      main_characters: mainCharacters,
      series,
      progressions: [initialProgression]
    };

    onSubmit(arcData);
    resetForm();
  };

  const resetForm = () => {
    setTitle('');
    setDescription('');
    setArcType(ArcType.SoapArc);
    setMainCharacters([]);
    setProgressionContent('');
    setProgressionSeason('');
    setProgressionEpisode('');
    setInterferingCharacters([]);
  };

  const isFormValid = (): boolean => {
    return (
      title.trim() !== '' &&
      description.trim() !== '' &&
      progressionContent.trim() !== '' &&
      progressionSeason !== '' &&
      progressionEpisode !== ''
    );
  };

  const handleCharacterSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedChar = e.target.value;
    if (selectedChar && !mainCharacters.includes(selectedChar)) {
      setMainCharacters([...mainCharacters, selectedChar]);
    }
  };

  const handleInterferingCharacterSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedChar = e.target.value;
    if (selectedChar && !interferingCharacters.includes(selectedChar)) {
      setInterferingCharacters([...interferingCharacters, selectedChar]);
    }
  };

  const handleGenerateContent = async () => {
    if (!progressionSeason || !progressionEpisode || !title || !description || !series) return;

    try {
      const response = await api.generateProgression(
        null,
        series,
        `S${progressionSeason.padStart(2, '0')}`,
        `E${progressionEpisode.padStart(2, '0')}`,
        title,
        description
      );

      if (!('error' in response)) {
        setProgressionContent(response.content);
        setInterferingCharacters(response.interfering_characters);
        toast({
          title: 'Content generated',
          description: 'AI has generated progression content and characters',
          status: 'success',
          duration: 3000,
        });
      }
    } catch (error) {
      toast({
        title: 'Error generating content',
        description: error instanceof Error ? error.message : 'Failed to generate content',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const handleGenerateAllProgressions = async () => {
    if (!title || !description || !progressionSeason) {
      toast({
        title: 'Missing Information',
        description: 'Please fill in the title, description, and season first',
        status: 'warning',
        duration: 3000,
      });
      return;
    }

    setIsGeneratingAll(true);
    const loadingToast = toast({
      title: 'Generating progressions',
      description: 'This may take a few minutes...',
      status: 'info',
      duration: null,
      isClosable: true,
    });

    try {
      const seasonEpisodes = episodes
        .filter(ep => ep.season === `S${progressionSeason.padStart(2, '0')}`)
        .sort((a, b) => parseInt(a.episode.replace('E', '')) - parseInt(b.episode.replace('E', '')));

      console.log('Processing episodes:', seasonEpisodes);
      const allProgressions: Omit<Partial<ArcProgression>, 'id'>[] = [];
      let generatedCount = 0;
      const noProgressionCount = 0;
      let errorCount = 0;

      for (const ep of seasonEpisodes) {
        console.log(`Generating for episode ${ep.season}${ep.episode}`);
        const response = await api.generateProgression(
          null,
          series,
          ep.season,
          ep.episode,
          title,
          description
        );

        if ('error' in response) {
          console.warn(`Error for episode ${ep.episode}:`, response.error);
          errorCount++;
          continue;
        }

        allProgressions.push({
          content: response.content,
          season: ep.season,
          episode: ep.episode,
          series,
          ordinal_position: parseInt(ep.episode.replace('E', '')),
          interfering_characters: response.interfering_characters
        });
        generatedCount++;
        console.log(`Added progression for episode ${ep.episode}, total now: ${allProgressions.length}`);

        toast.update(loadingToast, {
          description: `Processing episode ${ep.episode}... (${generatedCount} generated, ${noProgressionCount} skipped, ${errorCount} errors)`,
        });
      }

      if (allProgressions.length > 0) {
        console.log(`Creating arc with ${allProgressions.length} progressions`);
        const arcData: CreateArcData = {
          title: title.trim(),
          description: description.trim(),
          arc_type: arcType,
          main_characters: mainCharacters,
          series,
          progressions: allProgressions
        };

        console.log('Submitting arc data:', arcData);
        toast.close(loadingToast);
        toast({
          title: 'Generation Complete',
          description: `Generated ${generatedCount} progressions, ${noProgressionCount} skipped, ${errorCount} errors`,
          status: 'success',
          duration: 5000,
        });

        onSubmit(arcData);
        resetForm();
      } else {
        toast({
          title: 'No Progressions Generated',
          description: `No valid progressions found (${noProgressionCount} skipped, ${errorCount} errors)`,
          status: 'warning',
          duration: 5000,
        });
      }

    } catch (error) {
      toast.close(loadingToast);
      toast({
        title: 'Error generating progressions',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsGeneratingAll(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>Create New Arc</ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <VStack spacing={4}>
            <FormControl isRequired>
              <FormLabel>Title</FormLabel>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Enter arc title"
              />
            </FormControl>

            <FormControl isRequired>
              <FormLabel>Description</FormLabel>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Enter arc description"
                rows={4}
              />
            </FormControl>

            <FormControl isRequired>
              <FormLabel>Arc Type</FormLabel>
              <Select
                value={arcType}
                onChange={(e) => setArcType(e.target.value as ArcType)}
              >
                {Object.values(ArcType).map((type) => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel>Main Characters</FormLabel>
              <Select
                placeholder="Select characters"
                onChange={handleCharacterSelect}
                value=""
              >
                {availableCharacters
                  .filter(char => !mainCharacters.includes(char))
                  .map(char => (
                    <option key={char} value={char}>
                      {char}
                    </option>
                  ))}
              </Select>
              {mainCharacters.length > 0 && (
                <Box mt={2}>
                  <HStack spacing={2} wrap="wrap">
                    {mainCharacters.map(char => (
                      <Tag
                        key={char}
                        size="md"
                        variant="solid"
                        colorScheme="blue"
                        cursor="pointer"
                      >
                        <TagLabel>{char}</TagLabel>
                        <TagCloseButton 
                          onClick={() => setMainCharacters(prev => 
                            prev.filter(c => c !== char)
                          )}
                        />
                      </Tag>
                    ))}
                  </HStack>
                </Box>
              )}
            </FormControl>

            <Box width="100%" borderWidth={1} borderRadius="md" p={4}>
              <Tabs onChange={setActiveTab} variant="enclosed">
                <TabList>
                  <Tab>Single Progression</Tab>
                  <Tab>AI Generate All</Tab>
                </TabList>

                <TabPanels>
                  <TabPanel>
                    <VStack spacing={4}>
                      <FormControl isRequired>
                        <FormLabel>Season</FormLabel>
                        <Input
                          placeholder="Enter season number (e.g., 1)"
                          value={progressionSeason}
                          onChange={(e) => {
                            const value = e.target.value.replace(/\D/g, '');
                            setProgressionSeason(value);
                          }}
                        />
                      </FormControl>

                      <FormControl isRequired>
                        <FormLabel>Episode</FormLabel>
                        <Input
                          placeholder="Enter episode number (e.g., 1)"
                          value={progressionEpisode}
                          onChange={(e) => {
                            const value = e.target.value.replace(/\D/g, '');
                            setProgressionEpisode(value);
                          }}
                        />
                      </FormControl>

                      <FormControl isRequired>
                        <FormLabel>Content</FormLabel>
                        <VStack width="100%" spacing={2}>
                          <Textarea
                            value={progressionContent}
                            onChange={(e) => setProgressionContent(e.target.value)}
                            placeholder="Enter progression content"
                            rows={4}
                          />
                          <Button
                            colorScheme="purple"
                            width="100%"
                            leftIcon={<StarIcon />}
                            isDisabled={!progressionSeason || !progressionEpisode || !title || !description}
                            onClick={handleGenerateContent}
                            size="sm"
                          >
                            Generate with AI
                          </Button>
                        </VStack>
                      </FormControl>

                      <FormControl>
                        <FormLabel>Interfering Characters</FormLabel>
                        <Select
                          placeholder="Select characters"
                          onChange={handleInterferingCharacterSelect}
                          value=""
                        >
                          {availableCharacters.map(char => (
                            <option key={char} value={char}>
                              {char}
                            </option>
                          ))}
                        </Select>
                        {interferingCharacters.length > 0 && (
                          <Box mt={2}>
                            <HStack spacing={2} wrap="wrap">
                              {interferingCharacters.map(char => (
                                <Tag
                                  key={char}
                                  size="md"
                                  variant="solid"
                                  colorScheme="purple"
                                >
                                  <TagLabel>{char}</TagLabel>
                                  <TagCloseButton 
                                    onClick={() => setInterferingCharacters(prev => 
                                      prev.filter(c => c !== char)
                                    )}
                                  />
                                </Tag>
                              ))}
                            </HStack>
                          </Box>
                        )}
                      </FormControl>
                    </VStack>
                  </TabPanel>

                  <TabPanel>
                    <VStack spacing={4}>
                      <FormControl isRequired>
                        <FormLabel>Season</FormLabel>
                        <Input
                          placeholder="Enter season number (e.g., 1)"
                          value={progressionSeason}
                          onChange={(e) => {
                            const value = e.target.value.replace(/\D/g, '');
                            setProgressionSeason(value);
                          }}
                        />
                      </FormControl>

                      <Button
                        colorScheme="purple"
                        width="100%"
                        leftIcon={<StarIcon />}
                        isDisabled={!progressionSeason || !title || !description}
                        onClick={handleGenerateAllProgressions}
                        isLoading={isGeneratingAll}
                      >
                        Generate All Progressions for Season {progressionSeason}
                      </Button>
                    </VStack>
                  </TabPanel>
                </TabPanels>
              </Tabs>
            </Box>
          </VStack>
        </ModalBody>

        <ModalFooter>
          <Button variant="ghost" mr={3} onClick={onClose}>
            Cancel
          </Button>
          <Button 
            colorScheme="blue" 
            onClick={handleSubmit}
            isDisabled={!isFormValid()}
          >
            Create Arc
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}; 