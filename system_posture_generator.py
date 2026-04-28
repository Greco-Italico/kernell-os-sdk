import os
import re
from collections import defaultdict
from datetime import datetime

class SystemPostureGenerator:

    def __init__(self, root_path):
        self.root = root_path
        self.files = []
        self.findings = defaultdict(list)
        self.scores = {
            "architecture": 80,
            "security": 100,
            "runtime": 70,
            "agents": 70,
            "economy": 60,
            "observability": 40,
            "testing": 80
        }

    # -------------------------
    # SCAN FILES
    # -------------------------
    def scan(self):
        for root, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
            for f in files:
                if f.endswith(".py"):
                    self.files.append(os.path.join(root, f))

    def read(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().lower()
        except:
            return ""

    # -------------------------
    # DETECTIONS
    # -------------------------

    def detect_except_pass(self):
        for f in self.files:
            content = self.read(f)
            if re.search(r"except\s+.*:\s+pass", content):
                self.findings["fail_open"].append(f)
                self.scores["security"] -= 10

    def detect_tmp_usage(self):
        for f in self.files:
            content = self.read(f)
            if "/tmp" in content:
                self.findings["tmp_usage"].append(f)
                self.scores["security"] -= 5

    def detect_subprocess(self):
        for f in self.files:
            content = self.read(f)
            if "subprocess" in content:
                if "run([" in content or "popen([" in content:
                    # Checamos si usan shutil.which
                    if "shutil.which" not in content:
                        self.findings["subprocess_absolute_path_missing"].append(f)
                        self.scores["security"] -= 5

    def detect_random_usage(self):
        for f in self.files:
            content = self.read(f)
            if "random." in content and "secrets" not in content:
                self.findings["predictable_random"].append(f)
                self.scores["economy"] -= 5

    def detect_logging_absence(self):
        has_logging = False
        for f in self.files:
            content = self.read(f)
            if "logging" in content:
                has_logging = True
        if not has_logging:
            self.findings["no_logging"].append("global")
            self.scores["observability"] -= 20

    def detect_network_risk(self):
        for f in self.files:
            content = self.read(f)
            if "requests." in content or "http" in content:
                self.findings["network_calls"].append(f)
                self.scores["security"] -= 10

    # -------------------------
    # ANALYZE
    # -------------------------

    def analyze(self):
        self.scan()

        self.detect_except_pass()
        self.detect_tmp_usage()
        self.detect_subprocess()
        self.detect_random_usage()
        self.detect_logging_absence()
        self.detect_network_risk()

    # -------------------------
    # REPORT GENERATION
    # -------------------------

    def generate_report(self):
        total = sum(self.scores.values()) / len(self.scores)

        report = []
        report.append("# 🧠 SYSTEM POSTURE REPORT\n")
        report.append(f"Generated: {datetime.utcnow().isoformat()}Z\n")
        report.append(f"Overall Score: {round(total,2)} / 100\n")

        report.append("\n## ⚠️ Findings\n")

        if not self.findings:
            report.append("No critical findings detected.\n")

        for k, v in self.findings.items():
            report.append(f"### {k}\n")
            for item in v[:5]:
                report.append(f"- {os.path.basename(item)}\n")

        report.append("\n## 📊 Scores\n")
        for k, v in self.scores.items():
            report.append(f"- {k}: {max(0,v)}\n")

        report.append("\n## 🚨 Risk Assessment\n")

        if total < 50:
            report.append("HIGH RISK — Not production ready\n")
        elif total < 70:
            report.append("MEDIUM RISK — Pre-production\n")
        else:
            report.append("LOW RISK — Production candidate\n")

        return "\n".join(report)

    def save(self):
        report = self.generate_report()
        with open("SYSTEM_POSTURE.md", "w") as f:
            f.write(report)


# -------------------------
# RUN
# -------------------------

if __name__ == "__main__":
    gen = SystemPostureGenerator("./")
    gen.analyze()
    gen.save()
    print("SYSTEM_POSTURE.md generated successfully.")
