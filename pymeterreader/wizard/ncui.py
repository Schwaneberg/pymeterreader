"""
Curses setup wizard
"""
import re
from cursesmenu import *
from cursesmenu.items import *
from pymeterreader.gateway import VolkszaehlerGateway
from pymeterreader.device_lib import Device
from pymeterreader.wizard.detector import detect


class Wizard:
    def __init__(self):
        self.url = "http://localhost/middleware.php"
        self.gateway = None
        self.gateway_channels = {}
        self.channel_mapping = {}
        self.menu = None
        print("Detecting meters...")
        self.available_meters = detect()
        self.create_menu()

    def input_gw(self, text):
        def is_valid_url():
            return re.match(r"^https?://[/\w\d.]+.php$", self.url)
        self.url = "invalid"
        while self.url and not is_valid_url():
            self.url = input(text)
            if not self.url:
                self.menu.stdscr.addstr(3, 0, "Defaulting to http://localhost/middleware.php")
                self.url = "http://localhost/middleware.php"
                self.menu.stdscr.getkey()
            elif not is_valid_url():
                self.menu.stdscr.addstr(3, 0, "Entered url is not valid."
                                        f" It must start with 'http://' or 'https://' and end with '.php'")
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

        function_item = FunctionItem("Volkszähler Gateway", self.input_gw, ["Enter URL: "])
        self.menu.append_item(function_item)

        for meter in self.available_meters:
            meter_menu = CursesMenu(f"Connect channels for meter {meter.identifier} at {meter.tty}", "By channel")
            for channel, value in meter.channels.items():
                meter_menu.append_item(FunctionItem(f"{channel}: {value[0]} {value[1]}",
                                                    self.__map_channel,
                                                    [meter, channel]))
            submenu_item = SubmenuItem(f"Meter {meter.identifier}", meter_menu, self.menu)

            self.menu.append_item(submenu_item)

        view_item = FunctionItem("View current mapping", self.__view_mapping)
        self.menu.append_item(view_item)

        save_item = FunctionItem("Save current mapping", self.__safe_mapping)
        self.menu.append_item(save_item)

        reset_item = FunctionItem("Reset all mappings", self.channel_mapping.clear)
        self.menu.append_item(reset_item)

        self.menu.show()

    def __safe_mapping(self):
        self.menu.stdscr.clear()
        # TODO YAML generator
        self.menu.stdscr.addstr(0, 0, "Saved to /etc/pymeterreader.yaml")
        self.menu.stdscr.addstr(1, 0, "(press any key)")
        self.menu.stdscr.getkey()

    def __view_mapping(self):
        self.menu.stdscr.clear()
        self.menu.stdscr.addstr(0, 0, "Mapped channels:")
        row = 2
        for uuid, value in self.channel_mapping.items():
            self.menu.stdscr.addstr(row, 2, f"{uuid} mapped to {value[0].identifier}: {value[1]}")
            row += 1
        self.menu.stdscr.addstr(row, 0, "(press any key)")
        self.menu.stdscr.getkey()

    def __map_channel(self, meter, channel):
        def assign_channel(uuid: str):
            self.channel_mapping[uuid] = (meter, channel)
        map_menu = CursesMenu(f"Channel selection for {channel} at meter {meter.identifier}", "Select a channel")
        for gateway_channel in self.gateway_channels:
            if gateway_channel.get('uuid') not in self.channel_mapping:
                menu_item = FunctionItem(f"{gateway_channel.get('uuid')}: {gateway_channel.get('title')}",
                                         assign_channel, [gateway_channel.get('uuid')])
                map_menu.append_item(menu_item)
        map_menu.show()


if __name__ == '__main__':
    Wizard()
