CREATE UNIQUE INDEX IF NOT EXISTS cloud_items_sync_uid ON cloud_items(user_id,json_extract(payload,'$._syncUid')) WHERE json_extract(payload,'$._syncUid') IS NOT NULL;
