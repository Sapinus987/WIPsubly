"""
Benchmark NLLB-200 1.3B vs MADLAD-400 3B vs DeepL API — traduction russe → français
Usage : python benchmark.py --deepl-key VOTRE_CLE_API
"""
import os
import sys
import time
import argparse
import gc
import io

# Force UTF-8 sur la console Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── DLL CUDA ───────────────────────────────────────────────────────────────────
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
_VENV_SITE = os.path.join(sys.prefix, "Lib", "site-packages")
for _dll_dir in (
    os.path.join(_VENV_SITE, "ctranslate2"),
    os.path.join(_VENV_SITE, "nvidia", "cublas", "bin"),
    os.path.join(_VENV_SITE, "nvidia", "cudnn", "bin"),
):
    if os.path.isdir(_dll_dir):
        os.add_dll_directory(_dll_dir)
        os.environ["PATH"] = _dll_dir + ";" + os.environ.get("PATH", "")

# ── Phrases de test (typiques d'un stream gaming russe) ────────────────────────
SAMPLES = [
    "Привет всем, добро пожаловать на стрим!",
    "Сегодня мы играем в новую игру, которая вышла на прошлой неделе.",
    "Подождите, я сейчас умру от этого босса, он слишком сильный.",
    "Спасибо за донат, очень приятно!",
    "Ребята, вы видели что случилось? Это было невероятно!",
    "Я не понимаю почему эта механика работает именно так.",
    "Нужно собрать команду для рейда, кто хочет присоединиться?",
    "Этот уровень намного сложнее чем я думал, придётся переигрывать.",
    "Смотрите, я нашёл секретный проход, который никто не замечал.",
    "Завтра будет специальный стрим с гостями, не пропустите!",
]

SEP = "─" * 95


# ══════════════════════════════════════════════════════════════════════════════
#  Fonctions de traduction
# ══════════════════════════════════════════════════════════════════════════════

def translate_nllb(texts, tok, model, fr_tok_id):
    """NLLB-200 distilled 1.3B."""
    results = []
    for text in texts:
        t0 = time.perf_counter()
        inp = tok(text, return_tensors="pt", padding=True,
                  truncation=True, max_length=512).to("cuda")
        out = model.generate(
            **inp, forced_bos_token_id=fr_tok_id,
            num_beams=2, max_new_tokens=128,
            repetition_penalty=1.2, no_repeat_ngram_size=3,
        )
        fr = tok.decode(out[0], skip_special_tokens=True)
        ms = (time.perf_counter() - t0) * 1000
        results.append((fr, ms))
    return results


def translate_madlad(texts, tok, model):
    """MADLAD-400 3B — préfixe <2fr> requis."""
    results = []
    for text in texts:
        t0 = time.perf_counter()
        tagged = f"<2fr> {text}"
        inp = tok(tagged, return_tensors="pt",
                  truncation=True, max_length=512).to("cuda")
        out = model.generate(
            **inp,
            num_beams=2, max_new_tokens=128,
            repetition_penalty=1.2, no_repeat_ngram_size=3,
        )
        fr = tok.decode(out[0], skip_special_tokens=True)
        ms = (time.perf_counter() - t0) * 1000
        results.append((fr, ms))
    return results


def translate_deepl(texts, api_key):
    """DeepL API."""
    try:
        import deepl
    except ImportError:
        print("  Installation de deepl...")
        os.system(f'"{sys.executable}" -m pip install deepl --quiet')
        import deepl

    translator = deepl.Translator(api_key)
    results = []
    for text in texts:
        t0 = time.perf_counter()
        result = translator.translate_text(text, source_lang="RU", target_lang="FR")
        ms = (time.perf_counter() - t0) * 1000
        results.append((result.text, ms))
    return results


def free_gpu(model, tok):
    """Libère la VRAM entre deux modèles."""
    import torch
    del model, tok
    gc.collect()
    torch.cuda.empty_cache()


# ══════════════════════════════════════════════════════════════════════════════
#  Rapport
# ══════════════════════════════════════════════════════════════════════════════

def print_report(nllb_res, madlad_res, deepl_res):
    print(f"\n{SEP}")
    print(f"  BENCHMARK  —  NLLB-200 1.3B  |  MADLAD-400 3B  |  DeepL API   (RU → FR)")
    print(f"{SEP}\n")

    for i, phrase in enumerate(SAMPLES):
        nllb_fr,   nllb_ms   = nllb_res[i]
        madlad_fr, madlad_ms = madlad_res[i]
        deepl_fr,  deepl_ms  = deepl_res[i]
        print(f"  [{i+1:02d}] {phrase}")
        print(f"       NLLB-1.3B  ({nllb_ms:5.0f} ms) : {nllb_fr}")
        print(f"       MADLAD-3B  ({madlad_ms:5.0f} ms) : {madlad_fr}")
        print(f"       DeepL      ({deepl_ms:5.0f} ms) : {deepl_fr}")
        print()

    nllb_t   = sum(ms for _, ms in nllb_res)
    madlad_t = sum(ms for _, ms in madlad_res)
    deepl_t  = sum(ms for _, ms in deepl_res)

    print(SEP)
    print(f"  Temps total (10 phrases)")
    print(f"    NLLB-200 1.3B : {nllb_t/1000:.1f}s  ({nllb_t/len(SAMPLES):.0f} ms/phrase)")
    print(f"    MADLAD-400 3B : {madlad_t/1000:.1f}s  ({madlad_t/len(SAMPLES):.0f} ms/phrase)")
    print(f"    DeepL         : {deepl_t/1000:.1f}s  ({deepl_t/len(SAMPLES):.0f} ms/phrase)")
    print(SEP)


# ══════════════════════════════════════════════════════════════════════════════
#  Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deepl-key", required=True)
    args = parser.parse_args()

    from transformers import NllbTokenizer, AutoModelForSeq2SeqLM, AutoTokenizer
    import torch

    # ── 1. NLLB-200 1.3B ──────────────────────────────────────────────────
    print("\n[1/3] Chargement NLLB-200 distilled 1.3B...")
    nllb_name = "facebook/nllb-200-distilled-1.3B"
    nllb_tok  = NllbTokenizer.from_pretrained(nllb_name, src_lang="rus_Cyrl")
    nllb_mdl  = AutoModelForSeq2SeqLM.from_pretrained(
        nllb_name, torch_dtype=torch.float16).to("cuda")
    fr_id = nllb_tok.convert_tokens_to_ids("fra_Latn")
    print("    Traduction en cours...")
    nllb_res = translate_nllb(SAMPLES, nllb_tok, nllb_mdl, fr_id)
    print(f"    Termine — {sum(ms for _,ms in nllb_res)/1000:.1f}s")

    free_gpu(nllb_mdl, nllb_tok)

    # ── 2. MADLAD-400 3B ──────────────────────────────────────────────────
    print("\n[2/3] Chargement MADLAD-400 3B (premier lancement = telechargement ~6 GB)...")
    madlad_name = "google/madlad400-3b-mt"
    madlad_tok  = AutoTokenizer.from_pretrained(madlad_name)
    madlad_mdl  = AutoModelForSeq2SeqLM.from_pretrained(
        madlad_name, torch_dtype=torch.float16).to("cuda")
    print("    Traduction en cours...")
    madlad_res = translate_madlad(SAMPLES, madlad_tok, madlad_mdl)
    print(f"    Termine — {sum(ms for _,ms in madlad_res)/1000:.1f}s")

    free_gpu(madlad_mdl, madlad_tok)

    # ── 3. DeepL API ──────────────────────────────────────────────────────
    print("\n[3/3] DeepL API en cours...")
    deepl_res = translate_deepl(SAMPLES, args.deepl_key)
    print(f"    Termine — {sum(ms for _,ms in deepl_res)/1000:.1f}s")

    print_report(nllb_res, madlad_res, deepl_res)


if __name__ == "__main__":
    main()
