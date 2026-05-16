#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from gpiozero import CPUTemperature

cpu = CPUTemperature()
print(f"CPU温度: {cpu.temperature:.2f} °C")
