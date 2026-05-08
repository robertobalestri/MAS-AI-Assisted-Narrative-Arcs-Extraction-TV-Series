import React, { useState, useEffect } from 'react';
import {
  Box,
  VStack,
  Heading,
  Text,
  Button,
  useColorModeValue,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
} from '@chakra-ui/react';
import styles from '@/styles/components/Layout.module.css';
import { NarrativeArcManager } from './components/narrative/NarrativeArcManager';
import { VectorStoreTabManager } from './components/vector/VectorStoreTabManager';
import { CharacterManager } from './components/character/CharacterManager';
import { AnalysisEnginePanel } from './components/analysis/AnalysisEnginePanel';
import { LibraryExplorer } from './components/library/LibraryExplorer';
import { ApiClient } from './services/api/ApiClient';
import { isApiSuccess } from './architecture/types/api';
import type { NarrativeArc, Episode, LibrarySeriesStatus } from './architecture/types';

interface ExplorerEpisodeStatus {
  series: string;
  season: string;
  episode: string;
  has_plot_file: boolean;
  has_srt_file: boolean;
  has_dialogue_json: boolean;
  has_analysis_artifacts: boolean;
  progression_count: number;
  analysis_status: 'processed' | 'plot_ready' | 'subtitle_only' | 'empty';
}

interface ExplorerSeason {
  season: string;
  episodes: ExplorerEpisodeStatus[];
}

interface ExplorerSeries {
  code: string;
  display_name: string;
  seasons: ExplorerSeason[];
}

type WorkspaceSection = 'series-manager' | 'analysis-engine' | 'visualization-dashboard';

const App: React.FC = () => {
  const [selectedSeries, setSelectedSeries] = useState<string>('');
  const [analysisSelectedSeries, setAnalysisSelectedSeries] = useState<string>('');
  const [dashboardSelectedSeries, setDashboardSelectedSeries] = useState<string>('');
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [arcs, setArcs] = useState<NarrativeArc[]>([]);
  const [libraryStatus] = useState<LibrarySeriesStatus | null>(null);
  const [knownSeries, setKnownSeries] = useState<string[]>([]);
  const [explorerSeries, setExplorerSeries] = useState<ExplorerSeries[]>([]);
  const [explorerRefreshKey, setExplorerRefreshKey] = useState(0);
  const [activeSection, setActiveSection] = useState<WorkspaceSection>('series-manager');
  const api = new ApiClient();

  useEffect(() => {
    const fetchSeries = async () => {
      try {
        const response = await api.getSeries();
        if (isApiSuccess<string[]>(response)) {
          setKnownSeries(response.data);
        }
      } catch (error) {
        console.error('Error fetching series:', error);
      }
    };

    fetchSeries();
  }, []);

  useEffect(() => {
    if (selectedSeries && !analysisSelectedSeries) {
      setAnalysisSelectedSeries(selectedSeries);
    }
    if (selectedSeries && !dashboardSelectedSeries) {
      setDashboardSelectedSeries(selectedSeries);
    }
  }, [selectedSeries, analysisSelectedSeries, dashboardSelectedSeries]);

  useEffect(() => {
    if (dashboardSelectedSeries) {
      const fetchData = async () => {
        try {
          const [episodesResponse, arcsResponse] = await Promise.all([
            api.request<Episode[]>(`/episodes/${dashboardSelectedSeries}`),
            api.request<NarrativeArc[]>(`/arcs/series/${dashboardSelectedSeries}`)
          ]);

          if (isApiSuccess<Episode[]>(episodesResponse)) {
            setEpisodes(episodesResponse.data);
          }
          if (isApiSuccess<NarrativeArc[]>(arcsResponse)) {
            setArcs(arcsResponse.data);
          }
        } catch (error) {
          console.error('Error fetching data:', error);
          setEpisodes([]);
          setArcs([]);
        }
      };

      fetchData();
    }
  }, [dashboardSelectedSeries]);

  const handleArcUpdated = async () => {
    if (dashboardSelectedSeries) {
      try {
        const response = await api.request<NarrativeArc[]>(`/arcs/series/${dashboardSelectedSeries}`);
        if (isApiSuccess<NarrativeArc[]>(response)) {
          setArcs(response.data);
        }
      } catch (error) {
        console.error('Error refreshing arcs:', error);
      }
    }
  };

  const hasNarrativeData = arcs.length > 0;
  const emptyStateBg = useColorModeValue('white', 'gray.800');
  const dashboardSelectorBg = useColorModeValue('white', 'gray.800');

  const refreshExplorerData = async () => {
    const response = await api.request<ExplorerSeries[]>('/library/explorer');
    if (isApiSuccess<ExplorerSeries[]>(response)) {
      setExplorerSeries(response.data);
    }
    setExplorerRefreshKey((current) => current + 1);
  };

  const renderActiveSection = () => {
    if (activeSection === 'series-manager') {
      return (
        <VStack spacing={4} align="stretch">
          <LibraryExplorer
            selectedSeries={selectedSeries}
            onSelectSeries={setSelectedSeries}
            onDataChange={setExplorerSeries}
            refreshKey={explorerRefreshKey}
          />
        </VStack>
      );
    }

    if (activeSection === 'analysis-engine') {
      return (
        <AnalysisEnginePanel
          seriesList={explorerSeries}
          selectedSeriesCode={analysisSelectedSeries}
          onSelectSeries={setAnalysisSelectedSeries}
          onSelectSeriesManager={() => setActiveSection('series-manager')}
          onRefresh={refreshExplorerData}
        />
      );
    }

    if (dashboardSelectedSeries && (libraryStatus?.analysis_state === 'completed' || hasNarrativeData || (knownSeries.includes(dashboardSelectedSeries) && libraryStatus === null))) {
      return (
        <VStack spacing={4} align="stretch">
          <Box bg={dashboardSelectorBg} p={4} borderRadius="lg" shadow="sm">
            <Text fontWeight="bold" mb={2}>Visualization Dashboard</Text>
            <select
              value={dashboardSelectedSeries}
              onChange={(event) => setDashboardSelectedSeries(event.target.value)}
              style={{ width: '100%', padding: '8px', borderRadius: '8px' }}
            >
              <option value="">Select series</option>
              {knownSeries.map((series) => (
                <option key={series} value={series}>{series}</option>
              ))}
            </select>
          </Box>
          <Box className={styles.tabContainer}>
            <Tabs isFitted variant="enclosed">
            <TabList>
              <Tab>Narrative Arcs Timeline</Tab>
              <Tab>Vector Store</Tab>
              <Tab>Characters</Tab>
            </TabList>
            <TabPanels>
              <TabPanel p={0}>
                <NarrativeArcManager
                  series={dashboardSelectedSeries}
                  arcs={arcs}
                  episodes={episodes}
                  onArcUpdated={handleArcUpdated}
                />
              </TabPanel>
              <TabPanel>
                <VectorStoreTabManager
                  series={dashboardSelectedSeries}
                  onArcUpdated={handleArcUpdated}
                />
              </TabPanel>
              <TabPanel>
                <CharacterManager
                  series={dashboardSelectedSeries}
                  onCharacterUpdated={handleArcUpdated}
                />
              </TabPanel>
            </TabPanels>
          </Tabs>
        </Box>
      </VStack>
      );
    }

    return (
      <Box textAlign="center" p={8} bg={emptyStateBg} borderRadius="lg" shadow="sm">
        <Text>
          {selectedSeries
            ? 'Select a series with available narrative results to open the Visualization Dashboard.'
            : 'Create or select a series to start building the dataset.'}
        </Text>
      </Box>
    );
  };

  return (
    <Box className={styles.pageContainer} bg={useColorModeValue('gray.50', 'gray.900')}>
      <Box className={styles.appShell}>
        <Box className={styles.sidebar} bg={useColorModeValue('white', 'gray.800')}>
          <VStack align="stretch" spacing={3}>
            <Heading size="md">Workspace</Heading>
            <Button variant={activeSection === 'series-manager' ? 'solid' : 'ghost'} onClick={() => setActiveSection('series-manager')}>
              Series Manager
            </Button>
            <Button variant={activeSection === 'analysis-engine' ? 'solid' : 'ghost'} onClick={() => setActiveSection('analysis-engine')}>
              Analysis Engine
            </Button>
            <Button variant={activeSection === 'visualization-dashboard' ? 'solid' : 'ghost'} onClick={() => setActiveSection('visualization-dashboard')}>
              Visualization Dashboard
            </Button>
            {selectedSeries && (
              <Box pt={4}>
                <Text fontSize="sm" color="gray.500">Selected series</Text>
                <Text fontWeight="bold">{selectedSeries}</Text>
              </Box>
            )}
          </VStack>
        </Box>

        <Box className={styles.mainContent}>
          <VStack spacing={4} align="stretch">
            <Box className={styles.header} bg={useColorModeValue('white', 'gray.800')}>
              <Heading className={styles.pageTitle}>Narrative Arcs Dashboard</Heading>
            </Box>
            <Box px={4}>{renderActiveSection()}</Box>
          </VStack>
        </Box>
      </Box>
    </Box>
  );
};

export default App;