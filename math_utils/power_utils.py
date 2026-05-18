import math

def compute_power(
    speed_ms: float,          # speed in m/s
    gradient: float,          # slope in % (e.g. 5 for 5%)
    mass_kg: float,           # rider + bike mass in kg
    wind_speed_ms: float = 0, # headwind in m/s (positive = headwind)
    altitude_m: float = 0,    # altitude in meters (affects air density)
    temp_celsius: float = 20, # temperature in °C (affects air density)
    crr: float = 0.005,       # rolling resistance coefficient (road bike default)
    cda: float = 0.32,        # drag coefficient * frontal area (road bike default)
    drivetrain_loss: float = 0.02  # drivetrain loss (2% default)
) -> dict:
    """
    Compute cycling power from physical parameters.
    Returns a breakdown of each power component.
    """
    G = 9.81  # gravity m/s²

    # --- Air density (varies with altitude and temperature) ---
    pressure = 101325 * (1 - 0.0000226 * altitude_m) ** 5.256  # Pascal
    temp_kelvin = temp_celsius + 273.15
    air_density = pressure / (287.05 * temp_kelvin)  # kg/m³

    # --- Gradient ---
    slope_angle = math.atan(gradient / 100)

    # --- Power components ---

    # 1. Gravity (climbing)
    p_gravity = mass_kg * G * math.sin(slope_angle) * speed_ms

    # 2. Rolling resistance
    p_rolling = crr * mass_kg * G * math.cos(slope_angle) * speed_ms

    # 3. Aerodynamic drag
    relative_speed = speed_ms + wind_speed_ms  # effective air speed
    p_drag = 0.5 * cda * air_density * relative_speed**2 * speed_ms

    # 4. Sum before drivetrain loss
    p_total_raw = p_gravity + p_rolling + p_drag

    # 5. Drivetrain loss
    p_drivetrain = p_total_raw * drivetrain_loss

    # 6. Total power (what you actually produce)
    p_total = p_total_raw + p_drivetrain
    return {
        "power_total_w":     round(p_total, 1) if p_total > 0 else 0,
        "power_gravity_w":   round(p_gravity, 1),
        "power_rolling_w":   round(p_rolling, 1),
        "power_drag_w":      round(p_drag, 1),
        "power_drivetrain_w":round(p_drivetrain, 1),
        "air_density":       round(air_density, 4),
        "w_per_kg":          round(p_total / mass_kg, 2) if p_total > 0 else 0,
    }