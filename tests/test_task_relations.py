import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from task_relations import TaskRelations, build_graph, ensure_child_ids


class TaskRelationsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'task_relations.json'
        self.store = TaskRelations(self.path)
        self.nodes = [{'key': key, 'done': False} for key in ('task:1', 'task:2', 'milestone:3:m')]

    def test_next_is_directed_and_cannot_loop(self):
        self.store.connect('task:1', 'task:2', 'next', self.nodes)
        self.store.connect('task:2', 'milestone:3:m', 'next', self.nodes)
        with self.assertRaises(ValueError):
            self.store.connect('milestone:3:m', 'task:1', 'next', self.nodes)
        self.assertEqual([n['key'] for n in self.store.related('task:1', 'next', self.nodes)], ['task:2'])
        self.assertEqual(self.store.related('milestone:3:m', 'next', self.nodes), [])

    def test_together_is_symmetric_transitive_and_deduplicated(self):
        self.store.connect('task:1', 'task:2', 'together', self.nodes)
        self.store.connect('task:2', 'milestone:3:m', 'together', self.nodes)
        with self.assertRaises(ValueError):
            self.store.connect('task:2', 'task:1', 'together', self.nodes)
        self.assertEqual({n['key'] for n in self.store.related('milestone:3:m', 'together', self.nodes)}, {'task:1', 'task:2'})

    def test_rejects_self_missing_and_invalid_links(self):
        for a, b, kind in [('task:1', 'task:1', 'next'), ('missing', 'task:2', 'next'), ('task:1', 'task:2', 'bad')]:
            with self.assertRaises(ValueError): self.store.connect(a, b, kind, self.nodes)

    def test_edges_and_layout_survive_restart(self):
        self.store.connect('task:1', 'task:2', 'next', self.nodes)
        self.store.move('task:1', 20, 100)
        restored = TaskRelations(self.path)
        self.assertEqual(restored.data, self.store.data)
        edge = restored.data['edges'][0]
        restored.disconnect(edge['id'])
        self.assertEqual(TaskRelations(self.path).data['edges'], [])

    def test_failed_write_does_not_change_in_memory_state(self):
        before = copy.deepcopy(self.store.data)
        with patch('task_relations.write_state', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.store.connect('task:1', 'task:2', 'next', self.nodes)
        self.assertEqual(self.store.data, before)

    def test_delete_removes_edges_and_position(self):
        self.store.connect('task:1', 'task:2', 'next', self.nodes)
        self.store.move('task:1', 20, 100)
        self.store.remove_nodes(['task:1'])
        self.assertEqual(self.store.data['edges'], [])
        self.assertNotIn('task:1', self.store.data['positions'])

    def test_child_identity_survives_rename_and_reorder(self):
        groups = [{'id': 2, 'name':'流程', 'steps':[{'name':'第一步'}, {'name':'第一步'}]}]
        ensure_child_ids(groups, 'steps')
        first = groups[0]['steps'][0]['relationId']
        groups[0]['steps'].reverse()
        groups[0]['steps'][1]['name'] = '新名称'
        self.assertFalse(ensure_child_ids(groups, 'steps'))
        graph = build_graph([], groups, [], '2026-10-09')
        node = next(n for n in graph['nodes'] if n['key'] == 'step:2:' + first)
        self.assertEqual(node['title'], '新名称')

    def test_collection_move_preserves_relative_positions_and_expands_canvas(self):
        tasks = [{'id': 1, 'title':'报告'}]
        self.store.move('task:1', 42, 90)
        self.store.move_collection('today', 1500, 800)
        restored = TaskRelations(self.path)
        graph = build_graph(tasks, [], [], '2026-10-09', restored.data['positions'], restored.data['collectionPositions'])
        self.assertEqual(graph['nodes'][0]['x'], 1542)
        self.assertEqual(graph['nodes'][0]['y'], 890)
        self.assertGreater(graph['width'], 1800)
        self.assertGreater(graph['height'], 1000)
        self.assertEqual(graph['collections'][0]['x'], 1500)

    def test_failed_collection_move_retains_state_and_rejects_nonfinite(self):
        before = copy.deepcopy(self.store.data)
        with patch('task_relations.write_state', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.store.move_collection('today', 20, 40)
        self.assertEqual(self.store.data, before)
        with self.assertRaises(ValueError): self.store.move_collection('today', float('nan'), 40)

    def test_membership_repositions_rescheduled_task_with_saved_offsets(self):
        tasks = [{'id':1,'title':'报告','scheduledDate':'2026-10-10'}, {'id':2,'title':'今天','scheduledDate':'2026-10-09'}]
        graph = build_graph(tasks, [], [], '2026-10-09', {'task:1':{'x':40,'y':75}})
        self.assertEqual(graph['nodes'][0]['collection'], 'schedule')
        tasks[0]['scheduledDate'] = '2026-10-09'
        graph = build_graph(tasks, [], [], '2026-10-09', {'task:1':{'x':40,'y':75}})
        self.assertEqual(graph['nodes'][0]['collection'], 'today')
        self.assertEqual(graph['nodes'][0]['offsetY'], 75)

    def test_mixed_together_and_next_cycle_is_rejected_without_saving(self):
        self.store.connect('task:1', 'task:2', 'together', self.nodes)
        self.store.connect('task:2', 'milestone:3:m', 'next', self.nodes)
        before = copy.deepcopy(self.store.data)
        with self.assertRaises(ValueError):
            self.store.connect('milestone:3:m', 'task:1', 'next', self.nodes)
        with self.assertRaises(ValueError):
            self.store.connect('task:1', 'milestone:3:m', 'together', self.nodes)
        self.assertEqual(before, self.store.data)

    def test_branches_merges_and_transitive_redundancy_are_rejected(self):
        self.store.connect('task:1', 'task:2', 'next', self.nodes)
        for a, b in [('task:1', 'milestone:3:m'), ('milestone:3:m', 'task:2')]:
            with self.assertRaises(ValueError): self.store.connect(a, b, 'next', self.nodes)
        self.store.connect('task:2', 'milestone:3:m', 'next', self.nodes)
        with self.assertRaises(ValueError): self.store.connect('task:1', 'milestone:3:m', 'next', self.nodes)

    def test_together_triangle_is_duplicate_logic(self):
        self.store.connect('task:1', 'task:2', 'together', self.nodes)
        self.store.connect('task:2', 'milestone:3:m', 'together', self.nodes)
        with self.assertRaises(ValueError): self.store.connect('task:1', 'milestone:3:m', 'together', self.nodes)

    def test_group_references_canonical_tasks_and_orders_children(self):
        tasks = [{'id': 1, 'title': '阅读', 'done': False}, {'id': 2, 'title': '写作', 'done': True}]
        groups = [{'id': 4, 'name': '英语作业', 'steps': [{'taskId': 1}, {'taskId': 2}]}]
        ensure_child_ids(groups, 'steps')
        graph = build_graph(tasks, groups, [], '2026-10-11')
        self.assertEqual(len(graph['nodes']), 3)
        first = next(n for n in graph['nodes'] if n['key'] == 'task:1')
        self.assertEqual(first['collectionTitle'], '英语作业')
        self.assertEqual(len(self.store.execution_edges(graph['nodes'])), 1)
        self.assertEqual(self.store.related('task:1', 'next', graph['nodes']), [])
        with self.assertRaises(ValueError): self.store.connect('task:2', 'task:1', 'next', graph['nodes'])
        with self.assertRaises(ValueError): self.store.connect('group:4', 'task:1', 'next', graph['nodes'])
        with self.assertRaises(ValueError): self.store.disconnect(self.store.execution_edges(graph['nodes'])[0]['id'])

    def test_next_continues_from_completion_component_and_skips_done(self):
        nodes = self.nodes + [{'key': 'task:4', 'done': False}]
        self.store.connect('task:1', 'task:2', 'together', nodes)
        self.store.connect('task:2', 'milestone:3:m', 'next', nodes)
        self.store.connect('milestone:3:m', 'task:4', 'next', nodes)
        nodes[2]['done'] = True
        self.assertEqual([n['key'] for n in self.store.related('task:1', 'next', nodes)], ['task:4'])

    def test_loaded_invalid_graph_does_not_hang_or_silently_run(self):
        self.store.data['edges'] = [dict(id=str(i), source=a, target=b, type='next') for i, (a,b) in enumerate([('task:1','task:2'),('task:2','task:1')])]
        self.nodes[0]['done'] = self.nodes[1]['done'] = True
        self.assertEqual(self.store.related('task:1', 'next', self.nodes), [])
        with self.assertRaises(ValueError): self.store.validate(self.nodes, 'task:1')

    def test_whole_flow_edges_resolve_to_entry_and_exit_and_cannot_branch(self):
        groups = [dict(id=i, name=str(i), steps=[dict(name='A'), dict(name='B')]) for i in (4, 5)]
        ensure_child_ids(groups, 'steps')
        nodes = build_graph([dict(id=1, title='外部任务')], groups, [], '2026-10-11')['nodes']
        self.store.connect('group:4', 'group:5', 'next', nodes)
        last = next(n['key'] for n in nodes if n.get('parentKey') == 'group:4' and n.get('sequence') == 1)
        with self.assertRaises(ValueError): self.store.connect(last, 'task:1', 'next', nodes)
        with self.assertRaises(ValueError): self.store.connect('group:5', 'group:4', 'next', nodes)

    def test_parent_child_overlap_detected_across_separate_aggregates(self):
        nodes = [dict(key='group:1', members=['task:1'], done=False), dict(key='group:2', members=['task:1'], done=False), dict(key='task:1', done=False)]
        with self.assertRaises(ValueError): self.store.connect('group:1', 'group:2', 'next', nodes)


if __name__ == '__main__': unittest.main()
