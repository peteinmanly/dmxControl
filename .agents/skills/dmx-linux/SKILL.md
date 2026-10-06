---
name: dmx-linux
description: >-
  Hardware diagnostics, USB permissions, and troubleshooting for the ENTTEC Open DMX USB interface on Linux Mint / Debian.
---

# Linux DMX Hardware Diagnostic & Fix Skill

Use this skill when running the DMX Web Controller on the Linux Mint lighting laptop.

## Quick Hardware Checks

1. **Verify USB Device Detection**:
   ```bash
   lsusb | grep -i ftdi
   dmesg | grep -i ttyusb
   ```
   Expected: FTDI FT232R USB-to-Serial converter attached to `ttyUSB0`.

2. **Verify User Group Permissions**:
   ```bash
   groups $USER
   ```
   If `dialout` is missing:
   ```bash
   sudo usermod -a -G dialout $USER
   newgrp dialout
   ```

3. **Check for `brltty` Conflict (Most common Linux Mint issue)**:
   ```bash
   systemctl is-active brltty
   ```
   If active:
   ```bash
   sudo systemctl stop brltty
   sudo systemctl mask brltty
   ```

4. **Verify Latency Timer**:
   ```bash
   cat /sys/bus/usb-serial/devices/ttyUSB0/latency_timer
   ```
   If higher than 1:
   ```bash
   echo 1 | sudo tee /sys/bus/usb-serial/devices/ttyUSB0/latency_timer
   ```

5. **Start or Test the Controller**:
   ```bash
   ./run.sh
   ```
