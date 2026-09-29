# FTC Robot Configuration Guard

A local preflight check for FTC hardware configuration. Compare Java `hardwareMap` requests with a JSON/CSV wiring list or an FTC Robot Controller XML export, inspect hub ports, and review what changed since a previous robot configuration.

**Use it before deploying new code or after changing wiring.** The Robot Controller can already report an unavailable hardware name when an OpMode initializes. This tool scans the repository ahead of time and points to the source file and line, so a team can review many OpModes in one pass. It also compares configuration snapshots and audits duplicate names and hub ports. It does not connect to the robot or certify hardware health.

## Open the app

- **Local:** download the repository ZIP, unzip it, and double-click [`index.html`](index.html). No installation, account, Python, or server is needed.
- **GitHub Pages:** repository owner can enable **Settings → Pages → Deploy from a branch → main → /(root)**. Then open `https://brianxhy-png.github.io/FTC-Robot-Configuration-Guard-2/`. The `index.html` in the root is ready to publish. This URL will work only after Pages is enabled.

Select the **FTC repository folder** that contains the team's Java code, then the **active robot configuration** XML/JSON/CSV file. Optionally add a *previous known-good configuration* to see differences. Click **Run configuration scan**. Browse findings, inspect the wiring map, or download Markdown and JSON reports. The files are read by your browser on your device; the app has no upload endpoint.

Try it without team files: choose the [`demo`](demo) folder for the repository and [`example_robot_config.json`](example_robot_config.json) for the configuration. The included sample intentionally contains problems so you can see the diagnostics.

## What it checks

| Check | Example | What to do |
| --- | --- | --- |
| Missing configured name | Java asks for `turretMotor`, config says `turret` | Match the names exactly; they are case-sensitive. |
| Type mismatch | Code requests a motor, config defines a servo | Verify configuration and Java mapping. |
| Conflicting code types | Two classes request `feeder` as different device categories | Review both source locations. |
| Duplicate names or ports | Two devices assigned to a single hub motor port | Confirm active config and intended wiring. |
| Unused config entry | A configured device is absent from scanned mappings | Review whether it is intentionally unused or code is missing. |
| Configuration drift | `intake` moved from motor 1 to motor 2 | Check the electrical change and update records. |
| Dynamic name | A hardware name is assembled at runtime | Review manually; the scanner does not guess. |

**Static analysis limitation:** A name present in both code and the config is not proof the motor is plugged into the stated port or turns the right way. Continue with an on-robot hardware check for motor direction, encoders, sensors, and mechanism movement. Java expressions built dynamically may require manual review. XML schemas and third-party device types vary; an unknown type is reported without claiming compatibility.

## Command line for CI or power users

Requires Python 3.10+; no third-party packages:

```bash
python3 config_guard.py --repo /path/to/FTC-project --config /path/to/active.xml \
  --baseline /path/to/previous.xml \
  --report report.md --json-report report.json
```

Omit `--baseline` if there is no previous configuration. `--strict-warnings` makes warnings fail the command. Exit status `0` means no errors, `1` means scanner errors (or strict warnings), and `2` means invalid input. A zero exit status is **not** a physical robot test.

### Input formats

- **FTC XML:** named device elements from a saved Robot Controller configuration; use the *active* configuration where possible.
- **JSON:** an array or `{ "devices": [...] }`; each row needs `name` and may include `type`, `hub`, `port_type`, and `port`. See [`example_robot_config.json`](example_robot_config.json).
- **CSV:** header `name,type,hub,port_type,port`. Each row represents one device.

A JSON device example:

```json
{"name":"frontLeft","type":"DcMotorEx","hub":"Control Hub","port_type":"motor","port":0}
```

### Team workflow

1. Keep a saved configuration snapshot when the robot wiring changes.
2. Run the guard on a pull request or before an important deployment.
3. Review warnings and dynamic names, not just the error count.
4. Initialize and test every relevant OpMode on the robot; check physical motion and live telemetry.
5. Save the report with your build/test notes to document what was checked.

## Development

The browser app is a standalone HTML file; the CLI implementation is in `config_guard.py`. Both run locally. Tests cover missing names, types, duplicate ports, comments, drift, and unknown types:

```bash
python3 -m unittest discover -s tests -v
```

## License

Code and included original examples are available under the [MIT License](LICENSE). This project is independent and is not affiliated with FIRST.
