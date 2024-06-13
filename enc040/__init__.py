from RPi import GPIO
from time import sleep, time
import logging
import warnings
import threading

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

try:
    import evdev
except ImportError:
    evdev = None
    logging.info("The `evdev` package wasn't found, install it if you need to use the `device` mode.")

class Encoder:
    def __init__(self, CLK=None, DT=None, SW=None, polling_interval=1, device=None):
        self.clk = CLK
        self.dt = DT
        self.sw = SW
        self.polling_interval = polling_interval
        self.device = device
        self.counter = 0
        self.step = 1
        self.sw_debounce_time = 250
        self.long_click_time = 1000
        self.clk_last_state = None
        self.sw_triggered = False
        self.latest_switch_press = None
        self.switch_pressed_time = None

        self.inc_event = threading.Event()
        self.dec_event = threading.Event()
        self.click_event_flag = threading.Event()
        self.held_event_flag = threading.Event()

        self._is_clicked = False
        self._is_held = False

        if device is not None:
            if evdev is None:
                raise ImportError("The `evdev` package is required for device mode. Install it via pip.")
            try:
                self.device = evdev.InputDevice(device)
                logger.info("Please note that the encoder switch functionality isn't handled in `device` mode yet.")
            except OSError:
                raise Exception("The rotary encoder needs to be installed before use: https://github.com/raphaelyancey/pyky040#install-device")
        else:
            if not CLK or not DT:
                raise Exception("You must specify at least the CLK & DT pins")

            assert isinstance(CLK, int)
            assert isinstance(DT, int)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.clk, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            GPIO.setup(self.dt, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

            if SW is not None:
                assert isinstance(SW, int)
                self.sw = SW
                GPIO.setup(self.sw, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Pulled-up because KY-040 switch is shorted to ground when pressed

            self.clk_last_state = GPIO.input(self.clk)

    def _switch_press(self):
        now = time() * 1000
        if not self.sw_triggered:
            self.switch_pressed_time = now
            self.sw_triggered = True

    def _switch_release(self):
        now = time() * 1000
        if self.sw_triggered:
            press_duration = now - self.switch_pressed_time
            if press_duration > self.long_click_time:
                self.longclick_event()
            else:
                self.click_event()
        self.sw_triggered = False

    def _rotateup(self):
        self.counter += self.step
        self.rotateup_event(self.counter)

    def _rotatedown(self):
        self.counter -= self.step
        self.rotatedown_event(self.counter)

    def click_event(self):
        logger.info("Button click event")
        self._is_clicked = True
        self.click_event_flag.set()

    def longclick_event(self):
        logger.info("Button long click event")
        self._is_held = True
        self.held_event_flag.set()

    def rotateup_event(self, counter):
        logger.info(f"Rotated up to {counter}")
        self.inc_event.set()

    def rotatedown_event(self, counter):
        logger.info(f"Rotated down to {counter}")
        self.dec_event.set()

    def watch(self):
        if self.device is not None:
            for event in self.device.read_loop():
                if event.type == 2:
                    if event.value == 1:
                        self._rotateup()
                    elif event.value == -1:
                        self._rotatedown()
        else:
            while True:
                try:
                    if self.sw is not None:
                        if GPIO.input(self.sw) == GPIO.LOW:
                            self._switch_press()
                        else:
                            self._switch_release()

                    clkState = GPIO.input(self.clk)
                    dtState = GPIO.input(self.dt)

                    if clkState != self.clk_last_state:
                        if dtState != clkState:
                            self._rotateup()
                        else:
                            self._rotatedown()

                    self.clk_last_state = clkState
                    sleep(self.polling_interval / 1000)

                except BaseException as e:
                    logger.info("Exiting...")
                    logger.info(e)
                    GPIO.cleanup()
                    break
        return

    def waitForInc(self, timeout=None):
        self.inc_event.wait(timeout)
        self.inc_event.clear()

    def waitForDec(self, timeout=None):
        self.dec_event.wait(timeout)
        self.dec_event.clear()

    def waitForClick(self, timeout=None):
        self.click_event_flag.wait(timeout)
        self.click_event_flag.clear()

    def isClicked(self):
        if self._is_clicked:
            self._is_clicked = False
            return True
        return False

    def isHeld(self):
        if self._is_held:
            self._is_held = False
            return True
        return False
