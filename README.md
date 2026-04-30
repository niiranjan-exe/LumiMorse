<div align="center">

```
██╗      ██╗   ██╗███╗   ███╗██╗    ███╗   ███╗ ██████╗ ██████╗ ███████╗███████╗
██║      ██║   ██║████╗ ████║██║    ████╗ ████║██╔═══██╗██╔══██╗██╔════╝██╔════╝
██║      ██║   ██║██╔████╔██║██║    ██╔████╔██║██║   ██║██████╔╝███████╗█████╗  
██║      ██║   ██║██║╚██╔╝██║██║    ██║╚██╔╝██║██║   ██║██╔══██╗╚════██║██╔══╝  
███████╗ ╚██████╔╝██║ ╚═╝ ██║██║    ██║ ╚═╝ ██║╚██████╔╝██║  ██║███████║███████╗
╚══════╝  ╚═════╝ ╚═╝     ╚═╝╚═╝    ╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝
```

**LumiMorse — Where light speaks in code.**

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python)](https://www.python.org/)
[![Arduino](https://img.shields.io/badge/Arduino-Compatible-teal?style=flat-square&logo=arduino)](https://www.arduino.cc/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Author](https://img.shields.io/badge/Author-Niiranjan%20P-orange?style=flat-square&logo=github)](https://github.com/niiranjan-exe)

</div>

---

## 📡 What is LumiMorse?

**LumiMorse** is an Arduino-based optical communication system that transmits text as **Morse code via a laser beam** and decodes it on the receiving end using an **LDR (Light Dependent Resistor) sensor**. The decoded message is displayed in real time through a sleek, dark-themed Python GUI built on `customtkinter`.

It's a full end-to-end wireless communication pipeline — entirely using light.

```
[ PC / GUI ]  ──── Serial ────  [ Arduino TX ]  ──── Laser ────  [ Arduino RX ]  ──── Serial ────  [ PC / GUI ]
  Type msg                        Blinks laser                      LDR detects                       Displays text
```

---

## ✨ Features

### 🖥️ Python GUI (`laser_morse_hud.py`)
- **TX Mode** — Type a message and transmit it as Morse code over laser
- **RX Mode** — Listens on serial and displays decoded characters in real time
- **Calibration Mode** — Live LDR bar chart to align your laser and potentiometer
- **Morse Visualiser** — Animated dot/dash blocks rendered per character
- **Oscilloscope Panel** — Live animated signal waveform per mode (TX / RX / CAL)
- **HexRain Sidebar** — Scrolling matrix-style hex background animation
- **Live Morse Preview** — Real-time Morse preview while composing a TX message
- **Session Stats** — Tracks TX chars, RX chars, errors, and messages sent
- **Live Clock** — Real-time clock and date in the sidebar
- **Export** — Save the system log or received message as `.txt` files
- **API Key Auth** — Connection gated behind an API key

### ⚡ Arduino Firmware (`Secure_Beam_NAP__1_.ino`)
- Morse encode and decode tables (A–Z, 0–9)
- Laser TX with buzzer + LED feedback per symbol
- Non-blocking LDR receive loop with timing-based dot/dash detection
- LDR calibration routine with live serial output
- Serial command protocol (`TX`, `RX`, `CAL`)

---

## 🔌 Hardware Requirements

| Component | Quantity | Notes |
|-----------|----------|-------|
| Arduino Uno / Nano | 2 | One for TX, one for RX |
| Laser Module (5V) | 1 | KY-008 or equivalent |
| LDR Sensor | 1 | With 10kΩ pull-down resistor |
| LED (any colour) | 1 | Status indicator |
| Buzzer (active) | 1 | Audio feedback |
| Potentiometer | 1 | For LDR threshold tuning |
| Jumper Wires | — | As needed |
| USB Cables | 2 | One per Arduino |

---

## 📌 Arduino Pin Configuration

```cpp
#define LASER_PIN   9    // Laser module output
#define LDR_PIN     2    // LDR digital input
#define LED_PIN     13   // Status LED
#define BUZZER_PIN  3    // Buzzer output
```

---

## ⏱️ Morse Timing

| Symbol | Duration |
|--------|----------|
| DOT | 250 ms |
| DASH | 750 ms (DOT × 3) |
| Inter-symbol gap | 250 ms |
| Letter gap | 750 ms (DOT × 3) |
| Word gap | 1750 ms (DOT × 7) |

---

## 📟 Serial Protocol

The Python GUI communicates with the Arduino over serial using plain text commands:

| GUI → Arduino | Description |
|---------------|-------------|
| `TX <message>\n` | Transmit full message as Morse via laser |
| `RX\n` | Enter receive mode, listen on LDR |
| `CAL\n` | Run LDR calibration (40 readings × 200ms) |

| Arduino → GUI | Description |
|---------------|-------------|
| `LASER LINK READY` | Boot handshake |
| `RX MODE` | Confirmed receive mode |
| `[TX] Sending...` | TX started |
| `[TX] Done` | TX complete |
| `CAL MODE - Adjust Pot` | Calibration started |
| `CAL DONE` | Calibration finished |
| `0` / `1` | Raw LDR readings during CAL |
| `<char>` / `<word>` | Decoded Morse output during RX |

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/niiranjan-exe/lumi-morse.git
cd lumi-morse
```

### 2. Install Python Dependencies

```bash
pip install customtkinter pyserial
```

> Requires **Python 3.8+**

### 3. Flash the Arduino

1. Open `Secure_Beam_NAP__1_.ino` in the Arduino IDE
2. Select your board (Uno / Nano) and the correct COM port
3. Upload the sketch to **both** Arduinos (TX side and RX side)

### 4. Wire the Hardware

**TX Arduino:**
- Pin 9 → Laser module signal pin
- Pin 13 → LED (with resistor)
- Pin 3 → Buzzer

**RX Arduino:**
- Pin 2 → LDR output (via voltage divider / potentiometer)
- Pin 13 → LED (with resistor)
- Pin 3 → Buzzer

### 5. Run the GUI

```bash
python laser_morse_hud.py
```

---

## 🖱️ How to Use

1. **Launch** the GUI — it will auto-detect available COM ports
2. **Enter the API Key** in the sidebar field
3. **Select the COM port** of your Arduino and click **CONNECT**
4. Wait for the `LASER LINK READY` handshake in the log
5. **TX Mode** → Click `TX MODE` or `SEND MESSAGE`, type your message, press `TRANSMIT` or `Ctrl+Enter`
6. **RX Mode** → Click `RX MODE` or `START RX`, point the laser at the LDR and watch the message appear
7. **Calibrate** → Click `CALIBRATE`, adjust the potentiometer until the LDR bar shows clean `0/1` transitions

---

## 📂 Project Structure

```
lumi-morse/
│
├── laser_morse_hud.py          # Python GUI (customtkinter)
├── Secure_Beam_NAP__1_.ino     # Arduino firmware (TX + RX + CAL)
└── README.md
```

---

## 🎨 GUI Modes & Colour Themes

| Mode | Accent Colour | Description |
|------|--------------|-------------|
| IDLE | Sky Blue | System waiting, no active operation |
| TX | Orange | Transmitting laser Morse code |
| RX | Cyan | Receiving and decoding laser pulses |
| CAL | Purple | LDR calibration with live bar chart |

---

## 🛠️ Built With

| Technology | Purpose |
|------------|---------|
| `customtkinter` | Modern dark-themed GUI framework |
| `pyserial` | Arduino serial communication |
| `tkinter` | Canvas animations (oscilloscope, morse bar, hex rain) |
| `threading` | Non-blocking serial read + TX animation |
| `Arduino C++` | Morse encode/decode, laser control, LDR detection |

---

## 📸 Screenshots

> *(Add your screenshots here)*

---

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you'd like to change.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).

---

## 👤 Author

**Niiranjan P**

[![GitHub](https://img.shields.io/badge/GitHub-niiranjan--exe-181717?style=flat-square&logo=github)](https://github.com/niiranjan-exe)

---

<div align="center">

*Built with 💡 light, ⚡ electricity, and a love for old-school communication.*

</div>
