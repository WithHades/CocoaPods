class logger_:
    def __init__(self, logger=None):
        self._logger = logger
        if self._logger is None:
            import logging
            self._logger = logging.getLogger("logger")
            self._logger.setLevel(level=logging.INFO)
            self.console = logging.StreamHandler()
            self.console.setLevel(level=logging.INFO)
            self._logger.addHandler(self.console)
