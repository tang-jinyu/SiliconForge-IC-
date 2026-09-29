"""Generate a restrained synthetic ambient bed without external audio assets."""

from __future__ import annotations

import argparse
import math
import wave
from array import array
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("duration", type=float)
    args = parser.parse_args()

    sample_rate = 48_000
    frame_count = int(args.duration * sample_rate)
    samples = array("h")
    for index in range(frame_count):
        t = index / sample_rate
        fade_in = min(1.0, t / 2.0)
        fade_out = min(1.0, max(0.0, (args.duration - t) / 3.0))
        envelope = fade_in * fade_out
        pulse = 0.72 + 0.28 * math.sin(2 * math.pi * 0.18 * t)
        signal = (
            0.58 * math.sin(2 * math.pi * 55.0 * t)
            + 0.29 * math.sin(2 * math.pi * 82.41 * t)
            + 0.13 * pulse * math.sin(2 * math.pi * 220.0 * t)
        )
        samples.append(int(32767 * 0.12 * envelope * signal))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(args.output), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(samples.tobytes())


if __name__ == "__main__":
    main()
