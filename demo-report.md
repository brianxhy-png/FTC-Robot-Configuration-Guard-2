# FTC Robot Configuration Guard Report

**Status:** FAIL

- Repository: `/workspace/scratch/b5e7196b6baf/FTC-Robot-Configuration-Guard/demo`
- Configuration: `/workspace/scratch/b5e7196b6baf/FTC-Robot-Configuration-Guard/example_robot_config.json`
- Java hardware mappings found: **9**
- Configured devices found: **9**
- Errors: **1**
- Warnings: **1**
- Informational notices: **0**
- Compatible devices: **8**

## Error

- **MISSING_CONFIG_DEVICE:** Code requires 'turret' (TeamCode/src/main/java/DemoRobot.java:11), but it is absent from the configuration. Possible match: turretMotor.

## Warning

- **UNUSED_CONFIG_DEVICE:** Configuration contains 'turretMotor' (DcMotorEx), but no scanned Java mapping uses it.

## Pass

- **MATCHED_DEVICE:** 'backLeft' exists with a compatible type (motor).
- **MATCHED_DEVICE:** 'backRight' exists with a compatible type (motor).
- **MATCHED_DEVICE:** 'feeder' exists with a compatible type (servo).
- **MATCHED_DEVICE:** 'flywheel' exists with a compatible type (motor).
- **MATCHED_DEVICE:** 'frontLeft' exists with a compatible type (motor).
- **MATCHED_DEVICE:** 'frontRight' exists with a compatible type (motor).
- **MATCHED_DEVICE:** 'intakeMotor' exists with a compatible type (motor).
- **MATCHED_DEVICE:** 'limelight' exists with a compatible type (limelight).
