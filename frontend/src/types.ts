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

export type TrackSegment = {
  id: number;
  title: string;
  sourceType: "flight" | "train" | "gps";
  transportType: "flight" | "train" | "walk" | "car" | "other";
  externalCode: string | null;
  startedAt: string | null;
  endedAt: string | null;
  summary: string | null;
  note: string | null;
  isApproximate: boolean;
  version: number;
  createdAt: string;
  updatedAt: string;
  points: TrackPoint[];
};

export type AuthMode = "login" | "register";
export type WorkspaceView = "tracks" | "flight" | "train";
