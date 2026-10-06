import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/work_unit.py'
spec = importlib.util.spec_from_file_location('work_unit_under_test', SCRIPT)
unit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(unit)


class WorkUnitTests(unittest.TestCase):
    def plan(self):
        return {'task_id':'actual-task','outcome':'Complete scoped result',
                'scope_ref':'scope.json','limits_ref':'limits.json','authority_ref':'human.json',
                'steps':['Implement','Validate permitted case','Repair and deliver'],
                'preauthorized_continuations':[{'id':'explain','when':'Frozen results available',
                    'action':'Interpret the actual output','requires_new_authorization':False,'extra_native_calls':False}],
                'direct_delivery':[{'id':'consumer','thread_id':'actual-consumer','host_id':'local','purpose':'consumer'},
                                   {'id':'review','thread_id':'original-reviewer','host_id':'remote','purpose':'review'}]}

    def test_original_limits_and_human_authority_survive_rendering(self):
        text=unit.render_plan(self.plan())
        for value in ['scope.json','limits.json','human.json','actual-consumer','original-reviewer','Interpret the actual output']:
            self.assertIn(value,text)

    def test_delivery_targets_original_peers_without_model_override_or_acceptance(self):
        result=unit.delivery_requests(self.plan(),'remote:/owned/result.json','a'*64)
        self.assertEqual([r['arguments']['threadId'] for r in result['requests']],['actual-consumer','original-reviewer'])
        self.assertFalse(result['sent'])
        self.assertFalse(result['scientific_acceptance_verified'])
        self.assertFalse(result['permission_verified'])
        for r in result['requests']:
            self.assertNotIn('model',r['arguments'])
            self.assertNotIn('thinking',r['arguments'])

    def test_arbitrary_recipient_rejected(self):
        with self.assertRaises(ValueError):unit.delivery_requests(self.plan(),'result','b'*64,'unrelated-chat')

    def test_parent_owned_reviewer_is_not_sent_through_app_interface(self):
        p=self.plan();p['direct_delivery'][1].update(transport='original_parent_review_channel',owner_thread_id='original-author')
        result=unit.delivery_requests(p,'remote:/result.json','a'*64)
        self.assertEqual(result['requests'][0]['tool'],'send_message_to_thread')
        request=result['requests'][1]
        self.assertEqual(request['tool'],'original_parent_review_channel')
        self.assertEqual(request['execution_owner_thread_id'],'original-author')
        self.assertNotIn('arguments',request)

    def test_original_parent_transport_requires_parent_owner(self):
        p=self.plan();p['direct_delivery'][1]['transport']='original_parent_review_channel'
        with self.assertRaises(ValueError):unit.validate_plan(p)

    def test_brief_cannot_overwrite_its_linked_execution_plan(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);plan=root/'execution.json';plan.write_text('protected plan',encoding='utf-8')
            task={'schema_version':1,'task_id':'A','task_kind':'research','objective':'scope',
                  'read_first':[],'allowed_write_roots':['owned'],'expected_outputs':[],
                  'done_criteria':['complete'],'global_constraints':['same limits'],'report_path':None,
                  'result_path':None,'execution_plan_ref':'execution.json'}
            path=root/'task.json';path.write_text(json.dumps(task),encoding='utf-8')
            command=[sys.executable,'-B',str(SCRIPT.parent/'coord.py'),'brief','--task',str(path),'--output',str(plan)]
            result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertEqual(plan.read_text(encoding='utf-8'),'protected plan')

    def test_extra_calls_cannot_hide_in_preauthorization(self):
        p=self.plan();p['preauthorized_continuations'][0]['extra_native_calls']=True
        with self.assertRaises(ValueError):unit.validate_plan(p)
        p['preauthorized_continuations'][0]['operation_authorization_ref']='explicit-new-operation.json'
        p['preauthorized_continuations'][0]['requires_new_authorization']=True
        self.assertIn('需新授权',unit.render_plan(p))

    def test_false_or_unknown_action_flags_not_coerced(self):
        for value in [None,'false',0]:
            p=self.plan();p['preauthorized_continuations'][0]['extra_native_calls']=value
            with self.assertRaises(ValueError):unit.validate_plan(p)

    def test_duplicate_or_unresolved_routes_rejected(self):
        p=self.plan();p['direct_delivery'].append(copy.deepcopy(p['direct_delivery'][0]))
        with self.assertRaises(ValueError):unit.validate_plan(p)
        p=self.plan();p['direct_delivery'][0]['host_id']=None
        with self.assertRaises(ValueError):unit.validate_plan(p)

    def test_cli_never_executes_reference_text(self):
        with tempfile.TemporaryDirectory()as root:
            marker=Path(root)/'should-not-exist'
            p=self.plan();p['preauthorized_continuations'][0]['action']='$(touch '+str(marker)+')'
            path=Path(root)/'plan.json';path.write_text(json.dumps(p),encoding='utf-8')
            result=subprocess.run([sys.executable,'-B',str(SCRIPT),'render','--plan',str(path)],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertFalse(marker.exists())

    def test_cli_refuses_overwriting_contract_or_authority(self):
        with tempfile.TemporaryDirectory()as root:
            path=Path(root)/'plan.json';p=self.plan();p['authority_ref']='human.json'
            path.write_text(json.dumps(p),encoding='utf-8');target=Path(root)/'human.json';target.write_text('original authority',encoding='utf-8')
            result=subprocess.run([sys.executable,'-B',str(SCRIPT),'render','--plan',str(path),'--output',str(target)],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,2,result.stderr)
            self.assertEqual(target.read_text(encoding='utf-8'),'original authority')


if __name__=='__main__':unittest.main()
