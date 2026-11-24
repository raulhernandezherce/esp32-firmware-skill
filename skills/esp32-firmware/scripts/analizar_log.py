#!/usr/bin/env python3
"""Analiza la salida del monitor serie de un ESP32 / ESP32-C3 y explica qué ha pasado.

    python3 analizar_log.py serial.log            # informe en Markdown
    python3 analizar_log.py serial.log --json     # para herramientas o agentes
    pio device monitor | tee serial.log           # una forma de capturarlo

Detecta: motivo de cada reinicio, bucles de reinicio, brownout, Guru Meditation (Xtensa y
RISC-V), watchdogs, desbordamiento de pila, abort/assert, heap corrupto, y prepara el comando
addr2line para decodificar el backtrace. Sin dependencias.
"""
import json
import re
import sys
from pathlib import Path

PANICOS = {
    "LoadProhibited": "Lectura de una dirección no válida: casi siempre un puntero NULL o liberado.",
    "StoreProhibited": "Escritura en una dirección no válida: puntero NULL, liberado o fuera de un array.",
    "InstrFetchProhibited": "Salto a una dirección no válida: puntero a función corrupto o pila dañada.",
    "IllegalInstruction": "Instrucción inválida: pila corrupta o salto a datos.",
    "Illegal instruction": "Instrucción inválida: pila corrupta o salto a datos.",
    "IntegerDivideByZero": "División entera entre cero.",
    "LoadStoreAlignment": "Acceso desalineado a memoria (p. ej. un cast de uint8_t* a uint32_t*).",
    "Load access fault": "Lectura de una dirección no válida (RISC-V): puntero NULL o liberado.",
    "Store access fault": "Escritura en una dirección no válida (RISC-V): puntero NULL, liberado o fuera de rango.",
    "Instruction access fault": "Salto a una dirección no válida (RISC-V): puntero a función corrupto.",
    "Cache disabled but cached memory region accessed":
        "Una interrupción usó código o datos en flash mientras la caché estaba desactivada: "
        "marca la ISR con IRAM_ATTR y sus constantes con DRAM_ATTR.",
    "Interrupt wdt timeout": "Una interrupción o sección crítica tardó demasiado: acorta la ISR.",
    "Unhandled debug exception": "Excepción de depuración: suele ser un desbordamiento de pila detectado.",
}


def motivo_reinicio(nombre):
    n = nombre.upper()
    if "BROWN" in n:
        return "brownout", "Caída de tensión: la alimentación no aguanta los picos de consumo."
    if "WDT" in n:
        return "watchdog", "Reinicio por watchdog: algo bloqueó la CPU demasiado tiempo."
    if "DEEPSLEEP" in n or "DSLEEP" in n:
        return "deep_sleep", "Despertar de deep sleep (normal si el firmware duerme)."
    if "POWERON" in n:
        return "encendido", "Encendido normal."
    if "SW" in n:
        return "software", "Reinicio por software: esp_restart() o tras un pánico."
    if "USB" in n:
        return "usb", "Reinicio por USB (p. ej. al abrir el monitor o al programar)."
    if "EXT" in n or "CHIP_RESET" in n:
        return "externo", "Reinicio externo: botón EN/RST o señal de reset."
    return "otro", "Motivo no clasificado: consulta la tabla de reset reasons de tu chip."


def analizar(texto):
    lineas = texto.splitlines()
    hallazgos, reinicios, direcciones = [], [], []
    arquitectura = None

    def hallazgo(tipo, gravedad, linea, explicacion, pasos):
        hallazgos.append({"tipo": tipo, "gravedad": gravedad, "linea": linea,
                          "explicacion": explicacion, "siguientes_pasos": pasos})

    for i, l in enumerate(lineas, 1):
        m = re.search(r"rst:0x([0-9a-fA-F]+) \(([A-Z0-9_]+)\)", l)
        if m:
            clase, expl = motivo_reinicio(m.group(2))
            reinicios.append({"linea": i, "codigo": "0x" + m.group(1), "nombre": m.group(2), "clase": clase})
        if "Brownout detector was triggered" in l:
            hallazgo("brownout", "alta", i, "El detector de brownout ha saltado: la tensión cayó por debajo del umbral.", [
                "Mide la tensión de 3,3 V con osciloscopio durante el arranque del Wi-Fi o del BLE (picos de cientos de mA).",
                "Pon un condensador de 100-470 µF cerca del módulo y otro cerámico de 100 nF.",
                "Revisa el regulador (corriente máxima y caída) y el cable USB.",
                "No desactives el detector de brownout como «solución»: oculta el problema."])
        m = re.search(r"Guru Meditation Error: Core\s+(\d+) panic'ed \(([^)]+)\)", l)
        if m:
            tipo = m.group(2).strip()
            expl = next((v for k, v in PANICOS.items() if tipo.startswith(k)), "Pánico de la CPU.")
            hallazgo("panico", "critica", i, f"Pánico en el núcleo {m.group(1)} ({tipo}). {expl}", [
                "Decodifica el backtrace con el comando addr2line de abajo para ver la función y la línea.",
                "Si la dirección de fallo (EXCVADDR / MTVAL) es 0x0 o muy baja, es un puntero NULL."])
        if re.search(r"task_wdt: Task watchdog got triggered", l):
            tareas = [re.sub(r".*task_wdt:\s+-\s+", "", x).strip()
                      for x in lineas[i:i + 6] if re.search(r"task_wdt:\s+-\s+\S", x)]
            hallazgo("task_watchdog", "alta", i,
                     "El task watchdog ha saltado: una tarea no cedió la CPU" +
                     (f" ({', '.join(tareas)})." if tareas else "."), [
                         "Busca bucles sin delay()/vTaskDelay() o esperas activas (while sin ceder).",
                         "Mueve las operaciones largas (Wi-Fi, flash, cálculos) a su propia tarea.",
                         "Si IDLE aparece en la lista, otra tarea de más prioridad acapara ese núcleo."])
        m = re.search(r"stack overflow in task (\S+)", l, re.I)
        if m:
            hallazgo("stack_overflow", "critica", i, f"Desbordamiento de pila en la tarea «{m.group(1)}».", [
                "Aumenta la pila en xTaskCreate() y mide el margen con uxTaskGetStackHighWaterMark().",
                "Evita arrays grandes en variables locales: hazlos static o pídelos al heap."])
        m = re.search(r"abort\(\) was called at PC (0x[0-9a-fA-F]+)", l)
        if m:
            hallazgo("abort", "critica", i, f"abort() llamado en PC {m.group(1)}.", [
                "Mira las líneas anteriores: suele haber un ESP_ERROR_CHECK o un assert fallido con el motivo."])
        if re.search(r"assert(ion)? failed", l, re.I):
            hallazgo("assert", "critica", i, f"Aserción fallida: {l.strip()[:160]}", [])
        if "CORRUPT HEAP" in l:
            hallazgo("heap_corrupto", "critica", i, "Heap corrupto: escritura fuera de un bloque de memoria dinámica o doble free.", [
                "Activa el heap poisoning completo (CONFIG_HEAP_POISONING_COMPREHENSIVE) para localizarlo."])
        if l.strip().startswith("Backtrace:"):
            arquitectura = arquitectura or "xtensa"
            direcciones += re.findall(r"(0x[0-9a-fA-F]{8}):0x[0-9a-fA-F]{8}", l)
        for reg in ("MEPC", "RA"):
            m = re.search(rf"\b{reg}\s*:\s*(0x[0-9a-fA-F]{{8}})", l)
            if m:
                arquitectura = "riscv"
                direcciones.append(m.group(1))

    for clase in ("brownout", "watchdog"):
        rs = [r for r in reinicios if r["clase"] == clase]
        if rs:
            veces = f" ({len(rs)} veces)" if len(rs) > 1 else ""
            hallazgo(f"reinicio_{clase}", "alta", rs[0]["linea"],
                     f"{rs[0]['nombre']}{veces}: {motivo_reinicio(rs[0]['nombre'])[1]}", [])

    sin_arranques = [r for r in reinicios if r["clase"] not in ("encendido", "usb", "externo", "deep_sleep")]
    if len(sin_arranques) >= 3:
        hallazgo("bucle_reinicio", "alta", sin_arranques[0]["linea"],
                 f"Bucle de reinicio: {len(sin_arranques)} reinicios no provocados por el usuario.", [
                     "Corrige primero el primer fallo del log: los siguientes suelen ser consecuencia."])

    direcciones = list(dict.fromkeys(direcciones))
    addr2line = None
    if direcciones:
        herramienta = "riscv32-esp-elf-addr2line" if arquitectura == "riscv" else "xtensa-esp32-elf-addr2line"
        addr2line = f"{herramienta} -pfiaC -e build/firmware.elf " + " ".join(direcciones)

    orden = {"critica": 0, "alta": 1, "media": 2}
    hallazgos.sort(key=lambda h: (orden[h["gravedad"]], h["linea"]))
    return {"reinicios": reinicios, "hallazgos": hallazgos, "arquitectura": arquitectura,
            "direcciones": direcciones, "addr2line": addr2line}


def markdown(r):
    out = ["# Análisis del log serie", ""]
    if not r["hallazgos"]:
        out += ["No se han detectado fallos conocidos. ✅", ""]
    for h in r["hallazgos"]:
        icono = {"critica": "🔴", "alta": "🟠", "media": "🟡"}[h["gravedad"]]
        out += [f"## {icono} {h['tipo']} (línea {h['linea']})", "", h["explicacion"]]
        out += [f"- {p}" for p in h["siguientes_pasos"]] + [""]
    if r["reinicios"]:
        out += ["## Reinicios", "", "| Línea | Código | Motivo | Clase |", "|---:|---|---|---|"]
        out += [f"| {x['linea']} | {x['codigo']} | {x['nombre']} | {x['clase']} |" for x in r["reinicios"]]
        out.append("")
    if r["addr2line"]:
        out += ["## Decodificar el backtrace", "", "Cambia la ruta del `.elf` por la de tu compilación:", "",
                "```bash", r["addr2line"], "```", ""]
    return "\n".join(out)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    texto = Path(args[0]).read_text(encoding="utf-8", errors="replace") if args else sys.stdin.read()
    r = analizar(texto)
    print(json.dumps(r, ensure_ascii=False, indent=2) if "--json" in sys.argv else markdown(r))
    sys.exit(1 if any(h["gravedad"] == "critica" for h in r["hallazgos"]) else 0)


if __name__ == "__main__":
    main()
