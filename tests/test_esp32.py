import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SKILL = RAIZ / "skills" / "esp32-firmware"
SCRIPT = SKILL / "scripts" / "analizar_log.py"
LOGS = RAIZ / "tests" / "logs"
sys.path.insert(0, str(SCRIPT.parent))
from analizar_log import analizar, motivo_reinicio  # noqa: E402


def tipos(nombre):
    return [h["tipo"] for h in analizar((LOGS / nombre).read_text())["hallazgos"]]


class AnalizadorTest(unittest.TestCase):
    def test_panico_xtensa_y_backtrace(self):
        r = analizar((LOGS / "esp32_loadprohibited.log").read_text())
        self.assertEqual(r["hallazgos"][0]["tipo"], "panico")
        self.assertIn("puntero NULL", r["hallazgos"][0]["explicacion"])
        self.assertEqual(r["arquitectura"], "xtensa")
        self.assertTrue(r["addr2line"].startswith("xtensa-esp32-elf-addr2line"))
        self.assertEqual(r["direcciones"], ["0x400d1a29", "0x400d2b59", "0x40088b7d"])

    def test_brownout_c3(self):
        self.assertEqual(tipos("c3_brownout.log"), ["brownout", "reinicio_brownout"])

    def test_watchdog_stack_overflow_y_bucle_c3(self):
        r = analizar((LOGS / "c3_watchdog_bucle.log").read_text())
        t = [h["tipo"] for h in r["hallazgos"]]
        self.assertEqual(t[:2], ["stack_overflow", "panico"])  # críticos primero
        for esperado in ("task_watchdog", "reinicio_watchdog", "bucle_reinicio"):
            self.assertIn(esperado, t)
        self.assertEqual(t.count("reinicio_watchdog"), 1)       # agrupado, no repetido
        self.assertEqual(r["arquitectura"], "riscv")
        self.assertTrue(r["addr2line"].startswith("riscv32-esp-elf-addr2line"))
        self.assertIn("IDLE (CPU 0)", next(h for h in r["hallazgos"] if h["tipo"] == "task_watchdog")["explicacion"])

    def test_log_sano(self):
        self.assertEqual(tipos("sano.log"), [])

    def test_motivos_de_reinicio(self):
        self.assertEqual(motivo_reinicio("RTCWDT_BROWN_OUT_RESET")[0], "brownout")
        self.assertEqual(motivo_reinicio("TG1WDT_SYS_RESET")[0], "watchdog")
        self.assertEqual(motivo_reinicio("DEEPSLEEP_RESET")[0], "deep_sleep")
        self.assertEqual(motivo_reinicio("SW_CPU_RESET")[0], "software")

    def test_cli_codigo_de_salida_y_json(self):
        r = subprocess.run([sys.executable, str(SCRIPT), str(LOGS / "esp32_loadprohibited.log"), "--json"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["hallazgos"][0]["tipo"], "panico")
        r = subprocess.run([sys.executable, str(SCRIPT)], input=(LOGS / "sano.log").read_text(),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0)


class PluginTest(unittest.TestCase):
    def test_manifiestos_y_skill(self):
        plugin = json.loads((RAIZ / ".claude-plugin" / "plugin.json").read_text())
        market = json.loads((RAIZ / ".claude-plugin" / "marketplace.json").read_text())
        self.assertEqual(market["plugins"][0]["name"], plugin["name"])
        texto = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        fm = dict(l.split(": ", 1) for l in re.match(r"^---\n(.*?)\n---\n", texto, re.S).group(1).splitlines())
        self.assertEqual(fm["name"], SKILL.name)
        for enlace in re.findall(r"\]\(([^)#:]+)\)", texto):
            self.assertTrue((SKILL / enlace).exists(), enlace)


if __name__ == "__main__":
    unittest.main()
