// Shared proposal data; actual entitlement changes remain server controlled.
export const PLANS = [
  { id: 'free', name: 'Free', monthly: 0, annual: 0, tasks: 30, flows: 5, aiPlans: 5, storageMB: 100, aiCalls: 5, aiPeriod: '累计试用', versions: 0 },
  { id: 'lite', name: 'Lite', monthly: 5.99, annual: 59.90, tasks: 300, flows: 50, aiPlans: 50, storageMB: 1024, aiCalls: 100, aiPeriod: '每月', versions: 7 },
  { id: 'standard', name: 'Standard', monthly: 9.99, annual: 99.90, tasks: 2000, flows: 300, aiPlans: 300, storageMB: 5120, aiCalls: 300, aiPeriod: '每月', versions: 30 },
];
