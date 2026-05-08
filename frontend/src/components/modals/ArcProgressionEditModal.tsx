import React, { useState, useEffect } from 'react';
import {
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  Button,
  FormControl,
  FormLabel,
  Textarea,
  VStack,
  Box,
  Checkbox,
  Text,
  useColorModeValue,
  useToast,
  HStack,
  Badge,
} from '@chakra-ui/react';
import { DeleteIcon, StarIcon } from '@chakra-ui/icons';
import { isApiSuccess } from '@/architecture/types/api';
import type { ProgressionMapping } from '@/architecture/types';
import { ApiClient } from '@/services/api/ApiClient';

interface ArcProgressionEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  progression: ProgressionMapping | null;
  onSave: (updatedProgression: ProgressionMapping) => void;
  onDelete?: () => void;
  availableCharacters: string[];
  arcId: string;
  series: string;
}

export const ArcProgressionEditModal: React.FC<ArcProgressionEditModalProps> = ({
  isOpen,
  onClose,
  progression,
  onSave,
  onDelete,
  availableCharacters,
  arcId,
  series,
}) => {
  const [content, setContent] = useState('');
  const [interferingCharacters, setInterferingCharacters] = useState<string[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [arcTitle, setArcTitle] = useState<string>('');
  const bgColor = useColorModeValue('gray.50', 'gray.700');
  const toast = useToast();
  const api = new ApiClient();

  useEffect(() => {
    if (progression) {
      setContent(progression.content);
      setInterferingCharacters(progression.interfering_characters || []);
    }
  }, [progression]);

  useEffect(() => {
    // Fetch arc title when modal opens
    const fetchArcTitle = async () => {
      if (arcId) {
        try {
          const response = await api.getArcById(arcId);
          if (isApiSuccess(response)) {
            setArcTitle(response.data.title);
          }
        } catch (error) {
          console.error('Error fetching arc title:', error);
        }
      }
    };

    if (isOpen) {
      fetchArcTitle();
    }
  }, [isOpen, arcId]);

  const handleSave = () => {
    if (progression) {
      onSave({
        ...progression,
        content,
        interfering_characters: interferingCharacters,
      });
    }
  };

  const handleGenerate = async () => {
    if (!progression || !arcId || !series) {
      console.log('Missing required data:', { progression, arcId, series });
      toast({
        title: 'Error',
        description: 'Missing required information to generate content',
        status: 'error',
        duration: 5000,
      });
      return;
    }
    
    setIsGenerating(true);
    try {
      const arcResponse = await api.getArcById(arcId);
      if (!isApiSuccess(arcResponse)) {
        throw new Error(arcResponse.error);
      }

      const response = await api.generateProgression(
        arcId,
        series,
        progression.season,
        progression.episode,
        arcResponse.data.title,
        arcResponse.data.description
      );

      console.log('Generation response:', response);

      if ('error' in response) {
        toast({
          title: 'No Progression',
          description: response.error,
          status: 'warning',
          duration: 5000,
        });
        return;
      }

      setContent(response.content);
      setInterferingCharacters(response.interfering_characters || []);
      toast({
        title: 'Content generated',
        description: 'LLM has generated progression content and characters',
        status: 'success',
        duration: 3000,
      });
    } catch (error) {
      console.error('Generation error:', error);
      toast({
        title: 'Error generating content',
        description: error instanceof Error ? error.message : 'Failed to generate content',
        status: 'error',
        duration: 5000,
      });
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl">
      <ModalOverlay />
      <ModalContent>
        <ModalHeader>
          <VStack align="start" spacing={1}>
            <HStack spacing={2} align="center">
              <Text>Edit Progression</Text>
              {progression && (
                <Badge colorScheme="purple" fontSize="md">
                  {progression.season}{progression.episode}
                </Badge>
              )}
            </HStack>
            {arcTitle && (
              <Text fontSize="sm" color="gray.500">
                Arc: {arcTitle}
              </Text>
            )}
          </VStack>
        </ModalHeader>
        <ModalCloseButton />
        <ModalBody>
          <VStack spacing={4}>
            <FormControl>
              <FormLabel>Content</FormLabel>
              <HStack width="100%" mb={2}>
                <Button
                  colorScheme="purple"
                  leftIcon={<StarIcon />}
                  onClick={handleGenerate}
                  isLoading={isGenerating}
                  width="100%"
                >
                  Generate Content with AI
                </Button>
              </HStack>
              <Textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={6}
              />
            </FormControl>

            <FormControl>
              <FormLabel>Interfering Characters</FormLabel>
              <Box 
                maxH="200px" 
                overflowY="auto" 
                borderWidth={1} 
                borderRadius="md" 
                p={2}
                bg={bgColor}
              >
                <VStack align="start" spacing={1}>
                  {availableCharacters.map(char => (
                    <Checkbox
                      key={char}
                      isChecked={interferingCharacters.includes(char)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setInterferingCharacters([...interferingCharacters, char]);
                        } else {
                          setInterferingCharacters(interferingCharacters.filter(c => c !== char));
                        }
                      }}
                    >
                      <Text fontSize="sm">{char}</Text>
                    </Checkbox>
                  ))}
                </VStack>
              </Box>
            </FormControl>
          </VStack>
        </ModalBody>
        <ModalFooter>
          {onDelete && (
            <Button
              leftIcon={<DeleteIcon />}
              colorScheme="red"
              variant="ghost"
              mr="auto"
              onClick={onDelete}
            >
              Delete
            </Button>
          )}
          <Button variant="ghost" mr={3} onClick={onClose}>
            Cancel
          </Button>
          <Button 
            colorScheme="blue" 
            onClick={handleSave}
            isDisabled={!content.trim()}
          >
            Save Changes
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}; 