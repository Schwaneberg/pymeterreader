"""
Curses setup wizard
"""
import logging
import platform
import re
import typing as tp
from os.path import exists
from pathlib import Path
from subprocess import run

from cursesmenu import CursesMenu
from cursesmenu.items import FunctionItem, SubmenuItem

from pymeterreader.device_lib.common import Device, ChannelValue
from pymeterreader.gateway import VolkszaehlerGateway
from pymeterreader.wizard.detector import detect
from pymeterreader.wizard.generator import generate_yaml, SERVICE_TEMPLATE


class Wizard:
    CONFIG_FILE_NAME = "pymeterreader.yaml"
    POSIX_CONFIG_PATH = Path("/etc") / CONFIG_FILE_NAME

    def __init__(self) -> None:
        logging.basicConfig(level=logging.INFO)
        self.url = "http://localhost/middleware.php"
        self.gateway = VolkszaehlerGateway(self.url)
        self.gateway_channels = self.gateway.get_channels()
        self.menu: CursesMenu
        print("Detecting meters...")
        self.meters = detect()
        self.channel_config: tp.Dict[str, tp.Dict[str, tp.Union[str, tp.Dict]]] = {}
        self.restart_ui = True
        while self.restart_ui:
            self.restart_ui = False
            self.create_menu()

    def input_gw(self, text) -> None:
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

    def create_menu(self) -> None:
        # Create the menu
        self.menu = CursesMenu("PyMeterReader Configuration Wizard", "Choose item to configure")

        function_item = FunctionItem("Volkszähler Gateway", self.input_gw, ["Enter URL: "], should_exit=True)
        self.menu.append_item(function_item)

        for meter in self.meters:
            meter_menu = CursesMenu(f"Connect channels for meter {meter.meter_id} at {meter.meter_address}",
                                    "By channel")
            for channel in meter.channels:
                map_menu = CursesMenu(f"Choose uuid for {channel.channel_name}")
                for choice in self.gateway_channels:
                    map_menu.append_item(FunctionItem(f"{choice.uuid}: {choice.title}",
                                                      self.__assign, [meter, channel, choice.uuid, '30m'],
                                                      should_exit=True))
                map_menu.append_item(FunctionItem("Enter private UUID",
                                                  self.__assign, [meter, channel, None, '30m'],
                                                  should_exit=True))
                meter_menu.append_item(
                    SubmenuItem(f"{channel.channel_name}: {channel.value} {channel.unit}", map_menu, self.menu))
            submenu_item = SubmenuItem(f"Meter {meter.meter_id}", meter_menu, self.menu)

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

    def __register_service(self) -> None:
        self.menu.clear_screen()
        if platform.system() != "Linux":
            self.menu.stdscr.addstr(0, 0, "Systemd Service registration is only supported on Linux!")
            self.menu.stdscr.addstr(1, 0, "(press any key)")
            self.menu.stdscr.getkey()
            return
        self.menu.stdscr.addstr(0, 0, "Installing service...")
        run('sudo systemctl stop pymeterreader',  # pylint: disable=subprocess-run-check
            universal_newlines=True,
            shell=True)

        target_service_file = "/etc/systemd/system/pymeterreader.service"

        service_str = SERVICE_TEMPLATE.format(f'pymeterreader -c {self.POSIX_CONFIG_PATH.absolute()}')
        try:
            with open(target_service_file, 'w', encoding='utf-8') as target_file:
                target_file.write(service_str)
            run('systemctl daemon-reload',  # pylint: disable=subprocess-run-check
                universal_newlines=True,
                shell=True)
            if not exists(self.POSIX_CONFIG_PATH):
                self.menu.stdscr.addstr(1, 0,
                                        f"Copy example configuration file to '{self.POSIX_CONFIG_PATH.absolute()}'")
                with open('example_configuration.yaml', 'r', encoding='utf-8') as file:
                    example_config = file.read()
                with open(self.POSIX_CONFIG_PATH, 'w', encoding='utf-8') as file:
                    file.write(example_config)
            self.menu.stdscr.addstr(2, 0, "Registered pymeterreader as service.\n"
                                          "Enable with 'sudo systemctl enable pymeterreader'\n."
                                          f"IMPORTANT: Create configuration file '{self.POSIX_CONFIG_PATH.absolute()}'")
        except FileNotFoundError as err:
            self.menu.stdscr.addstr(4, 0, f"Could not access file: {err}!")
        except PermissionError:
            self.menu.stdscr.addstr(4, 0, "Cannot write service file to /etc/systemd/system. "
                                          "Run as root (sudo) to solve this.")
        self.menu.stdscr.addstr(6, 0, "(press any key)")
        self.menu.stdscr.getkey()

    def __clear(self) -> None:
        """
        Remove channel mappings
        """
        self.channel_config.clear()

    def __safe_mapping(self) -> None:
        """
        Save yaml to system
        """
        self.menu.clear_screen()
        result = generate_yaml(self.channel_config, self.url)
        try:
            if platform.system() in ["Linux", "Darwin"]:
                config_path = self.POSIX_CONFIG_PATH
            else:
                config_path = Path(".") / "pymeterreader.yaml"
            with open(config_path, "w", encoding='utf-8') as config_file:
                config_file.write(result)
            self.menu.stdscr.addstr(0, 0, f"Saved to {config_path.absolute()}")
        except PermissionError:
            self.menu.stdscr.addstr(0, 0, f"Insufficient permissions: cannot write to {config_path.absolute()}!")
        except FileNotFoundError:
            self.menu.stdscr.addstr(0, 0, f"Could not access path: {config_path.absolute()}!")
        self.menu.stdscr.addstr(1, 0, "(press any key)")
        self.menu.stdscr.getkey()

    def __view_mapping(self) -> None:
        self.menu.clear_screen()
        self.menu.stdscr.addstr(0, 0, "Mapped channels:")
        row = 2
        for meter in self.channel_config.values():
            for channel, content in meter['channels'].items():
                self.menu.stdscr.addstr(row, 2, f"{channel} at {meter.get('id')} mapped to UUID {content.get('uuid')}")
                row += 1
        self.menu.stdscr.addstr(row, 0, "(press any key)")
        self.menu.stdscr.getkey()

    def __assign(self, meter: Device, channel: ChannelValue, uuid: tp.Optional[str], interval: str) -> None:
        if uuid is None:
            self.menu.clear_screen()
            uuid = input("Enter private UUID: ")
        if meter.meter_id not in self.channel_config:
            self.channel_config[meter.meter_id] = {'channels': {},
                                                   'protocol': meter.protocol,
                                                   'meter_address': meter.meter_address,
                                                   'meter_id': meter.meter_id}
        self.channel_config[meter.meter_id]['channels'][channel.channel_name] = {
            'uuid': uuid,
            'interval': interval
        }


if __name__ == '__main__':
    Wizard()
