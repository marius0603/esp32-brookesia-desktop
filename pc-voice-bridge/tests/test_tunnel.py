import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import public_tunnel

class TunnelHealthTests(unittest.TestCase):
    def test_expired_route_is_not_reported_as_running(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'logs').mkdir()
            log=root/'logs/tunnel-current.log'
            log.write_text('Registered tunnel connection\nUnauthorized: Tunnel not found\n')
            with patch.object(public_tunnel,'ROOT',root),patch.object(public_tunnel,'load',return_value={'network_mode':'quick_tunnel'}),patch.dict(public_tunnel.state,{'running':True}):
                self.assertFalse(public_tunnel.snapshot()['running'])
                self.assertIn('失效',public_tunnel.snapshot()['error'])
                log.write_text('Unauthorized: Tunnel not found\nRegistered tunnel connection\n')
                self.assertTrue(public_tunnel.snapshot()['running'])

if __name__=='__main__':unittest.main()
