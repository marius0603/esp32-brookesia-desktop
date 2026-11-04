import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from maintenance_client import MaintenanceClient,SharedPowerDiagnosticClient

class DiagnosticTests(unittest.TestCase):
 def client(self):
  client=object.__new__(SharedPowerDiagnosticClient)
  client.power_dependency_at=None;client.power_dependency_logs=[]
  return client
 def error(self,stamp,text):return RuntimeError('invalid device response: '+repr(('E ('+str(stamp)+') '+text+'\r\n').encode()))
 def test_known_chain_keeps_the_rpc_reply(self):
  rows=[self.error(10,'BOARD_DEVICE: Cannot deinit axp2101_power_manager, it is in use by audio_dac'),
        self.error(10,'BOARD_MANAGER: Failed to deinitialize device axp2101_power_manager'),
        self.error(12,'HalAdpt: : Checked ESP error: ERROR(524793)'),
        self.error(12,'HalAdpt: : Failed to deinit AXP2101 power manager')]
  client=self.client();reply={'ok':True,'op':'call'}
  with patch.object(MaintenanceClient,'read_json',side_effect=rows+[reply]):
   self.assertEqual(client.read_json(),reply)
  self.assertEqual(len(client.power_dependency_logs),4)
 def test_unmatched_power_error_fails(self):
  with patch.object(MaintenanceClient,'read_json',side_effect=self.error(12,'HalAdpt: : Checked ESP error: ERROR(524793)')):
   with self.assertRaises(RuntimeError):self.client().read_json()
 def test_unrelated_dma_error_fails(self):
  with patch.object(MaintenanceClient,'read_json',side_effect=self.error(12,'spi_common: DMA allocation failed')):
   with self.assertRaises(RuntimeError):self.client().read_json()
 def test_old_chain_does_not_hide_a_later_error(self):
  rows=[self.error(10,'BOARD_DEVICE: Cannot deinit axp2101_power_manager, it is in use by audio_dac'),self.error(111,'HalAdpt: : Failed to deinit AXP2101 power manager')]
  with patch.object(MaintenanceClient,'read_json',side_effect=rows):
   with self.assertRaises(RuntimeError):self.client().read_json()
 def test_malformed_json_still_fails(self):
  with patch.object(MaintenanceClient,'read_json',side_effect=RuntimeError('invalid device response: malformed JSON')):
   with self.assertRaises(RuntimeError):self.client().read_json()

if __name__=='__main__':unittest.main()
