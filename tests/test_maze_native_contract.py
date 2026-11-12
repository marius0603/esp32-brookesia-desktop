"""ServiceManager associates schemas and handlers by position, not handler label."""
import re,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class MazeNativeContract(unittest.TestCase):
 def check_service(self,relative):
  source=(ROOT/relative).read_text(encoding='utf-8');schemas=source.split('get_function_schemas() override',1)[1].split('get_function_handlers()',1)[0]
  names=re.findall(r'\{"(\w+)"\s*,',schemas)
  # Parameter names are nested schemas, not service methods.
  if 'AutoRotation' in source:names=['GetState','AcquireMotion','ReadMotion','ReleaseMotion','SetEnabled','SetRotation','CalibrateUpright']
  else:names=['PlayGameCue','StopGameCue','PlayFile','PlayNavigationPrompt','StopNavigationPrompt','StartRecording','StopRecording','Replay','Stop','Discard','GetState']
  handlers=source.split('get_function_handlers() override',1)[1]
  def extract(text):return [a or b for a,b in re.findall(r'\{"(\w+)"\s*,|BROOKESIA_SERVICE_FUNC_HANDLER_\d\("(\w+)"',text) if (a or b) in names]
  self.assertEqual(extract(schemas),names);self.assertEqual(extract(handlers),names)
 def test_motion(self):self.check_service('platform/super_s3_216/main/modules/auto_rotation/auto_rotation.cpp')
 def test_game_cue(self):self.check_service('platform/super_s3_216/main/modules/learning_audio/learning_audio.cpp')
if __name__=='__main__':unittest.main()
