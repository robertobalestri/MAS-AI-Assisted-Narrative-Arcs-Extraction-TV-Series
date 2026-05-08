import React from 'react';
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
  Input,
  VStack,
  Box,
  Tag,
  TagLabel,
  TagCloseButton,
  HStack,
} from '@chakra-ui/react';
import styles from '@/styles/components/Modal.module.css';

interface CharacterEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: () => void;
  onDeleteCharacter?: (character: any) => void;
  onMergeCharacters?: (char1: any, char2: any, keepCharacter: 'character1' | 'character2') => void;
  character: any | null;
  entityName: string;
  bestAppellation: string;
  appellations: string[];
  newAppellation: string;
  setEntityName: (value: string) => void;
  setBestAppellation: (value: string) => void;
  setAppellations: (value: string[]) => void;
  setNewAppellation: (value: string) => void;
}

export const CharacterEditModal: React.FC<CharacterEditModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  character,
  entityName,
  bestAppellation,
  appellations,
  newAppellation,
  setEntityName,
  setBestAppellation,
  setAppellations,
  setNewAppellation,
}) => {
  const handleAddAppellation = () => {
    if (newAppellation.trim() && !appellations.includes(newAppellation.trim())) {
      setAppellations([...appellations, newAppellation.trim()]);
      setNewAppellation('');
    }
  };

  const handleRemoveAppellation = (appellation: string) => {
    setAppellations(appellations.filter(a => a !== appellation));
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleAddAppellation();
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl">
      <ModalOverlay />
      <ModalContent className={styles.modalContent}>
        <ModalHeader className={styles.modalHeader}>
          {character ? 'Edit Character' : 'Add Character'}
        </ModalHeader>
        <ModalCloseButton />
        
        <ModalBody className={styles.modalBody}>
          <VStack spacing={4}>
            <FormControl isRequired>
              <FormLabel>Entity Name</FormLabel>
              <Input
                value={entityName}
                onChange={(e) => setEntityName(e.target.value)}
                placeholder="Enter entity name"
                isReadOnly={!!character}
              />
            </FormControl>

            <FormControl isRequired>
              <FormLabel>Best Appellation</FormLabel>
              <Input
                value={bestAppellation}
                onChange={(e) => setBestAppellation(e.target.value)}
                placeholder="Enter best appellation"
              />
            </FormControl>

            <FormControl>
              <FormLabel>Appellations</FormLabel>
              <Input
                value={newAppellation}
                onChange={(e) => setNewAppellation(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Enter new appellation and press Enter"
              />
              
              <Box mt={2}>
                <HStack spacing={2} wrap="wrap">
                  {appellations.map((appellation) => (
                    <Tag
                      key={appellation}
                      size="md"
                      variant="solid"
                      colorScheme="blue"
                    >
                      <TagLabel>{appellation}</TagLabel>
                      <TagCloseButton
                        onClick={() => handleRemoveAppellation(appellation)}
                      />
                    </Tag>
                  ))}
                </HStack>
              </Box>
            </FormControl>
          </VStack>
        </ModalBody>

        <ModalFooter className={styles.modalFooter}>
          <Button variant="ghost" mr={3} onClick={onClose}>
            Cancel
          </Button>
          <Button
            colorScheme="blue"
            onClick={onSubmit}
            isDisabled={!entityName.trim() || !bestAppellation.trim() || appellations.length === 0}
          >
            {character ? 'Save Changes' : 'Create Character'}
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}; 