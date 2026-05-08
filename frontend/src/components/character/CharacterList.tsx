import React, { useState } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  IconButton,
  useDisclosure,
  useToast,
  Badge,
} from '@chakra-ui/react';
import { EditIcon, DeleteIcon } from '@chakra-ui/icons';
import type { Character } from '@/architecture/types';
import { useApi } from '@/hooks/useApi';
import { ApiClient } from '@/services/api/ApiClient';

interface CharacterListProps {
  series: string;
  characters: Character[];
  onCharacterUpdated: () => void;
}

export const CharacterList: React.FC<CharacterListProps> = ({
  series,
  characters,
  onCharacterUpdated,
}) => {
  const toast = useToast();
  const { request } = useApi();
  const api = new ApiClient();

  // Modals
  const {
    onOpen: openEditModal,
  } = useDisclosure();

  // State
  const [selectedCharacter, setSelectedCharacter] = useState<Character | null>(null);

  // Handlers
  const handleEdit = (character: Character) => {
    setSelectedCharacter(character);
    openEditModal();
  };

  const handleDelete = async (character: Character) => {
    if (window.confirm(`Are you sure you want to delete ${character.best_appellation}?`)) {
      try {
        await request(() => api.deleteCharacter(series, character.entity_name));
        toast({
          title: 'Character deleted',
          status: 'success',
          duration: 3000,
        });
        onCharacterUpdated();
      } catch (error) {
        toast({
          title: 'Error deleting character',
          description: error instanceof Error ? error.message : 'Unknown error',
          status: 'error',
          duration: 5000,
        });
      }
    }
  };


  return (
    <VStack spacing={4} align="stretch">
      {characters.map((character) => (
        <Box
          key={character.entity_name}
          p={4}
          borderWidth={1}
          borderRadius="md"
          position="relative"
        >
          <HStack justify="space-between">
            <VStack align="start" spacing={1}>
              <Text fontWeight="bold">{character.best_appellation}</Text>
              <HStack>
                {character.appellations.map((appellation) => (
                  <Badge key={appellation} colorScheme="blue">
                    {appellation}
                  </Badge>
                ))}
              </HStack>
            </VStack>
            <HStack>
              <IconButton
                aria-label="Edit character"
                icon={<EditIcon />}
                size="sm"
                onClick={() => handleEdit(character)}
              />
              <IconButton
                aria-label="Delete character"
                icon={<DeleteIcon />}
                size="sm"
                colorScheme="red"
                onClick={() => handleDelete(character)}
              />
            </HStack>
          </HStack>
        </Box>
      ))}

      {selectedCharacter && (
        <Box p={4} borderWidth={1} borderRadius="md">
          <Text fontWeight="medium">Editing is handled in the character manager panel.</Text>
        </Box>
      )}
    </VStack>
  );
}; 