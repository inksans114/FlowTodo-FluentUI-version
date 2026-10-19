"""Durable graph of task membership and execution relationships."""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
from uuid import uuid4
from ai_library import write_state


def ensure_child_ids(records, field):
    changed = False
    for record in records:
        seen = set()
        for child in record.get(field, []):
            key = child.get("relationId")
            if not isinstance(key, str) or not key or key in seen:
                child["relationId"] = uuid4().hex
                changed = True
            seen.add(child["relationId"])
    return changed


def build_graph(tasks, groups, projects, today, positions=None, collection_positions=None):
    positions, buckets, nodes = positions or {}, {}, []
    collection_positions = collection_positions or {}
    def add(collection, label, kind, key, title, record, **extra):
        buckets.setdefault(collection, {"key": collection, "title": label, "nodes": []})
        node = {"key": key, "kind": kind, "title": str(title or "未命名"),
                "collection": collection, "collectionTitle": label, "done": bool(record.get("done")),
                "minutes": 25, "width": 250, "height": 82, **extra}
        buckets[collection]["nodes"].append(node)
        nodes.append(node)
    task_lookup = {str(t['id']): t for t in tasks if not t.get('archived')}
    memberships = {}
    for group in groups:
        for step in group.get('steps', []):
            if step.get('taskId') is not None:
                memberships.setdefault(str(step['taskId']), []).append(f"group:{group['id']}")
    for task in tasks:
        if task.get("archived"):
            continue
        if str(task['id']) in memberships:
            continue
        date = str(task.get("scheduledDate") or task.get("dailyDate") or today)
        daily = task.get("taskType") == "daily"
        bucket = "daily" if daily else "today" if date == today else "schedule"
        label = "每日重复" if daily else "今日任务" if bucket == "today" else "日程任务"
        add(bucket, label, "task", f"task:{task['id']}", task.get("title"), task,
            itemId=task["id"], detail=date, minutes=task.get("focusMinutes", 25))
    for group in groups:
        bucket, label = f"group:{group['id']}", str(group.get("name") or "任务流")
        steps = group.get("steps", [])
        focus_steps = [s for s in steps if s.get("type") != "break"]
        members = [f"task:{s['taskId']}" if s.get('taskId') is not None else f"step:{group['id']}:{s['relationId']}" for s in focus_steps]
        add(bucket, label, "group", bucket, "启动整个任务流", {"done": bool(focus_steps) and all(task_lookup.get(str(s['taskId']), {}).get('done') if s.get('taskId') is not None else s.get("relationDone") for s in focus_steps)},
            itemId=group["id"], detail=label, members=members,
            minutes=sum(float(s.get('duration') or s.get('time') or 25) for s in steps))
        for index, step in enumerate(steps):
            if step.get('taskId') is not None:
                task = task_lookup.get(str(step['taskId']), {})
                key = f"task:{step['taskId']}"
                if any(n['key'] == key for n in nodes):
                    continue
                add(bucket, label, "task", key, task.get('title') or step.get('name'), task,
                    itemId=step['taskId'], parentKey=bucket, parents=memberships[str(step['taskId'])], sequence=index,
                    detail=f"步骤 {index + 1} · 关联待办", minutes=step.get('duration') or task.get('focusMinutes', 25))
                continue
            add(bucket, label, "step", f"step:{group['id']}:{step['relationId']}", step.get("name") or step.get("title"),
                {"done": step.get("relationDone", False)}, itemId=group["id"], childId=step["relationId"],
                parentKey=bucket, sequence=index,
                detail=f"步骤 {index + 1}" + (" · 休息" if step.get("type") == "break" else ""),
                minutes=step.get("duration") or step.get("time") or 25, isBreak=step.get("type") == "break")
    for project in projects:
        bucket, label = f"project:{project['id']}", str(project.get("name") or "项目")
        milestones = project.get("milestones", [])
        add(bucket, label, "project", bucket, label, {"done": bool(milestones) and all(m.get("done") for m in milestones)},
            itemId=project["id"], detail="整个项目", members=[f"milestone:{project['id']}:{m['relationId']}" for m in milestones])
        for index, milestone in enumerate(milestones):
            add(bucket, label, "milestone", f"milestone:{project['id']}:{milestone['relationId']}", milestone.get("title") or milestone.get("name"),
                milestone, itemId=project["id"], childId=milestone["relationId"], detail=f"里程碑 {index + 1}")
    collections, row_y, values = [], 24, list(buckets.values())
    for start in range(0, len(values), 3):
        row_height = 0
        for column, bucket in enumerate(values[start:start + 3]):
            bucket.update(x=24 + column * 360, y=row_y, width=330, height=180 + len(bucket["nodes"]) * 108)
            saved_collection = collection_positions.get(bucket["key"])
            if saved_collection:
                bucket["x"] = max(0, saved_collection["x"])
                bucket["y"] = max(0, saved_collection["y"])
            for index, node in enumerate(bucket["nodes"]):
                saved = positions.get(node["key"], {})
                node["offsetX"] = max(16, min(64, float(saved.get("x", 40))))
                node["offsetY"] = max(58, min(bucket["height"] - 98, float(saved.get("y", 64 + index * 108))))
                node["x"], node["y"] = bucket["x"] + node["offsetX"], bucket["y"] + node["offsetY"]
            row_height = max(row_height, bucket["height"])
            collections.append({k: v for k, v in bucket.items() if k != "nodes"})
        row_y += row_height + 36
    return {"nodes": nodes, "collections": collections,
            "width": max([720] + [c["x"] + c["width"] + 24 for c in collections]),
            "height": max([480, row_y] + [c["y"] + c["height"] + 24 for c in collections])}


class TaskRelations:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {"version": 1, "edges": [], "positions": {}, "collectionPositions": {}}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(raw, dict) and raw.get("version") == 1:
                self.data["edges"] = [e for e in raw.get("edges", []) if isinstance(e, dict)
                    and e.get("type") in ("next", "together") and isinstance(e.get("id"), str)
                    and isinstance(e.get("source"), str) and isinstance(e.get("target"), str) and e["source"] != e["target"]]
                self.data["positions"] = {key: value for key, value in raw.get("positions", {}).items()
                    if isinstance(value, dict) and all(isinstance(value.get(k), (int, float)) and math.isfinite(value[k]) for k in ("x", "y"))}
                self.data["collectionPositions"] = {key: value for key, value in raw.get("collectionPositions", {}).items()
                    if isinstance(key, str) and isinstance(value, dict)
                    and all(isinstance(value.get(k), (int, float)) and math.isfinite(value[k]) for k in ("x", "y"))}
        except (OSError, ValueError, TypeError, AttributeError):
            pass

    def commit(self, data):
        write_state(self.path, data)
        self.data = data

    def edges(self, nodes):
        keys = {n["key"] for n in nodes}
        return [e for e in self.data["edges"] if e["source"] in keys and e["target"] in keys]

    def execution_edges(self, nodes):
        edges = list(self.edges(nodes))
        parents = {}
        for node in nodes:
            if node.get('parentKey') and not node.get('isBreak'):
                parents.setdefault(node['parentKey'], []).append(node)
        for parent, children in parents.items():
            children.sort(key=lambda n: n.get('sequence', 0))
            for first, second in zip(children, children[1:]):
                edges.append({'id': f"sequence:{parent}:{first['key']}", 'source': first['key'],
                              'target': second['key'], 'type': 'next', 'readonly': True})
        return edges

    def validate(self, nodes, key=None, edges=None):
        """Validate execution, including implicit step order and completion sets."""
        lookup = {n['key']: n for n in nodes}
        edges = self.execution_edges(nodes) if edges is None else edges
        selected = set(lookup)
        if key is not None:
            selected, pending = {key}, [key]
            if lookup.get(key, {}).get('parentKey'):
                selected.add(lookup[key]['parentKey'])
            selected.update(lookup.get(key, {}).get('members', []))
            pending = list(selected)
            while pending:
                current = pending.pop()
                for member in lookup.get(current, {}).get('members', []):
                    if member not in selected:
                        selected.add(member); pending.append(member)
                for e in edges:
                    neighbor = e['target'] if e['source'] == current else e['source'] if e['target'] == current else None
                    if neighbor and neighbor not in selected:
                        selected.add(neighbor); pending.append(neighbor)
        edges = [e for e in edges if e['source'] in selected and e['target'] in selected]
        owners = {k: k for k in selected}
        def root(k):
            while owners[k] != k:
                owners[k] = owners[owners[k]]; k = owners[k]
            return k
        pairs = set()
        for e in edges:
            a, b = e['source'], e['target']
            pair = tuple(sorted((a, b))) if e['type'] == 'together' else (a, b)
            token = (e['type'], pair)
            if token in pairs or a == b:
                raise ValueError('存在重复连线，请保留一条关联。')
            pairs.add(token)
            if e['type'] == 'together':
                ra, rb = root(a), root(b)
                if ra == rb:
                    raise ValueError('一起完成的任务已经关联，不能重复嵌套。')
                owners[ra] = rb
        outgoing, incoming = {}, {}
        coarse = {}
        for e in edges:
            if e['type'] != 'next': continue
            a, b = root(e['source']), root(e['target'])
            if a == b: raise ValueError('同一组任务不能既一起完成又接着做。')
            coarse.setdefault(a, set()).add(b)
        indegree = {k: 0 for k in {root(k) for k in selected}}
        for targets in coarse.values():
            for target in targets: indegree[target] += 1
        pending = [k for k, degree in indegree.items() if degree == 0]
        processed = 0
        while pending:
            current = pending.pop(); processed += 1
            for target in coarse.get(current, ()):
                indegree[target] -= 1
                if indegree[target] == 0: pending.append(target)
        if processed != len(indegree): raise ValueError('流程形成循环，请调整任务顺序。')
        for e in edges:
            if e['type'] != 'next': continue
            source_members = lookup.get(e['source'], {}).get('members') or [e['source']]
            target_members = lookup.get(e['target'], {}).get('members') or [e['target']]
            a, b = root(source_members[-1]), root(target_members[0])
            if a == b:
                raise ValueError('同一组任务不能既一起完成又接着做。')
            if a in outgoing or b in incoming:
                raise ValueError('流程出现交叉或重复路径。每组任务只能有一个前一步和一个下一步。')
            outgoing[a], incoming[b] = b, a
        for start in outgoing:
            seen, current = set(), start
            while current in outgoing:
                if current in seen: raise ValueError('流程形成循环，请调整任务顺序。')
                seen.add(current); current = outgoing[current]
        # An aggregate and its children must never run twice in one connected flow.
        adjacency = {k: set() for k in selected}
        for e in edges:
            adjacency[e['source']].add(e['target']); adjacency[e['target']].add(e['source'])
        visited = set()
        for start in selected:
            if start in visited: continue
            pending, units = [start], set()
            while pending:
                current = pending.pop()
                if current in visited: continue
                visited.add(current)
                node = lookup.get(current, {})
                members = node.get('members') or [current]
                if len(members) != len(set(members)) or units.intersection(members):
                    raise ValueError('整个集合和它的子任务重复嵌套，请只连接其中一层。')
                units.update(members); pending.extend(adjacency[current] - visited)
        return True

    def connect(self, source, target, kind, nodes):
        keys = {n["key"] for n in nodes}
        if source not in keys or target not in keys:
            raise ValueError("任务已经移除，请刷新关系图。")
        if source == target:
            raise ValueError("请选择另一个任务。")
        if kind not in ("next", "together"):
            raise ValueError("请选择连线类型。")
        if kind == "together":
            source, target = sorted((source, target))
        edges = self.edges(nodes)
        if any(e["source"] == source and e["target"] == target and e["type"] == kind for e in edges):
            raise ValueError("这条关联已经存在。")
        if kind == "next":
            reachable, pending = set(), [target]
            while pending:
                key = pending.pop()
                if key == source:
                    raise ValueError("这条连线会形成循环，请调整任务顺序。")
                if key in reachable:
                    continue
                reachable.add(key)
                pending.extend(e["target"] for e in edges if e["type"] == "next" and e["source"] == key)
        data = copy.deepcopy(self.data)
        edge = {"id": uuid4().hex, "source": source, "target": target, "type": kind}
        self.validate(nodes, source, self.execution_edges(nodes) + [edge])
        data["edges"] = edges + [edge]
        self.commit(data)
        return edge

    def disconnect(self, edge_id):
        if edge_id.startswith('sequence:'):
            raise ValueError('步骤顺序由任务流管理，请在编辑任务流中调整。')
        data = copy.deepcopy(self.data)
        data["edges"] = [e for e in data["edges"] if e.get("id") != edge_id]
        self.commit(data)

    def move(self, key, x, y):
        if not all(math.isfinite(v) for v in (x, y)):
            raise ValueError("节点位置无效。")
        data = copy.deepcopy(self.data)
        data["positions"][key] = {"x": x, "y": y}
        self.commit(data)

    def related(self, key, kind, nodes):
        lookup = {n["key"]: n for n in nodes}
        edges = self.execution_edges(nodes)
        if kind == "next":
            component, pending = {key}, [key]
            while pending:
                current = pending.pop()
                for e in edges:
                    if e['type'] != 'together': continue
                    neighbor = e['target'] if e['source'] == current else e['source'] if e['target'] == current else None
                    if neighbor and neighbor not in component:
                        component.add(neighbor); pending.append(neighbor)
            keys = list(dict.fromkeys(e['target'] for e in edges if e['type'] == 'next' and e['source'] in component))
            pending, keys, visited = keys, [], set(component)
            while pending:
                current = pending.pop(0)
                if current in visited: continue
                visited.add(current)
                if not lookup.get(current, {}).get('done'):
                    keys.append(current)
                else:
                    pending.extend(e['target'] for e in edges if e['type'] == 'next' and e['source'] == current)
        else:
            visited, pending = {key}, [key]
            while pending:
                current = pending.pop()
                for edge in edges:
                    if edge["type"] != "together":
                        continue
                    neighbor = edge["target"] if edge["source"] == current else edge["source"] if edge["target"] == current else None
                    if neighbor and neighbor not in visited:
                        visited.add(neighbor)
                        pending.append(neighbor)
            keys = sorted(visited - {key})
        return [lookup[k] for k in keys if k in lookup and not lookup[k]["done"]]

    def move_collection(self, key, x, y):
        if not all(math.isfinite(v) for v in (x, y)):
            raise ValueError("集合位置无效。")
        data = copy.deepcopy(self.data)
        data["collectionPositions"][key] = {"x": max(0, x), "y": max(0, y)}
        self.commit(data)

    def remove_nodes(self, keys):
        keys = set(keys)
        data = copy.deepcopy(self.data)
        data["edges"] = [e for e in data["edges"] if e["source"] not in keys and e["target"] not in keys]
        data["positions"] = {k: v for k, v in data["positions"].items() if k not in keys}
        data["collectionPositions"] = {k: v for k, v in data["collectionPositions"].items() if k not in keys}
        self.commit(data)

    def clear(self):
        self.commit({"version": 1, "edges": [], "positions": {}, "collectionPositions": {}})
