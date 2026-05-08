import { useState, useCallback } from 'react';
import { isApiSuccess } from '@/architecture/types/api';
import type { NarrativeArc } from '@/architecture/types';
import { ApiClient } from '@/services/api/ApiClient';

export const useArcManagement = (series: string) => {
  const [arcs, setArcs] = useState<NarrativeArc[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const api = new ApiClient();

  const fetchArcs = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await api.request<NarrativeArc[]>(`/arcs/series/${series}`);
      if (!isApiSuccess<NarrativeArc[]>(response)) {
        throw new Error(response.error);
      }
      setArcs(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch arcs');
    } finally {
      setIsLoading(false);
    }
  }, [series]);

  const createArc = useCallback(async (arcData: Partial<NarrativeArc>) => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await api.request<NarrativeArc>('/arcs', {
        method: 'POST',
        body: JSON.stringify(arcData),
      });
      if (!isApiSuccess<NarrativeArc>(response)) {
        throw new Error(response.error);
      }
      setArcs((prev: NarrativeArc[]) => [...prev, response.data]);
      return response.data;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create arc');
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  return {
    arcs,
    isLoading,
    error,
    fetchArcs,
    createArc,
  };
}; 