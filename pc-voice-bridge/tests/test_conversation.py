import importlib.util,sys,types,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from deepseek_client import Cancellation,Cancelled,take_sentences
import conversation

class FakeEngines:
    def warm(self):pass
    def call(self,kind,request):
        if kind=='asr':return {'text':'测试问题','language':'Chinese'}
        return {'pcm':'AAAA','sample_rate':16000}

class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.events=[];self.dialog=conversation.Conversation()
        self.patches=[patch.object(conversation,'engines',FakeEngines()),patch.object(conversation,'load',return_value={'speaker':'Serena'})]
        for p in self.patches:p.start();self.addCleanup(p.stop)
    def test_success_adds_complete_turn_and_audio(self):
        with patch.object(conversation,'stream_answer',return_value=iter(['这是第一句话。','这是第二句话。'])):
            self.dialog.run(text='你好',emit=self.events.append)
        self.assertEqual([x['role'] for x in self.dialog.history],['user','assistant'])
        self.assertEqual(sum(e['type']=='audio' for e in self.events),2)
        self.assertEqual(self.events[-1]['type'],'done')
    def test_superseded_turn_is_rejected(self):
        previous=self.dialog.begin();self.dialog.begin()
        with self.assertRaises(Cancelled):self.dialog.run(text='旧问题',cancel=previous,emit=self.events.append)
        self.assertEqual(self.events,[]);self.assertEqual(self.dialog.history,[])
    def test_cancelled_generation_cannot_emit_audio(self):
        cancel=self.dialog.begin()
        class Cancelling(FakeEngines):
            def call(self,kind,request):cancel.cancel();return super().call(kind,request)
        with patch.object(conversation,'engines',Cancelling()),patch.object(conversation,'stream_answer',return_value=iter(['这是一句完整回答。'])):
            with self.assertRaises(Cancelled):self.dialog.run(text='你好',cancel=cancel,emit=self.events.append)
        self.assertFalse(any(e['type']=='audio' for e in self.events));self.assertEqual(self.dialog.history,[])
    def test_partial_failure_is_not_added_to_history(self):
        def broken(*args):yield '回答尚未完成';raise RuntimeError('断开')
        with patch.object(conversation,'stream_answer',side_effect=broken):
            with self.assertRaises(RuntimeError):self.dialog.run(text='你好',emit=self.events.append)
        self.assertEqual(self.dialog.history,[])
    def test_sentences_are_bounded_and_keep_all_text(self):
        text='很长的回答'*50+'。下一句。'
        chunks,rest=take_sentences(text,final=True)
        self.assertFalse(rest);self.assertEqual(''.join(chunks),text)
        self.assertTrue(all(len(part)<=48 for part in chunks))

if __name__=='__main__':unittest.main()
