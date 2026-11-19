"""Avalia o pipeline contra o gabarito das faturas sintéticas.

Métricas:
  * detecção do documento: taxa de sucesso (IoU >= 0,90) e IoU médio;
  * classificação da empresa: acurácia + matriz de confusão;
  * extração: acurácia por campo, endereço exato (todos os campos corretos),
    CER (taxa de erro de caractere) do endereço completo e taxa de "distrator"
    (quando o sistema devolve o endereço de cobrança/agência/sede);
  * calibração: acurácia dos casos que o sistema marcou como confiáveis.

Também roda um estudo de ablação para medir o ganho de cada etapa:
  completo        -> foto + detecção + correção de perspectiva + pré-processamento
  sem_perspectiva -> foto direto para o OCR (sem detectar/retificar)
  plana           -> fatura "escaneada" sem distorção (teto de desempenho)

Uso:
    python avaliacao/avaliar.py                       # usa dados/sinteticos
    python avaliacao/avaliar.py --configs completo    # só o pipeline final
"""
from __future__ import annotations

import argparse
import os

os.environ.setdefault("OMP_THREAD_LIMIT", "1")  # evita disputa de threads do Tesseract entre processos
import csv
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from visao_enderecos.documento import iou_quadrilateros  # noqa: E402
from visao_enderecos.endereco import normalizar_comparacao  # noqa: E402
from visao_enderecos.pipeline import LIMIAR_CONFIANCA, processar  # noqa: E402

CAMPOS = ["logradouro", "numero", "complemento", "bairro", "cidade", "uf", "cep"]


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    ant = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        atual = [i]
        for j, cb in enumerate(b, 1):
            atual.append(min(ant[j] + 1, atual[j - 1] + 1, ant[j - 1] + (ca != cb)))
        ant = atual
    return ant[-1]


def linha_endereco(e: dict | None) -> str:
    if not e:
        return ""
    return normalizar_comparacao(" ".join(e.get(c, "") for c in CAMPOS))


def _avaliar_um(args: tuple) -> dict:
    item, base, config = args
    caminho = base / (item["plana"] if config == "plana" else item["foto"])
    img = cv2.imread(str(caminho))
    t = time.perf_counter()
    r = processar(img, corrigir_perspectiva=(config != "sem_perspectiva"))
    dt = (time.perf_counter() - t) * 1000
    gt = item["endereco"]
    out = r.endereco or {}
    campos_ok = {c: normalizar_comparacao(out.get(c, "")) == normalizar_comparacao(gt[c]) for c in CAMPOS}
    ref = linha_endereco(gt)
    cer = levenshtein(linha_endereco(out), ref) / max(1, len(ref))
    distrator = any(normalizar_comparacao(out.get("cep", "")) == normalizar_comparacao(d["cep"]) and
                    d["cep"] != gt["cep"] for d in item["distratores"])
    iou = None
    if config == "completo" and r.cantos:
        iou = iou_quadrilateros(np.array(r.cantos), np.array(item["cantos"]), img.shape[:2])
    elif config == "completo":
        iou = 0.0
    return dict(id=item["id"], empresa=item["empresa"], nivel=item["nivel"], config=config,
                empresa_prevista=r.empresa or "", iou=iou, cer=round(cer, 4), exato=all(campos_ok.values()),
                distrator=distrator, valido=r.valido, confianca=r.confianca,
                confiavel=r.confianca >= LIMIAR_CONFIANCA and r.valido, tempo_ms=round(dt),
                **{f"ok_{c}": v for c, v in campos_ok.items()},
                previsto=json.dumps(out, ensure_ascii=False))


def resumir(linhas: list[dict]) -> dict:
    def m(xs):
        return round(float(np.mean(xs)), 4) if len(xs) else None

    res = dict(n=len(linhas), classificacao_acuracia=m([l["empresa_prevista"] == l["empresa"] for l in linhas]),
               endereco_exato=m([l["exato"] for l in linhas]), cer_medio=m([l["cer"] for l in linhas]),
               taxa_distrator=m([l["distrator"] for l in linhas]), validos=m([l["valido"] for l in linhas]),
               tempo_medio_ms=m([l["tempo_ms"] for l in linhas]),
               campos={c: m([l[f"ok_{c}"] for l in linhas]) for c in CAMPOS})
    ious = [l["iou"] for l in linhas if l["iou"] is not None]
    if ious:
        res["deteccao_iou_medio"] = m(ious)
        res["deteccao_sucesso_iou90"] = m([i >= 0.90 for i in ious])
    conf = [l for l in linhas if l["confiavel"]]
    res["cobertura_confiavel"] = m([l["confiavel"] for l in linhas])
    res["acuracia_quando_confiavel"] = m([l["exato"] for l in conf])
    res["acuracia_quando_revisar"] = m([l["exato"] for l in linhas if not l["confiavel"]])
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dados", type=Path, default=RAIZ / "dados" / "teste")
    ap.add_argument("--saida", type=Path, default=RAIZ / "resultados")
    ap.add_argument("--configs", nargs="+", default=["completo", "sem_perspectiva", "plana"])
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    gab = json.loads((a.dados / "gabarito.json").read_text(encoding="utf-8"))
    a.saida.mkdir(parents=True, exist_ok=True)

    tarefas = [(item, a.dados, cfg) for cfg in a.configs for item in gab]
    with ProcessPoolExecutor(a.workers) as ex:
        linhas = list(ex.map(_avaliar_um, tarefas))

    with open(a.saida / "por_documento.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)

    metricas = {}
    for cfg in a.configs:
        ls = [l for l in linhas if l["config"] == cfg]
        metricas[cfg] = dict(geral=resumir(ls),
                             por_empresa={e: resumir([l for l in ls if l["empresa"] == e]) for e in ("enel", "sabesp", "claro")},
                             por_nivel={n: resumir([l for l in ls if l["nivel"] == n]) for n in ("facil", "medio", "dificil")})
        emp = ["enel", "sabesp", "claro", ""]
        metricas[cfg]["matriz_confusao"] = {r: {p or "nenhuma": sum(1 for l in ls if l["empresa"] == r and l["empresa_prevista"] == p)
                                                for p in emp} for r in emp[:3]}
    (a.saida / "metricas.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=2), encoding="utf-8")

    for cfg in a.configs:
        g = metricas[cfg]["geral"]
        print(f"\n== {cfg} ==")
        print(json.dumps(g, ensure_ascii=False, indent=1))
    erros = [l for l in linhas if l["config"] == "completo" and not l["exato"]]
    if erros:
        print("\nErros (completo):")
        for l in erros:
            print(" ", l["id"], l["nivel"], [c for c in CAMPOS if not l[f"ok_{c}"]], l["previsto"])


if __name__ == "__main__":
    main()
