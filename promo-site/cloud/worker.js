import { createWorker } from './worker-core.js';
import { sendCode } from './smtp.js';
export default createWorker({ sendCode });
