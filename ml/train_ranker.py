from __future__ import annotations

"""
Stub entrypoint for a future preference ranker (PEFT/LoRA).

Planned flow:
1. Generate synthetic scenarios + offers with known ground-truth rankings.
2. Train a small classifier/regressor to mimic composite scoring weights.
3. Export artifacts to an object store and version in your MLOps pipeline.
"""


def main() -> None:
    print("train_ranker: not implemented (stub).")


if __name__ == "__main__":
    main()
