"""CLI helpers for controller scripts."""
from __future__ import annotations

import argparse


def add_chain_cli(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--chain",
        "-c",
        required=True,
        metavar="NAME",
        help="Chain name from chains.yaml (chains.<NAME>)",
    )
