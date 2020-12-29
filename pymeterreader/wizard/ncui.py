"""
Curses setup wizard
"""
import re
from os.path import exists
from subprocess import run
from cursesmenu import CursesMenu
from cursesmenu.items import FunctionItem, SubmenuItem
from pymeterreader.device_lib.common import Device
from pymeterreader.gateway import VolkszaehlerGateway
from pymeterreader.wizard.generator import generate_yaml, SERVICE_TEMPLATE
from pymeterreader.wizard.detector import detect


class Wizard:
    def __init__(self):
        self.url = "http://localhost/middleware.php"
        self.gateway = VolkszaehlerGateway(self.url)
        self.gateway_channels = self.gateway.get_channels()
        self.menu = None
        print("Detecting meters...")
        self.meters = detect()
        self.channel_config = {}
        self.restart_ui = True
        while self.restart_ui:
            self.restart_ui = False
            self.create_menu()

    def input_gw(self, text):
        def is_valid_url():
            return re.match(r"^https?://[/\w\d.]+.php$", self.url)
        self.restart_ui = True
        self.menu.clear_screen()
        self.url = "invalid"
        while self.url and not is_valid_url():
            self.url = input(text)
            if not self.url:
                self.menu.stdscr.addstr(3, 0, "Defaulting to http://localhost/middleware.php")
                self.url = "http://localhost/middleware.php"
                self.menu.stdscr.getkey()
            elif not is_valid_url():
                self.menu.stdscr.addstr(3, 0, "Entered url is not valid."
                                        " It must start with 'http://' or 'https://' and end with '.php'")
                self.menu.stdscr.getkey()
        self.gateway = VolkszaehlerGateway(self.url)
        self.gateway_channels = self.gateway.get_channels()
        if self.gateway_channels:
            self.menu.stdscr.addstr(3, 0,
                                    f"Found {len(self.gateway_channels)} public channels at gateway '{self.url}'.")
        else:
            self.menu.stdscr.addstr(3, 0, f"Unable to find any public channels at '{self.url}'.")
        self.menu.stdscr.getkey()

    def create_menu(self):
        # Create the menu
        self.menu = CursesMenu("PyMeterReader Configuration Wizard", "Choose item to configure")

        function_item = FunctionItem("Volkszähler Gateway", self.input_gw, ["Enter URL: "], should_exit=True)
        self.menu.append_item(function_item)

        for meter in self.meters:
            meter_menu = CursesMenu(f"Connect channels for meter {meter.identifier} at {meter.tty}", "By channel")
            for channel, value in meter.channels.items():
                map_menu = CursesMenu(f"Choose uuid for {channel}")
                for choice in self.gateway_channels:
                    map_menu.append_item(FunctionItem(f"{choice['uuid']}: {choice['title']}",
                                                      self.__assign, [meter, channel, choice['uuid'], '30m'],
                                                      should_exit=True))
                map_menu.append_item(FunctionItem("Enter private UUID",
                                                  self.__assign, [meter, channel, None, '30m'],
                                                  should_exit=True))
                meter_menu.append_item(SubmenuItem(f"{channel}: {value[0]} {value[1]}", map_menu, self.menu))
            submenu_item = SubmenuItem(f"Meter {meter.identifier}", meter_menu, self.menu)

            self.menu.append_item(submenu_item)

        view_item = FunctionItem("View current mapping", self.__view_mapping)
        self.menu.append_item(view_item)

        save_item = FunctionItem("Save current mapping", self.__safe_mapping)
        self.menu.append_item(save_item)

        register_service = FunctionItem("Register PymeterReader as systemd service.", self.__register_service)
        self.menu.append_item(register_service)

        reset_item = FunctionItem("Reset all mappings", self.__clear)
        self.menu.append_item(reset_item)

        self.menu.show()

    def __register_service(self):
        self.menu.clear_screen()
        self.menu.stdscr.addstr(0, 0, "Installing service...")
        run('sudo systemctl stop pymeterreader',  # pylint: disable=subprocess-run-check
            universal_newlines=True,
            shell=True)

        target_service_file = "/etc/systemd/system/pymeterreader.service"

        service_str = SERVICE_TEMPLATE.format('pymeterreader -c /etc/pymeterreader.yaml')
        try:
            with open(target_service_file, 'w') as target_file:
                target_file.write(service_str)
            run('systemctl daemon-reload',  # pylint: disable=subprocess-run-check
                universal_newlines=True,
                shell=True)
            if not exists('/etc/pymeterreader.yaml'):
                self.menu.stdscr.addstr(1, 0, "Copy example configuration file to '/etc/pymeterreader.yaml'")
                with open('example_configuration.yaml', 'r') as file:
                    example_config = file.read()
                with open('/etc/pymeterreader.yaml', 'w') as file:
                    file.write(example_config)
            self.menu.stdscr.addstr(2, 0, "Registered pymeterreader as servicee.\n"
                                          "Enable with 'sudo systemctl enable pymeterreader'\n."
                                          "IMPORTANT: Create configuration file '/etc/pymeterreader.yaml'")
        except OSError as err:
            if isinstance(err, PermissionError):
                self.menu.stdscr.addstr(4, 0, "Cannot write service file to /etc/systemd/system. "
                                              "Run as root (sudo) to solve this.")
        self.menu.stdscr.addstr(6, 0, "(press any key)")
        self.menu.stdscr.getkey()

    def __clear(self):
        """
        Remove channel mappings
        """
        self.channel_config.clear()

    def __safe_mapping(self):
        """
        Save yaml to system
        """
        self.menu.clear_screen()
        result = generate_yaml(self.channel_config, self.url)
        try:
            with open('/etc/pymeterreader.yaml', 'w') as config_file:
                config_file.write(result)
            self.menu.stdscr.addstr(0, 0, "Saved to /etc/pymeterreader.yaml")
        except PermissionError:
            self.menu.stdscr.addstr(0, 0, "Insufficient permissions: cannot write to /etc/pymeterreader.yaml")
        self.menu.stdscr.addstr(1, 0, "(press any key)")
        self.menu.stdscr.getkey()

    def __view_mapping(self):
        self.menu.clear_screen()
        self.menu.stdscr.addstr(0, 0, "Mapped channels:")
        row = 2
        for meter in self.channel_config.values():
            for channel, content in meter['channels'].items():
                self.menu.stdscr.addstr(row, 2, f"{channel} at {meter.get('id')} mapped to UUID {content.get('uuid')}")
                row += 1
        self.menu.stdscr.addstr(row, 0, "(press any key)")
        self.menu.stdscr.getkey()

    def __assign(self, meter: Device, channel, uuid: str, interval: str):
        if uuid is None:
            self.menu.clear_screen()
            uuid = input("Enter private UUID: ")
        if meter.identifier not in self.channel_config:
            self.channel_config[meter.identifier] = {'channels': {},
                                                     'id': meter.identifier,
                                                     'protocol': meter.protocol}
        self.channel_config[meter.identifier]['channels'][channel] = {
            'uuid': uuid,
            'interval': interval
        }


if __name__ == '__main__':
    Wizard()
