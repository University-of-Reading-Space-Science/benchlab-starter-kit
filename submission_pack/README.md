# Team SURF

This directory provides the containerised submission for Team SURF to the Benchlab Solar Wind 
Prediction Tournament. Given an inference timestamp, it runs a heliospheric solar-wind
simulation with the `surfs-up` package and generates an hourly, 72-hour forecast
of solar-wind speed at ACE.

## Competition Category

The Team SURF submission has been entered to the Operational Podium (Native Container) category.

## Summary

Our submission uses the open source SURF hydrodynamic model 
(https://github.com/University-of-Reading-Space-Science/SURF) to generate the required solar 
wind speed forecasts. We use the SURF-hydro configuration, which is a 1D hydrodynamic model, 
that, for a specified inner boundary condition, solves for the evolution of the solar wind 
between 21.5 and 240 solar radii. 

The inner boundary conditions are constructed from the composite real-time SWPC solar wind speed 
data for the previous 28-days. Periods of CME activity are removed using the CCMC DONKI ICME 
list. Resulting data gaps are linearly interpolated over. These data form the ambient solar wind 
boundary conditions to SURF-hydro. The CCMC DONKI CME catalogue is queried for any CMEs over the 
previous 5 days, and those data are used to generate Cone CMEs that are added to the SURF-hydro 
simulation. The resulting 72-hour solar wind speed forecast at ACE is then interpolated from the 
model solution using ACE ephemeris data.

If the model fails for any reason, it instead returns 72 NaN values.

## Declared Domains
The below table summarises the domains our model requires access to:

| Domain | Why it is accessed |
|---|---|
| `iswa.ccmc.gsfc.nasa.gov` | Retrieves real-time SWPC plasma/magnetic data through ISWA HAPI. |
| `ccmc.gsfc.nasa.gov` | Queries DONKI ICME and CME catalogues. |
| `ssd.jpl.nasa.gov` | Resolves ACE spacecraft coordinates for the forecast period through SunPy/JPL Horizons. |

## Submission contract

The platform starts the image as:

```text
/app/run.sh YYYYMMDDTHHMMSSZ
```

For example, `20261111T060000Z`. `run.sh` passes that timestamp to `model.py`,
which writes `/tmp/forecast.json`. It then invokes `upload.sh`; the platform
provides its presigned multipart-upload details in `OUTPUT_POST`.

The generated JSON has this shape:

```json
{
  "t0": "2026-11-11T06:00:00Z",
  "valid_from": "2026-11-11T07:00:00Z",
  "forecast_speed_kms": ["72 hourly values"]
}
```

`forecast_speed_kms` contains exactly 72 integer values in km/s, corresponding
to the hours from `valid_from` through `t0 + 72 hours`.

## Image contents and resources

The `Dockerfile` builds an `linux/amd64` Python 3.12 image, installs
`surfs-up`, and configures `/app/run.sh` as its entrypoint. `submission.json`
declares a 4-CPU / 16-GiB allocation and the external services used by the
forecast. The platform upload helper additionally needs `curl` and `jq`.

The presigned POST upload requires the file form field to be last; `upload.sh`
preserves that ordering. It retries failed uploads up to three times and has a
120-second request timeout.

## Run locally

Docker is required. From this directory:

```bash
cd local_tests
./test_local.sh 20261111T060000Z
```

The test script:

1. builds `../Dockerfile` as `swp-local` for `linux/amd64`;
2. rejects images of 15 GiB or larger;
3. starts a local mock presigned-POST endpoint on port 8899;
4. runs the image with the same timestamp argument and environment variables
   used by the platform; and
5. saves the upload to `local_tests/out/forecast.json` and checks that it has
   72 finite speeds between 0 and 10,000 km/s.

The test uses the current UTC hour if no timestamp is supplied. The checked-in sample under 
`local_tests/out/` is only an earlier captured output; rerunning the test replaces it.
