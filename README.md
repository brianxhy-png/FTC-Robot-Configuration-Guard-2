# FTC Robot Configuration Guard

Catch hardware-name, device-type, and port-assignment mistakes before an FTC
OpMode initializes.

The tool scans Java source for FTC hardware mappings such as:

```java
flywheel = hardwareMap.get(DcMotorEx.class, "flywheel");
feeder = hardwareMap.get(Servo.class, RobotConfig.FEEDER_NAME);
```

It compares them with a robot configuration supplied as:

- A manual JSON wiring list
- A CSV wiring list
- An FTC Robot Controller configuration XML export

It reports:

- Hardware names required by code but missing from the configuration
- Configuration devices that are not mapped by scanned Java code
- Motor/servo/sensor type mismatches
- One name requested as conflicting types in different Java files
- Duplicate configuration names
- Multiple devices assigned to the same hub port
- Likely spelling matches such as `turretMotor` versus `turret`
- Hardware names stored in simple Java `String` constants

## Requirements

- macOS, Windows, or Linux
- Python 3.10 or newer
- No external Python packages

## Easiest method: browser interface

No Terminal is required:

1. Double-click `FTC-Config-Guard.html`.
2. If macOS asks which application to use, choose Chrome.
3. Press **Choose the FTC repository** and select the complete repository
   folder.
4. Press **Choose the robot configuration** and select a JSON, CSV, or FTC XML
   file.
5. Press **Run configuration scan**.
6. Review the colour-coded findings or download the Markdown report.

All processing happens locally inside the browser. The selected private team
code is not uploaded anywhere.

## Command-line method

Open Terminal and move into this tool's folder:

```bash
cd /path/to/FTC-Robot-Configuration-Guard
```

Run it against the cloned Aimbot repository using the included example wiring
file:

```bash
python3 config_guard.py \
  --repo "$HOME/Documents/GitHub/ClonedFTCController" \
  --config example_robot_config.json \
  --report aimbot-config-report.md
```

Replace the repository path if GitHub Desktop saved it elsewhere.

Exit codes:

- `0`: no errors
- `1`: errors found, or warnings found when `--strict-warnings` is enabled
- `2`: invalid path or configuration input

## JSON configuration format

Edit `example_robot_config.json` to match the real Control Hub and Expansion
Hub wiring. Each device requires `name` and `type`. Hub and port information is
needed for duplicate-port checking.

```json
{
  "devices": [
    {
      "name": "frontLeft",
      "type": "DcMotorEx",
      "hub": "Control Hub",
      "port_type": "motor",
      "port": 0
    }
  ]
}
```

## CSV configuration format

Use this header:

```csv
name,type,hub,port_type,port
frontLeft,DcMotorEx,Control Hub,motor,0
```

## FTC XML configuration

If the team exports or retrieves the FTC Robot Controller configuration XML,
pass that file directly:

```bash
python3 config_guard.py \
  --repo "/path/to/ClonedFTCController" \
  --config "/path/to/AimbotRobot.xml" \
  --report report.md
```

FTC XML structures can vary by SDK and device. The guard reads named device
elements and their hub/port attributes, but the generated report should still
be checked by a programmer and electrical member.

## Recommended team workflow

1. Electrical updates the wiring list whenever a port or device changes.
2. Programming runs the guard before deploying an important build.
3. Errors must be resolved before robot initialization.
4. Warnings are reviewed; some configured devices may intentionally be unused
   by a particular branch.
5. Save the Markdown report with test notes or attach it to a pull request.

## Current limitations

- Dynamically generated hardware names cannot always be resolved.
- Constants with the same Java identifier but different values are ignored to
  avoid guessing incorrectly.
- The tool checks configuration agreement, not physical wiring continuity,
  motor direction, encoder direction, PID tuning, or mechanism performance.
- XML device type names vary; verify unusual third-party devices manually.

## Run the tests

```bash
python3 -m unittest discover -s tests -v
```
