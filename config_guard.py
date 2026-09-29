#!/usr/bin/env python3
"""FTC Robot Configuration Guard.

Scans FTC Java source for hardware mappings and compares them with a robot
configuration supplied as JSON, CSV, or an FTC Robot Controller XML export.
Uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


STRING_CONSTANT_RE = re.compile(
    r"\b(?:public\s+|private\s+|protected\s+)?(?:static\s+)?(?:final\s+)?"
    r"String\s+([A-Za-z_$][\w$]*)\s*=\s*\"([^\"]+)\""
)

MODERN_GET_RE = re.compile(
    r"\b(?:hardwareMap|hwMap)\s*\.\s*get\s*\(\s*"
    r"([A-Za-z_$][\w$<>.]*)\s*\.\s*class\s*,\s*"
    r"([^,)]+)",
    re.MULTILINE,
)

LEGACY_GET_RE = re.compile(
    r"\b(?:hardwareMap|hwMap)\s*\.\s*([A-Za-z_$][\w$]*)\s*"
    r"\.\s*get\s*\(\s*\"([^\"]+)\"\s*\)",
    re.MULTILINE,
)

QUOTED_RE = re.compile(r'^\s*"([^\"]+)"\s*$')
IDENTIFIER_RE = re.compile(r"(?:[A-Za-z_$][\w$]*\s*\.\s*)*([A-Za-z_$][\w$]*)\s*$")


@dataclass(frozen=True)
class CodeDevice:
    name: str
    device_type: str
    file: str
    line: int


@dataclass(frozen=True)
class ConfigDevice:
    name: str
    device_type: str
    hub: str = ""
    port_type: str = ""
    port: str = ""


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    message: str


TYPE_ALIASES = {
    "dcmotor": "motor",
    "dcmotorex": "motor",
    "motor": "motor",
    "lynxmotor": "motor",
    "servo": "servo",
    "standardservo": "servo",
    "crservo": "crservo",
    "continuousrotationservo": "crservo",
    "limelight3a": "limelight",
    "limelight": "limelight",
    "webcamname": "camera",
    "webcam": "camera",
    "camera": "camera",
    "imu": "imu",
    "bno055imu": "imu",
    "colorsensor": "color_sensor",
    "normalizedcolorsensor": "color_sensor",
    "revcolorsensorv3": "color_sensor",
    "distancesensor": "distance_sensor",
    "digitalchannel": "digital",
    "analoginput": "analog",
    "touchsensor": "touch_sensor",
    "voltagesensor": "voltage_sensor",
}

LEGACY_TYPE_ALIASES = {
    "dcmotor": "DcMotor",
    "dcmotorex": "DcMotorEx",
    "servo": "Servo",
    "crservo": "CRServo",
    "colorsensor": "ColorSensor",
    "distancesensor": "DistanceSensor",
    "digitalchannel": "DigitalChannel",
    "analoginput": "AnalogInput",
    "touchsensor": "TouchSensor",
}

XML_CONTAINER_TAGS = {
    "robot",
    "lynxusbdevice",
    "lynxmodule",
    "module",
    "hub",
    "deviceinterfacemodule",
    "motorcontroller",
    "servocontroller",
}


def clean_type(value: str) -> str:
    value = value.strip().split(".")[-1]
    value = re.sub(r"<.*>", "", value)
    return value


def type_category(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]", "", clean_type(value)).lower()
    return TYPE_ALIASES.get(cleaned, cleaned)


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def strip_java_comments(text: str) -> str:
    """Replace Java comments with spaces while preserving offsets/newlines."""
    pattern = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)

    def replace(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else " " for char in match.group(0))

    return pattern.sub(replace, text)


def resolve_name(expression: str, constants: dict[str, str]) -> str | None:
    expression = expression.strip()
    quoted = QUOTED_RE.match(expression)
    if quoted:
        return quoted.group(1)
    identifier = IDENTIFIER_RE.fullmatch(expression)
    if identifier:
        return constants.get(identifier.group(1))
    return None


def collect_string_constants(java_files: Iterable[Path]) -> dict[str, str]:
    constants: dict[str, str] = {}
    conflicts: set[str] = set()
    for path in java_files:
        text = strip_java_comments(path.read_text(encoding="utf-8", errors="replace"))
        for name, value in STRING_CONSTANT_RE.findall(text):
            if name in constants and constants[name] != value:
                conflicts.add(name)
            else:
                constants[name] = value
    for name in conflicts:
        constants.pop(name, None)
    return constants


def scan_java(repo: Path) -> tuple[list[CodeDevice], list[Finding]]:
    java_files = sorted(
        path
        for path in repo.rglob("*.java")
        if not any(part in {"build", ".gradle", ".git"} for part in path.parts)
    )
    constants = collect_string_constants(java_files)
    devices: list[CodeDevice] = []
    findings: list[Finding] = []

    for path in java_files:
        text = strip_java_comments(path.read_text(encoding="utf-8", errors="replace"))
        relative = str(path.relative_to(repo))

        for match in MODERN_GET_RE.finditer(text):
            raw_type, expression = match.groups()
            name = resolve_name(expression, constants)
            if name is None:
                findings.append(
                    Finding(
                        "INFO",
                        "DYNAMIC_NAME",
                        f"Could not resolve hardware name expression '{expression.strip()}' "
                        f"in {relative}:{line_number(text, match.start())}.",
                    )
                )
                continue
            devices.append(
                CodeDevice(
                    name,
                    clean_type(raw_type),
                    relative,
                    line_number(text, match.start()),
                )
            )

        for match in LEGACY_GET_RE.finditer(text):
            collection, name = match.groups()
            device_type = LEGACY_TYPE_ALIASES.get(collection.lower(), collection)
            devices.append(
                CodeDevice(
                    name,
                    device_type,
                    relative,
                    line_number(text, match.start()),
                )
            )

    return devices, findings


def parse_json(path: Path) -> list[ConfigDevice]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("devices") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("JSON configuration must contain a devices array")
    if any(not isinstance(row, dict) or not row.get("name") for row in rows):
        raise ValueError("Every configured device needs a nonempty name")
    return [
        ConfigDevice(
            name=str(row["name"]),
            device_type=str(row.get("type", row.get("device_type", "unknown"))),
            hub=str(row.get("hub", "")),
            port_type=str(row.get("port_type", "")),
            port=str(row.get("port", "")),
        )
        for row in rows
    ]


def parse_csv(path: Path) -> list[ConfigDevice]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        if not rows.fieldnames or "name" not in rows.fieldnames:
            raise ValueError("CSV configuration needs a name column")
        return [
            ConfigDevice(
                name=str(row.get("name", "")),
                device_type=str(row.get("type", row.get("device_type", "unknown"))),
                hub=str(row.get("hub", "")),
                port_type=str(row.get("port_type", "")),
                port=str(row.get("port", "")),
            )
            for row in rows
            if row.get("name")
        ]


def strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_xml(path: Path) -> list[ConfigDevice]:
    root = ET.parse(path).getroot()
    devices: list[ConfigDevice] = []

    def visit(element: ET.Element, current_hub: str = "") -> None:
        tag = strip_namespace(element.tag)
        tag_lower = tag.lower()
        name = element.attrib.get("name", "")
        next_hub = current_hub
        if tag_lower in {"lynxmodule", "module", "hub"} and name:
            next_hub = name

        children = list(element)
        is_container = tag_lower in XML_CONTAINER_TAGS
        if name and not is_container:
            port = str(element.attrib.get("port", element.attrib.get("bus", "")))
            port_type = type_category(tag)
            devices.append(ConfigDevice(name, tag, current_hub, port_type, port))

        for child in children:
            visit(child, next_hub)

    visit(root)
    return devices


def load_config(path: Path) -> list[ConfigDevice]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return parse_json(path)
    if suffix == ".csv":
        return parse_csv(path)
    if suffix == ".xml":
        return parse_xml(path)
    raise ValueError("Configuration must be a .json, .csv, or .xml file")


def nearest_names(name: str, candidates: Iterable[str]) -> list[str]:
    return difflib.get_close_matches(name, list(candidates), n=3, cutoff=0.58)


def analyze(
    code_devices: list[CodeDevice], config_devices: list[ConfigDevice]
) -> list[Finding]:
    findings: list[Finding] = []
    code_by_name: dict[str, list[CodeDevice]] = {}
    config_by_name: dict[str, list[ConfigDevice]] = {}

    for device in code_devices:
        code_by_name.setdefault(device.name, []).append(device)
    for device in config_devices:
        config_by_name.setdefault(device.name, []).append(device)

    config_names = set(config_by_name)
    code_names = set(code_by_name)

    for name in sorted(code_names - config_names):
        locations = ", ".join(
            f"{item.file}:{item.line}" for item in code_by_name[name][:4]
        )
        suggestions = nearest_names(name, config_names)
        hint = f" Possible match: {', '.join(suggestions)}." if suggestions else ""
        findings.append(
            Finding(
                "ERROR",
                "MISSING_CONFIG_DEVICE",
                f"Code requires '{name}' ({locations}), but it is absent from the configuration.{hint}",
            )
        )

    for name in sorted(config_names - code_names):
        device = config_by_name[name][0]
        findings.append(
            Finding(
                "WARNING",
                "UNUSED_CONFIG_DEVICE",
                f"Configuration contains '{name}' ({device.device_type}), but no scanned Java mapping uses it.",
            )
        )

    for name in sorted(code_names & config_names):
        code_categories = {type_category(item.device_type) for item in code_by_name[name]}
        config_categories = {type_category(item.device_type) for item in config_by_name[name]}
        if len(code_categories) > 1:
            findings.append(
                Finding(
                    "ERROR",
                    "CONFLICTING_CODE_TYPES",
                    f"'{name}' is requested as multiple incompatible code types: "
                    f"{', '.join(sorted(code_categories))}.",
                )
            )
        if code_categories.isdisjoint(config_categories) and "unknown" not in config_categories:
            findings.append(
                Finding(
                    "ERROR",
                    "TYPE_MISMATCH",
                    f"'{name}' is {', '.join(sorted(code_categories))} in code but "
                    f"{', '.join(sorted(config_categories))} in the configuration.",
                )
            )
        elif not code_categories.isdisjoint(config_categories):
            findings.append(
                Finding(
                    "PASS",
                    "MATCHED_DEVICE",
                    f"'{name}' exists with a compatible type ({', '.join(sorted(code_categories))}).",
                )
            )
        else:
            findings.append(Finding("INFO", "UNKNOWN_CONFIG_TYPE", f"'{name}' is present, but its configuration type is unknown; verify it on the robot."))

    for name, devices in sorted(config_by_name.items()):
        if len(devices) > 1:
            descriptions = ", ".join(
                f"{item.hub or 'unknown hub'} {item.port_type or 'port'} {item.port or '?'}"
                for item in devices
            )
            findings.append(
                Finding(
                    "ERROR",
                    "DUPLICATE_CONFIG_NAME",
                    f"Configuration name '{name}' appears more than once: {descriptions}.",
                )
            )

    ports: dict[tuple[str, str, str], list[ConfigDevice]] = {}
    for device in config_devices:
        if device.hub and device.port:
            key = (device.hub, device.port_type or type_category(device.device_type), device.port)
            ports.setdefault(key, []).append(device)
    for (hub, port_type, port), devices in sorted(ports.items()):
        if len(devices) > 1:
            findings.append(
                Finding(
                    "ERROR",
                    "DUPLICATE_PORT",
                    f"{hub} {port_type} port {port} is assigned to: "
                    f"{', '.join(item.name for item in devices)}.",
                )
            )

    severity_order = {"ERROR": 0, "WARNING": 1, "INFO": 2, "PASS": 3}
    return sorted(findings, key=lambda item: (severity_order[item.severity], item.code, item.message))


def compare_configs(current: list[ConfigDevice], baseline: list[ConfigDevice]) -> list[Finding]:
    """Describe changes since a known-good configuration, without assuming they are mistakes."""
    old = {device.name: device for device in baseline}
    new = {device.name: device for device in current}
    findings: list[Finding] = []
    for name in sorted(old.keys() - new.keys()):
        findings.append(Finding("WARNING", "REMOVED_DEVICE", f"'{name}' was removed since the baseline configuration."))
    for name in sorted(new.keys() - old.keys()):
        findings.append(Finding("INFO", "ADDED_DEVICE", f"'{name}' was added since the baseline configuration."))
    for name in sorted(old.keys() & new.keys()):
        before, after = old[name], new[name]
        if type_category(before.device_type) != type_category(after.device_type):
            findings.append(Finding("WARNING", "TYPE_CHANGED", f"'{name}' changed type: {before.device_type} → {after.device_type}."))
        if (before.hub, before.port_type, before.port) != (after.hub, after.port_type, after.port):
            findings.append(Finding("WARNING", "PORT_CHANGED", f"'{name}' moved from {before.hub or '?'} {before.port_type or '?'} {before.port or '?'} to {after.hub or '?'} {after.port_type or '?'} {after.port or '?'}."))
    return findings


def report_data(code_devices: list[CodeDevice], config_devices: list[ConfigDevice], findings: list[Finding]) -> dict:
    """Stable machine-readable format for CI, scripts, and saved scan comparison."""
    return {
        "schema_version": 1,
        "summary": summary(findings),
        "mappings": [vars(device) for device in code_devices],
        "devices": [vars(device) for device in config_devices],
        "findings": [vars(finding) for finding in findings],
    }


def summary(findings: list[Finding]) -> dict[str, int]:
    counts = {"ERROR": 0, "WARNING": 0, "INFO": 0, "PASS": 0}
    for finding in findings:
        counts[finding.severity] += 1
    return counts


def render_terminal(findings: list[Finding]) -> str:
    counts = summary(findings)
    lines = [
        "FTC ROBOT CONFIGURATION GUARD",
        "=" * 29,
        f"Errors: {counts['ERROR']} | Warnings: {counts['WARNING']} | "
        f"Info: {counts['INFO']} | Passed: {counts['PASS']}",
        "",
    ]
    for finding in findings:
        lines.append(f"[{finding.severity}] {finding.code}: {finding.message}")
    if not findings:
        lines.append("No hardware mappings or findings were discovered.")
    return "\n".join(lines)


def render_markdown(
    repo: Path,
    config: Path,
    code_devices: list[CodeDevice],
    config_devices: list[ConfigDevice],
    findings: list[Finding],
) -> str:
    counts = summary(findings)
    status = "FAIL" if counts["ERROR"] else "REVIEW" if counts["WARNING"] else "PASS"
    lines = [
        "# FTC Robot Configuration Guard Report",
        "",
        f"**Status:** {status}",
        "",
        f"- Repository: `{repo}`",
        f"- Configuration: `{config}`",
        f"- Java hardware mappings found: **{len(code_devices)}**",
        f"- Configured devices found: **{len(config_devices)}**",
        f"- Errors: **{counts['ERROR']}**",
        f"- Warnings: **{counts['WARNING']}**",
        f"- Informational notices: **{counts['INFO']}**",
        f"- Compatible devices: **{counts['PASS']}**",
        "",
    ]
    for severity in ("ERROR", "WARNING", "INFO", "PASS"):
        selected = [item for item in findings if item.severity == severity]
        if not selected:
            continue
        lines.extend([f"## {severity.title()}", ""])
        for item in selected:
            lines.append(f"- **{item.code}:** {item.message}")
        lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare FTC Java hardware mappings with a robot configuration."
    )
    parser.add_argument("--repo", required=True, type=Path, help="FTC repository root")
    parser.add_argument(
        "--config", required=True, type=Path, help="Robot config (.json, .csv, or .xml)"
    )
    parser.add_argument(
        "--report", type=Path, help="Optional Markdown report output path"
    )
    parser.add_argument("--json-report", type=Path, help="Optional machine-readable JSON report")
    parser.add_argument("--baseline", type=Path, help="Optional previous JSON/CSV/XML configuration for drift review")
    parser.add_argument(
        "--strict-warnings",
        action="store_true",
        help="Return failure exit code when warnings exist",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.repo.is_dir():
        print(f"ERROR: Repository directory not found: {args.repo}", file=sys.stderr)
        return 2
    if not args.config.is_file():
        print(f"ERROR: Configuration file not found: {args.config}", file=sys.stderr)
        return 2
    if args.baseline and not args.baseline.is_file():
        print(f"ERROR: Baseline file not found: {args.baseline}", file=sys.stderr)
        return 2

    try:
        code_devices, scan_findings = scan_java(args.repo)
        config_devices = load_config(args.config)
        baseline_devices = load_config(args.baseline) if args.baseline else None
    except (OSError, ValueError, KeyError, json.JSONDecodeError, ET.ParseError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    findings = analyze(code_devices, config_devices) + scan_findings
    if not code_devices:
        findings.append(Finding("WARNING", "NO_MAPPINGS", "No resolvable hardware mappings were found in the scanned Java files; this is not a verified pass."))
    if not config_devices:
        findings.append(Finding("WARNING", "EMPTY_CONFIGURATION", "No configured devices were parsed; confirm this is the active robot configuration."))
    if baseline_devices is not None:
        findings += compare_configs(config_devices, baseline_devices)
    print(render_terminal(findings))

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            render_markdown(
                args.repo.resolve(),
                args.config.resolve(),
                code_devices,
                config_devices,
                findings,
            ),
            encoding="utf-8",
        )
        print(f"\nReport written to: {args.report}")

    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(json.dumps(report_data(code_devices, config_devices, findings), indent=2) + "\n", encoding="utf-8")
        print(f"JSON report written to: {args.json_report}")

    counts = summary(findings)
    if counts["ERROR"] or (args.strict_warnings and counts["WARNING"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
