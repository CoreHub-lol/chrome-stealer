# 🎮 CoreHub.lol – XScripting Executor Template

Welcome to the **XScripting Executor Template**, a powerful component of the **CoreHub.lol** ecosystem.  
This Python-based template simulates a Roblox script executor and serves as a flexible foundation for educational purposes, security research, or experimental UI and data handling projects.

> ⚠️ **Disclaimer:** This tool is intended **for educational and ethical research purposes only**. Any misuse for malicious or illegal activity is strictly prohibited and may result in legal consequences.

---

## 🚀 Features

- **📡 System Information Collection**  
  - Hostname  
  - Public IP address  
  - Geolocation (via IP-API or Google Maps API)  
  - Current username  

- **🔐 Chrome Data Extraction (Windows only)**  
  - Stored passwords  
  - Autofill data (addresses, phone numbers)

- **📬 Discord Webhook Integration**  
  - Automatically sends collected data to a configurable Discord webhook  
  - Well-structured messages with timestamps and formatting

- **🖥️ Realistic Fake UI**  
  - Simulates a Roblox script executor with an interactive Tkinter-based interface  
  - Ideal for testing, user interaction studies, or UI experiments

---

## ⚙️ Requirements

- **Operating System**: Windows (required for Chrome data and WiFi scanning)
- **Python Version**: 3.8 or higher
- **Required Libraries**:
  ```bash
  pip install pywin32 cryptography pillow
  ```
