import unittest

from app.api.v1.routeros import _can_execute_command, _required_perm_for_command


class RouterOSCommandPermissionTests(unittest.TestCase):
    def test_recognized_read_requires_section_or_config_permission(self):
        command = "/ip/address/print"
        self.assertEqual(_required_perm_for_command(command), "routers:view_addresses")
        self.assertTrue(_can_execute_command(command, ["routers:view_addresses"]))
        self.assertTrue(_can_execute_command(command, ["routers:cfg_addresses_edit"]))
        self.assertFalse(_can_execute_command(command, []))

    def test_unknown_command_requires_terminal_permission(self):
        command = "/ip/address/export"
        self.assertEqual(_required_perm_for_command(command), "routers:terminal")
        self.assertFalse(_can_execute_command(command, ["routers:view_addresses"]))
        self.assertTrue(_can_execute_command(command, ["routers:terminal"]))


if __name__ == "__main__":
    unittest.main()
