export interface Result {
    name: string;
    alternateName?: string;
    thumbnailUrl?: string;
    description?: string;
    keywords?: string;
    license?: { name: string };
    creator?: { name: string };
    "creator-name"?: string;
    publisher?: { name: string };
    "publisher-name"?: string;
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
    marked_name?: string;
    dataType: string[];
    histogram?: Histogram;
    counts?: { Yes?: number; No?: number };
    min_date?: string;
    max_date?: string;
    unique_dates?: number;
    n_unique?: number;
    most_common?: Record<string, number>;
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
    "25%": number;
    "50%": number;
    "75%": number;
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