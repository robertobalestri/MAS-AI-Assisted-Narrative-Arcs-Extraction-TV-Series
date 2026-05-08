import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  VStack,
  Text,
  Button,
  Spinner,
  HStack,
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
  FormControl,
  FormLabel,
  NumberInput,
  NumberInputField,
  NumberInputStepper,
  NumberIncrementStepper,
  NumberDecrementStepper,
  Select,
  useDisclosure,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalCloseButton,
  Badge,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Grid,
  GridItem,
  useColorModeValue,
} from '@chakra-ui/react';
import Plot from 'react-plotly.js';
import { PCA } from 'ml-pca';
import type { VectorStoreEntry, ArcCluster } from '@/architecture/types';

interface ArcClusterVisualizerProps {
  entries: VectorStoreEntry[];
  clusters: ArcCluster[];
  fetchClusters: (options?: {
    threshold: number;
    minClusterSize: number;
    maxClusters: number;
  }) => void;
  isLoading: boolean;
}

interface ClusterVisualizationData {
  x: number[];
  y: number[];
  z: number[];
  text: string[];
  cluster: number[];
  sizes: number[];
  colors: string[];
}

interface ClusterArc {
  id: string;
  title: string;
  type: string;
  cluster_probability: number;
}

export const ArcClusterVisualizer: React.FC<ArcClusterVisualizerProps> = ({
  entries,
  clusters,
  fetchClusters,
  isLoading,
}) => {
  // Color mode hooks
  const boxBgColor = useColorModeValue('white', 'gray.700');
  const plotBgColor = useColorModeValue('white', 'gray.800');

  // Modal hooks
  const { isOpen: isClusterOpen, onOpen: onClusterOpen, onClose: onClusterClose } = useDisclosure();

  // State hooks
  const [clusterThreshold, setClusterThreshold] = useState<number>(0.75);
  const [minClusterSize, setMinClusterSize] = useState<number>(2);
  const [maxClusters, setMaxClusters] = useState<number>(20);
  const [colorScheme, setColorScheme] = useState<string>('Set1');
  const [clusterVisualization, setClusterVisualization] =
    useState<ClusterVisualizationData | null>(null);
  const [selectedCluster, setSelectedCluster] = useState<ArcCluster | null>(null);

  // Color schemes
  const colorSchemes = useMemo(
    () => ['Set1', 'Set2', 'Paired', 'Dark2', 'Pastel1', 'Pastel2', 'Accent'],
    []
  );

  // Calculate cluster visualization when clusters change
  useEffect(() => {
    if (clusters.length > 0) {
      calculateClusterVisualization(clusters);
    }
  }, [clusters]);

  // Function to calculate cluster visualization
  const calculateClusterVisualization = (clusterData: ArcCluster[]) => {
    if (!clusterData.length) return;

    // Extract all arcs from clusters
    const allArcs = clusterData.flatMap((cluster) =>
      cluster.arcs.map((arc: ClusterArc) => ({
        ...arc,
        cluster_id: cluster.cluster_id,
      }))
    );

    // Get embeddings from vector store entries
    const arcEmbeddings = entries.filter((entry) =>
      allArcs.some((arc) => arc.id === entry.id)
    );

    if (arcEmbeddings.length < 3) return;

    // Perform PCA
    const embeddings = arcEmbeddings.map((entry) => entry.embedding!);
    const pca = new PCA(embeddings);
    const result = pca.predict(embeddings, { nComponents: 3 });
    const pcaResult = result.to2DArray();

    // Prepare visualization data
    const visualData: ClusterVisualizationData = {
      x: pcaResult.map((p) => p[0]),
      y: pcaResult.map((p) => p[1]),
      z: pcaResult.map((p) => p[2]),
      text: arcEmbeddings.map((entry) => {
        const arc = allArcs.find((a) => a.id === entry.id);
        return `Title: ${arc?.title}<br>Cluster: ${arc?.cluster_id}<br>Probability: ${
          (arc?.cluster_probability || 0) * 100
        }%`;
      }),
      cluster: arcEmbeddings.map(
        (entry) => allArcs.find((a) => a.id === entry.id)?.cluster_id || 0
      ),
      sizes: arcEmbeddings.map((entry) => {
        const arc = allArcs.find((a) => a.id === entry.id);
        return (arc?.cluster_probability || 0.5) * 20 + 10;
      }),
      colors: getClusterColors(clusterData.length),
    };

    setClusterVisualization(visualData);
  };

  // Get cluster colors
  const getClusterColors = (numClusters: number): string[] => {
    const colorSchemes = {
      Set1: [
        '#e41a1c',
        '#377eb8',
        '#4daf4a',
        '#984ea3',
        '#ff7f00',
        '#ffff33',
        '#a65628',
        '#f781bf',
        '#999999',
      ],
      Set2: [
        '#66c2a5',
        '#fc8d62',
        '#8da0cb',
        '#e78ac3',
        '#a6d854',
        '#ffd92f',
        '#e5c494',
        '#b3b3b3',
      ],
      Paired: [
        '#a6cee3',
        '#1f78b4',
        '#b2df8a',
        '#33a02c',
        '#fb9a99',
        '#e31a1c',
        '#fdbf6f',
        '#ff7f00',
        '#cab2d6',
        '#6a3d9a',
      ],
      Dark2: [
        '#1b9e77',
        '#d95f02',
        '#7570b3',
        '#e7298a',
        '#66a61e',
        '#e6ab02',
        '#a6761d',
        '#666666',
      ],
    };

    const colors = colorSchemes[colorScheme as keyof typeof colorSchemes] || colorSchemes.Set1;

    const finalColors: string[] = [];
    for (let i = 0; i < numClusters; i++) {
      finalColors.push(colors[i % colors.length]);
    }

    return finalColors;
  };

  // Initialize WebGL
  const initializeWebGL = (canvas: HTMLCanvasElement) => {
    const gl = canvas.getContext('webgl') as WebGLRenderingContext;
    if (gl) {
      gl.getExtension('WEBGL_color_buffer_float');
      gl.getExtension('EXT_float_blend');
      gl.getExtension('OES_texture_float');
      gl.getExtension('OES_texture_float_linear');
    }
  };

  // Plot configuration
  const plotConfig = {
    displayModeBar: true,
    responsive: true,
    scrollZoom: true,
    displaylogo: false,
    webgl: {
      preserveDrawingBuffer: true,
      extensions: [
        'WEBGL_color_buffer_float',
        'EXT_float_blend',
        'OES_texture_float',
        'OES_texture_float_linear',
      ],
    },
  };

  // Handlers
  const handleClusterSelect = (cluster: ArcCluster) => {
    setSelectedCluster(cluster);
    onClusterOpen();
  };

  const handleRecalculateClusters = () => {
    fetchClusters({
      threshold: clusterThreshold,
      minClusterSize: minClusterSize,
      maxClusters: maxClusters,
    });
  };

  return (
    <>
      <Grid templateColumns="250px 1fr 600px" gap={4}>
        {/* Clustering Setup Sidebar */}
        <GridItem>
          <VStack spacing={4} align="stretch" p={4} borderWidth={1} borderRadius="md">
            <Text fontWeight="bold" fontSize="lg">
              Clustering Setup
            </Text>

            <FormControl>
              <FormLabel>
                Similarity Threshold: {(clusterThreshold * 100).toFixed(2)}%
              </FormLabel>
              <Slider
                value={clusterThreshold}
                min={0}
                max={1}
                step={0.01}
                onChange={setClusterThreshold}
              >
                <SliderTrack>
                  <SliderFilledTrack />
                </SliderTrack>
                <SliderThumb />
              </Slider>
            </FormControl>

            <FormControl>
              <FormLabel>Minimum Cluster Size</FormLabel>
              <NumberInput
                value={minClusterSize}
                min={2}
                max={10}
                onChange={(_, value) => setMinClusterSize(value)}
              >
                <NumberInputField />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
            </FormControl>

            <FormControl>
              <FormLabel>Maximum Number of Clusters</FormLabel>
              <NumberInput
                value={maxClusters}
                min={2}
                max={50}
                onChange={(_, value) => setMaxClusters(value)}
              >
                <NumberInputField />
                <NumberInputStepper>
                  <NumberIncrementStepper />
                  <NumberDecrementStepper />
                </NumberInputStepper>
              </NumberInput>
            </FormControl>

            <FormControl>
              <FormLabel>Color Scheme</FormLabel>
              <Select value={colorScheme} onChange={(e) => setColorScheme(e.target.value)}>
                {colorSchemes.map((scheme) => (
                  <option key={scheme} value={scheme}>
                    {scheme}
                  </option>
                ))}
              </Select>
            </FormControl>

            <Button colorScheme="blue" onClick={handleRecalculateClusters} isLoading={isLoading}>
              Recalculate Clusters
            </Button>
          </VStack>
        </GridItem>

        {/* Cluster Details */}
        <GridItem>
          <VStack spacing={4} align="stretch">
            {clusters.map((cluster) => (
              <Box
                key={cluster.cluster_id}
                p={4}
                borderWidth={1}
                borderRadius="md"
                mb={4}
                bg={boxBgColor}
                shadow="sm"
                _hover={{ shadow: 'md' }}
                onClick={() => handleClusterSelect(cluster)}
                cursor="pointer"
              >
                <HStack justify="space-between" mb={2}>
                  <Text fontWeight="bold">
                    Cluster {cluster.cluster_id} ({cluster.size} arcs)
                  </Text>
                  <Badge colorScheme="blue">
                    {(cluster.average_probability * 100).toFixed(1)}% avg. probability
                  </Badge>
                </HStack>
                <VStack align="start" spacing={2}>
                  {cluster.arcs.map((arc: ClusterArc) => (
                    <HStack key={arc.id} spacing={4} width="100%" justify="space-between">
                      <Text>{arc.title}</Text>
                      <Badge colorScheme="green">
                        {(arc.cluster_probability * 100).toFixed(1)}%
                      </Badge>
                    </HStack>
                  ))}
                </VStack>
              </Box>
            ))}
            {clusters.length === 0 && !isLoading && (
              <Box textAlign="center" p={8}>
                <Text>
                  No clusters available. Click "Recalculate Clusters" to begin analysis.
                </Text>
              </Box>
            )}
          </VStack>
        </GridItem>

        {/* Cluster Visualization */}
        <GridItem>
          <Box
            height="calc(100vh - 200px)"
            borderWidth={1}
            borderRadius="lg"
            position="sticky"
            top="20px"
          >
            {isLoading ? (
              <VStack justify="center" height="100%">
                <Spinner />
                <Text>Analyzing clusters...</Text>
              </VStack>
            ) : clusterVisualization ? (
              <Plot
                data={[
                  {
                    type: 'scatter3d',
                    mode: 'markers',
                    x: clusterVisualization.x,
                    y: clusterVisualization.y,
                    z: clusterVisualization.z,
                    text: clusterVisualization.text,
                    hoverinfo: 'text',
                    marker: {
                      size: clusterVisualization.sizes,
                      color: clusterVisualization.cluster,
                      colorscale: colorScheme,
                      opacity: 0.8,
                    },
                  },
                ]}
                layout={{
                  title: 'Narrative Arc Clusters',
                  scene: {
                    xaxis: { title: 'PC1' },
                    yaxis: { title: 'PC2' },
                    zaxis: { title: 'PC3' },
                    aspectmode: 'cube',
                    aspectratio: { x: 1, y: 1, z: 1 },
                    camera: {
                      eye: { x: 1.5, y: 1.5, z: 1.5 },
                    },
                  },
                  margin: { l: 0, r: 0, t: 30, b: 0 },
                  showlegend: false,
                  paper_bgcolor: plotBgColor,
                  plot_bgcolor: plotBgColor,
                }}
                style={{ width: '100%', height: '100%' }}
                config={plotConfig}
                useResizeHandler
                onInitialized={() => {
                  const canvas = document.querySelector('.plotly canvas');
                  if (canvas) {
                    initializeWebGL(canvas as HTMLCanvasElement);
                  }
                }}
              />
            ) : (
              <VStack justify="center" height="100%">
                <Text>No cluster visualization available</Text>
              </VStack>
            )}
          </Box>
        </GridItem>
      </Grid>

      {/* Cluster Details Modal */}
      <Modal isOpen={isClusterOpen} onClose={onClusterClose} size="xl">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Cluster Details</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            {selectedCluster ? (
              <VStack spacing={4} align="stretch">
                <Box>
                  <Text fontWeight="bold">
                    Cluster Size: {selectedCluster.size} arcs
                  </Text>
                  <Text>
                    Average Similarity:{' '}
                    {((1 - selectedCluster.average_distance) * 100).toFixed(1)}%
                  </Text>
                  {selectedCluster.cluster_persistence && (
                    <Text>
                      Cluster Stability:{' '}
                      {(selectedCluster.cluster_persistence * 100).toFixed(1)}%
                    </Text>
                  )}
                </Box>
                <Table variant="simple">
                  <Thead>
                    <Tr>
                      <Th>Arc Title</Th>
                      <Th>Type</Th>
                      <Th>Cluster Probability</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {selectedCluster.arcs.map((arc: ClusterArc) => (
                      <Tr key={arc.id}>
                        <Td>{arc.title}</Td>
                        <Td>
                          <Badge colorScheme="blue">{arc.type}</Badge>
                        </Td>
                        <Td>{(arc.cluster_probability * 100).toFixed(1)}%</Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
              </VStack>
            ) : (
              <Text>No cluster selected.</Text>
            )}
          </ModalBody>
        </ModalContent>
      </Modal>
    </>
  );
};
