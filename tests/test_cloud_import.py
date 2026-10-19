import copy,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from cloud_records import snapshot,import_record
from cloud_import import import_downloads
from cloud_sync import SyncEngine

class ImportTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();p=Path(self.tmp.name)
  signal=SimpleNamespace(emit=lambda:None)
  self.b=SimpleNamespace(data_dir=str(p),local_database=[],groups_database=[],ai_state_database={'savedPlans':[]},stats_database={'history':[]},tasks_file=p/'tasks.json',groups_file=p/'flows.json',ai_state_file=p/'ai.json',tasksChanged=signal,groupsChanged=signal,aiLibraryChanged=signal)
  self.b._cloud_snapshot=lambda:snapshot(self.b);self.b._import_cloud_record=lambda item,key=None:import_record(self.b,item,key)
  self.engine=SyncEngine(p/'sync.json')
 def tearDown(self):self.tmp.cleanup()
 def item(self,id,kind,uid,record):return {'id':id,'kind':kind,'title':record.get('title',record.get('name','Plan')),'payload':{'format':'flowtodo-desktop-v1','_syncUid':uid,'record':record,'note':''},'version':1,'updatedAt':'2026-10-11T00:00:00Z','deletedAt':None}
 def test_batch_resolves_flow_task_references_and_deduplicates(self):
  task=self.item('task-cloud','tasks','task-uid',{'title':'数学作业','done':False})
  flow=self.item('flow-cloud','flows','flow-uid',{'name':'晚间流程','steps':[{'name':'数学','taskUid':'task-uid','duration':25}]})
  self.assertEqual(import_downloads(self.b,self.engine,[flow,task]),(2,0))
  self.assertEqual(self.b.groups_database[0]['steps'][0]['taskId'],self.b.local_database[0]['id'])
  self.assertEqual(import_downloads(self.b,self.engine,[flow,task]),(0,2));self.assertEqual(len(self.b.local_database),1)
 def test_existing_local_edit_is_never_overwritten(self):
  task=self.item('task-cloud','tasks','task-uid',{'title':'数学作业','done':False});import_downloads(self.b,self.engine,[task])
  self.b.local_database[0]['title']='本机新修改'
  self.assertEqual(import_downloads(self.b,self.engine,[task]),(0,1));self.assertEqual(self.b.local_database[0]['title'],'本机新修改')
 def test_legacy_identity_is_deduplicated_using_cloud_link(self):
  item=self.item('legacy-cloud','tasks','uid',{'title':'旧记录'});item['payload'].pop('_syncUid')
  self.assertEqual(import_downloads(self.b,self.engine,[item]),(1,0))
  self.assertEqual(import_downloads(self.b,self.engine,[item]),(0,1));self.assertEqual(len(self.b.local_database),1)
 def test_ai_import_does_not_import_execution_state(self):
  item=self.item('plan-cloud','aiPlans','plan-uid',{'plan':{'title':'学习计划','tasks':[]},'journey':{'status':'running'},'savedPath':'private-file'})
  import_downloads(self.b,self.engine,[item]);plan=self.b.ai_state_database['savedPlans'][0]
  self.assertNotIn('journey',plan);self.assertNotIn('savedPath',plan)
