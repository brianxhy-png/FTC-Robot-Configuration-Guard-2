import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config_guard import ConfigDevice, analyze, compare_configs, load_config, report_data, scan_java, summary


class ConfigurationGuardTests(unittest.TestCase):
    def make_repo(self, root: Path) -> Path:
        repo = root / "repo"
        source = repo / "TeamCode" / "src" / "main" / "java"
        source.mkdir(parents=True)
        (source / "Robot.java").write_text(
            """
            public class Robot {
                public static final String FEEDER_NAME = "feeder";
                void init() {
                    hardwareMap.get(DcMotorEx.class, "flywheel");
                    hardwareMap.get(Servo.class, Robot.FEEDER_NAME);
                    hardwareMap.servo.get("legacyServo");
                }
            }
            """,
            encoding="utf-8",
        )
        return repo

    def write_config(self, root: Path, devices: list[dict]) -> Path:
        path = root / "robot.json"
        path.write_text(json.dumps({"devices": devices}), encoding="utf-8")
        return path

    def test_matching_and_type_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self.make_repo(root)
            config = self.write_config(
                root,
                [
                    {"name": "flywheel", "type": "DcMotorEx"},
                    {"name": "feeder", "type": "Servo"},
                    {"name": "legacyServo", "type": "DcMotorEx"},
                ],
            )
            code_devices, _ = scan_java(repo)
            findings = analyze(code_devices, load_config(config))
            counts = summary(findings)
            self.assertEqual(counts["PASS"], 2)
            self.assertEqual(counts["ERROR"], 1)
            self.assertTrue(any(item.code == "TYPE_MISMATCH" for item in findings))

    def test_missing_name_suggests_close_match(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self.make_repo(root)
            config = self.write_config(
                root,
                [
                    {"name": "flyWheel", "type": "DcMotorEx"},
                    {"name": "feeder", "type": "Servo"},
                    {"name": "legacyServo", "type": "Servo"},
                ],
            )
            code_devices, _ = scan_java(repo)
            findings = analyze(code_devices, load_config(config))
            missing = [item for item in findings if item.code == "MISSING_CONFIG_DEVICE"]
            self.assertEqual(len(missing), 1)
            self.assertIn("flyWheel", missing[0].message)

    def test_duplicate_port(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self.make_repo(root)
            config = self.write_config(
                root,
                [
                    {
                        "name": "flywheel",
                        "type": "DcMotorEx",
                        "hub": "Control Hub",
                        "port_type": "motor",
                        "port": 0,
                    },
                    {
                        "name": "feeder",
                        "type": "Servo",
                        "hub": "Expansion Hub",
                        "port_type": "servo",
                        "port": 0,
                    },
                    {
                        "name": "legacyServo",
                        "type": "Servo",
                        "hub": "Expansion Hub",
                        "port_type": "servo",
                        "port": 0,
                    },
                ],
            )
            code_devices, _ = scan_java(repo)
            findings = analyze(code_devices, load_config(config))
            self.assertTrue(any(item.code == "DUPLICATE_PORT" for item in findings))

    def test_commented_mapping_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            (repo / "Commented.java").write_text(
                '// hardwareMap.get(DcMotorEx.class, "ghostMotor");\n'
                '/* hardwareMap.get(Servo.class, "ghostServo"); */\n'
                'hardwareMap.get(DcMotorEx.class, "realMotor");\n',
                encoding="utf-8",
            )
            devices, _ = scan_java(repo)
            self.assertEqual([device.name for device in devices], ["realMotor"])

    def test_drift_report_distinguishes_added_removed_and_moved(self):
        old = [ConfigDevice("left", "DcMotorEx", "Control Hub", "motor", "0"),
               ConfigDevice("oldSensor", "ColorSensor")]
        new = [ConfigDevice("left", "DcMotor", "Control Hub", "motor", "1"),
               ConfigDevice("newSensor", "ColorSensor")]
        findings = compare_configs(new, old)
        self.assertEqual({item.code for item in findings}, {"ADDED_DEVICE", "REMOVED_DEVICE", "PORT_CHANGED"})
        self.assertEqual(report_data([], new, findings)["schema_version"], 1)

    def test_unknown_type_does_not_claim_compatible_or_wrong_type(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = self.make_repo(Path(directory))
            code, _ = scan_java(repo)
            findings = analyze(code, [ConfigDevice("flywheel", "unknown")])
            self.assertIn("UNKNOWN_CONFIG_TYPE", {item.code for item in findings})
            self.assertNotIn("TYPE_MISMATCH", {item.code for item in findings})

    def test_computed_name_is_not_mistaken_for_a_constant(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "Robot.java").write_text(
                'static final String NAME = "left";\n'
                'hardwareMap.get(DcMotor.class, prefix + NAME);\n', encoding="utf-8"
            )
            devices, findings = scan_java(repo)
            self.assertEqual(devices, [])
            self.assertEqual([item.code for item in findings], ["DYNAMIC_NAME"])


if __name__ == "__main__":
    unittest.main()
