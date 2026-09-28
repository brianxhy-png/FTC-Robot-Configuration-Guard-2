import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config_guard import analyze, load_config, scan_java, summary


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


if __name__ == "__main__":
    unittest.main()
