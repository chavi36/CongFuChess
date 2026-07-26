class MenuState:
    def __init__(self, options):
        self.options = list(options)
        self.index = 0

    def current_value(self):
        return self.options[self.index]

    def move_up(self):
        if not self.options:
            return self.current_value()
        self.index = (self.index - 1) % len(self.options)
        return self.current_value()

    def move_down(self):
        if not self.options:
            return self.current_value()
        self.index = (self.index + 1) % len(self.options)
        return self.current_value()

    def select(self):
        return self.current_value()
