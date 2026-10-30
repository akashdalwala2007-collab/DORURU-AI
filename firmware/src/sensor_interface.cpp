#include "sensor_interface.h"

namespace doruru {
namespace sensors {

// Provide global disabled sensor instance
static DisabledSensorProvider g_disabledSensorProvider;

ISensorProvider& getSensorProvider() {
    return g_disabledSensorProvider;
}

} // namespace sensors
} // namespace doruru

