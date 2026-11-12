
# Team SURF

This directory provides the containerised submission for Team SURF to the Benchlab Solar Wind 
Prediction Tournament. Given an inference timestamp, it runs a heliospheric solar-wind
simulation with the `surfs-up` package and submits an hourly, 72-hour forecast
of solar-wind speed at ACE.

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
  "forecast_speed_kms": [500]
}
```

`forecast_speed_kms` contains exactly 72 integer values in km/s, corresponding
to the hours from `valid_from` through `t0 + 72 hours`.

## Forecast method

`model.py` uses a hydrodynamic SURF simulation over 21.5--240 solar radii:

- starts five days before `t0` for spin-up and runs through four days after it;
- uses real-time SWPC solar-wind input from the preceding 28 days, linearly
  filling numerical gaps;
- removes identified ICMEs using DONKI, then obtains DONKI leading-edge CMEs
  and injects them as fixed-duration sinusoidal cone CMEs;
- uses the mean Earth latitude across the simulation and samples the solved
  field at the ACE trajectory hourly;
- returns the first 72 samples, from one hour after the inference timestamp.

The model deliberately fails if DONKI CME data cannot be retrieved or if it
does not produce 72 values. It therefore requires network access to the
domains declared in `submission.json`.

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

The test uses the current UTC hour if no
timestamp is supplied. The checked-in sample under `local_tests/out/` is only
an earlier captured output; rerunning the test replaces it.
