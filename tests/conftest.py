"""Shared fixtures for Kamado Joe tests."""
import sys
import os

# Inject stubs so tests run without a real homeassistant install
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "stubs"))

import pytest
from unittest.mock import AsyncMock, MagicMock

DEVICE_ID = "34ab959a8ec2"
THING_NAME = "451402ba5392ce1796870c5fb8a245f0"

VALID_CONFIG = {
    "username": "test@example.com",
    "password": "testpassword",
    "device_id": DEVICE_ID,
    "thing_name": THING_NAME,
    "scan_interval": 30,
}

SAMPLE_REPORTED = {
    "mac": DEVICE_ID,
    "model": "C:G:018:1:D",
    "vers": "02.00.30",
    "pwrOn": True,
    "fah": True,
    "engaged": True,
    "doorOpn": False,
    "lidOpn": False,
    "mainTemp": 350,
    "heat": {
        "t2": {"heating": True, "intensity": 75, "trgt": 400, "max": 700, "min": 150},
        "t1": {"heating": False},
        "t3": {"heating": False},
        "t4": {"heating": False},
    },
    "errors": [0, 0, 0, 0, 0],
    "ssid": "TestNet",
    "RSSI": -55,
}

SAMPLE_SHADOW = {
    "state": {"reported": SAMPLE_REPORTED},
    "timestamp": 1700000000,
}
