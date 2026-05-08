import React from 'react';
import {
  Box,
  VStack,
  HStack,
  FormControl,
  FormLabel,
  Switch,
  Select,
  Checkbox,
  Text,
  SimpleGrid,
  useColorModeValue,
} from '@chakra-ui/react';
import type { Episode } from '@/architecture/types';
import { ArcType } from '@/architecture/types/arc';
import styles from '@/styles/components/ArcFilters.module.css';

interface ArcFiltersProps {
  seasons: string[];
  selectedSeason: string;
  onSeasonChange: (season: string) => void;
  selectedEpisode: string;
  onEpisodeChange: (episode: string) => void;
  allCharacters: string[];
  selectedCharacters: string[];
  setSelectedCharacters: (characters: string[]) => void;
  includeInterferingCharacters: boolean;
  setIncludeInterferingCharacters: (include: boolean) => void;
  episodes: Episode[];
  selectedArcTypes: ArcType[];
  setSelectedArcTypes: (types: ArcType[]) => void;
}

export const ArcFilters: React.FC<ArcFiltersProps> = ({
  seasons,
  selectedSeason,
  onSeasonChange,
  selectedEpisode,
  onEpisodeChange,
  allCharacters,
  selectedCharacters,
  setSelectedCharacters,
  includeInterferingCharacters,
  setIncludeInterferingCharacters,
  episodes,
  selectedArcTypes,
  setSelectedArcTypes,
}) => {
  const seasonEpisodes = episodes
    .filter(ep => ep.season === selectedSeason)
    .map(ep => ep.episode)
    .sort();

  const bgColor = useColorModeValue('white', 'gray.800');

  const arcTypeColors = {
    [ArcType.SoapArc]: '#F687B3',
    [ArcType.GenreSpecificArc]: '#ED8936',
    [ArcType.AnthologyArc]: '#48BB78',
  };

  return (
    <div className={styles.filtersGrid}>
      <Box className={styles.filterBox} bg={bgColor}>
        <VStack spacing={3} align="stretch">
          <Text className={styles.filterTitle}>Episode Selection</Text>
          <HStack spacing={4}>
            <FormControl size="sm">
              <FormLabel fontSize="xs">Season</FormLabel>
              <Select
                size="sm"
                value={selectedSeason}
                onChange={(e) => onSeasonChange(e.target.value)}
              >
                {seasons.map(season => (
                  <option key={season} value={season}>
                    Season {season.replace('S', '')}
                  </option>
                ))}
              </Select>
            </FormControl>

            <FormControl size="sm">
              <FormLabel fontSize="xs">Episode</FormLabel>
              <Select
                size="sm"
                value={selectedEpisode}
                onChange={(e) => onEpisodeChange(e.target.value)}
                placeholder="All Episodes"
              >
                {seasonEpisodes.map(episode => (
                  <option key={episode} value={episode}>
                    Episode {episode.replace('E', '')}
                  </option>
                ))}
              </Select>
            </FormControl>
          </HStack>
        </VStack>
      </Box>

      <Box 
        p={4} 
        borderWidth={1} 
        borderRadius="md" 
        bg={bgColor}
        shadow="sm"
      >
        <VStack spacing={3} align="stretch">
          <Text fontWeight="bold" fontSize="sm">Arc Types</Text>
          <SimpleGrid columns={1} spacing={2}>
            {Object.values(ArcType).map(type => (
              <Checkbox
                key={type}
                size="sm"
                isChecked={selectedArcTypes.includes(type)}
                onChange={(e) => {
                  if (e.target.checked) {
                    setSelectedArcTypes([...selectedArcTypes, type]);
                  } else {
                    setSelectedArcTypes(selectedArcTypes.filter(t => t !== type));
                  }
                }}
              >
                <HStack spacing={2} align="center">
                  <Box
                    w="3"
                    h="3"
                    borderRadius="full"
                    bg={arcTypeColors[type]}
                  />
                  <Text fontSize="sm">{type}</Text>
                </HStack>
              </Checkbox>
            ))}
          </SimpleGrid>
        </VStack>
      </Box>

      <Box 
        p={4} 
        borderWidth={1} 
        borderRadius="md" 
        bg={bgColor}
        shadow="sm"
      >
        <VStack spacing={3} align="stretch">
          <Text fontWeight="bold" fontSize="sm">Character Filter</Text>
          <Box 
            maxH="120px" 
            overflowY="auto" 
            borderWidth={1} 
            borderRadius="md" 
            p={2}
          >
            <VStack align="start" spacing={1}>
              {allCharacters.map(char => (
                <Checkbox
                  key={char}
                  size="sm"
                  isChecked={selectedCharacters.includes(char)}
                  onChange={(e) => {
                    if (e.target.checked) {
                      setSelectedCharacters([...selectedCharacters, char]);
                    } else {
                      setSelectedCharacters(selectedCharacters.filter(c => c !== char));
                    }
                  }}
                >
                  <Text fontSize="sm">{char}</Text>
                </Checkbox>
              ))}
            </VStack>
          </Box>
          <FormControl>
            <HStack spacing={2} align="center">
              <Switch
                size="sm"
                id="include-interfering"
                isChecked={includeInterferingCharacters}
                onChange={(e) => setIncludeInterferingCharacters(e.target.checked)}
              />
              <FormLabel htmlFor="include-interfering" fontSize="xs" mb={0}>
                Include Interfering Characters
              </FormLabel>
            </HStack>
          </FormControl>
        </VStack>
      </Box>
    </div>
  );
}; 