"""Testes da API de integração com o MVP (cadastro com confirmação do cidadão)."""
import random
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "gerador"))


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("CADASTRO_DB", str(tmp_path / "teste.sqlite3"))
    import importlib

    import api.app as modulo
    importlib.reload(modulo)
    from fastapi.testclient import TestClient
    return TestClient(modulo.app)


ENDERECO = dict(logradouro="Rua Augusta", numero="675", complemento="", bairro="Consolação",
                cidade="São Paulo", uf="SP", cep="01305154")


def test_saude(cliente):
    if not shutil.which("tesseract"):
        pytest.skip("Tesseract não instalado")
    assert cliente.get("/api/v1/saude").json()["status"] == "ok"


def test_cadastro_exige_consentimento(cliente):
    r = cliente.post("/api/v1/cadastros", json=dict(endereco=ENDERECO, canal="whatsapp",
                                                    contato="11912345678", consentimento=False))
    assert r.status_code == 422


def test_cadastro_rejeita_cep_de_outro_estado(cliente):
    e = dict(ENDERECO, uf="RJ")
    r = cliente.post("/api/v1/cadastros", json=dict(endereco=e, canal="sms", contato="11912345678", consentimento=True))
    assert r.status_code == 422


def test_cadastro_fluxo_completo_e_exclusao(cliente):
    r = cliente.post("/api/v1/cadastros", json=dict(endereco=ENDERECO, canal="whatsapp", contato="(11) 91234-5678",
                                                    consentimento=True, origem="ocr", empresa_documento="sabesp",
                                                    campos_corrigidos=["bairro"], confianca_ocr=0.9))
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["endereco"]["cep"] == "01305-154"
    assert "5678" in j["contato"] and "91234" not in j["contato"]  # contato mascarado
    m = cliente.get("/api/v1/metricas").json()
    assert m["via_ocr"] == 1 and m["correcoes_por_campo"] == {"bairro": 1}
    assert cliente.delete(f"/api/v1/cadastros/{j['id']}").status_code == 204
    assert cliente.get(f"/api/v1/cadastros/{j['id']}").status_code == 404


def test_extrair_rejeita_arquivo_que_nao_e_imagem(cliente):
    r = cliente.post("/api/v1/enderecos/extrair", files={"arquivo": ("a.txt", b"oi", "text/plain")})
    assert r.status_code == 415


@pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract não instalado")
def test_extrair_de_foto(cliente):
    import gerar_faturas as G
    rng = random.Random(3)
    end = G.endereco_aleatorio(rng, {"SP"})
    plana = cv2.cvtColor(np.array(G.desenhar_sabesp(dict(nome="Teste", endereco=end), rng).convert("RGB")),
                         cv2.COLOR_RGB2BGR)
    foto, _ = G.simular_foto(plana, "facil", np.random.default_rng(3))
    ok, buf = cv2.imencode(".jpg", foto)
    r = cliente.post("/api/v1/enderecos/extrair", files={"arquivo": ("conta.jpg", buf.tobytes(), "image/jpeg")})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["empresa"] == "sabesp"
    assert j["endereco"]["cep"] == end["cep"]
    assert j["trecho_documento"].startswith("data:image/jpeg;base64,")


def test_foto_com_rotacao_exif_e_endireitada():
    """Celulares gravam a foto 'deitada' + tag EXIF de rotação; a API deve respeitar a tag."""
    import io

    from PIL import Image
    import api.app as modulo
    im = Image.new("RGB", (40, 20), "white")
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation = girar 90° no sentido horário
    buf = io.BytesIO()
    im.save(buf, format="JPEG", exif=exif)
    out = modulo._abrir_imagem(buf.getvalue())
    assert out.shape[:2] == (40, 20)
