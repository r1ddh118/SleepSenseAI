// Mock data for SleepSense AI Dashboard

export type RiskLevel = "low" | "moderate" | "high";

export interface Session {
  id: string;
  sid: string;
  date: string;
  duration: number; // in minutes
  riskProbability: number;
  riskLevel: RiskLevel;
  status: "completed" | "processing" | "recording";
  sleepStages: {
    wake: number;
    n1: number;
    n2: number;
    n3: number;
    rem: number;
  };
  features: {
    HR_mean: number;
    HR_std: number;
    EDA_mean: number;
    TEMP_mean: number;
    event_rate: number;
    sleep_efficiency: number;
  };
}

export interface SensorDataPoint {
  timestamp: number;
  value: number;
}

export interface SensorStream {
  hr: SensorDataPoint[];
  eda: SensorDataPoint[];
  temp: SensorDataPoint[];
  bvp: SensorDataPoint[];
}

export interface HypnogramPoint {
  timestamp: number;
  stage: number; // 0=Wake, 1=N1, 2=N2, 3=N3, 4=REM
}

export interface ModelMetrics {
  name: string;
  accuracy: number;
  precision: number;
  recall: number;
  f1Score: number;
  aucRoc: number;
  trainTime: number; // seconds
  isActive: boolean;
}

// Generate mock sessions
export const mockSessions: Session[] = [
  {
    id: "S001",
    sid: "S001",
    date: "2026-04-09",
    duration: 480,
    riskProbability: 0.23,
    riskLevel: "low",
    status: "completed",
    sleepStages: {
      wake: 8,
      n1: 12,
      n2: 48,
      n3: 18,
      rem: 14,
    },
    features: {
      HR_mean: 62.3,
      HR_std: 8.2,
      EDA_mean: 2.4,
      TEMP_mean: 33.8,
      event_rate: 0.02,
      sleep_efficiency: 92.5,
    },
  },
  {
    id: "S002",
    sid: "S002",
    date: "2026-04-08",
    duration: 465,
    riskProbability: 0.72,
    riskLevel: "high",
    status: "completed",
    sleepStages: {
      wake: 22,
      n1: 18,
      n2: 42,
      n3: 8,
      rem: 10,
    },
    features: {
      HR_mean: 78.5,
      HR_std: 12.6,
      EDA_mean: 4.2,
      TEMP_mean: 34.2,
      event_rate: 0.08,
      sleep_efficiency: 68.2,
    },
  },
  {
    id: "S003",
    sid: "S003",
    date: "2026-04-07",
    duration: 420,
    riskProbability: 0.45,
    riskLevel: "moderate",
    status: "completed",
    sleepStages: {
      wake: 15,
      n1: 14,
      n2: 45,
      n3: 12,
      rem: 14,
    },
    features: {
      HR_mean: 68.2,
      HR_std: 9.8,
      EDA_mean: 3.1,
      TEMP_mean: 33.9,
      event_rate: 0.04,
      sleep_efficiency: 78.5,
    },
  },
  {
    id: "S004",
    sid: "S004",
    date: "2026-04-06",
    duration: 495,
    riskProbability: 0.18,
    riskLevel: "low",
    status: "completed",
    sleepStages: {
      wake: 5,
      n1: 10,
      n2: 50,
      n3: 20,
      rem: 15,
    },
    features: {
      HR_mean: 58.7,
      HR_std: 7.4,
      EDA_mean: 2.2,
      TEMP_mean: 33.6,
      event_rate: 0.01,
      sleep_efficiency: 94.8,
    },
  },
  {
    id: "S005",
    sid: "S005",
    date: "2026-04-05",
    duration: 510,
    riskProbability: 0.89,
    riskLevel: "high",
    status: "completed",
    sleepStages: {
      wake: 28,
      n1: 22,
      n2: 38,
      n3: 5,
      rem: 7,
    },
    features: {
      HR_mean: 82.4,
      HR_std: 14.2,
      EDA_mean: 5.1,
      TEMP_mean: 34.5,
      event_rate: 0.12,
      sleep_efficiency: 62.3,
    },
  },
];

// Generate continuous sensor data
export const generateSensorData = (sessionId: string): SensorStream => {
  const baseTimestamp = new Date("2026-04-09T22:00:00").getTime();
  const points = 480; // 8 hours of data, one per minute
  
  const hr: SensorDataPoint[] = [];
  const eda: SensorDataPoint[] = [];
  const temp: SensorDataPoint[] = [];
  const bvp: SensorDataPoint[] = [];
  
  const session = mockSessions.find(s => s.id === sessionId);
  const hrMean = session?.features.HR_mean || 65;
  const hrStd = session?.features.HR_std || 8;
  const edaMean = session?.features.EDA_mean || 3;
  const tempMean = session?.features.TEMP_mean || 34;
  
  for (let i = 0; i < points; i++) {
    const timestamp = baseTimestamp + i * 60000;
    
    // Simulate sleep cycles (HR drops during deep sleep)
    const sleepCycle = Math.sin((i / points) * Math.PI * 3) * 0.3;
    
    hr.push({
      timestamp,
      value: hrMean + (Math.random() - 0.5) * hrStd * 2 - sleepCycle * 15,
    });
    
    eda.push({
      timestamp,
      value: Math.max(0, edaMean + (Math.random() - 0.5) * 1.5),
    });
    
    temp.push({
      timestamp,
      value: tempMean + (Math.random() - 0.5) * 0.4 - sleepCycle * 0.3,
    });
    
    bvp.push({
      timestamp,
      value: 60 + (Math.random() - 0.5) * 40,
    });
  }
  
  return { hr, eda, temp, bvp };
};

// Generate hypnogram data
export const generateHypnogramData = (sessionId: string): HypnogramPoint[] => {
  const baseTimestamp = new Date("2026-04-09T22:00:00").getTime();
  const epochs = 96; // 8 hours, 5-minute epochs
  const data: HypnogramPoint[] = [];
  
  const session = mockSessions.find(s => s.id === sessionId);
  if (!session) return [];
  
  const stages = session.sleepStages;
  const totalPct = stages.wake + stages.n1 + stages.n2 + stages.n3 + stages.rem;
  
  let currentStage = 0; // Start awake
  
  for (let i = 0; i < epochs; i++) {
    const timestamp = baseTimestamp + i * 300000; // 5 minutes
    
    // Simulate realistic sleep progression
    if (i < 3) currentStage = 0; // Wake at start
    else if (i < 6) currentStage = 1; // N1
    else if (i < 30) {
      // First sleep cycle
      const cycle = (i - 6) % 20;
      if (cycle < 4) currentStage = 2; // N2
      else if (cycle < 10) currentStage = 3; // N3
      else if (cycle < 14) currentStage = 2; // N2
      else currentStage = 4; // REM
    } else if (i < 60) {
      // Second sleep cycle
      const cycle = (i - 30) % 20;
      if (cycle < 6) currentStage = 2;
      else if (cycle < 10) currentStage = 3;
      else if (cycle < 14) currentStage = 2;
      else currentStage = 4;
    } else {
      // Later cycles - less deep sleep
      const cycle = (i - 60) % 18;
      if (cycle < 8) currentStage = 2;
      else if (cycle < 10) currentStage = 3;
      else if (cycle < 14) currentStage = 2;
      else currentStage = 4;
    }
    
    // Add some wake periods for high-risk sessions
    if (session.riskLevel === "high" && Math.random() < 0.15) {
      currentStage = 0;
    }
    
    data.push({ timestamp, stage: currentStage });
  }
  
  return data;
};

// Model leaderboard data
export const modelLeaderboard: ModelMetrics[] = [
  {
    name: "XGBoost",
    accuracy: 0.932,
    precision: 0.918,
    recall: 0.945,
    f1Score: 0.931,
    aucRoc: 0.967,
    trainTime: 45.2,
    isActive: true,
  },
  {
    name: "Random Forest",
    accuracy: 0.928,
    precision: 0.912,
    recall: 0.941,
    f1Score: 0.926,
    aucRoc: 0.961,
    trainTime: 62.8,
    isActive: false,
  },
  {
    name: "LightGBM",
    accuracy: 0.925,
    precision: 0.908,
    recall: 0.938,
    f1Score: 0.923,
    aucRoc: 0.958,
    trainTime: 38.6,
    isActive: false,
  },
  {
    name: "Neural Network (MLP)",
    accuracy: 0.918,
    precision: 0.901,
    recall: 0.932,
    f1Score: 0.916,
    aucRoc: 0.952,
    trainTime: 124.3,
    isActive: false,
  },
  {
    name: "SVM (RBF)",
    accuracy: 0.912,
    precision: 0.895,
    recall: 0.925,
    f1Score: 0.910,
    aucRoc: 0.945,
    trainTime: 89.5,
    isActive: false,
  },
  {
    name: "Logistic Regression",
    accuracy: 0.898,
    precision: 0.882,
    recall: 0.912,
    f1Score: 0.897,
    aucRoc: 0.932,
    trainTime: 12.4,
    isActive: false,
  },
  {
    name: "Decision Tree",
    accuracy: 0.885,
    precision: 0.868,
    recall: 0.898,
    f1Score: 0.883,
    aucRoc: 0.918,
    trainTime: 8.7,
    isActive: false,
  },
  {
    name: "Naive Bayes",
    accuracy: 0.872,
    precision: 0.854,
    recall: 0.886,
    f1Score: 0.870,
    aucRoc: 0.905,
    trainTime: 5.2,
    isActive: false,
  },
];

// Patient metadata
export const patientInfo = {
  name: "John Doe",
  patientId: "PT-2026-001",
  age: 42,
  deviceId: "E4-RPi5-001",
  totalSessions: 47,
  avgRiskScore: 0.34,
  lastSessionDate: "2026-04-09",
};
