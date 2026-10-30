/**
 * @file display_interface.cpp
 * @brief Implementation of display state coordinator.
 */

#include "display_interface.h"
#include <stdio.h>

static display_state_callback_t s_state_cb = nullptr;
static display_state_t s_current_state = DISPLAY_STATE_BOOTING;

void display_register_state_callback(display_state_callback_t cb) {
    s_state_cb = cb;
}

void display_set_state(display_state_t state, const char* message) {
    s_current_state = state;
    if (s_state_cb) {
        s_state_cb(state, message);
    }
}

display_state_t display_get_current_state(void) {
    return s_current_state;
}

