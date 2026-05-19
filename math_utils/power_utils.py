import math
from typing import Union

import pandas as pd

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


# ─────────────────────────────────────────────
# FTP estimation via Mean Maximal Power (MMP)
# ─────────────────────────────────────────────

DEFAULT_DURATIONS = [60, 300, 600, 1200, 3600]  # 1 min, 5 min, 10 min, 20 min, 60 min


def compute_mmp(
    power_series: pd.Series,
    min_gradient_pct,
    gradient_series: pd.Series = None,
    durations_seconds: list = None,
) -> dict:
    """
    Compute the Mean Maximal Power (MMP) curve for a single ride.

    When gradient_series is provided only continuous climbing segments
    (gradient >= min_gradient_pct) are considered, so the rolling windows
    never cross flat or descending sections where the physics model is
    unreliable (wind noise, coast-down, etc.).

    Returns {duration_seconds: best_avg_watts} — None when no climbing
    segment is long enough for that duration.
    """
    if durations_seconds is None:
        durations_seconds = DEFAULT_DURATIONS

    mmp: dict = {dur: None for dur in durations_seconds}
    for dur in durations_seconds:
        if len(power_series) < dur:
            continue
        rolling_power = power_series.rolling(window=dur, min_periods=dur).mean()
        if gradient_series is not None:
            rolling_gradient = gradient_series.rolling(window=dur, min_periods=dur).mean()
            rolling_power = rolling_power[rolling_gradient >= min_gradient_pct]
        if not rolling_power.empty:
            best = rolling_power.max()
            if not pd.isna(best):
                mmp[dur] = round(float(best), 1)

    return mmp


def estimate_ftp(
    power_sources: Union[pd.Series, list],
    min_gradient_pct: float,
    gradient_sources: Union[pd.Series, list, None] = None,
    durations_seconds: list = None,
) -> dict:
    """
    Estimate FTP from one or several rides using the 20-minute method.

    power_sources    : a single pd.Series or a list of pd.Series (one per ride).
    gradient_sources : matching gradient pd.Series or list thereof. When provided,
                       only climbing segments are considered (passed to compute_mmp).
    FTP ≈ 95% × best 20-minute average power across all rides.

    Returns:
        ftp_watts       : estimated FTP in watts (None if no climbing segment ≥ 20 min)
        best_20min_watts: raw best 20-min power before the 0.95 factor
        mmp             : merged MMP curve {duration_s: best_avg_w}
    """
    if durations_seconds is None:
        durations_seconds = DEFAULT_DURATIONS

    if isinstance(power_sources, pd.Series):
        power_sources = [power_sources]
    if isinstance(gradient_sources, pd.Series):
        gradient_sources = [gradient_sources]

    merged: dict = {dur: None for dur in durations_seconds}
    for idx, series in enumerate(power_sources):
        grad = gradient_sources[idx] if gradient_sources is not None else None
        ride_mmp = compute_mmp(
            series,
            gradient_series=grad,
            min_gradient_pct=min_gradient_pct,
            durations_seconds=durations_seconds,
        )
        for dur, val in ride_mmp.items():
            if val is not None:
                merged[dur] = val if merged[dur] is None else max(merged[dur], val)

    best_20min = merged.get(1200)
    ftp = round(best_20min * 0.95, 1) if best_20min is not None else None
    return {
        "ftp_watts": ftp,
        "best_20min_watts": best_20min,
        "mmp": merged,
    }