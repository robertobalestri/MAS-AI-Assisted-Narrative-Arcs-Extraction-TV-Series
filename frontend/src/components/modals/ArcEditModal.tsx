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
  Input,
  Textarea,
  Select,
  VStack,
  Box,
  Checkbox,
  Text,
} from '@chakra-ui/react';
import { DeleteIcon } from '@chakra-ui/icons';
import { ArcType } from '@/architecture/types/arc';
import type { NarrativeArc } from '@/architecture/types';
import styles from '@/styles/components/Modal.module.css';

interface ArcEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  arc: NarrativeArc | null;
  onSave: (updatedArc: Partial<NarrativeArc>) => void;
  onDelete?: () => void;
  availableCharacters: string[];
}

export const ArcEditModal: React.FC<ArcEditModalProps> = ({
  isOpen,
  onClose,
  arc,
  onSave,
  onDelete,
  availableCharacters,
}) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [arcType, setArcType] = useState<ArcType>(ArcType.SoapArc);
  const [mainCharacters, setMainCharacters] = useState<string[]>([]);

  useEffect(() => {
    if (arc) {
      setTitle(arc.title);
      setDescription(arc.description);
      setArcType(arc.arc_type);
      setMainCharacters(arc.main_characters);
    }
  }, [arc]);

  const handleSave = () => {
    if (arc) {
      onSave({
        ...arc,
        title,
        description,
        arc_type: arcType,
        main_characters: mainCharacters,
      });
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="xl">
      <ModalOverlay />
      <ModalContent className={styles.modalContent}>
        <ModalHeader className={styles.modalHeader}>Edit Arc</ModalHeader>
        <ModalCloseButton />
        <ModalBody className={styles.modalBody}>
          <VStack spacing={4}>
            <FormControl className={styles.formControl} isRequired>
              <FormLabel className={styles.formLabel}>Title</FormLabel>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </FormControl>

            <FormControl isRequired>
              <FormLabel>Description</FormLabel>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={4}
              />
            </FormControl>

            <FormControl isRequired>
              <FormLabel>Arc Type</FormLabel>
              <Select
                value={arcType}
                onChange={(e) => setArcType(e.target.value as ArcType)}
              >
                {Object.values(ArcType).map(type => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </Select>
            </FormControl>

            <FormControl>
              <FormLabel className={styles.formLabel}>Main Characters</FormLabel>
              <Box className={styles.characterList}>
                <VStack align="start" spacing={1}>
                  {availableCharacters.map(char => (
                    <Checkbox
                      key={char}
                      isChecked={mainCharacters.includes(char)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setMainCharacters([...mainCharacters, char]);
                        } else {
                          setMainCharacters(mainCharacters.filter(c => c !== char));
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
        <ModalFooter className={styles.modalFooter}>
          {onDelete && (
            <Button
              leftIcon={<DeleteIcon />}
              colorScheme="red"
              variant="ghost"
              mr="auto"
              onClick={onDelete}
            >
              Delete Arc
            </Button>
          )}
          <Button variant="ghost" mr={3} onClick={onClose}>
            Cancel
          </Button>
          <Button 
            colorScheme="blue" 
            onClick={handleSave}
            isDisabled={!title.trim() || !description.trim()}
          >
            Save Changes
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
}; 