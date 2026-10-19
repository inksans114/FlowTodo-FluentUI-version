"""Explicit downloads: no uploads, no overwrite of an existing local record."""
from cloud_sync import fingerprint

def import_downloads(backend,engine,rows):
    imported=skipped=0
    for item in sorted(rows,key=lambda r:0 if r['kind']=='tasks' else 1):
        if item.get('deletedAt'):continue
        local=backend._cloud_snapshot()
        uid=item.get('payload',{}).get('_syncUid')
        linked=next((key for key,link in engine.links.items() if link['id']==item['id']),None)
        existing=next((r for r in local if r['key']==linked or (uid and r['kind']==item['kind'] and r['payload'].get('_syncUid')==uid)),None)
        if existing:
            # An explicit import must never replace work already on this device.
            if fingerprint(existing)==fingerprint(item):
                engine.links[existing['key']]={'id':item['id'],'version':item['version'],'kind':item['kind'],'base':fingerprint(existing),'remoteBase':fingerprint(item)}
                engine.save(engine.links)
            skipped+=1;continue
        key=backend._import_cloud_record(item)
        current=next(r for r in backend._cloud_snapshot() if r['key']==key)
        engine.links[key]={'id':item['id'],'version':item['version'],'kind':item['kind'],'base':fingerprint(current),'remoteBase':fingerprint(item)}
        engine.save(engine.links)
        imported+=1
    return imported,skipped
