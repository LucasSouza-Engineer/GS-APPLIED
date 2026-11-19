"""Testes de unidade: interpretação e validação de endereços (não precisam do Tesseract)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from visao_enderecos.endereco import (Endereco, corrigir_digitos_ocr, formatar_cep, interpretar,  # noqa: E402
                                      normalizar_comparacao, uf_do_cep, validar)


@pytest.mark.parametrize("linhas, esperado", [
    # layout Enel (maiúsculas, CEP antes da cidade)
    (["RUA TOBIAS BARRETO, 581 APTO 32", "MOOCA", "03176-754 SÃO PAULO SP"],
     dict(logradouro="Rua Tobias Barreto", numero="581", complemento="Apto 32", bairro="Mooca",
          cidade="São Paulo", uf="SP", cep="03176-754")),
    # layout Sabesp (abreviação, separador " - ")
    (["R. Augusta, 675 - Apto 32 - Consolação", "São Paulo - SP - CEP 01305-154"],
     dict(logradouro="Rua Augusta", numero="675", complemento="Apto 32", bairro="Consolação",
          cidade="São Paulo", uf="SP", cep="01305-154")),
    # layout Claro (cidade/UF com barra, "CEP:")
    (["Avenida Paulista, 3053, Bloco C Apto 47", "Bela Vista - São Paulo/SP", "CEP: 01311-089"],
     dict(logradouro="Avenida Paulista", numero="3053", complemento="Bloco C Apto 47", bairro="Bela Vista",
          cidade="São Paulo", uf="SP", cep="01311-089")),
    # número no nome da rua
    (["Rua 25 de Março, 100 - Centro", "São Paulo/SP", "CEP 01021-200"],
     dict(logradouro="Rua 25 de Março", numero="100", complemento="", bairro="Centro",
          cidade="São Paulo", uf="SP", cep="01021-200")),
    # ruído típico de OCR: "R-", letra O no CEP, lixo de outra coluna
    (["R-tobias Barreto, 2245 - Bloco C Apto 68 - Mooca", "São Paulo - SP - CEP O3176-519"],
     dict(logradouro="Rua Tobias Barreto", numero="2245", complemento="Bloco C Apto 68", bairro="Mooca",
          cidade="São Paulo", uf="SP", cep="03176-519")),
    (["RUA CONDE DE BONFIM, 3801 BLOCO A APTO 20 | VENCIMENTO", "TIJUCA", "20524-593 RIO DE JANEIRO RJ"],
     dict(logradouro="Rua Conde de Bonfim", numero="3801", complemento="Bloco A Apto 20", bairro="Tijuca",
          cidade="Rio de Janeiro", uf="RJ", cep="20524-593")),
])
def test_interpretar_formatos(linhas, esperado):
    assert interpretar(linhas).to_dict() == esperado


def test_cep_por_uf():
    assert uf_do_cep("01310-100") == "SP"
    assert uf_do_cep("20520-000") == "RJ"
    assert uf_do_cep("30130-000") == "MG"
    assert uf_do_cep("123") is None


def test_validar_detecta_inconsistencia_cep_uf():
    e = Endereco("Rua Augusta", "10", "", "Consolação", "São Paulo", "RJ", "01305-154")
    v = validar(e)
    assert not v.valido
    assert {"cep", "uf"} <= set(v.campos_revisar)


def test_validar_endereco_completo():
    e = Endereco("Rua Augusta", "10", "", "Consolação", "São Paulo", "SP", "01305-154")
    assert validar(e).valido


def test_validar_campos_faltando():
    v = validar(Endereco(cep="01305-154", uf="SP"))
    assert not v.valido
    assert {"logradouro", "numero", "cidade"} <= set(v.campos_revisar)


def test_corrigir_digitos_ocr_so_mexe_em_cep():
    assert corrigir_digitos_ocr("CEP O5429-O1O") == "CEP 05429-010"
    assert corrigir_digitos_ocr("São Paulo") == "São Paulo"


def test_numero_de_hidrometro_nao_vira_cep():
    e = interpretar(["Av. Industrial, 1105 - Jardim", "RGI: 6963259532-7 Hidrômetro: Y87747016"])
    assert e.cep == ""


def test_formatar_e_normalizar():
    assert formatar_cep("01310100") == "01310-100"
    assert normalizar_comparacao("  São  PAULO ") == "sao paulo"
