---
orphan: true
---

# PRISM Studio v1.20.0

## Highlights

- **The BIDS check is part of `prism-validator` and runs by default.** One `pip install prism-validator`
  gives you PRISM and BIDS validation. The validator now depends on `bids-validator-deno` (the official
  pre-compiled BIDS validator, which brings the Deno runtime as a pip wheel; about 80 MB installed).
  `--no-bids` skips the BIDS part (also `"runBids": false` in `.prismrc.json`); `--bids` is still accepted.
  There is one verdict: `valid` means valid PRISM and valid BIDS. The BIDS validator moves from 2.4.1 to
  3.0.2, so some check codes may differ.
- **Projects created before 1.20** carry `"runBids": false` in their `.prismrc.json` (the validator prints a
  notice on stderr). Delete that line or pass `--bids`. New projects and the demo write `true`.
- **Fail closed.** `PRISM902` is reported when the BIDS check cannot run, produces nothing readable, exits
  unexpectedly, or takes longer than 30 minutes.
- **JSON.** `--json` and `--format json` carry a `bids_validator` object (engine, version) when the BIDS
  check ran.
- **Install.** No separate Deno is needed anywhere (the installers no longer run the deno.land script), and
  it works offline. Supported: macOS, Linux x86_64/aarch64 (glibc 2.27 or newer) and Windows x64.
  **On Alpine/musl and on glibc older than 2.27, `pip install prism-validator` fails** (use the Docker
  image). On other architectures (for example Windows ARM64) the install works, and a run reports `PRISM902`
  with the `--no-bids` hint.
- **DataLad Desktop and the Austrian neurocloud:** just pin `prism-validator`. Their own Deno download script,
  lock file, `DENO_DIR`, neutral working folder and `PATH` change are no longer needed.
- **Demo dataset.** `examples/wellbeing_multi_demo` now reports its real BIDS findings (`DEMO_GUIDE.md` is not
  part of BIDS, `PARTICIPANT_ID_MISMATCH`) by default.
- **PyPI page.** The logo and the links render correctly from this release on.

See `CHANGELOG.md` for the full list of changes.

## Downloads

- Windows: `prism-studio-Windows.zip`
- macOS (Apple Silicon): `prism-studio-macOS-AppleSilicon.zip`
- Linux: `prism-studio-Linux.zip`

## macOS First Launch

If macOS blocks the app on first launch, open the extracted release folder and double-click:

`Prism Studio Installer.app`

If App Translocation prevents auto-detection, the installer asks you to select `PrismStudio.app` once.

Fallback:

`Open Prism Studio.command`
