"""
Curses setup wizard
"""
import re
from cursesmenu import *
from cursesmenu.items import *
from pymeterreader.gateway import VolkszaehlerGateway
from pymeterreader.wizard.detector import detect


class Wizard:
    def __init__(self):
        self.url = "http://localhost/middleware.php"
        self.gateway = None
        self.gateway_channels = {}
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

        # A SelectionMenu constructs a menu from a list of strings
        selection_menu = SelectionMenu(["item1", "item2", "item3"])

        # A SubmenuItem lets you add a menu (the selection_menu above, for example)
        # as a submenu of another menu
        submenu_item = SubmenuItem("Submenu item", selection_menu, self.menu)

        # Once we're done creating them, we just add the items to the menu
        self.menu.append_item(function_item)
        self.menu.append_item(submenu_item)

        # Finally, we call show to show the menu and allow the user to interact
        self.menu.show()


if __name__ == '__main__':
    Wizard()
