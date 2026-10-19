"""Three-way record sync. Conflicts and cloud deletions never overwrite local work."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from ai_library import write_state


def fingerprint(record):
    value = {key: record[key] for key in ("kind", "title", "payload")}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class SyncEngine:
    def __init__(self, path):
        self.path = Path(path)
        try:
            self.links = json.loads(self.path.read_text(encoding="utf-8")).get("links", {})
        except (OSError, ValueError):
            self.links = {}

    def save(self, links):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_state(self.path, {"version": 1, "links": links})
        self.links = links

    def run(self, client, local, selected=(), pull_new=True):
        links = copy.deepcopy(self.links)
        committed = copy.deepcopy(self.links)
        remote = {row["id"]: row for row in client.list_records() + client.list_records(True)}
        local_by_key = {row["key"]: row for row in local}
        pulls, conflicts, uploaded, known = [], [], 0, set()
        for key, row in local_by_key.items():
            link = links.get(key)
            if not link:
                candidate = next((r for r in remote.values() if row['payload'].get('_syncUid') and r['payload'].get('_syncUid')==row['payload']['_syncUid']), None)
                if candidate:
                    links[key]={'id':candidate['id'],'version':candidate['version'],'base':fingerprint(row),'remoteBase':fingerprint(candidate),'kind':row['kind']}
                    known.add(candidate['id'])
                    if candidate.get('deletedAt') or fingerprint(row)!=fingerprint(candidate):
                        links[key].update(base=None,remoteBase=None)
                        conflicts.append({'key':key,'title':row['title'],'reason':'发现同一记录的云端版本，请确认保留哪一份。','remote':candidate})
                    continue
                if key in selected:
                    created = client.request('/api/cloud/items', {k: row[k] for k in ('kind','title','payload')})['item']
                    links[key] = {'id': created['id'], 'version': created['version'], 'base': fingerprint(row), 'kind': row['kind']}
                    if created.get('payload') is not None and (created.get('deletedAt') or fingerprint(created)!=fingerprint(row)):
                        links[key].update(base=None,remoteBase=None)
                        conflicts.append({'key':key,'title':row['title'],'reason':'上传期间发现同一记录的其他版本，两份内容均已保留。','remote':created})
                        known.add(created['id']);continue
                    committed[key]=copy.deepcopy(links[key]);self.save(committed)
                    known.add(created['id']); uploaded += 1
                continue
            known.add(link['id'])
            cloud = remote.get(link['id'])
            if not cloud or cloud.get('deletedAt'):
                conflicts.append({'key': key, 'title': row['title'], 'reason': '云端已删除，本地记录已保留。', 'remote': cloud})
                continue
            here, there, base = fingerprint(row), fingerprint(cloud), link['base']
            remote_base=link.get('remoteBase',base)
            if here == there:
                links[key].update(version=cloud['version'], base=here,remoteBase=there)
            elif here != base and there != remote_base:
                conflicts.append({'key': key, 'title': row['title'], 'reason': '本地与云端都已修改，请选择保留哪一份。', 'remote': cloud})
            elif here != base:
                try:
                    client.request('/api/cloud/items/'+cloud['id'], {k: row[k] for k in ('title','payload')} | {'version': cloud['version']}, 'PATCH')
                    links[key].update(version=cloud['version']+1, base=here); uploaded += 1
                    links[key]['remoteBase']=here
                    committed[key]=copy.deepcopy(links[key]);self.save(committed)
                except Exception as error:
                    if getattr(error, 'status', 0) != 409:
                        raise
                    conflicts.append({'key': key, 'title': row['title'], 'reason': '云端刚刚发生修改，请重新同步。', 'remote': cloud})
            elif there != remote_base:
                pulls.append({'key': key, 'expected': here, 'item': cloud})
                links[key].update(version=cloud['version'], base=there)
        if pull_new:
            for cloud in remote.values():
                if not cloud.get('deletedAt') and cloud['id'] not in known and not any(link['id']==cloud['id'] for link in links.values()):
                    pulls.append({'key': None, 'expected': None, 'item': cloud})
        return {'links': links, 'pulls': pulls, 'conflicts': conflicts, 'uploaded': uploaded}
