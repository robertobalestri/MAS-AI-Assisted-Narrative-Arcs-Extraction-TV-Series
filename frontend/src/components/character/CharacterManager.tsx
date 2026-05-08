import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  IconButton,
  useDisclosure,
  useToast,
  Badge,
  useColorModeValue,
  Grid,
} from '@chakra-ui/react';
import { AddIcon, EditIcon, DeleteIcon } from '@chakra-ui/icons';
import { useApi } from '@/hooks/useApi';
import { ApiClient } from '@/services/api/ApiClient';
import type { Character } from '@/architecture/types';
import { CharacterEditModal } from './CharacterEditModal';
import { SimilarCharactersPanel } from './SimilarCharactersPanel';
import styles from '@/styles/components/Character.module.css';

interface CharacterManagerProps {
  series: string;
  onCharacterUpdated?: () => void;
}

interface SimilarCharacterPair {
  character1: Character;
  character2: Character;
  similarity: number;
}

export const CharacterManager: React.FC<CharacterManagerProps> = ({
  series,
  onCharacterUpdated,
}) => {
  // State
  const [characters, setCharacters] = useState<Character[]>([]);
  const [editingCharacter, setEditingCharacter] = useState<Character | null>(null);
  const [newAppellation, setNewAppellation] = useState('');
  const [entityName, setEntityName] = useState('');
  const [bestAppellation, setBestAppellation] = useState('');
  const [appellations, setAppellations] = useState<string[]>([]);
  const [similarCharacters, setSimilarCharacters] = useState<SimilarCharacterPair[]>([]);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.5);

  // Hooks
  const toast = useToast();
  const { request } = useApi();
  const api = new ApiClient();
  const { isOpen, onOpen, onClose } = useDisclosure();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  // Fetch characters on mount
  useEffect(() => {
    if (series) {
      fetchCharacters();
    }
  }, [series]);

  // API calls
  const fetchCharacters = async () => {
    try {
      const response = await request(() => api.getCharacters(series));
      if (response && Array.isArray(response)) {
        setCharacters(response as Character[]);
        if (onCharacterUpdated) {
          onCharacterUpdated();
        }
      }
    } catch (error) {
      toast({
        title: 'Error fetching characters',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const handleAddCharacter = () => {
    setEditingCharacter(null);
    setEntityName('');
    setBestAppellation('');
    setAppellations([]);
    onOpen();
  };

  const handleEditCharacter = (character: Character) => {
    setEditingCharacter(character);
    setEntityName(character.entity_name);
    setBestAppellation(character.best_appellation);
    setAppellations(character.appellations);
    onOpen();
  };

  const handleSubmit = async () => {
    const characterData = {
      entity_name: entityName,
      best_appellation: bestAppellation,
      series,
      appellations,
    };

    try {
      const response = await request(() =>
        editingCharacter
          ? api.updateCharacter(series, characterData)
          : api.createCharacter(series, characterData)
      );

      if (response) {
        toast({
          title: 'Success',
          description: `Character ${editingCharacter ? 'updated' : 'created'} successfully`,
          status: 'success',
          duration: 3000,
        });
        fetchCharacters();
        onClose();
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      if (errorMessage.includes('UNIQUE constraint failed')) {
        toast({
          title: 'Error',
          description: 'One or more appellations are already used by another character.',
          status: 'error',
          duration: 5000,
        });
      } else {
        toast({
          title: 'Error',
          description: errorMessage,
          status: 'error',
          duration: 5000,
        });
      }
    }
  };

  const handleDeleteCharacter = async (character: Character) => {
    try {
      await request(() => api.deleteCharacter(series, character.entity_name));
      fetchCharacters();
      toast({
        title: 'Character deleted',
        status: 'success',
        duration: 3000,
      });
    } catch (error) {
      toast({
        title: 'Error deleting character',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const handleMergeCharacters = async (
    char1: Character,
    char2: Character,
    keepCharacter: 'character1' | 'character2'
  ) => {
    try {
      await request(() =>
        api.mergeCharacters(
          series,
          {
            character1_id: char1.entity_name,
            character2_id: char2.entity_name,
            keep_character: keepCharacter
          }
        )
      );
      
      fetchCharacters(); // Refresh the character list
      toast({
        title: 'Characters merged',
        description: `Successfully merged into "${keepCharacter === 'character1' ? char1.best_appellation : char2.best_appellation}"`,
        status: 'success',
        duration: 3000,
      });
    } catch (error) {
      toast({
        title: 'Error merging characters',
        description: error instanceof Error ? error.message : 'Unknown error',
        status: 'error',
        duration: 5000,
      });
    }
  };

  const calculateSimilarCharacters = useCallback(() => {
    const similarPairs: SimilarCharacterPair[] = [];
    const threshold = similarityThreshold;

    for (let i = 0; i < characters.length; i++) {
      for (let j = i + 1; j < characters.length; j++) {
        const char1 = characters[i];
        const char2 = characters[j];

        // Create arrays of all possible names for each character
        const names1 = [
          char1.entity_name.toLowerCase(),
          char1.best_appellation.toLowerCase(),
          ...char1.appellations.map(a => a.toLowerCase())
        ];
        const names2 = [
          char2.entity_name.toLowerCase(),
          char2.best_appellation.toLowerCase(),
          ...char2.appellations.map(a => a.toLowerCase())
        ];

        // Calculate maximum similarity between any pair of names
        let maxSimilarity = 0;
        for (const name1 of names1) {
          for (const name2 of names2) {
            // Calculate Jaccard similarity for individual words
            const words1 = new Set(name1.split(/[\s-]+/));
            const words2 = new Set(name2.split(/[\s-]+/));
            
            const intersection = new Set([...words1].filter(x => words2.has(x)));
            const union = new Set([...words1, ...words2]);
            
            const similarity = intersection.size / union.size;
            maxSimilarity = Math.max(maxSimilarity, similarity);
          }
        }

        if (maxSimilarity >= threshold) {
          console.log(`Found similar characters: ${char1.best_appellation} and ${char2.best_appellation} with similarity ${maxSimilarity}`);
          similarPairs.push({
            character1: char1,
            character2: char2,
            similarity: maxSimilarity
          });
        }
      }
    }

    // Sort by similarity in descending order
    similarPairs.sort((a, b) => b.similarity - a.similarity);
    setSimilarCharacters(similarPairs);
  }, [characters, similarityThreshold]);

  useEffect(() => {
    if (characters.length > 0) {
      calculateSimilarCharacters();
    }
  }, [characters, calculateSimilarCharacters]);

  const handleThresholdChange = (newThreshold: number) => {
    setSimilarityThreshold(newThreshold);
  };

  return (
    <Box p={4}>
      <Grid templateColumns="1fr 300px" gap={4}>
        {/* Left side - Character List */}
        <VStack spacing={4} align="stretch">
          {/* Action Bar */}
          <HStack justify="space-between" mb={4}>
            <Text fontSize="lg" fontWeight="bold">Characters</Text>
            <HStack spacing={2}>
              <Button
                leftIcon={<AddIcon />}
                colorScheme="green"
                onClick={handleAddCharacter}
                size="sm"
              >
                Add Character
              </Button>
            </HStack>
          </HStack>

          {/* Character Grid */}
          <Box className={styles.characterGrid}>
            {characters.map((character) => (
              <Box
                key={character.entity_name}
                className={styles.characterCard}
                bg={bgColor}
                borderColor={borderColor}
                _hover={{ shadow: 'md', transform: 'translateY(-2px)' }}
                transition="all 0.2s"
              >
                <HStack justify="space-between" mb={3}>
                  <Text fontWeight="bold" fontSize="lg">
                    {character.best_appellation}
                  </Text>
                  <HStack spacing={2}>
                    <IconButton
                      aria-label="Edit character"
                      icon={<EditIcon />}
                      size="sm"
                      variant="ghost"
                      onClick={() => handleEditCharacter(character)}
                    />
                    <IconButton
                      aria-label="Delete character"
                      icon={<DeleteIcon />}
                      size="sm"
                      variant="ghost"
                      colorScheme="red"
                      onClick={() => handleDeleteCharacter(character)}
                    />
                  </HStack>
                </HStack>

                <Text fontSize="sm" color="gray.500" mb={3}>
                  Entity: {character.entity_name}
                </Text>

                <Box className={styles.appellationList}>
                  {character.appellations.map((appellation) => (
                    <Badge
                      key={appellation}
                      colorScheme="blue"
                      variant="subtle"
                      px={2}
                      py={1}
                      borderRadius="full"
                    >
                      {appellation}
                    </Badge>
                  ))}
                </Box>
              </Box>
            ))}
          </Box>
        </VStack>

        {/* Right side - Similar Characters Panel */}
        <Box>
          <SimilarCharactersPanel
            similarCharacters={similarCharacters}
            onMergeCharacters={handleMergeCharacters}
            onThresholdChange={handleThresholdChange}
          />
        </Box>
      </Grid>

      {/* Modals */}
      <CharacterEditModal
        isOpen={isOpen}
        onClose={onClose}
        onSubmit={handleSubmit}
        onDeleteCharacter={handleDeleteCharacter}
        onMergeCharacters={handleMergeCharacters}
        character={editingCharacter}
        entityName={entityName}
        bestAppellation={bestAppellation}
        appellations={appellations}
        newAppellation={newAppellation}
        setEntityName={setEntityName}
        setBestAppellation={setBestAppellation}
        setAppellations={setAppellations}
        setNewAppellation={setNewAppellation}
      />
    </Box>
  );
}; 