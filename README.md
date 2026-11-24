<div align="center">

# 🔌 esp32-firmware-skill

**Skill para que tu agente de IA escriba, revise y depure firmware ESP32 / ESP32-C3 como un ingeniero de sistemas embebidos.**
Incluye un analizador de logs serie que convierte un `Guru Meditation` en una explicación y un plan de acción.

![tests](https://github.com/raulhernandezherce/esp32-firmware-skill/actions/workflows/tests.yml/badge.svg)
![Claude Code plugin](https://img.shields.io/badge/Claude_Code-plugin-D97757)
![ESP32](https://img.shields.io/badge/ESP32%20·%20C3-E7352C?logo=espressif&logoColor=white)
![dependencias](https://img.shields.io/badge/dependencias-0-39FF88)

</div>

---

## El problema

Cuando un ESP32 se reinicia, el monitor serie escupe registros, direcciones y códigos como `rst:0x7 (TG0WDT_SYS_RST)`. Un asistente de IA suele leer la última línea y adivinar. Esta skill le da **un método y una herramienta**: analizar el log completo, corregir el *primer* fallo y no proponer cambios sin decodificar antes el backtrace.

## Instalación (Claude Code)

```
/plugin marketplace add raulhernandezherce/esp32-firmware-skill
```

```
/plugin install esp32-firmware@esp32-firmware-skill
```

También funciona con otros agentes compatibles con Agent Skills: copia `skills/esp32-firmware` en su carpeta de skills.

## El analizador de logs

```bash
python3 skills/esp32-firmware/scripts/analizar_log.py serial.log
```

Ejemplo con un ESP32-C3 en bucle de reinicio ([log](tests/logs/c3_watchdog_bucle.log)):

```
🔴 stack_overflow    Desbordamiento de pila en la tarea «sensorTask».
🔴 panico            Store access fault: escritura en una dirección no válida (RISC-V)…
🟠 task_watchdog     Una tarea no cedió la CPU (IDLE (CPU 0)).
🟠 reinicio_watchdog TG0WDT_SYS_RST (2 veces)
🟠 bucle_reinicio    3 reinicios no provocados por el usuario.

riscv32-esp-elf-addr2line -pfiaC -e build/firmware.elf 0x42001c3e 0x42001c36
```

| Detecta | Detalle |
|---|---|
| Motivo de cada reinicio | Encendido, software, watchdog, brownout, deep sleep, USB, externo |
| Bucles de reinicio | 3 o más reinicios no provocados por el usuario |
| Pánicos | Xtensa (`LoadProhibited`, `StoreProhibited`…) y RISC-V (`Load/Store access fault`…), con su causa típica |
| Watchdogs | Task WDT (con las tareas implicadas) e interrupt WDT |
| Memoria | Stack overflow, heap corrupto, `abort()` y `assert` |
| Backtrace | Extrae las direcciones y prepara `addr2line` con la toolchain correcta (Xtensa o RISC-V) |

Con `--json` devuelve el resultado estructurado. El código de salida es 1 si hay un fallo crítico, para usarlo en scripts o en CI de hardware-in-the-loop.

## La skill

[`SKILL.md`](skills/esp32-firmware/SKILL.md) define cómo debe trabajar el agente, y [`checklist.md`](skills/esp32-firmware/references/checklist.md) reúne los puntos de revisión que más fallan en la práctica:

- **Pines de arranque** del ESP32 (0, 2, 5, 12, 15) y del C3 (2, 8, 9) y el USB nativo del C3.
- **ISR**: `IRAM_ATTR`, nada de `Serial`, `malloc` ni `delay` dentro.
- **Watchdog**: bucles que no ceden la CPU y operaciones sin timeout.
- **Memoria**: pila de las tareas, `String` en bucles, punteros colgantes en callbacks de BLE.
- **ADC**: usa ADC1, con atenuación y calibración.
- **Bajo consumo y alimentación**: `RTC_DATA_ATTR`, pines de despertar del C3 y desacoplo para los picos de radio.


## Desarrollo

```bash
python3 -m unittest discover -s tests -v
```

---

<sub>Hecho por <a href="https://github.com/raulhernandezherce">Raúl Hernández Herce</a> · Licencia MIT</sub>
