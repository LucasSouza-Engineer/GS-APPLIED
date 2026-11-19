"""Gera as figuras usadas no PDF de entrega (docs/figuras/*.png)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from visao_enderecos.documento import _mascara_grabcut, detectar_documento, retificar  # noqa: E402
from visao_enderecos.pipeline import processar  # noqa: E402
from visao_enderecos.preprocessamento import preprocessar  # noqa: E402

FIG = RAIZ / "docs" / "figuras"
FIG.mkdir(parents=True, exist_ok=True)
AZUL, CINZA, LARANJA = "#1f5fa8", "#9aa4b1", "#d9822b"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})


def rgb(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if img.ndim == 3 else img


def fig_exemplos(dados: Path):
    gab = json.loads((dados / "gabarito.json").read_text(encoding="utf-8"))
    escolha = [g for g in gab if g["nivel"] == "dificil"]
    ids = [next(g for g in escolha if g["empresa"] == e) for e in ("enel", "sabesp", "claro")]
    fig, ax = plt.subplots(2, 3, figsize=(10, 7.4))
    for j, g in enumerate(ids):
        ax[0, j].imshow(rgb(cv2.imread(str(dados / g["plana"]))))
        ax[0, j].set_title(f"{g['empresa'].capitalize()}: fatura sintética")
        ax[1, j].imshow(rgb(cv2.imread(str(dados / g["foto"]))))
        ax[1, j].set_title("foto simulada (nível difícil)")
    for a in ax.ravel():
        a.axis("off")
    fig.tight_layout()
    fig.savefig(FIG / "exemplos.png", dpi=150)
    plt.close(fig)


def fig_etapas(caminho: Path):
    img = cv2.imread(str(caminho))
    det = detectar_documento(img)
    marcada = img.copy()
    cv2.polylines(marcada, [det.cantos.astype(np.int32)], True, (0, 200, 0), 8)
    esc = 800 / max(img.shape[:2])
    gc = _mascara_grabcut(cv2.resize(img, None, fx=esc, fy=esc))
    doc = retificar(img, det.cantos)
    limpo = preprocessar(doc)
    r = processar(img)
    x1, y1, x2, y2 = r.caixa_endereco
    trecho = doc.copy()
    cv2.rectangle(trecho, (x1 - 10, y1 - 10), (x2 + 10, y2 + 10), (0, 0, 255), 5)
    paineis = [(rgb(img), "1. foto original"), (gc, "2. segmentação (GrabCut)"),
               (rgb(marcada), f"3. quadrilátero ({det.metodo})"), (rgb(doc), "4. perspectiva corrigida"),
               (limpo, "5. pré-processada"), (rgb(trecho), "6. bloco escolhido")]
    fig, ax = plt.subplots(1, 6, figsize=(14, 4.2))
    for a, (im, t) in zip(ax, paineis):
        a.imshow(im, cmap="gray")
        a.set_title(t, fontsize=9)
        a.axis("off")
    fig.tight_layout()
    fig.savefig(FIG / "etapas.png", dpi=150)
    plt.close(fig)
    return r


def fig_ablacao(met: dict):
    cfgs = [("sem_perspectiva", "Sem correção\nde perspectiva"), ("completo", "Pipeline\ncompleto"),
            ("plana", "Fatura escaneada\n(teto)")]
    cfgs = [c for c in cfgs if c[0] in met]
    vals = [met[c]["geral"]["endereco_exato"] * 100 for c, _ in cfgs]
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    cores = [CINZA if c == "sem_perspectiva" else AZUL if c == "completo" else LARANJA for c, _ in cfgs]
    b = ax.bar([n for _, n in cfgs], vals, color=cores, width=0.55)
    ax.bar_label(b, labels=[f"{v:.1f}%" for v in vals], padding=3)
    ax.set_ylabel("Endereços 100% corretos (%)")
    ax.set_ylim(0, 110)
    fig.tight_layout()
    fig.savefig(FIG / "ablacao.png", dpi=150)
    plt.close(fig)


def fig_campos(met: dict):
    campos = ["logradouro", "numero", "complemento", "bairro", "cidade", "uf", "cep"]
    fig, ax = plt.subplots(figsize=(6.8, 3.0))
    x = np.arange(len(campos))
    largura = 0.38
    for k, (cfg, cor, nome) in enumerate((("sem_perspectiva", CINZA, "sem correção"), ("completo", AZUL, "completo"))):
        if cfg not in met:
            continue
        v = [met[cfg]["geral"]["campos"][c] * 100 for c in campos]
        ax.bar(x + (k - 0.5) * largura, v, largura, color=cor, label=nome)
    ax.set_xticks(x, campos)
    ax.set_ylabel("Acurácia (%)")
    ax.set_ylim(0, 105)
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout()
    fig.savefig(FIG / "campos.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    dados = RAIZ / "dados" / "teste"
    met = json.loads((RAIZ / "resultados" / "teste" / "metricas.json").read_text(encoding="utf-8"))
    fig_exemplos(dados)
    fig_etapas(dados / "fotos" / "claro_001.jpg")
    fig_ablacao(met)
    fig_campos(met)
    print("figuras em", FIG)
