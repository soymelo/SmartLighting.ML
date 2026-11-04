"""Confere um executável C++ nativo com os casos congelados em Python."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path


def verify_cpp_predictor(reference_path: Path, program: Path) -> int:
    """Exige probabilidades próximas e decisões PWM idênticas nos oito casos."""
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    cases = reference["cases"]
    if not cases:
        raise ValueError("Não há casos de referência.")
    for index, case in enumerate(cases, start=1):
        result = subprocess.run(
            [str(program), str(case["local_hour"]), str(case["local_weekday"]),
             str(case["previous_30m_count"])],
            capture_output=True, text=True, check=True,
        )
        count, probability, pwm = result.stdout.split()
        if (not math.isclose(float(count), case["predicted_count"], rel_tol=1e-9, abs_tol=1e-9)
                or not math.isclose(float(probability), case["activity_probability"],
                                    rel_tol=1e-9, abs_tol=1e-9)
                or int(pwm) != case["rest_pwm"]):
            raise AssertionError(f"Previsão C++ diferente do Python no caso {index}.")
    return len(cases)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=Path("config/firmware_reference.json"))
    parser.add_argument("--program", type=Path, required=True)
    args = parser.parse_args()
    total = verify_cpp_predictor(args.reference, args.program)
    print(f"C++ e Python concordam em {total} casos de referência.")


if __name__ == "__main__":
    main()
