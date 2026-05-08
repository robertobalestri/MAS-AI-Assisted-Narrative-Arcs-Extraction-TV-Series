import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  Input,
  Button,
  useToast,
  HStack,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
} from '@chakra-ui/react';
import { SearchIcon } from '@chakra-ui/icons';
import { useApi } from '@/hooks/useApi';
import { ApiClient } from '@/services/api/ApiClient';
import type { VectorStoreEntry, ArcCluster } from '@/architecture/types';
import { ArcClusterVisualizer } from './ArcClusterVisualizer';
import { VectorStoreExplorer } from './VectorStoreExplorer';

interface VectorStoreTabManagerProps {
  series: string;
  onArcUpdated?: () => void;
}

export const VectorStoreTabManager: React.FC<VectorStoreTabManagerProps> = ({
  series,
}) => {

  // State hooks
  const [entries, setEntries] = useState<VectorStoreEntry[]>([]);
  const [clusters, setClusters] = useState<ArcCluster[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<number>(0);

  // API hooks
  const toast = useToast();
  const { request, isLoading } = useApi();
  const api = new ApiClient();

  // Fetch entries when series changes
  useEffect(() => {
    if (series) {
      fetchEntries();
    }
  }, [series]);

  // Fetch clusters or calculate visualization when active tab changes
  useEffect(() => {
    if (activeTab === 0 && entries.length > 0) {
      fetchClusters();
    }
  }, [activeTab, entries]);

  // Fetch entries from API
  const fetchEntries = async (query?: string) => {
    try {
      const response = await request(() =>
        query ? api.searchVectorStore(series, query) : api.searchVectorStore(series)
      );

      if (response) {
        setEntries(response);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setError(errorMessage);
      toast({
        title: 'Error fetching entries',
        description: errorMessage,
        status: 'error',
        duration: 5000,
      });
    }
  };

  // Fetch clusters from API
  const fetchClusters = async (options?: {
    threshold: number;
    minClusterSize: number;
    maxClusters: number;
  }) => {
    try {
      const response = await request(() =>
        api.getArcClusters(series, {
          threshold: options?.threshold || 0.75,
          min_cluster_size: options?.minClusterSize || 2,
          max_clusters: options?.maxClusters || 20,
        })
      );

      if (response) {
        setClusters(response);
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setError(errorMessage);
      toast({
        title: 'Error fetching clusters',
        description: errorMessage,
        status: 'error',
        duration: 5000,
      });
    }
  };

  // Handle search input
  const handleSearch = () => {
    fetchEntries(searchQuery);
  };

  // Handle tab change
  const handleTabChange = (index: number) => {
    setActiveTab(index);
  };

  return (
    <Box p={4}>
      <VStack spacing={4} align="stretch">
        {error && (
          <Alert status="error">
            <AlertIcon />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Search Bar */}
        <HStack>
          <Input
            placeholder="Search vector store..."
            value={searchQuery}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) => setSearchQuery(e.target.value)}
            onKeyPress={(e: React.KeyboardEvent) => e.key === 'Enter' && handleSearch()}
          />
          <Button leftIcon={<SearchIcon />} onClick={handleSearch} isLoading={isLoading}>
            Search
          </Button>
          <Button onClick={() => fetchEntries()} variant="outline">
            Reset
          </Button>
        </HStack>

        <Tabs onChange={handleTabChange}>
          <TabList>
            <Tab>Cluster Analysis</Tab>
            <Tab>Vector Store Explorer</Tab>
          </TabList>

          <TabPanels>
            {/* Cluster Analysis Tab */}
            <TabPanel>
              <ArcClusterVisualizer
                entries={entries}
                clusters={clusters}
                fetchClusters={fetchClusters}
                isLoading={isLoading}
              />
            </TabPanel>

            {/* Vector Store Explorer Tab */}
            <TabPanel>
              <VectorStoreExplorer entries={entries} isLoading={isLoading} />
            </TabPanel>
          </TabPanels>
        </Tabs>
      </VStack>
    </Box>
  );
};
