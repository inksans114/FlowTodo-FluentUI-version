PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,plan TEXT NOT NULL DEFAULT 'free' CHECK(plan IN ('free','lite','standard')),role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user','admin')),balance_cents INTEGER NOT NULL DEFAULT 0,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,csrf TEXT NOT NULL,expires INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires);
CREATE TABLE IF NOT EXISTS codes(owner TEXT NOT NULL,email TEXT NOT NULL,purpose TEXT NOT NULL,hash TEXT NOT NULL,expires INTEGER NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(owner,email,purpose));
CREATE TABLE IF NOT EXISTS rate_limits(key TEXT PRIMARY KEY,count INTEGER NOT NULL,expires INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS rate_expiry ON rate_limits(expires);
CREATE TABLE IF NOT EXISTS interests(user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,plan TEXT NOT NULL,cycle TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(user_id,plan,cycle));
CREATE TABLE IF NOT EXISTS cloud_items(id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,kind TEXT NOT NULL CHECK(kind IN ('tasks','flows','aiPlans')),title TEXT NOT NULL,payload TEXT NOT NULL,bytes INTEGER NOT NULL,version INTEGER NOT NULL DEFAULT 1,updated_at TEXT NOT NULL,deleted_at TEXT);
CREATE INDEX IF NOT EXISTS cloud_owner_kind ON cloud_items(user_id,kind,deleted_at);
CREATE INDEX IF NOT EXISTS cloud_owner_updated ON cloud_items(user_id,updated_at);
CREATE TRIGGER IF NOT EXISTS cloud_insert_quota BEFORE INSERT ON cloud_items WHEN NEW.deleted_at IS NULL BEGIN
 SELECT CASE WHEN (SELECT COUNT(*) FROM cloud_items WHERE user_id=NEW.user_id AND kind=NEW.kind AND deleted_at IS NULL)>=
 (SELECT CASE WHEN plan='free' THEN CASE NEW.kind WHEN 'tasks' THEN 30 ELSE 5 END WHEN plan='lite' THEN CASE NEW.kind WHEN 'tasks' THEN 300 ELSE 50 END ELSE CASE NEW.kind WHEN 'tasks' THEN 2000 ELSE 300 END END FROM users WHERE id=NEW.user_id)
 THEN RAISE(ABORT,'record_quota') END;
 SELECT CASE WHEN COALESCE((SELECT SUM(bytes) FROM cloud_items WHERE user_id=NEW.user_id AND deleted_at IS NULL),0)+NEW.bytes>
 (SELECT CASE plan WHEN 'free' THEN 104857600 WHEN 'lite' THEN 1073741824 ELSE 5368709120 END FROM users WHERE id=NEW.user_id)
 THEN RAISE(ABORT,'storage_quota') END;
END;
CREATE TRIGGER IF NOT EXISTS cloud_update_quota BEFORE UPDATE ON cloud_items WHEN NEW.deleted_at IS NULL BEGIN
 SELECT CASE WHEN (SELECT COUNT(*) FROM cloud_items WHERE user_id=NEW.user_id AND kind=NEW.kind AND deleted_at IS NULL AND id<>NEW.id)>=
 (SELECT CASE WHEN plan='free' THEN CASE NEW.kind WHEN 'tasks' THEN 30 ELSE 5 END WHEN plan='lite' THEN CASE NEW.kind WHEN 'tasks' THEN 300 ELSE 50 END ELSE CASE NEW.kind WHEN 'tasks' THEN 2000 ELSE 300 END END FROM users WHERE id=NEW.user_id)
 THEN RAISE(ABORT,'record_quota') END;
 SELECT CASE WHEN COALESCE((SELECT SUM(bytes) FROM cloud_items WHERE user_id=NEW.user_id AND deleted_at IS NULL AND id<>NEW.id),0)+NEW.bytes>
 (SELECT CASE plan WHEN 'free' THEN 104857600 WHEN 'lite' THEN 1073741824 ELSE 5368709120 END FROM users WHERE id=NEW.user_id)
 THEN RAISE(ABORT,'storage_quota') END;
END;
