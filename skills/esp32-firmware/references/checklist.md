# Checklist de revisión de firmware ESP32

Marca cada punto como ✅, ❌ (con la línea y la corrección) o N/A.

## Arranque y pines

- [ ] No se usan pines de arranque (strapping) de forma que cambien el modo de arranque. **ESP32**: GPIO0, 2, 5, 12, 15. **ESP32-C3**: GPIO2, 8, 9.
- [ ] En el ESP32-C3, GPIO18/19 son el USB nativo: si se usan para otra cosa, se pierde el puerto de programación y depuración por USB.
- [ ] Las entradas sin pull-up o pull-down externos lo configuran por software (`INPUT_PULLUP`).
- [ ] Las salidas que gobiernan actuadores tienen un estado seguro durante el arranque y el reinicio.

## Tareas, loop y watchdog

- [ ] Ningún bucle espera sin ceder la CPU (`delay()`, `vTaskDelay()`, `yield()`).
- [ ] Las operaciones de red, de flash y de sensores lentos tienen timeout.
- [ ] Las tareas de FreeRTOS tienen una pila dimensionada y medida con `uxTaskGetStackHighWaterMark()`.
- [ ] Los datos compartidos entre tareas se protegen con mutex o colas, no con variables globales sin más.

## Interrupciones

- [ ] Las ISR llevan `IRAM_ATTR` y las constantes que leen, `DRAM_ATTR`.
- [ ] Dentro de una ISR no hay `Serial`, `malloc`/`new`, `delay`, `printf` ni accesos a flash.
- [ ] Las variables que modifica una ISR son `volatile`, y la comunicación con tareas usa `xQueueSendFromISR` o similares.

## Memoria

- [ ] No hay arrays grandes como variables locales en tareas o callbacks.
- [ ] Se evita `String` concatenado en bucles: se prefieren buffers fijos y `snprintf`.
- [ ] Se comprueba el valor de retorno de cada `malloc` y de cada función de ESP-IDF (`esp_err_t`).
- [ ] Ningún puntero sobrevive al buffer al que apunta (por ejemplo, datos de un callback de BLE).

## ADC y sensores

- [ ] Se usa **ADC1**. ADC2 no está disponible con Wi-Fi activo en el ESP32 y tiene limitaciones en el ESP32-C3.
- [ ] Se configura la atenuación según el rango de tensión y se usa la calibración del ADC (`esp_adc_cal` o `adc_cali` en IDF 5).
- [ ] Las lecturas ruidosas se filtran (media móvil o mediana) y se documenta la latencia que añade el filtro.

## Bajo consumo

- [ ] Antes de dormir, se apagan los periféricos y se dejan los pines en un estado definido.
- [ ] Los datos que deben sobrevivir al deep sleep van en `RTC_DATA_ATTR`.
- [ ] En el ESP32-C3, el despertar por GPIO desde deep sleep usa solo los pines con esa capacidad (GPIO0-5).
- [ ] Se ha medido el consumo real, no solo calculado.

## Alimentación

- [ ] Hay desacoplo cerca del módulo: condensador electrolítico o de tántalo (100-470 µF) más uno cerámico de 100 nF.
- [ ] El regulador soporta los picos de transmisión de radio con margen.
- [ ] El detector de brownout está **activado**.

## BLE y Wi-Fi

- [ ] Se gestiona la desconexión y la reconexión (el cliente puede desaparecer en cualquier momento).
- [ ] Los callbacks de BLE no bloquean: copian los datos y delegan el trabajo en una tarea.
- [ ] Las credenciales no están en el código fuente que se sube al repositorio.
