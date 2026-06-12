"""GPIO hardware abstraction for the Octavio Raspberry Pi device.

Wraps the red/green LED indicators and push button via gpiozero,
providing simple state-control methods used by the client to signal
recording and privacy status.

Note: documentation in this file was written with assistance from AI tools.
"""

import gpiozero
import signal
import sys

class OctavioHardware:
    """Controls the LED indicators and push button on the Octavio Pi device."""

    def __init__(self, red_pin=25, green_pin=24, button_pin=20):
        """Initializes LED and button GPIO devices.

        Args:
            red_pin (int): BCM pin number for the red LED. Defaults to 25.
            green_pin (int): BCM pin number for the green LED. Defaults to 24.
            button_pin (int): BCM pin number for the push button. Defaults to 20.
        """
        self.red_pin = red_pin
        self.green_pin = green_pin
        self.button_pin = button_pin

        self.red_led = gpiozero.LED(red_pin)
        self.green_led = gpiozero.LED(green_pin)
        self.button = gpiozero.Button(button_pin, bounce_time=0.1)

    def close_devices(self):
        """Releases all GPIO resources."""
        self.green_led.close()
        self.red_led.close()
        self.button.close()

    def shine_red(self):
        """Turns on the red LED and turns off the green LED."""
        self.green_led.off()
        self.red_led.on()

    def shine_green(self):
        """Turns on the green LED and turns off the red LED."""
        self.red_led.off()
        self.green_led.on()

    def shine_yellow(self):
        """Turns on both LEDs simultaneously to produce yellow."""
        self.green_led.on()
        self.red_led.on()

    def deactivate_light(self):
        """Turns off both LEDs."""
        self.red_led.off()
        self.green_led.off()

    @property
    def button_pressed(self):
        """bool: True if the push button is currently held down."""
        return self.button.is_pressed

def test_hardware_repl():
    """Interactive REPL for manually testing LED and button hardware."""
    hardware = OctavioHardware()
    def on_shutdown():
        hardware.deactivate_light()
        hardware.close_devices()
        sys.exit(0)
    signal.signal(signal.SIGTERM, lambda signum, frame: on_shutdown())
    signal.signal(signal.SIGINT, lambda signum, frame: on_shutdown())

    print('Engaging hardware testing REPL')

    test_instructions = "\nOptions are:\n" \
    "\t'd' for lights-off\n" \
    "\t'g' for green\n" \
    "\t'r' for red\n" \
    "\t'y' for yellow\n" \
    "\t'b' to show if button is pressed\n" \
    "\t'exit' or 'quit' to quit\n\n"

    while True:
        command = input(test_instructions)
        match command.strip().lower():
            case 'exit' | 'quit':
                print('Exiting hardware testing REPL')
                break
            case 'd':
                hardware.deactivate_light()
            case 'g':
                hardware.shine_green()
            case 'r':
                hardware.shine_red()
            case 'y':
                hardware.shine_yellow()
            case 'b':
                b = hardware.button_pressed
                text = 'Button is pressed' if b else 'Button is not pressed'
                print(text)
            case _:
                print('Not a valid command to test')

if __name__ == '__main__':
    ...

    test_hardware_repl()
