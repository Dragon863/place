#include <ESP32-HUB75-MatrixPanel-I2S-DMA.h>

#define PANEL_RES_X 64
#define PANEL_RES_Y 64
#define PANEL_CHAIN 1

#define START_MARKER 0xFF

MatrixPanel_I2S_DMA *dma_display = nullptr;

void setup()
{
    Serial.begin(115200);

    HUB75_I2S_CFG mxconfig(PANEL_RES_X, PANEL_RES_Y, PANEL_CHAIN);
    mxconfig.gpio.e = 18;

    dma_display = new MatrixPanel_I2S_DMA(mxconfig);
    dma_display->begin();
    dma_display->setBrightness8(60);
    dma_display->clearScreen();
}

void loop()
{
    // Buffer for incoming data (I chose to go with: start marker, x, y, r, g, b, checksum)
    uint8_t buffer[7];

    while (Serial.available() >= 7)
    {
        Serial.readBytes(buffer, 7);

        // Check for start marker (ensures we are in sync) - if not, discard the packet
        if (buffer[0] == START_MARKER)
        {
            uint8_t x = buffer[1];
            uint8_t y = buffer[2];
            uint8_t r = buffer[3];
            uint8_t g = buffer[4];
            uint8_t b = buffer[5];
            uint8_t checksum = buffer[6];

            // Calculate expected checksum - this is actually justt a simple XOR of all bytes
            uint8_t expected_checksum = buffer[1] ^ buffer[2] ^ buffer[3] ^ buffer[4] ^ buffer[5];

            if (checksum == expected_checksum)
            {
                if (x == 244)
                {
                    dma_display->clearScreen();
                }
                else
                {
                    // Packet is valid, process the pixel!
                    uint16_t color = dma_display->color565(r, g, b);
                    dma_display->drawPixel(x, y, color);
                }
            }
            // If the checksum is wrong, ignore the packet and wait for the next start marker because something went horribly wrong
        }
    }
}
