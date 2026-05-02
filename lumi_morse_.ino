// ================= PIN CONFIG =================
#define LASER_PIN 9
#define LDR_PIN 2
#define LED_PIN 13
#define BUZZER_PIN 3

// ================= MORSE TIMING =================
const int DOT = 250;
const int DASH = DOT * 3;
const int LETTER_GAP = DOT * 3;
const int WORD_GAP = DOT * 7;

// ================= STATE =================
bool receiving = false;
bool prevState;
unsigned long lastChange;
unsigned long lastActivity;
String morseBuffer = "";

// ================= MORSE TABLE =================
char decodeMorse(String s) {
  const char* chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  const char* codes[] = {
    ".-","-...","-.-.","-..",".","..-.","--.","....","..",
    ".---","-.-",".-..","--","-.","---",".--.","--.-",".-.","...","-",
    "..-","...-",".--","-..-","-.--","--..",
    "-----",".----","..---","...--","....-",".....","-....","--...","---..","----."
  };
  for (int i = 0; i < 36; i++) if (s == codes[i]) return chars[i];
  return '?';
}

String encodeMorse(char c) {
  c = toupper(c);
  const char* chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  const char* codes[] = {
    ".-","-...","-.-.","-..",".","..-.","--.","....","..",
    ".---","-.-",".-..","--","-.","---",".--.","--.-",".-.","...","-",
    "..-","...-",".--","-..-","-.--","--..",
    "-----",".----","..---","...--","....-",".....","-....","--...","---..","----."
  };
  for (int i = 0; i < 36; i++) if (c == chars[i]) return codes[i];
  return "";
}

// ================= SEND DOT/DASH =================
void sendPulse(int duration) {

  digitalWrite(LASER_PIN, HIGH);
  digitalWrite(LED_PIN, HIGH);
  tone(BUZZER_PIN, 1200);

  delay(duration);

  digitalWrite(LASER_PIN, LOW);
  digitalWrite(LED_PIN, LOW);
  noTone(BUZZER_PIN);

  delay(DOT);
}

// ================= TRANSMIT =================
void transmitMessage(String msg) {

  receiving = false;

  Serial.println("[TX] Sending...");
  msg.toUpperCase();

  for (int i = 0; i < msg.length(); i++) {

    char c = msg[i];

    if (c == ' ') {
      delay(WORD_GAP);
      continue;
    }

    String code = encodeMorse(c);

    for (int j = 0; j < code.length(); j++) {

      if (code[j] == '.') sendPulse(DOT);
      else sendPulse(DASH);
    }

    delay(LETTER_GAP);
  }

  Serial.println("[TX] Done");
}

// ================= RECEIVE LOOP (NON BLOCKING) =================
void receiveLoop() {

  bool state = digitalRead(LDR_PIN);   // LOW = Laser detected
  unsigned long now = millis();
  unsigned long duration = now - lastChange;

  digitalWrite(LED_PIN, state == LOW);
  if(state == LOW) tone(BUZZER_PIN, 1000);
  else noTone(BUZZER_PIN);

  if (state != prevState) {

    lastChange = now;
    lastActivity = now;

    // Laser OFF → pulse ended
    if (state == HIGH) {

      if (duration < DOT * 2) morseBuffer += ".";
      else morseBuffer += "-";
    }

    // Laser ON → gap ended
    else {

      if (duration > WORD_GAP) {

        if (morseBuffer.length()) {
          Serial.print(decodeMorse(morseBuffer));
          morseBuffer = "";
        }
        Serial.print(" ");
      }

      else if (duration > LETTER_GAP) {

        if (morseBuffer.length()) {
          Serial.print(decodeMorse(morseBuffer));
          morseBuffer = "";
        }
      }
    }

    prevState = state;
  }

  // idle decode
  if (state == HIGH && morseBuffer.length() &&
      (millis() - lastActivity) > WORD_GAP) {

    Serial.print(decodeMorse(morseBuffer));
    morseBuffer = "";
    lastActivity = millis();
  }
}

// ================= CALIBRATION =================
void calibrate() {

  Serial.println("CAL MODE - Adjust Pot");

  for(int i=0;i<40;i++){
    Serial.println(digitalRead(LDR_PIN));
    delay(200);
  }

  Serial.println("CAL DONE");
}

// ================= SETUP =================
void setup() {

  pinMode(LASER_PIN, OUTPUT);
  pinMode(LDR_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  digitalWrite(LASER_PIN, LOW);

  Serial.begin(9600);

  prevState = digitalRead(LDR_PIN);
  lastChange = millis();
  lastActivity = millis();

  Serial.println("LASER LINK READY");
}

// ================= MAIN LOOP =================
void loop() {

  if (Serial.available()) {

    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd == "RX") {
      receiving = true;
      Serial.println("RX MODE");
    }

    else if (cmd.startsWith("TX ")) {
      transmitMessage(cmd.substring(3));
    }

    else if (cmd == "CAL") {
      calibrate();
    }
  }

  if (receiving) {
    receiveLoop();
  }
}