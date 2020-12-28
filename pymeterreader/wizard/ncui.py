"""
Curses setup wizard
"""
import re
from cursesmenu import *
from cursesmenu.items import *
from pymeterreader.gateway import VolkszaehlerGateway
from pymeterreader.wizard.generator import generate_yaml
from pymeterreader.wizard.detector import detect


class Wizard:
    def __init__(self):
        self.url = "http://localhost/middleware.php"
        self.gateway = None
        self.gateway_channels = {}
        self.menu = None
        print("Detecting meters...")
        self.meters = detect()
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

        for meter in self.meters:
            meter_menu = CursesMenu(f"Connect channels for meter {meter.identifier} at {meter.tty}", "By channel")
            for channel, value in meter.channels.items():
                map_menu = CursesMenu(f"Choose uuid for f{channel}")
                for choice in self.gateway_channels:
                    map_menu.append_item(FunctionItem(f"{choice['uuid']: content['title']}",
                                                      self.__assign, [meter, channel, choice['uuid']]))
                map_menu.append_item(FunctionItem("Enter private UUID",
                                                  self.__assign, [meter, channel, None]))
                meter_menu.append_item(SubmenuItem(f"{channel}: {value[0]} {value[1]}", map_menu))
            submenu_item = SubmenuItem(f"Meter {meter.identifier}", meter_menu, self.menu)

            self.menu.append_item(submenu_item)

        view_item = FunctionItem("View current mapping", self.__view_mapping)
        self.menu.append_item(view_item)

        save_item = FunctionItem("Save current mapping", self.__safe_mapping)
        self.menu.append_item(save_item)

        reset_item = FunctionItem("Reset all mappings", self.__clear)
        self.menu.append_item(reset_item)

        self.menu.show()

    def __clear(self):
        for meter in self.meters:
            for channel in meter.channels.values():
                if 'uuid' in channel:
                    channel.pop('uuid')

    def __safe_mapping(self):
        self.menu.stdscr.clear()
        result = generate_yaml(self.meters, self.url)
        try:
            with open('/etc/pymeterreader.yaml', 'w') as config_file:
                config_file.write(result)
            self.menu.stdscr.addstr(0, 0, "Saved to /etc/pymeterreader.yaml")
        except PermissionError:
            self.menu.stdscr.addstr(0, 0, "Insufficient permissions: cannot write to /etc/pymeterreader.yaml")
        self.menu.stdscr.addstr(1, 0, "(press any key)")
        self.menu.stdscr.getkey()

    def __view_mapping(self):
        self.menu.stdscr.clear()
        self.menu.stdscr.addstr(0, 0, "Mapped channels:")
        row = 2
        for meter in self.meters:
            for channel, content in meter.channels.items():
                if 'uuid' in content:
                    self.menu.stdscr.addstr(row, 2, f"{content['uuid']} mapped to {channel}")
                    row += 1
        self.menu.stdscr.addstr(row, 0, "(press any key)")
        self.menu.stdscr.getkey()

    def __assign(self, meter, channel, uuid):
        if uuid is None:
            uuid = input("Enter private UUID: ")
        meter[channel]['uuid'] = uuid


if __name__ == '__main__':
    Wizard()
