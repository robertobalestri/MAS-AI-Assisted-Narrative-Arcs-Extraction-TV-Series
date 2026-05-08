import React, { useState } from 'react';
import {
  Box,
  VStack,
  Text,
  Button,
  Badge,
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
  FormControl,
  FormLabel,
  RadioGroup,
  Radio,
  Stack,
} from '@chakra-ui/react';
import type { Character } from '@/architecture/types';
import styles from '@/styles/components/SimilarCharactersPanel.module.css';

interface SimilarCharacterPair {
  character1: Character;
  character2: Character;
  similarity: number;
}

interface SimilarCharactersPanelProps {
  similarCharacters: SimilarCharacterPair[];
  onMergeCharacters: (char1: Character, char2: Character, keepCharacter: 'character1' | 'character2') => void;
  onThresholdChange?: (threshold: number) => void;
}

export const SimilarCharactersPanel: React.FC<SimilarCharactersPanelProps> = ({
  similarCharacters,
  onMergeCharacters,
  onThresholdChange,
}) => {
  const [threshold, setThreshold] = useState(0.5);
  const [selectedCharacter, setSelectedCharacter] = useState<'character1' | 'character2'>('character1');

  const handleThresholdChange = (value: number) => {
    setThreshold(value);
    if (onThresholdChange) {
      onThresholdChange(value);
    }
  };

  return (
    <Box className={styles.similarCharactersPanel}>
      <VStack spacing={4} align="stretch">
        <Text fontSize="lg" fontWeight="bold">
          Similar Characters
        </Text>

        <FormControl>
          <FormLabel fontSize="sm">
            Similarity Threshold: {(threshold * 100).toFixed(0)}%
          </FormLabel>
          <Slider
            value={threshold}
            min={0.1}
            max={0.9}
            step={0.1}
            onChange={handleThresholdChange}
            mb={4}
          >
            <SliderTrack>
              <SliderFilledTrack />
            </SliderTrack>
            <SliderThumb />
          </Slider>
        </FormControl>

        {similarCharacters.length === 0 ? (
          <Text color="gray.500">No similar characters found</Text>
        ) : (
          <VStack spacing={4} align="stretch">
            {similarCharacters
              .filter(pair => pair.similarity >= threshold)
              .map((pair, index) => (
                <Box key={index} className={styles.warningBox}>
                  <Text fontWeight="bold" mb={2}>
                    Possible Character Match
                    <Badge ml={2} colorScheme="yellow" className={styles.similarityScore}>
                      {(pair.similarity * 100).toFixed(1)}% Similar
                    </Badge>
                  </Text>
                  
                  <Box className={styles.characterInfo}>
                    <Text fontWeight="bold">{pair.character1.best_appellation}</Text>
                    <Text fontSize="sm">
                      Appellations: {pair.character1.appellations.join(', ')}
                    </Text>
                  </Box>
                  
                  <Box className={styles.characterInfo}>
                    <Text fontWeight="bold">{pair.character2.best_appellation}</Text>
                    <Text fontSize="sm">
                      Appellations: {pair.character2.appellations.join(', ')}
                    </Text>
                  </Box>
                  
                  <RadioGroup
                    value={selectedCharacter}
                    onChange={(value: 'character1' | 'character2') => setSelectedCharacter(value)}
                    mb={3}
                  >
                    <Stack>
                      <Radio value="character1">
                        Keep "{pair.character1.best_appellation}"
                      </Radio>
                      <Radio value="character2">
                        Keep "{pair.character2.best_appellation}"
                      </Radio>
                    </Stack>
                  </RadioGroup>
                  
                  <Button
                    size="sm"
                    colorScheme="yellow"
                    onClick={() => onMergeCharacters(
                      pair.character1,
                      pair.character2,
                      selectedCharacter
                    )}
                  >
                    Merge Characters
                  </Button>
                </Box>
              ))}
          </VStack>
        )}
      </VStack>
    </Box>
  );
}; 