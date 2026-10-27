import sys,tempfile,unittest,wave
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import audio_diagnostics

class AudioDiagnosticTests(unittest.TestCase):
    def test_unarmed_recording_is_not_saved(self):
        with patch.object(audio_diagnostics,'load',return_value={}),patch.object(audio_diagnostics,'save') as save:
            self.assertIsNone(audio_diagnostics.capture_if_armed(b'\x00\x00'))
            save.assert_not_called()
    def test_single_capture_preserves_pcm_and_reports_clipping(self):
        config={'diagnostic_next_recording':True}
        with tempfile.TemporaryDirectory() as folder,patch.object(audio_diagnostics,'ROOT',Path(folder)),patch.object(audio_diagnostics,'load',return_value=config),patch.object(audio_diagnostics,'save'):
            pcm=b'\xff\x7f\x00\x80\x00\x00\x00\x00'
            result=audio_diagnostics.capture_if_armed(pcm)
            self.assertEqual(result['clipped_fraction'],.5)
            self.assertEqual(result['zero_fraction'],.5)
            with wave.open(result['file'],'rb') as source:self.assertEqual(source.readframes(4),pcm)
            self.assertIsNone(audio_diagnostics.capture_if_armed(pcm))

if __name__=='__main__':unittest.main()
