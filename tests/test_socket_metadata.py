import copy
import ipaddress
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('socket_metadata',Path(__file__).resolve().parents[1]/'scripts/socket_metadata.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def fixture():
    p={'pid':42,'name':'data-service','start_ticks':123,'uid':0,'identity_stable':True,'same_network_namespace':True}
    s={'pid':42,'protocol':'tcp6','inode':1234,'uid':0,'state':'01',
       'local_hex':'00000000000000000000000001000000:0016',
       'remote_hex':'B80D0120000000000000000001000000:01BB'}
    sample={'tables':list(m.TABLES),'complete':True,'process_inventory_complete':True,'transient_processes_skipped':0,'processes':[p],'sockets':[s]}
    return {'scope':m.SCOPE,'schema_version':3,'completed':True,'uid':0,'euid':0,'little_endian':True,
            'payload_capture':False,'service_control':False,'settings_or_registry_write':False,
            'known_children_ended':True,'started_children':[],'selected_names':list(m.NAMES),
            'snapshots':[copy.deepcopy(sample),copy.deepcopy(sample)]}

class SocketMetadata(unittest.TestCase):
    def test_ipv4_and_ipv6_word_order(self):
        self.assertEqual(m.endpoint('0100007F:01BB',False),{'address':'127.0.0.1','port':443})
        self.assertEqual(m.endpoint('B80D0120000000000000000001000000:FFFF',True),{'address':'2001:db8::1','port':65535})
        self.assertEqual(ipaddress.ip_address(m.endpoint('0000000000000000FFFF00000100007F:0000',True)['address']),ipaddress.ip_address('::ffff:127.0.0.1'))
    def test_truncated_or_invalid_endpoint(self):
        for value in ('2001:db8::1:443','0100007F:1','00000000:GGGG','0000000:0000'):
            with self.subTest(value=value),self.assertRaises(ValueError):m.endpoint(value,False)
    def test_good_report_is_not_all_tracking_off(self):
        r=m.validate(fixture());self.assertFalse(r['all_telemetry_off'])
        self.assertEqual(r['snapshots'][0]['sockets'][0]['remote']['address'],'2001:db8::1')
    def test_reject_missing_coverage_or_limits(self):
        for edit in (lambda r:r.update(completed=False),lambda r:r.update(started_children=[9]),
                     lambda r:r['snapshots'][0].update(tables=['tcp']),
                     lambda r:r['snapshots'][0].update(sockets=[r['snapshots'][0]['sockets'][0]]*129)):
            r=fixture();edit(r)
            with self.assertRaises(ValueError):m.validate(r)
    def test_reject_pid_reuse_namespace_and_unmapped_socket(self):
        for key,value in (('identity_stable',False),('same_network_namespace',False),('start_ticks',0),('name','unreviewed')):
            r=fixture();r['snapshots'][0]['processes'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):m.validate(r)
        r=fixture();r['snapshots'][0]['sockets'][0]['pid']=77
        with self.assertRaises(ValueError):m.validate(r)
    def test_process_churn_never_proves_absence(self):
        r=fixture();r['snapshots'][0].update(process_inventory_complete=False,transient_processes_skipped=1)
        v=m.validate(r);self.assertFalse(v['process_absence_proven']);self.assertFalse(v['snapshots'][0]['process_inventory_complete'])
        r['snapshots'][0]['process_inventory_complete']=True
        with self.assertRaises(ValueError):m.validate(r)
    def test_duplicate_socket_rejected_but_shared_fd_owner_allowed(self):
        r=fixture();r['snapshots'][0]['sockets']*=2
        with self.assertRaises(ValueError):m.validate(r)
        r=fixture();p=copy.deepcopy(r['snapshots'][0]['processes'][0]);p['pid']=43
        r['snapshots'][0]['processes'].append(p)
        s=copy.deepcopy(r['snapshots'][0]['sockets'][0]);s['pid']=43
        r['snapshots'][0]['sockets'].append(s);m.validate(r)

if __name__=='__main__':unittest.main()
