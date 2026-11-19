"""Testes de visão: detecção/retificação e pipeline ponta a ponta em faturas sintéticas.

Geram as próprias faturas (semente fixa) em uma pasta temporária, então não
dependem de arquivos versionados. Os testes de OCR são pulados se o Tesseract
não estiver instalado.
"""
import random
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "gerador"))

import gerar_faturas as G  # noqa: E402
from visao_enderecos.documento import detectar_documento, iou_quadrilateros, ordenar_cantos, retificar  # noqa: E402
from visao_enderecos.endereco import normalizar_comparacao  # noqa: E402

TEM_TESSERACT = shutil.which("tesseract") is not None


@pytest.fixture(scope="module")
def amostras():
    rng = random.Random(7)
    nrng = np.random.default_rng(7)
    out = []
    for empresa, desenhar in G.DESENHOS.items():
        end = G.endereco_aleatorio(rng, G.UF_POR_EMPRESA[empresa])
        cli = dict(nome=G.nome_aleatorio(rng), endereco=end)
        if empresa == "claro":  # cobrança diferente: o pipeline precisa escolher a instalação
            cli["cobranca"] = G.endereco_aleatorio(rng, G.UF_POR_EMPRESA[empresa])
        plana = cv2.cvtColor(np.array(desenhar(cli, rng).convert("RGB")), cv2.COLOR_RGB2BGR)
        foto, cantos = G.simular_foto(plana, "medio", nrng)
        out.append(dict(empresa=empresa, endereco=end, foto=foto, cantos=np.array(cantos), plana=plana))
    return out


def test_ordenar_cantos():
    pts = np.array([[10, 90], [90, 10], [10, 10], [90, 90]], np.float32)
    assert ordenar_cantos(pts).tolist() == [[10, 10], [90, 10], [90, 90], [10, 90]]


def test_deteccao_documento(amostras):
    for a in amostras:
        det = detectar_documento(a["foto"])
        assert det.cantos is not None, a["empresa"]
        iou = iou_quadrilateros(det.cantos, a["cantos"], a["foto"].shape[:2])
        assert iou > 0.90, f"{a['empresa']}: IoU {iou:.3f}"


def test_retificacao_gera_a4(amostras):
    a = amostras[0]
    doc = retificar(a["foto"], a["cantos"])
    assert doc.shape[1] == 1240
    assert abs(doc.shape[0] / doc.shape[1] - 297 / 210) < 0.01


def test_sem_documento_nao_quebra():
    fundo = np.full((600, 800, 3), 90, np.uint8)
    assert detectar_documento(fundo).cantos is None


@pytest.mark.skipif(not TEM_TESSERACT, reason="Tesseract não instalado")
def test_pipeline_ponta_a_ponta(amostras):
    from visao_enderecos import processar
    for a in amostras:
        r = processar(a["foto"])
        assert r.empresa == a["empresa"]
        assert r.endereco is not None, a["empresa"]
        assert normalizar_comparacao(r.endereco["cep"]) == normalizar_comparacao(a["endereco"]["cep"])
        assert normalizar_comparacao(r.endereco["logradouro"]) == normalizar_comparacao(a["endereco"]["logradouro"])
        assert r.endereco["numero"] == a["endereco"]["numero"]


@pytest.mark.skipif(not TEM_TESSERACT, reason="Tesseract não instalado")
def test_imagem_sem_conta_nao_inventa_endereco():
    from visao_enderecos import processar
    img = np.full((1600, 1200, 3), 255, np.uint8)
    cv2.putText(img, "Lista de compras: arroz, feijao", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)
    r = processar(img)
    assert r.endereco is None
    assert not r.valido


@pytest.mark.skipif(not TEM_TESSERACT, reason="Tesseract não instalado")
@pytest.mark.parametrize("giro", [cv2.ROTATE_90_CLOCKWISE, cv2.ROTATE_180, cv2.ROTATE_90_COUNTERCLOCKWISE])
def test_foto_girada(amostras, giro):
    """Celular deitado ou de cabeça para baixo: o endereço ainda deve ser lido."""
    from visao_enderecos import processar
    a = amostras[1]
    r = processar(cv2.rotate(a["foto"], giro))
    assert r.endereco is not None
    assert r.endereco["cep"] == a["endereco"]["cep"]
