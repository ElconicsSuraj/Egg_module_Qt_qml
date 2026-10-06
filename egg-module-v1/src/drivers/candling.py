import logging

logger = logging.getLogger(__name__)

class CandlingLED:
    """
    Controls the Candling LED connected to a Raspberry Pi GPIO pin.
    Defaults to GPIO pin 17.
    """
    def __init__(self, pin=17):
        self.pin = pin
        self.state = False
        self._handle = None
        self._available = False
        
        try:
            import lgpio
            self.lgpio = lgpio
            self._handle = lgpio.gpiochip_open(0)
            lgpio.gpio_claim_output(self._handle, self.pin)
            lgpio.gpio_write(self._handle, self.pin, 0)
            self._available = True
            logger.info(f"Candling LED initialized on Raspberry Pi GPIO pin {self.pin}")
        except Exception as e:
            logger.warning(f"Candling LED hardware init skipped (simulated mode): {e}")
            self._available = False

    def toggle(self) -> bool:
        return self.set_state(not self.state)

    def set_state(self, on: bool) -> bool:
        self.state = on
        if self._available and self._handle is not None:
            try:
                self.lgpio.gpio_write(self._handle, self.pin, 1 if on else 0)
            except Exception as e:
                logger.error(f"Failed to write Candling LED state: {e}")
        logger.info(f"Candling LED state: {'ON' if self.state else 'OFF'}")
        return self.state

    def cleanup(self):
        if self._available and self._handle is not None:
            try:
                self.lgpio.gpio_write(self._handle, self.pin, 0)
                self.lgpio.gpiochip_close(self._handle)
            except Exception:
                pass
            self._handle = None
