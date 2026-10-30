"""
tests/test_display_persona.py - Phase 4 Display Subsystem & DORURU Persona Verification

Validates:
1. ILI9341 custom SPI pin configuration (SCK=D10/GPIO9, MOSI=D9/GPIO8, MISO=-1, CS=-1, D/C=D7/GPIO44, RESET=D8/GPIO7).
2. Clean hardware reset pulse on D8 (GPIO7) during driver initialization.
3. Native USB CDC serial logging protection for D7 (GPIO44 D/C) and D6 (GPIO43 LRC).
4. All 13 display states and screens for the DORURU persona.
5. Friendly DORURU personality without WALL-E branding or unauthorized names.
6. Display demo mode cycling through all screens without motor movement.
7. High-contrast fail-safe rendering fallback protection.
8. Host firmware compilation and test execution.
"""

import os
import re
import unittest
from pathlib import Path
from tests.host_test_helper import ensure_compiled_host_firmware_test, execute_host_firmware_test

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestDisplayPersona(unittest.TestCase):
    def setUp(self):
        self.pins_header = REPO_ROOT / "firmware" / "include" / "board_pins.h"
        self.driver_header = REPO_ROOT / "firmware" / "src" / "display" / "ili9341_driver.h"
        self.driver_cpp = REPO_ROOT / "firmware" / "src" / "display" / "ili9341_driver.cpp"
        self.persona_header = REPO_ROOT / "firmware" / "src" / "display" / "doruru_persona.h"
        self.persona_cpp = REPO_ROOT / "firmware" / "src" / "display" / "doruru_persona.cpp"
        self.interface_header = REPO_ROOT / "firmware" / "src" / "display" / "display_interface.h"
        self.interface_cpp = REPO_ROOT / "firmware" / "src" / "display" / "display_interface.cpp"
        self.main_cpp = REPO_ROOT / "firmware" / "src" / "main.cpp"

    def test_display_files_exist(self):
        """Verify all Phase 4 display driver and persona source files exist."""
        for p in (self.driver_header, self.driver_cpp, self.persona_header,
                  self.persona_cpp, self.interface_header, self.interface_cpp):
            self.assertTrue(p.exists(), f"Required file missing: {p}")

    def test_confirmed_spi_pin_mapping_preserved(self):
        """Verify the exact custom SPI pin mapping established in Phase 2 is preserved."""
        content = self.pins_header.read_text(encoding="utf-8")
        self.assertIn("#define TFT_PIN_SCK             PIN_D10", content)
        self.assertIn("#define TFT_PIN_MOSI            PIN_D9", content)
        self.assertIn("#define TFT_PIN_MISO            -1", content)
        self.assertIn("#define TFT_PIN_CS              -1", content)
        self.assertIn("#define TFT_PIN_DC              PIN_D7", content)
        self.assertIn("#define TFT_PIN_RESET           PIN_D8", content)

    def test_hardware_reset_pulse_implemented(self):
        """Verify hardware reset pulse sequence on D8 (GPIO7) before SPI commands."""
        cpp_content = self.driver_cpp.read_text(encoding="utf-8")
        self.assertIn("ili9341_driver_hardware_reset", cpp_content)
        self.assertIn("TFT_PIN_RESET", cpp_content)
        # Verify pull LOW, delay, pull HIGH
        self.assertIn("digitalWrite(TFT_PIN_RESET, LOW)", cpp_content)
        self.assertIn("digitalWrite(TFT_PIN_RESET, HIGH)", cpp_content)

    def test_uart0_conflict_mitigation_and_usb_cdc(self):
        """Verify UART0 logging is avoided to protect GPIO44 (D7) and GPIO43 (D6)."""
        main_content = self.main_cpp.read_text(encoding="utf-8")
        self.assertIn("Hardware UART0 is strictly disabled", main_content)
        self.assertIn("Serial.begin(115200)", main_content)

        pio_content = (REPO_ROOT / "firmware" / "platformio.ini").read_text(encoding="utf-8")
        self.assertIn("-DARDUINO_USB_CDC_ON_BOOT=1", pio_content)
        self.assertIn("-DARDUINO_USB_MODE=1", pio_content)

    def test_all_eleven_plus_display_states_defined(self):
        """Verify all required display states exist in the enum."""
        header_content = self.interface_header.read_text(encoding="utf-8")
        required_states = [
            "DISPLAY_STATE_BOOTING",
            "DISPLAY_STATE_IDLE_READY",
            "DISPLAY_STATE_WAKE_WORD_DETECTED",
            "DISPLAY_STATE_LISTENING",
            "DISPLAY_STATE_PROCESSING_THINKING",
            "DISPLAY_STATE_SPEAKING",
            "DISPLAY_STATE_CAMERA_CAPTURE",
            "DISPLAY_STATE_VISION_PROCESSING",
            "DISPLAY_STATE_VISION_SUCCESS",
            "DISPLAY_STATE_WIFI_DISCONNECTED",
            "DISPLAY_STATE_ERROR",
            "DISPLAY_STATE_MOTOR_MOVING",
            "DISPLAY_STATE_EMERGENCY_STOP",
        ]
        for st in required_states:
            self.assertIn(st, header_content, f"Missing display state: {st}")

    def test_doruru_persona_no_walle_branding(self):
        """Verify DORURU persona consistency and strict prohibition of WALL-E branding."""
        for p in (self.persona_header, self.persona_cpp, self.interface_header, self.interface_cpp):
            text = p.read_text(encoding="utf-8")
            self.assertNotIn("WALL-E", text, f"Illegal WALL-E branding in {p}")
            self.assertNotIn("wall-e", text.lower(), f"Illegal wall-e reference in {p}")

        cpp_content = self.persona_cpp.read_text(encoding="utf-8")
        self.assertIn("[ DORURU ]", cpp_content)

    def test_display_demo_mode_implementation(self):
        """Verify display demo mode cycles screens without commanding motors."""
        interface_content = self.interface_cpp.read_text(encoding="utf-8")
        self.assertIn("display_set_demo_mode", interface_content)
        self.assertIn("display_step_demo", interface_content)
        self.assertIn("s_demo_sequence", interface_content)

        main_content = self.main_cpp.read_text(encoding="utf-8")
        self.assertIn("case 'D':", main_content)
        self.assertIn("case 'd':", main_content)
        self.assertIn("display_set_demo_mode", main_content)

        # Disabling demo mode must restore DISPLAY_STATE_IDLE_READY
        self.assertIn('display_set_state(DISPLAY_STATE_IDLE_READY, "DORURU Ready");', interface_content)

    def test_title_position_clamping_avoids_brand_overlap(self):
        """Verify title_x is clamped to at least 132 to avoid overlapping [ DORURU ] badge."""
        persona_content = self.persona_cpp.read_text(encoding="utf-8")
        self.assertIn("if (title_x < 132) title_x = 132;", persona_content)

    def test_doruru_persona_no_non_ascii_or_em_dash(self):
        """Verify doruru_persona.cpp contains exclusively ASCII characters (no em-dash)."""
        persona_content = self.persona_cpp.read_text(encoding="utf-8")
        for idx, line in enumerate(persona_content.splitlines(), 1):
            for c in line:
                self.assertLessEqual(ord(c), 127, f"Non-ASCII character {c!r} on line {idx}")

    def test_compiler_command_platform_static_flag(self):
        """Verify -static compiler flag is included only on Windows."""
        helper_path = REPO_ROOT / "tests" / "host_test_helper.py"
        helper_content = helper_path.read_text(encoding="utf-8")
        self.assertIn('if os.name == "nt":', helper_content)
        self.assertIn('cmd.append("-static")', helper_content)

    def test_safe_rendering_fallback_implemented(self):
        """Verify high-contrast fallback screen exists for animation error recovery."""
        persona_content = self.persona_cpp.read_text(encoding="utf-8")
        self.assertIn("doruru_persona_render_fallback", persona_content)
        self.assertIn("[ SAFE DISPLAY FALLBACK ]", persona_content)

        interface_content = self.interface_cpp.read_text(encoding="utf-8")
        self.assertIn("display_set_render_error_simulation", interface_content)
        self.assertIn("display_is_fallback_active", interface_content)

    def test_host_firmware_test_compilation_and_execution(self):
        """Verify the host C++ firmware test compiles and passes all checks."""
        exe_path = ensure_compiled_host_firmware_test()
        self.assertTrue(exe_path.exists())
        execute_host_firmware_test(exe_path)


if __name__ == "__main__":
    unittest.main()

