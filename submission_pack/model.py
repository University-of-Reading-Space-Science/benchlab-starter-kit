#!/usr/bin/env python3
# Example submission. Replace with anything — this exists to show the shape
# of the contract, not to constrain your language.
#
# Usage:  python3 model.py 20261111T060000Z   ->  logs to stdout and writes JSON to the supplied
# output path.

from datetime import datetime, timedelta
import json
import sys

import astropy.units as u
from astropy.time import Time
import astropy.constants as const
import numpy as np
import surf.surf as s
import surf.surf_insitu as sinsit
import surf.surf_inputs as sin
import surf.surf_analysis as sa

FORECAST_HOURS = 72

def predict(t0):
    """
    This function uses in-situ-SURF to predict the solar wind conditions at Earth for a given
    time. The prediction spans 72 hours ahead of the input time.

    :param t0: The time for which to predict the solar wind conditions.
    :return: A dictionary containing the predicted solar wind conditions.
    """

    try:
        # Define settings shared by the boundary preparation and model setup.
        solver = 'hydro'
        rmin = 21.5 * u.solRad
        rmax = 240.0 * u.solRad
        forecast_time = t0.replace(tzinfo=None)
        buffer_time = 5 * u.day
        start_time = forecast_time - timedelta(days=buffer_time.value)  # 5 days spin up
        end_time = forecast_time + timedelta(
            days=4)  # forecast 4 days ahead to pull out 72hr forecast
        simtime = (end_time - start_time).total_seconds() * u.s  # total sim time
        gamma = 1.5

        # Get mean Earth latitude over forecast period.
        step = 12 * u.hour
        n_steps = int(simtime / step.to(u.s))
        times = Time(start_time) + np.array([i * step.value for i in range(n_steps)]) * step.unit
        ert = s.Observer('EARTH', times)
        latitude = np.mean(ert.lat).to(u.deg)

        # Prepare the selected ambient solar-wind boundary.
        omni_input = sinsit.get_SWPC_realtime(forecast_time - timedelta(days=28), forecast_time)
        omni_numeric = omni_input.select_dtypes(include='number').columns

        omni_input[omni_numeric] = omni_input[omni_numeric].interpolate(method='linear',
                                                                        limit_direction='both')

        omni_input = sinsit.removeICMEs(omni_input, icme_list='DONKI', pre_icme_buffer=0.2,
                                        post_icme_buffer=1.0, donki_min_quality=1)

        model = sinsit.omniSURF_forecast(forecast_time, simtime=simtime, buffertime=buffer_time,
                                         rmin=rmin, rmax=rmax, dr=1.5 * u.solRad, nlon=128,
                                         v_max=3000.0 * (u.km / u.s), dt_scale=4, solver=solver,
                                         gamma=gamma, run_2d=False, track_cmes=False,
                                         include_b_boundary=False, icme_list='DONKI',
                                         omni_input=omni_input)

        model.latitude = latitude.to(u.rad)

        # Build the list of cone CMEs injected into the simulation.
        cme_list = []
        try:
            donki_cmes = sin.get_DONKI_cme_list(model, start_time, forecast_time, feature='LE')
        except Exception as exc:
            donki_cmes = []
            print('DONKI CME data could not be accessed')

        print(f'Loaded {len(donki_cmes)} DONKI cone CMEs for this run')
        if donki_cmes:
            for donki_cme in donki_cmes:
                donki_cme.profile_type = 'sinusoidal'
                donki_cme.cme_expansion = False
                donki_cme.cme_fixed_duration = True
                donki_cme.fixed_duration = 10.0 * u.hour
                donki_cme.thickness = 0.0 * u.solRad
                donki_cme.initial_height = 21.5 * u.solRad
                donki_cme.cme_density = (600.0 / u.cm ** 3 * const.m_p).to(u.kg / u.m ** 3)
                donki_cme.cme_temperature = 1000000.0 * u.K
            cme_list.extend(donki_cmes)

        # Evolve the model with the configured CMEs and optional streak lines.
        model = s.solve_chunked(model, cme_list, chunk_simtime=3.0 * u.day)

        first_forecast = Time(forecast_time + timedelta(hours=1))
        last_forecast = Time(first_forecast + timedelta(hours=71))
        ace = sa.get_horizons_body_for_SURF(first_forecast, last_forecast, step='1H', naif_code=-92,
                                            body_name='ACE')
        vsw = sa.get_SURF_at_position_HEEQ(model, ace['mjd'], ace['r_rs'], ace['lon_rad'])

        speed = [int(v) for v in vsw['vsw'].to_list()]

    except Exception as exc:
        print(f"Forecast failed ({type(exc).__name__}): {exc}",
            file=sys.stderr)
        speed = [np.nan] * FORECAST_HOURS

    return speed


def main():
    if len(sys.argv) != 3:
        print("usage: model.py <YYYYMMDDTHHMMSSZ> <output_path>", file=sys.stderr)
        return 2

    t0_in = sys.argv[1]
    out_path = sys.argv[2]

    t0 = datetime.strptime(t0_in, "%Y%m%dT%H%M%SZ")

    # To be safe, force t0 to snap to the nearest six-hour boundary
    rounded_t0 = t0 + timedelta(hours=3)
    t0 = rounded_t0.replace(
        hour=rounded_t0.hour - (rounded_t0.hour % 6),
        minute=0,
        second=0,
        microsecond=0,
    )

    valid_from = t0 + timedelta(hours=1)
    speeds = predict(t0)

    if len(speeds) != FORECAST_HOURS:
        print(
            "FATAL: produced %d values, need %d" % (len(speeds), FORECAST_HOURS),
            file=sys.stderr,
        )
        return 3

    # Write the speeds to the output file
    out_dict = {'t0':t0.strftime("%Y-%m-%dT%H:%M:%SZ"),
                'valid_from':valid_from.strftime("%Y-%m-%dT%H:%M:%SZ"),
                'forecast_speed_kms':speeds,
                }

    for key, value in out_dict.items():
        print(f"{key}: {value}")

    with open(out_path, "w") as f:
        json.dump(out_dict, f)

    return 0


if __name__ == "__main__":
    sys.exit(main())
