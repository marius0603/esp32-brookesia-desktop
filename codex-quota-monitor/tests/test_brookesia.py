import json
import threading
import unittest
from unittest.mock import patch
import serial
from quota_monitor.brookesia import BrookesiaBridge, StableUsbClient


class BrookesiaTransportTests(unittest.TestCase):
    def test_logs_cannot_extend_response_deadline_forever(self):
        from unittest.mock import Mock
        client = StableUsbClient.__new__(StableUsbClient)
        client.session_active = True
        client.diagnostic_lines = []
        client.serial = Mock(timeout=1)
        client.serial.readline.return_value = b'I (1234) S3_PERF: render cycles=40 avg_us=11000 max_us=16000\r\n'
        with patch('quota_monitor.brookesia.time.monotonic', side_effect=[0, 0, 2]):
            with self.assertRaises(TimeoutError):
                client.read_json()

    def test_rejected_call_reestablishes_expired_session(self):
        from unittest.mock import Mock
        client = StableUsbClient.__new__(StableUsbClient)
        client.session_active = True
        client.hello = Mock()
        with patch('quota_monitor.brookesia.UsbClient.call', side_effect=[
            RuntimeError('invalid_command: hello is required first'), {'ok': True, 'result': None}
        ]) as call:
            self.assertTrue(client.call('Storage','FSWriteText',{})['ok'])
        self.assertEqual(call.call_count,2)
        client.hello.assert_called_once()

    def test_service_error_is_not_retried(self):
        from unittest.mock import Mock
        client = StableUsbClient.__new__(StableUsbClient)
        client.hello = Mock()
        with patch('quota_monitor.brookesia.UsbClient.call', side_effect=RuntimeError('call_failed: error')) as call:
            with self.assertRaises(RuntimeError):
                client.call('Storage','FSWriteText',{})
        self.assertEqual(call.call_count,1)
        client.hello.assert_not_called()

    def test_exact_renderer_telemetry_does_not_break_usb_response(self):
        from unittest.mock import Mock
        client = StableUsbClient.__new__(StableUsbClient)
        client.session_active = True
        client.diagnostic_lines = []
        client.serial = Mock()
        telemetry = b'I (1234) S3_PERF: render cycles=40 avg_us=11000 max_us=16000\r\n'
        client.serial.readline.side_effect = [telemetry, b'{"ok":true,"result":null}\n']
        self.assertEqual(client.read_json(), {'ok':True,'result':None})
        self.assertEqual(client.diagnostic_lines, [telemetry])

    def test_empty_console_line_does_not_break_active_protocol(self):
        from unittest.mock import Mock
        client = StableUsbClient.__new__(StableUsbClient)
        client.session_active = True
        client.serial = Mock()
        client.serial.readline.side_effect = [b'\r\n', b'{"ok":true,"request_id":2}\n']
        self.assertEqual(client.read_json(), {'ok':True,'request_id':2})

    def test_quota_console_ack_is_separate_from_usb_response(self):
        from unittest.mock import Mock
        client = StableUsbClient.__new__(StableUsbClient)
        client.session_active = True
        client.diagnostic_lines = []
        client.serial = Mock()
        ack = b'Codex quota UI updated: 123\r\n'
        client.serial.readline.side_effect = [ack, b'{"ok":true,"result":null}\n']
        self.assertEqual(client.read_json(), {'ok':True,'result':None})
        self.assertEqual(client.diagnostic_lines, [ack])

    def test_control_lines_are_low_before_port_opens(self):
        opened = []
        class Port:
            def __init__(self, **kwargs): self.port = kwargs['port']
            def open(self): opened.append((self.port, self.dtr, self.rts))
        with patch('quota_monitor.brookesia.serial.Serial', Port):
            StableUsbClient('COM5')
        self.assertEqual(opened, [('COM5', False, False)])

    def test_successful_storage_delivery_matches_device_request(self):
        stop = threading.Event()
        connected, calls = [], []
        class Client:
            def __init__(self, *args): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def hello(self): pass
            def call(self, service, function, args):
                calls.append((service, function, args))
                if function == 'FSStat': return {'result':{'exists':True}}
                if function == 'FSReadText': return {'result':json.dumps({'type':'quota_request','v':1,'request_id':'test-1','active':True})}
                stop.set()
                return {'ok': True, 'result': None}
        packet = {'type':'quota','v':1,'request_id':'test-1','sampled_at':1000,'windows':[]}
        requests = []
        bridge = BrookesiaBridge({}, lambda: packet.copy(), requests.append, connected.append, stop)
        with patch('quota_monitor.brookesia.StableUsbClient', Client), patch('quota_monitor.brookesia.time.time',return_value=2000):
            bridge._connect('COM5')
        self.assertEqual(connected, ['COM5'])
        self.assertEqual(requests,['test-1'])
        service, function, args = calls[-1]
        self.assertEqual((service,function,args['Path']),('Storage','FSWriteText','/littlefs/quota.json'))
        self.assertEqual(json.loads(args['Data'])['bridge_at'],2000)
        self.assertNotIn('bridge_at',packet)

    def test_no_request_means_no_write_and_no_cloud_query(self):
        stop, requests, writes = threading.Event(), [], []
        class Client:
            def __init__(self,*args): pass
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def hello(self): pass
            def call(self,service,function,args):
                self.assertion = function
                if function == 'FSStat':
                    stop.set()
                    return {'result':{'exists':False}}
                writes.append(function)
        bridge = BrookesiaBridge({}, lambda:{'status':'ok'},requests.append,lambda p:None,stop)
        with patch('quota_monitor.brookesia.StableUsbClient',Client): bridge._connect('COM5')
        self.assertEqual(requests,[])
        self.assertEqual(writes,[])

    def test_request_is_deduplicated_and_inactive_request_does_not_query(self):
        from unittest.mock import Mock
        requests, writes = [], []
        stop = Mock()
        stop.is_set.return_value = False
        stop.wait.side_effect = [False,False,True]
        packet = {'request_id':'test-1','status':'ok','sampled_at':1000}
        active = iter([True,True,False])
        class Client:
            def __init__(self,*args): self.active=next(active)
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def hello(self): pass
            def call(self,service,function,args):
                if function == 'FSStat': return {'result':{'exists':True}}
                if function == 'FSReadText': return {'result':json.dumps({'type':'quota_request','v':1,'request_id':'test-1','active':self.active})}
                writes.append(args)
                return {'ok':True}
        bridge = BrookesiaBridge({},lambda:packet.copy(),requests.append,lambda p:None,stop)
        with patch('quota_monitor.brookesia.StableUsbClient',Client):bridge._connect('COM5')
        self.assertEqual(requests,['test-1'])
        self.assertEqual(len(writes),1)

    def test_storage_failure_never_reports_connected(self):
        connected = []
        class Client:
            def __init__(self,*args): pass
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def hello(self): pass
            def call(self,*args): raise RuntimeError('write failed')
        bridge = BrookesiaBridge({}, lambda:{},None,connected.append,threading.Event())
        with patch('quota_monitor.brookesia.StableUsbClient',Client):
            with self.assertRaises(serial.SerialException): bridge._connect('COM5')
        self.assertEqual(connected,[])

if __name__ == '__main__':
    unittest.main()
