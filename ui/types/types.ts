import type { ChartDataset } from "chart.js";

export interface Result {
  name: string;
  alternateName?: string;
  thumbnailUrl?: string;
  description?: string;
  keywords?: string;
  license?: { name: string };
  creator?: { name: string };
  creatorName?: string;
  publisher?: { name: string };
  publisherName?: string;
  datePublished?: string;
  dateModified?: string;
  recordSet?: RecordSetFile[];
  distribution?: DistributionFile[];
}
export interface RecordSetFile {
  name: string;
  field: Field[];
}
export interface Field {
  id: string;
  name: string;
  markedName?: string; // where does this come from?
  dataType: string[];
  histogram?: Histogram;
  counts?: Record<string, number>;
  minDate?: string;
  maxDate?: string;
  uniqueDates?: number;
  nUnique?: number;
  mostCommon?: Record<string, number>;
  statistics?: Statistics;
}

export interface Histogram {
  bins: number[];
  densities: number[];
}

export interface Statistics {
  count: number;
  mean: number;
  std: number;
  min: number;
  firstQuartile: number;
  secondQuartile: number;
  thirdQuartile: number;
  max: number;
}

export interface DistributionFile {
  "@id": string;
  name: string;
  contentUrl: string;
  encodingFormat: string;
  contentSize?: string;
  description?: string;
}

export interface CustomDataset extends ChartDataset<"bar"> {
  binEdges: number[];
}
