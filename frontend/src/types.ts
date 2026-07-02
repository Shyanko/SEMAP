export type HealthState = "checking" | "ok" | "error";

export type Account = {
  id: number;
  username: string;
  createdAt: string;
  updatedAt: string;
};

export type TrackPoint = {
  id: number;
  sequence: number;
  lat: number;
  lng: number;
  altitude: number | null;
  speed: number | null;
  recordedAt: string | null;
  name: string | null;
  raw: Record<string, unknown> | null;
};

export type TrackSegmentMetadata = {
  vehicleModel?: string;
  registration?: string;
  operatorName?: string;
  operatorCode?: string;
  logoKind?: "airline" | "railway_12306" | "gps_road";
  logoUrl?: string;
  logoText?: string;
  unitNo?: string;
  originLocation?: string;
  destinationLocation?: string;
};

export type TrackSegment = {
  id: number;
  title: string;
  sourceType: "flight" | "train" | "gps";
  transportType: "flight" | "train" | "walk" | "car" | "other";
  externalCode: string | null;
  startedAt: string | null;
  endedAt: string | null;
  summary: string | null;
  isApproximate: boolean;
  metadata: TrackSegmentMetadata;
  version: number;
  createdAt: string;
  updatedAt: string;
  points: TrackPoint[];
};

export type TrainStationOption = {
  sequence: number;
  name: string;
  arriveTime: string | null;
  startTime: string | null;
  arriveDayDiff: number;
};

export type TrainStationsResponse = {
  trainCode: string;
  requestedDate: string;
  queryDate: string;
  stations: TrainStationOption[];
};

export type AuthMode = "login" | "register";
export type WorkspaceView = "tracks" | "flight" | "train";
