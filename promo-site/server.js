import { createApp } from './api.js';
const port = Number(process.env.PORT || 4190);
const service = createApp();
const server = service.app.listen(port, '127.0.0.1', () => console.log(`FlowTodo user website: http://localhost:${port}`));
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => server.close(() => { service.close(); process.exit(0); }));
