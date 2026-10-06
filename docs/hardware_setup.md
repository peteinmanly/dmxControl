# Linux Mint & Enttec Open DMX USB Hardware Guide

This document details hardware setup, USB serial permissions, udev rules, latency timer tuning, and conflict resolution on **Linux Mint** (Mint 21 & 22) and Debian-based systems.

## 1. Hardware Architecture: Enttec Open DMX USB
The Enttec Open DMX USB interface uses an FTDI FT232R/BM USB-to-UART chip connected to an RS485 differential transceiver. 

Unlike the microcontroller-based *DMX USB Pro*, the Open DMX USB interface relies on host CPU timing to generate the DMX512 frame:
- **Break**: Line held in continuous low state for $\ge 88\,\mu\text{s}$ (our driver uses $100\,\mu\text{s}$).
- **Mark After Break (MAB)**: Line held high for $\ge 8\,\mu\text{s}$ (our driver uses $12\,\mu\text{s}$).
- **Baudrate**: 250,000 baud, 8 data bits, 2 stop bits, no parity (8N2).
- **Start Code**: Byte `0x00` preceding the 512 channel values.

## 2. Linux Mint Serial Permissions (`dialout`)
By default, serial device nodes in Linux Mint (`/dev/ttyUSB0`) belong to the `root:dialout` group. Non-root users will receive `PermissionError: [Errno 13] Permission denied`.

To grant persistent access:
```bash
sudo usermod -a -G dialout $USER
```
To apply group membership immediately in the current shell:
```bash
newgrp dialout
```

## 3. Persistent Udev Device Rules
Deploy the rule to create consistent read/write permissions for FTDI devices:
```bash
sudo cp udev/99-ftdi.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
```

## 4. Latency Timer Tuning (Eliminating Frame Jitter)
The Linux `ftdi_sio` kernel module defaults to a 16ms latency buffer. For real-time 40 Hz DMX frame transmission, this can introduce frame timing jitter.

To check your current latency timer:
```bash
cat /sys/bus/usb-serial/devices/ttyUSB0/latency_timer
```
To reduce it to 1ms:
```bash
echo 1 | sudo tee /sys/bus/usb-serial/devices/ttyUSB0/latency_timer
```

## 5. Resolving Conflicting Daemons (`brltty`)
In Linux Mint and Ubuntu, the Braille Terminal daemon (`brltty`) aggressively claims FTDI USB chips when plugged in, locking `/dev/ttyUSB0` or disconnecting it from the system.

If you encounter `Device or resource busy` or the device node disappears:
```bash
sudo systemctl stop brltty
sudo systemctl mask brltty
```
