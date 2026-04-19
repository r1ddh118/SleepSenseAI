import type { Session, RiskLevel } from "./mockData";

type MaybeSession = Partial<Session> & {
  patientName?: string;
  sleepQuality?: number;
  risk?: RiskLevel;
  riskScore?: number;
  createdAt?: string;
};

const defaultSleepStages: Session["sleepStages"] = {
  wake: 0,
  n1: 0,
  n2: 0,
  n3: 0,
  rem: 0,
};

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const toNumber = (value: unknown, fallback: number) => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string") {
    const parsed = Number.parseFloat(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }

  return fallback;
};

const parseDurationMinutes = (value: unknown) => {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  if (typeof value === "string") {
    const hoursMatch = value.match(/(\d+(?:\.\d+)?)\s*h/i);
    if (hoursMatch) {
      return Math.round(Number.parseFloat(hoursMatch[1]) * 60);
    }

    const minutes = Number.parseInt(value, 10);
    if (Number.isFinite(minutes)) {
      return minutes;
    }
  }

  return 0;
};

const deriveRiskLevel = (probability: number, explicit?: string): RiskLevel => {
  if (explicit === "low" || explicit === "moderate" || explicit === "high") {
    return explicit;
  }

  if (probability >= 0.7) {
    return "high";
  }
  if (probability >= 0.4) {
    return "moderate";
  }
  return "low";
};

export const normalizeStoredSession = (value: unknown): Session | null => {
  if (!value || typeof value !== "object") {
    return null;
  }

  const raw = value as MaybeSession;
  const id = typeof raw.id === "string" && raw.id.trim() ? raw.id : null;
  if (!id) {
    return null;
  }

  const riskProbability = clamp(
    raw.riskProbability !== undefined
      ? toNumber(raw.riskProbability, 0)
      : toNumber(raw.riskScore, 0) / 100,
    0,
    1
  );

  const sleepEfficiency =
    raw.features?.sleep_efficiency !== undefined
      ? toNumber(raw.features.sleep_efficiency, 0)
      : clamp(toNumber(raw.sleepQuality, 0), 0, 100);

  return {
    id,
    sid: typeof raw.sid === "string" && raw.sid.trim() ? raw.sid : id,
    date:
      typeof raw.date === "string" && raw.date.trim()
        ? raw.date
        : typeof raw.createdAt === "string" && raw.createdAt.trim()
        ? raw.createdAt
        : new Date().toISOString(),
    duration: parseDurationMinutes(raw.duration),
    riskProbability,
    riskLevel: deriveRiskLevel(riskProbability, raw.riskLevel ?? raw.risk),
    status:
      raw.status === "completed" || raw.status === "processing" || raw.status === "recording"
        ? raw.status
        : "completed",
    sleepStages: {
      wake: toNumber(raw.sleepStages?.wake, defaultSleepStages.wake),
      n1: toNumber(raw.sleepStages?.n1, defaultSleepStages.n1),
      n2: toNumber(raw.sleepStages?.n2, defaultSleepStages.n2),
      n3: toNumber(raw.sleepStages?.n3, defaultSleepStages.n3),
      rem: toNumber(raw.sleepStages?.rem, defaultSleepStages.rem),
    },
    features: {
      HR_mean: toNumber(raw.features?.HR_mean, 0),
      HR_std: toNumber(raw.features?.HR_std, 0),
      EDA_mean: toNumber(raw.features?.EDA_mean, 0),
      TEMP_mean: toNumber(raw.features?.TEMP_mean, 0),
      event_rate: toNumber(raw.features?.event_rate, 0),
      sleep_efficiency: sleepEfficiency,
    },
  };
};

export const readStoredSessions = (storageKey: string): Session[] => {
  try {
    const parsed = JSON.parse(localStorage.getItem(storageKey) || "[]");
    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed
      .map((session) => normalizeStoredSession(session))
      .filter((session): session is Session => session !== null);
  } catch {
    return [];
  }
};
