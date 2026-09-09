#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
prep_models.py <destino>

Baixa os modelos faster-whisper (tiny + small) e deixa uma cópia limpa em
    <destino>/faster-whisper-tiny/
    <destino>/faster-whisper-small/
pronta pra ir no pacote (o instalador aponta o config pra essas pastas).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPOS = {
    "faster-whisper-tiny": "Systran/faster-whisper-tiny",
    "faster-whisper-small": "Systran/faster-whisper-small",
}


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: prep_models.py <pasta_destino>")
        return 2
    dest = Path(sys.argv[1])
    dest.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("Instale huggingface_hub:  uv pip install huggingface_hub")
        return 1

    for folder, repo in REPOS.items():
        target = dest / folder
        if (target / "model.bin").is_file():
            print(f"  {folder}: já existe, pulando")
            continue
        print(f"  baixando {repo} …")
        snap = snapshot_download(repo, allow_patterns=["*.bin", "*.txt", "*.json"])
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(snap, target)
        # tira links/symlinks de cache — copytree já resolve, mas garante arquivos reais
        for p in target.rglob("*"):
            if p.is_symlink():
                real = p.resolve()
                p.unlink()
                shutil.copy2(real, p)
        mb = sum(f.stat().st_size for f in target.rglob("*") if f.is_file()) / 1024**2
        print(f"  {folder}: {mb:.0f} MB")

    print("modelos prontos em", dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
