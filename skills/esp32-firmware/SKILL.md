---
name: esp32-firmware
description: Escribe, revisa y depura firmware para ESP32 y ESP32-C3 (Arduino o ESP-IDF, PlatformIO). Úsala cuando el usuario trabaje con un ESP32, pegue la salida del monitor serie, tenga reinicios, "Guru Meditation", brownout, watchdog, stack overflow o problemas de BLE, Wi-Fi, ADC, interrupciones o bajo consumo, o pida revisar su código de microcontrolador.
---

# Firmware ESP32 / ESP32-C3

## Si hay un fallo o reinicios: analiza el log primero

1. Pide la salida **completa** del monitor serie desde el arranque (115200 baudios por defecto). No basta con la última línea.
2. Guárdala en un archivo y ejecuta:

   ```bash
   python3 scripts/analizar_log.py serial.log
   ```

   Detecta el motivo de cada reinicio, bucles de reinicio, brownout, pánicos (Xtensa y RISC-V), watchdogs, desbordamientos de pila, abort/assert y heap corrupto, y prepara el comando `addr2line`. Código de salida 1 = hay un fallo crítico.
3. **Corrige el primer fallo del log.** Los siguientes suelen ser consecuencia de ese.
4. Si hay backtrace, pide al usuario que ejecute el `addr2line` sugerido con su `.elf` (en PlatformIO: `.pio/build/<entorno>/firmware.elf`) **antes** de proponer un cambio. Sin la línea exacta, cualquier corrección es una suposición.
5. Para brownouts, mira el hardware antes que el código.

## Si escribe o revisa código

Aplica la checklist de [references/checklist.md](references/checklist.md). Lo que más falla, en este orden:

1. **Bloquear el loop o una tarea** (esperas activas, `delay` largos en sitios críticos, lecturas sin timeout) → watchdog.
2. **ISR mal hechas**: sin `IRAM_ATTR`, con `Serial.print`, `malloc` o `delay` dentro. Una ISR solo marca un flag o envía a una cola con las funciones `FromISR`.
3. **Memoria**: arrays grandes en la pila de una tarea, `String` concatenado en bucle (fragmenta el heap) o punteros a buffers ya liberados.
4. **Pines**: pines de arranque (strapping) usados como entradas o salidas que bloquean el arranque, o ADC2 en uso.
5. **Alimentación**: picos de Wi-Fi y BLE sin condensadores de desacoplo.

## Estilo de las respuestas

- Indica el chip (ESP32, S3 o C3: cambian los pines, la arquitectura y la toolchain) y el framework antes de dar código.
- Da código completo y compilable para el fragmento que cambias, con los `#include` necesarios.
- Para dispositivos médicos o de seguridad: avisa de que los cambios en alarmas o en umbrales necesitan verificación y documentación.
