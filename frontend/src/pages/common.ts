import { PageId } from '../types';

export type Navigate = (page: PageId, param?: string, query?: Record<string, string>) => void;

export interface CommonPageProps {
  loaded: boolean;
  connection: 'connecting' | 'online' | 'offline';
  navigate: Navigate;
  onInject: () => void;
  onLoadSamples: () => void;
  isLoadingSamples: boolean;
}
