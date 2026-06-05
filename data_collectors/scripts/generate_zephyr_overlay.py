#!/usr/bin/env python3
"""Generate Zephyr devicetree overlays from hardware_config.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def load_board(config_path: Path, board_name: str | None) -> tuple[str, Dict[str, Any]]:
    with config_path.open("r", encoding="ascii") as f:
        config = json.load(f)

    selected = board_name or config.get("active_board")
    boards = config.get("boards", {})
    if selected not in boards:
        known = ", ".join(sorted(boards))
        raise SystemExit(f"unknown board '{selected}'. Known boards: {known}")
    return selected, boards[selected]


def esp32_spi_symbol(signal: str, instance: int, gpio: int) -> str:
    names = {
        "miso": "MISO",
        "mosi": "MOSI",
        "sck": "SCLK",
        "cs": "CSEL",
    }
    return f"SPIM{instance}_{names[signal]}_GPIO{gpio}"


def esp32_i2c_symbol(signal: str, instance: int, gpio: int) -> str:
    return f"I2C{instance}_{signal.upper()}_GPIO{gpio}"


def esp32_uart_symbol(signal: str, instance: int, gpio: int) -> str:
    return f"UART{instance}_{signal.upper()}_GPIO{gpio}"


def gpio_flag(active: str) -> str:
    return "GPIO_ACTIVE_LOW" if active.lower() == "low" else "GPIO_ACTIVE_HIGH"


def safe_label(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value)


def emit_sd_pinctrl(lines: List[str], board_name: str, board: Dict[str, Any]) -> None:
    sd = board.get("sd_card", {})
    if not sd.get("enabled", False):
        return

    label = safe_label(f"{board_name}_sd")
    instance = int(sd["spi_instance"])

    lines.extend(
        [
            f"    {label}_spim_default: {label}_spim_default {{",
            "        group1 {",
            "            pinmux = <"
            + esp32_spi_symbol("miso", instance, int(sd["miso_gpio"]))
            + ">,",
            "                     <"
            + esp32_spi_symbol("mosi", instance, int(sd["mosi_gpio"]))
            + ">,",
            "                     <"
            + esp32_spi_symbol("sck", instance, int(sd["sck_gpio"]))
            + ">,",
            "                     <"
            + esp32_spi_symbol("cs", instance, int(sd["cs_gpio"]))
            + ">;",
            "        };",
            "    };",
            "",
        ]
    )


def emit_sd_node(lines: List[str], board_name: str, board: Dict[str, Any]) -> None:
    sd = board.get("sd_card", {})
    if not sd.get("enabled", False):
        return

    label = safe_label(f"{board_name}_sd")
    spi_node = sd["spi_node"]

    lines.extend(
        [
            f"&{spi_node} {{",
            "    status = \"okay\";",
            f"    cs-gpios = <&{board['gpio_controller']} {int(sd['cs_gpio'])} GPIO_ACTIVE_LOW>;",
            f"    pinctrl-0 = <&{label}_spim_default>;",
            "    pinctrl-names = \"default\";",
            "",
            "    sdhc0: sdhc@0 {",
            "        compatible = \"zephyr,sdhc-spi-slot\";",
            "        reg = <0>;",
            "        status = \"okay\";",
            f"        spi-max-frequency = <{int(sd['max_frequency_hz'])}>;",
            "",
            "        mmc {",
            "            compatible = \"zephyr,sdmmc-disk\";",
            f"            disk-name = \"{sd.get('disk_name', 'SD')}\";",
            "            status = \"okay\";",
            "        };",
            "    };",
            "};",
            "",
        ]
    )


def emit_i2c_pinctrl(lines: List[str], board_name: str, board: Dict[str, Any], used_buses: set[str]) -> None:
    for bus_name, bus in board.get("i2c", {}).items():
        if bus_name not in used_buses or not bus.get("enabled", False):
            continue
        label = safe_label(f"{board_name}_{bus_name}")
        instance = int(bus["instance"])
        lines.extend(
            [
                f"    {label}_default: {label}_default {{",
                "        group1 {",
                "            pinmux = <"
                + esp32_i2c_symbol("sda", instance, int(bus["sda_gpio"]))
                + ">,",
                "                     <"
                + esp32_i2c_symbol("scl", instance, int(bus["scl_gpio"]))
                + ">;",
                "            bias-pull-up;",
                "            drive-open-drain;",
                "            output-high;",
                "        };",
                "    };",
                "",
            ]
        )


def emit_uart_pinctrl(lines: List[str], board_name: str, board: Dict[str, Any], used_uarts: set[str]) -> None:
    for uart_name, uart in board.get("uarts", {}).items():
        if uart_name not in used_uarts or not uart.get("enabled", False):
            continue
        label = safe_label(f"{board_name}_{uart_name}")
        instance = int(uart["instance"])
        lines.extend(
            [
                f"    {label}_default: {label}_default {{",
                "        group1 {",
                "            pinmux = <"
                + esp32_uart_symbol("tx", instance, int(uart["tx_gpio"]))
                + ">,",
                "                     <"
                + esp32_uart_symbol("rx", instance, int(uart["rx_gpio"]))
                + ">;",
                "        };",
                "    };",
                "",
            ]
        )


def emit_power(lines: List[str], board_name: str, board: Dict[str, Any], aliases: Dict[str, str]) -> None:
    power = board["experts"].get("power", {})
    ina = power.get("ina226", {})
    if not ina.get("enabled", False):
        return

    bus = board["i2c"][ina["i2c_bus"]]
    node_label = "power_sensor"
    alias = ina.get("alias", "power-sensor")
    lines.extend(
        [
            f"&{bus['node']} {{",
            "    status = \"okay\";",
            f"    clock-frequency = <{bus['clock_frequency']}>;",
            f"    pinctrl-0 = <&{safe_label(board_name + '_' + ina['i2c_bus'])}_default>;",
            "    pinctrl-names = \"default\";",
            "",
            f"    {node_label}: ina226@{str(ina['address']).replace('0x', '')} {{",
            "        compatible = \"ti,ina226\";",
            f"        reg = <{ina['address']}>;",
            f"        shunt-resistor-micro-ohms = <{int(ina['shunt_resistor_micro_ohms'])}>;",
            "    };",
            "};",
            "",
        ]
    )
    aliases[alias] = node_label


def emit_uart_nodes(lines: List[str], board_name: str, board: Dict[str, Any], used_uarts: set[str]) -> None:
    for uart_name, uart in board.get("uarts", {}).items():
        if uart_name not in used_uarts or not uart.get("enabled", False):
            continue
        label = safe_label(f"{board_name}_{uart_name}")
        lines.extend(
            [
                f"&{uart['node']} {{",
                "    status = \"okay\";",
                f"    current-speed = <{int(uart.get('baudrate', 115200))}>;",
                f"    pinctrl-0 = <&{label}_default>;",
                "    pinctrl-names = \"default\";",
                "};",
                "",
            ]
        )


def collect_used(expert: str, board: Dict[str, Any]) -> tuple[set[str], set[str]]:
    used_i2c: set[str] = set()
    used_uarts: set[str] = set()
    expert_cfg = board["experts"].get(expert, {})

    if expert == "power":
        ina = expert_cfg.get("ina226", {})
        if ina.get("enabled", False):
            used_i2c.add(ina["i2c_bus"])

    tel = expert_cfg.get("telemetry_uart", {})
    if tel.get("enabled", False):
        used_uarts.add(tel["uart"])

    return used_i2c, used_uarts


def emit_expert_aliases_and_nodes(lines: List[str], expert: str, board: Dict[str, Any], aliases: Dict[str, str]) -> None:
    expert_cfg = board["experts"].get(expert, {})

    tel = expert_cfg.get("telemetry_uart", {})
    if tel.get("enabled", False):
        uart = board["uarts"][tel["uart"]]
        aliases[tel["alias"]] = uart["node"]

    for alias, gpio in expert_cfg.get("gpios", {}).items():
        if not gpio.get("enabled", False):
            continue
        node = safe_label(alias) + "_node"
        lines.extend(
            [
                f"    {node}: {node} {{",
                f"        gpios = <&{board['gpio_controller']} {int(gpio['gpio'])} {gpio_flag(gpio.get('active', 'high'))}>;",
                "    };",
                "",
            ]
        )
        aliases[alias] = node


def generate(config_path: Path, expert: str, board_name: str | None, out_path: Path) -> None:
    selected, board = load_board(config_path, board_name)
    if board.get("mcu") != "esp32":
        raise SystemExit(f"generator currently supports esp32, got '{board.get('mcu')}'")

    used_i2c, used_uarts = collect_used(expert, board)
    aliases: Dict[str, str] = {}

    lines: List[str] = [
        "/* Generated by scripts/generate_zephyr_overlay.py. Do not edit directly. */",
        f"/* Board config: {selected}; expert: {expert}. Edit hardware_config.json. */",
        "",
        "#include <zephyr/dt-bindings/pinctrl/esp32-pinctrl.h>",
        "",
        "&pinctrl {",
    ]
    emit_sd_pinctrl(lines, selected, board)
    emit_i2c_pinctrl(lines, selected, board, used_i2c)
    emit_uart_pinctrl(lines, selected, board, used_uarts)
    lines.append("};")
    lines.append("")

    if expert == "power":
        emit_power(lines, selected, board, aliases)

    emit_sd_node(lines, selected, board)
    emit_uart_nodes(lines, selected, board, used_uarts)

    root_lines: List[str] = []
    emit_expert_aliases_and_nodes(root_lines, expert, board, aliases)
    if aliases or root_lines:
        lines.append("/ {")
        lines.extend(root_lines)
        if aliases:
            lines.append("    aliases {")
            for alias, node in sorted(aliases.items()):
                lines.append(f"        {alias} = &{node};")
            lines.append("    };")
        lines.append("};")
        lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Zephyr overlay from hardware_config.json.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--expert", required=True, choices=["power", "motor", "motor_driver", "esp32", "lighting"])
    parser.add_argument("--board", default=None)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    generate(args.config, args.expert, args.board, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
