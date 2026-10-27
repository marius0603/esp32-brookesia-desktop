import base64,importlib.util,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
spec=importlib.util.spec_from_file_location('speech_workbench_test',Path(__file__).resolve().parents[1]/'workbench/server.py')
server=importlib.util.module_from_spec(spec);spec.loader.exec_module(server)

class WorkbenchAsrTests(unittest.TestCase):
    def test_file_transcription_decodes_audio_before_calling_resident_worker(self):
        pcm=b'RIFF-test-upload'
        def infer(kind,request):
            self.assertEqual(kind,'asr')
            self.assertEqual(Path(request['input']).read_bytes(),pcm)
            Path(request['output']).write_text('小猫今天去找朋友',encoding='utf-8')
            return {'text':'小猫今天去找朋友'}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'outputs').mkdir();server.jobs['sample']={'state':'queued'}
            with patch.object(server,'ROOT',root),patch.object(server,'engines',SimpleNamespace(call=infer)):
                server.run_job('sample','asr',{'audio':base64.b64encode(pcm).decode(),'filename':'sample.wav'})
            self.assertEqual(server.jobs['sample']['state'],'done')
            self.assertEqual(server.jobs['sample']['result']['text'],'小猫今天去找朋友')

if __name__=='__main__':unittest.main()
