# ML (phase 2)

This folder holds optional training and provider wiring beyond the MVP:

- `stubs/gemini_provider.py` — optional Google Gemini / Vertex-style chat wrapper.
- `stubs/slm_extract.py` — placeholder structured extraction service for small models.
- `train_ranker.py` — stub for a future PEFT/LoRA ranker trained on synthetic preferences.

The production scoring path remains `packages/scoring` (Pandas/NumPy).
