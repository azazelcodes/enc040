from RPi import GPIO
from time import sleep, time
import logging
from os import getenv
import warnings

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG if getenv('DEBUG') == '1' else logging.INFO)

try:
    import evdev
except Exception:
    logging.info("The `evdev` package wasn't found, install it if you need to use the `device` mode.")

class Encoder:
    clk = None               # Board pin connected to the encoder CLK pin
    dt = None                # Same for the DT pin
    sw = None                # And for the switch pin
    polling_interval = None  # GPIO polling interval (in ms)
    sw_debounce_time = 250   # Debounce time (for switch only)

    # State
    clk_last_state = None
    sw_triggered = False     # Used to debounce a long switch click (prevent multiple callback calls)
    latest_switch_press = None
    press_start_time = None  # Timestamp when the switch was pressed

    device = None            # Device path (when used instead of GPIO polling)

    step = 1                 # Scale step
    counter = 0              # Initial scale position

    inc_callback = None      # Clockwise rotation callback (increment)
    dec_callback = None      # Anti-clockwise rotation callback (decrement)
    chg_callback = None      # Rotation callback (either way)
    sw_callback = None       # Switch pressed callback

    def __init__(self, CLK=None, DT=None, SW=None, polling_interval=1, device=None):

        if device is not None:
            try:
                self.device = evdev.InputDevice(device)
                logger.info("Please note that the encoder switch functionality isn't handled in `device` mode yet.")
            except OSError:
                raise BaseException("The rotary encoder needs to be installed before use: https://github.com/raphaelyancey/pyky040#install-device")
        else:
            if not CLK or not DT:
                raise BaseException("You must specify at least the CLK & DT pins")

            assert isinstance(CLK, int)
            assert isinstance(DT, int)
            self.clk = CLK
            self.dt = DT
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.clk, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            GPIO.setup(self.dt, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

            if SW is not None:
                assert isinstance(SW, int)
                self.sw = SW
                GPIO.setup(self.sw, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Pulled-up because KY-040 switch is shorted to ground when pressed

            self.clk_last_state = GPIO.input(self.clk)
            self.polling_interval = polling_interval

    def warnFloatDepreciation(self, i):
        if isinstance(i, float):
            warnings.warn('Float numbers as `sw_debounce_time` or `step` will be deprecated in the next major release. Use integers instead.', DeprecationWarning)

    def setup(self, **params):
        if 'step' in params:
            assert isinstance(params['step'], int) or isinstance(params['step'], float)
            self.step = params['step']
            self.warnFloatDepreciation(params['step'])
        if 'inc_callback' in params:
            assert callable(params['inc_callback'])
            self.inc_callback = params['inc_callback']
        if 'dec_callback' in params:
            assert callable(params['dec_callback'])
            self.dec_callback = params['dec_callback']
        if 'chg_callback' in params:
            assert callable(params['chg_callback'])
            self.chg_callback = params['chg_callback']
        if 'sw_callback' in params:
            assert callable(params['sw_callback'])
            self.sw_callback = params['sw_callback']
        if 'sw_debounce_time' in params:
            assert isinstance(params['sw_debounce_time'], int) or isinstance(params['sw_debounce_time'], float)
            self.sw_debounce_time = params['sw_debounce_time']
            self.warnFloatDepreciation(params['sw_debounce_time'])

    def _switch_press(self):
        now = time() * 1000
        if not self.sw_triggered:
            self.press_start_time = now
            self.sw_triggered = True
            self.latest_switch_press = now

    def _switch_release(self):
        if self.sw_triggered:
            self.sw_triggered = False
            self.press_start_time = None

    def get_switch_press_duration(self):
        if self.press_start_time is not None:
            now = time() * 1000
            return now - self.press_start_time
        return 0  # or return None if you prefer

    def _clockwise_tick(self):
        self.counter += self.step

        if self.inc_callback is not None:
            self.inc_callback(self.counter)
        if self.chg_callback is not None:
            self.chg_callback(self.counter)

    def _counterclockwise_tick(self):
        self.counter -= self.step

        if self.dec_callback is not None:
            self.dec_callback(self.counter)
        if self.chg_callback is not None:
            self.chg_callback(self.counter)

    def watch(self):
        if self.device is not None:
            for event in self.device.read_loop():
                if event.type == 2:
                    if event.value == 1:
                        self._clockwise_tick()
                    elif event.value == -1:
                        self._counterclockwise_tick()
        else:
            while True:
                try:
                    if self.sw_callback:
                        if GPIO.input(self.sw) == GPIO.LOW:
                            self._switch_press()
                        else:
                            self._switch_release()

                    clkState = GPIO.input(self.clk)
                    dtState = GPIO.input(self.dt)

                    if clkState != self.clk_last_state:
                        if dtState != clkState:
                            self._clockwise_tick()
                        else:
                            self._counterclockwise_tick()

                    self.clk_last_state = clkState
                    sleep(self.polling_interval / 1000)

                except BaseException as e:
                    logger.info("Exiting...")
                    logger.info(e)
                    GPIO.cleanup()
                    break
        return
