"""Offline checks; no assertion here claims that physical devices were tested."""
import importlib.util
import ipaddress
from pathlib import Path
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('setup_ssh', ROOT / 'scripts/setup_ssh.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class ProjectTests(unittest.TestCase):
    def host(self, name):
        return yaml.safe_load((ROOT / f'inventory/host_vars/{name}.yml').read_text())

    def test_router_bootstrap_has_two_non_overlapping_networks(self):
        for name in ['R1', 'R2']:
            host = self.host(name)
            upper, lower = host['management'], host['lower_mgmt']
            self.assertFalse(ipaddress.ip_network(f"{upper['ip']}/{upper['mask']}", strict=False).overlaps(
                ipaddress.ip_network(f"{lower['ip']}/{lower['mask']}", strict=False)))
            commands = module.bootstrap_commands(host, 'testuser', 'TestSecret123!', 'EnableSecret123!')
            self.assertIn('encapsulation dot1Q 199', commands)
            self.assertIn(f"ip address {lower['ip']} {lower['mask']}", commands)

    def test_switch_bootstrap_has_path_for_management(self):
        for name in ['SW-MGMT', 'SW-DIST', 'SW-ACCESS']:
            host = self.host(name)
            commands = module.bootstrap_commands(host, 'testuser', 'TestSecret123!', 'EnableSecret123!')
            self.assertIn(f"interface Vlan{host['management']['vlan']}", commands)
            self.assertIn(f"ip default-gateway {host['management']['gateway']}", commands)
            for port in host['trunk_ports']:
                self.assertIn(f'interface {port}', commands)
                self.assertIn('switchport trunk allowed vlan 199', commands)

    def test_inventory_matches_bootstrap_ip(self):
        inv = yaml.safe_load((ROOT / 'inventory/hosts.yml').read_text())
        groups = inv['all']['children']['ios']['children']
        for group in groups.values():
            for name, info in group['hosts'].items():
                self.assertEqual(info['ansible_host'], self.host(name)['management']['ip'])

    def test_dhcp_each_vlan_has_single_owner(self):
        networks = []
        for name in ['R1', 'R2']:
            for pool in self.host(name)['dhcp_pools']:
                net = ipaddress.ip_network(f"{pool['network']}/{pool['mask']}")
                self.assertIn(ipaddress.ip_address(pool['gateway']), net)
                self.assertIn(ipaddress.ip_address(pool['exclude_start']), net)
                self.assertIn(ipaddress.ip_address(pool['exclude_end']), net)
                networks.append(str(net))
        self.assertEqual(len(networks), len(set(networks)))
        self.assertEqual(set(networks), {'192.168.10.0/24','192.168.20.0/24','10.10.99.0/24','10.10.199.0/24'})

    def test_reject_command_injection_and_invalid_hostname(self):
        for password in ['bad\nend', 'help?', 'space secret']:
            with self.assertRaises(ValueError):
                module.bootstrap_commands(self.host('R1'), 'testuser', password, 'Secret123!')
        host = self.host('R1'); host['hostname'] = '1bad'
        with self.assertRaises(ValueError):
            module.bootstrap_commands(host, 'testuser', 'Secret123!', 'Enable123!')

    def test_ios_error_detection_and_prompts(self):
        self.assertTrue(module.ERROR.search('% Invalid input detected'))
        self.assertTrue(module.PROMPT.search('R1(config-subif)#'))
        self.assertTrue(module.PROMPT.search('SW-ACCESS#'))
        self.assertFalse(module.PROMPT.search('Password:'))

    def test_console_error_stops_without_exposing_secret(self):
        class Port:
            in_waiting = 1
            def reset_input_buffer(self): pass
            def write(self, data): self.sent = data
            def read(self, count): return b'% Invalid input detected\nR1(config)#'
        with self.assertRaises(RuntimeError) as raised:
            module.Console(Port()).command('username x secret Private123!')
        self.assertNotIn('Private123!', str(raised.exception))

    def test_etherchannel_is_explicit_and_excluded_from_site(self):
        vars_ = yaml.safe_load((ROOT / 'inventory/group_vars/ios.yml').read_text())
        self.assertFalse(vars_['shared_etherchannel_enabled'])
        self.assertNotIn('04_etherchannel.yml', (ROOT / 'playbooks/site.yml').read_text())

if __name__ == '__main__':
    unittest.main()
