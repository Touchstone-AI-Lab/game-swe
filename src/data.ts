// Typed view of src/data.json, which tools/build_data.py generates from the paper checkout.
import raw from './data.json';

export interface Cell { all: number; rep: number | null; con: number | null }
export interface Model {
  slug: string; name: string; icon: string;
  overall: number; repair: number; construct: number; f2pOnly: number; resolved: number;
  funnel: { changed: number; reachedTests: number; f2p: number; f2pAndP2p: number; resolved: number };
}
export interface Game {
  slug: string; name: string; language: string; runtime: string;
  tasks: number; repair: number; construct: number;
  best: number; bestModels: string[]; mean: number;
  scores: Record<string, Cell>;
}
export interface Stage { key: string; label: string; n: number }
export interface Data {
  asOf: string;
  totals: Record<string, number | string>;
  models: Model[];
  games: Game[];
  findings: {
    attempts: number; unresolved: number; stages: Stage[];
    inGameFail: number; inGameFailShare: number;
    submitted: number; submittedShare: number;
    claims: number; claimsShare: number; rho: number;
  };
}

export const data = raw as unknown as Data;
export const modelBySlug = new Map(data.models.map((m) => [m.slug, m]));
export const icon = (m: Model) => `./icons/${m.icon}`;
export const pct = (v: number) => `${v.toFixed(1)}%`;
