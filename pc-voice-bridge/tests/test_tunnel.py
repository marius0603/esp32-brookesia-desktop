import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import public_tunnel

class TunnelHealthTests(unittest.TestCase):
    def test_ssh_endpoint_parser_ignores_documentation_links(self):
        self.assertEqual(public_tunnel.ssh_endpoint('https://localhost.run/docs/'),'')
        banner='Manage domains at https://admin.localhost.run/\nhttps://localhost.run/docs/\n'
        self.assertEqual(public_tunnel.ssh_endpoint(banner),'')
        self.assertEqual(public_tunnel.ssh_endpoint(banner+'example123.lhr.life tunneled'), '')
        assigned='\x1b[32mexample123.lhr.life tunneled with tls termination, https://example123.lhr.life\x1b[0m'
        self.assertEqual(public_tunnel.ssh_endpoint(banner+assigned+'\nhttps://admin.localhost.run/'),'wss://example123.lhr.life/device')
    def test_latest_announced_hostname_is_selected(self):
        log='first.lhr.life tunneled with tls termination\nsecond.localhost.run tunneled with tls termination'
        self.assertEqual(public_tunnel.ssh_endpoint(log),'wss://second.localhost.run/device')
    def test_dead_ssh_process_is_not_a_ready_route(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'logs').mkdir();(root/'logs/ssh-tunnel.pid').write_text('123')
            with patch.object(public_tunnel,'ROOT',root),patch.object(public_tunnel,'load',return_value={'network_mode':'ssh_tunnel','device_url':'wss://example.lhr.life/device'}),patch.object(public_tunnel,'matching_process',return_value=False):
                result=public_tunnel.snapshot();self.assertFalse(result['running']);self.assertIn('停止',result['error'])
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
