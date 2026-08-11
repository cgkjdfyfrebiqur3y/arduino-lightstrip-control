const int LIGHTSTRIP_0_PIN = 2;
const int LIGHTSTRIP_1_PIN = 3;

String inputBuffer;

void setup() {
  pinMode(LIGHTSTRIP_0_PIN, OUTPUT);
  pinMode(LIGHTSTRIP_1_PIN, OUTPUT);

  // USB serial
  Serial.begin(115200);

  // Hardware UART1
  // RX1 = D19
  // TX1 = D18
  Serial1.begin(115200);

  Serial.println("Lightstrip controller ready");
}

void loop() {

  while (Serial1.available()) {

    char c = Serial1.read();

    // Command complete
    if (c == '\n' || c == '\r') {

      if (inputBuffer.length() > 0) {

        Serial.print("UART1 received: ");
        Serial.println(inputBuffer);

        processCommand(inputBuffer);

        inputBuffer = "";
      }

    } else {

      inputBuffer += c;
    }
  }
}

void processCommand(String command) {

  command.trim();

  int separator = command.indexOf(' ');

  if (separator == -1) {
    Serial.println("Invalid command: missing space");
    return;
  }

  int lightstripNo =
    command.substring(0, separator).toInt();

  int state =
    command.substring(separator + 1).toInt();


  // Validate
  if (
    (lightstripNo != 0 && lightstripNo != 1) ||
    (state != 0 && state != 1)
  ) {

    Serial.println("Invalid command");
    return;
  }


  int pin;

  if (lightstripNo == 0) {
    pin = LIGHTSTRIP_0_PIN;
  } else {
    pin = LIGHTSTRIP_1_PIN;
  }


  digitalWrite(pin, state ? HIGH : LOW);


  Serial.print("Lightstrip ");
  Serial.print(lightstripNo);
  Serial.print(" -> ");
  Serial.println(state ? "ON" : "OFF");
}