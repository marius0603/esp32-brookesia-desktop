import importlib.util,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('brief',Path(__file__).resolve().parents[1]/'tools/wechat_brief.py')
brief=importlib.util.module_from_spec(spec);spec.loader.exec_module(brief)
class WechatBriefTests(unittest.TestCase):
 def config(self,d):
  p=Path(d)/'config.json';p.write_text(json.dumps(dict(channel='openclaw-weixin',node='node',cli='cli',account='private-account',target='private-recipient')));return p
 def healthy(self):return subprocess.CompletedProcess([],0,'{"ok":true}','')
 def dispatch(self,cmd,**kw):
  if 'health' in cmd:return self.healthy()
  self.assertIn('gateway',cmd);self.assertNotIn('message',cmd)
  p=json.loads(cmd[cmd.index('--params')+1]);self.assertTrue(p['idempotencyKey'].startswith('work-brief-'))
  return subprocess.CompletedProcess([],0,json.dumps(dict(runId=p['idempotencyKey'],channel=p['channel'],messageId='receipt-1')),'')
 def test_delivery_duplicate_and_private_audit(self):
  with tempfile.TemporaryDirectory() as d:
   p=self.config(d)
   with patch.object(brief.subprocess,'run',side_effect=self.dispatch) as run:
    self.assertEqual(brief.send(p,'private-body','id')['status'],'sent')
    self.assertEqual(brief.send(p,'private-body','id')['previous'],'sent');self.assertEqual(run.call_count,2)
   audit=(p.parent/'brief-attempts.jsonl').read_text()
   for secret in ['private-body','private-account','private-recipient']:self.assertNotIn(secret,audit)
 def test_unavailable_gateway_does_not_consume_event(self):
  with tempfile.TemporaryDirectory() as d:
   p=self.config(d)
   with patch.object(brief.subprocess,'run',return_value=subprocess.CompletedProcess([],1,'','')) as run:
    self.assertEqual(brief.send(p,'完成','id')['status'],'not_sent');run.assert_called_once()
   self.assertFalse((p.parent/'brief-deliveries.json').exists())
   with patch.object(brief.subprocess,'run',side_effect=self.dispatch):self.assertEqual(brief.send(p,'完成','id')['status'],'sent')
 def test_health_timeout_cannot_dispatch(self):
  with tempfile.TemporaryDirectory() as d:
   p=self.config(d)
   with patch.object(brief.subprocess,'run',side_effect=subprocess.TimeoutExpired('node',30)):
    self.assertEqual(brief.send(p,'完成','id')['status'],'not_sent')
   self.assertFalse((p.parent/'brief-deliveries.json').exists())
 def test_send_timeout_never_automatically_resends(self):
  with tempfile.TemporaryDirectory() as d:
   p=self.config(d)
   with patch.object(brief.subprocess,'run',side_effect=[self.healthy(),subprocess.TimeoutExpired('node',180)]) as run:
    self.assertEqual(brief.send(p,'完成','id')['reason'],'gateway_send_timeout')
    self.assertEqual(brief.send(p,'完成','id')['previous'],'uncertain');self.assertEqual(run.call_count,2)
 def test_wrong_or_missing_receipt_is_not_success(self):
  for response in ['{"payload":{"deliveryStatus":"sent"}}','{"channel":"other","runId":"wrong","messageId":"id"}','bad']:
   with self.subTest(response=response),tempfile.TemporaryDirectory() as d:
    with patch.object(brief.subprocess,'run',side_effect=[self.healthy(),subprocess.CompletedProcess([],0,response,'')]):
     self.assertEqual(brief.send(self.config(d),'完成','id')['status'],'uncertain')
 def test_ack_before_process_timeout_is_preserved(self):
  def run(cmd,**kw):
   result=self.dispatch(cmd,**kw)
   if 'health' in cmd:return result
   raise subprocess.TimeoutExpired('node',180,output=result.stdout.encode())
  with tempfile.TemporaryDirectory() as d:
   with patch.object(brief.subprocess,'run',side_effect=run):self.assertEqual(brief.send(self.config(d),'完成','id')['status'],'sent')
 def test_dry_run_and_timeout_bounds(self):
  with tempfile.TemporaryDirectory() as d:
   p=self.config(d)
   with patch.object(brief.subprocess,'run') as run:
    self.assertEqual(brief.send(p,'完成','id',True)['status'],'dry_run')
    with self.assertRaises(ValueError):brief.send(p,'完成','id',timeout_seconds=2)
    run.assert_not_called()
if __name__=='__main__':unittest.main()
