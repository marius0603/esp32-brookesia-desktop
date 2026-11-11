import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('builder',ROOT/'phone-remote/tools/build_navigation_trial.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class TrialBuilderTests(unittest.TestCase):
 def test_private_key_inputs_and_apk_cannot_be_in_repository(self):
  for path in (ROOT/'packages/android/trial.apk',ROOT/'private-key.txt'):
   with self.assertRaises(ValueError):builder.external(path)
 def test_real_location_permissions_only_in_generated_trial_manifest(self):
  tree=builder.trial_manifest('0'*32);root=tree.getroot();a=builder.ANDROID
  self.assertEqual(root.get(a+'versionName'),'0.4.2-trial')
  permissions={n.get(a+'name'):n for n in root.findall('uses-permission')}
  self.assertNotIn(a+'maxSdkVersion',permissions['android.permission.ACCESS_FINE_LOCATION'].attrib)
  self.assertIn('android.permission.ACCESS_COARSE_LOCATION',permissions)
  self.assertNotIn('android.permission.ACCESS_BACKGROUND_LOCATION',permissions)
  self.assertNotIn('com.amap.api.v2.apikey',(ROOT/'phone-remote/android/AndroidManifest.xml').read_text())
 def test_invalid_key_is_not_echoed(self):
  with self.assertRaises(ValueError) as error:builder.trial_manifest('secret-input')
  self.assertNotIn('secret-input',str(error.exception))

if __name__=='__main__':unittest.main()
