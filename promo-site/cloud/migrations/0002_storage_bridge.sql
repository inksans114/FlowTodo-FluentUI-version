CREATE TABLE IF NOT EXISTS storage_bridge_jobs(id TEXT PRIMARY KEY,payload TEXT NOT NULL,response TEXT,state TEXT NOT NULL,kind TEXT NOT NULL,created INTEGER NOT NULL,expires INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS storage_bridge_pending ON storage_bridge_jobs(state,kind,created);
CREATE TABLE IF NOT EXISTS storage_bridge_nonces(id TEXT PRIMARY KEY,expires INTEGER NOT NULL);
