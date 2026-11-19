"""Gerador de faturas SINTÉTICAS (Enel, Sabesp, Claro) com gabarito.

Nenhum dado pessoal real é usado: nomes são combinações aleatórias e
números/complementos são sorteados. Os layouts imitam a ESTRUTURA de contas
reais (blocos, rótulos, endereços concorrentes), sem logotipos oficiais, e cada
documento traz a marca d'água "DOCUMENTO SINTÉTICO - SEM VALOR".

Para cada fatura são gerados:
  * a fatura "escaneada" (plana)            -> dados/sinteticos/planas/<id>.png
  * uma "foto de celular" da fatura          -> dados/sinteticos/fotos/<id>.jpg
    (perspectiva, rotação, sombra, desfoque, ruído, JPEG)
  * o gabarito com empresa, endereço correto, endereços distratores e os
    4 cantos do documento na foto            -> dados/sinteticos/gabarito.json

Uso:
    python gerador/gerar_faturas.py --por-empresa 20 --seed 42
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

RAIZ = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------
# Fontes
# --------------------------------------------------------------------------
_FONTES_CANDIDATAS = {
    "regular": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ],
    "bold": [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    ],
}


def fonte(tamanho: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for caminho in _FONTES_CANDIDATAS["bold" if bold else "regular"]:
        if Path(caminho).exists():
            return ImageFont.truetype(caminho, tamanho)
    return ImageFont.load_default(size=tamanho)


# --------------------------------------------------------------------------
# Endereços e pessoas fictícias
# --------------------------------------------------------------------------
# (tipo, nome do logradouro, bairro, cidade, UF, faixa de CEP)
LOGRADOUROS = [
    ("Rua", "Augusta", "Consolação", "São Paulo", "SP", (1304000, 1305999)),
    ("Rua", "Vergueiro", "Liberdade", "São Paulo", "SP", (1504000, 1504999)),
    ("Avenida", "Paulista", "Bela Vista", "São Paulo", "SP", (1310000, 1311999)),
    ("Rua", "Teodoro Sampaio", "Pinheiros", "São Paulo", "SP", (5405000, 5406999)),
    ("Rua", "Domingos de Morais", "Vila Mariana", "São Paulo", "SP", (4010000, 4036999)),
    ("Avenida", "Celso Garcia", "Brás", "São Paulo", "SP", (3014000, 3064999)),
    ("Rua", "Voluntários da Pátria", "Santana", "São Paulo", "SP", (2010000, 2402999)),
    ("Estrada", "do M'Boi Mirim", "Jardim Ângela", "São Paulo", "SP", (4905000, 4948999)),
    ("Avenida", "Sapopemba", "Sapopemba", "São Paulo", "SP", (3374000, 3989999)),
    ("Rua", "Ipiranga", "Ipiranga", "São Paulo", "SP", (4205000, 4209999)),
    ("Avenida", "Inajar de Souza", "Limão", "São Paulo", "SP", (2717000, 2861999)),
    ("Rua", "Itapura", "Tatuapé", "São Paulo", "SP", (3310000, 3310999)),
    ("Travessa", "das Flores", "Itaquera", "São Paulo", "SP", (8210000, 8295999)),
    ("Rua", "Dom Pedro II", "Centro", "Guarulhos", "SP", (7010000, 7099999)),
    ("Avenida", "Tiradentes", "Bom Clima", "Guarulhos", "SP", (7196000, 7196999)),
    ("Rua", "Primitiva Vianco", "Centro", "Osasco", "SP", (6016000, 6016999)),
    ("Avenida", "Industrial", "Jardim", "Santo André", "SP", (9080000, 9080999)),
    ("Rua", "Marechal Deodoro", "Centro", "São Bernardo do Campo", "SP", (9710000, 9710999)),
    ("Rua", "Barão de Jaguara", "Centro", "Campinas", "SP", (13015000, 13015999)),
    ("Rua", "Sete de Setembro", "Centro", "Santos", "SP", (11013000, 11013999)),
    ("Rua", "Tobias Barreto", "Mooca", "São Paulo", "SP", (3176000, 3176999)),
    ("Alameda", "Santos", "Jardim Paulista", "São Paulo", "SP", (1418000, 1419999)),
    ("Rua", "Conde de Bonfim", "Tijuca", "Rio de Janeiro", "RJ", (20520000, 20530999)),
    ("Rua", "Voluntários da Pátria", "Botafogo", "Rio de Janeiro", "RJ", (22270000, 22270999)),
    ("Avenida", "Afonso Pena", "Centro", "Belo Horizonte", "MG", (30130000, 30130999)),
]

# Empresas que só atendem certos estados (Sabesp = SP)
UF_POR_EMPRESA = {"enel": {"SP", "RJ"}, "sabesp": {"SP"}, "claro": {"SP", "RJ", "MG"}}

NOMES = ["Ana", "Bruno", "Carla", "Diego", "Elaine", "Fábio", "Gisele", "Hugo",
         "Isabela", "João", "Kátia", "Luís", "Márcia", "Nelson", "Olívia",
         "Paulo", "Rita", "Sérgio", "Tânia", "Vítor"]
SOBRENOMES = ["Almeida", "Barbosa", "Cardoso", "Duarte", "Esteves", "Ferraz",
              "Gouveia", "Holanda", "Igarashi", "Junqueira", "Lacerda", "Moraes",
              "Nogueira", "Prado", "Quintana", "Rezende", "Siqueira", "Teixeira"]

ABREV_TIPO = {"Rua": "R.", "Avenida": "Av.", "Travessa": "Tv.", "Alameda": "Al.",
              "Estrada": "Estr."}

# Endereços institucionais (distratores): sede/agência das empresas
SEDES = {
    "enel": dict(logradouro="Rua Ática", numero="673", complemento="", bairro="Jardim Brasil",
                 cidade="São Paulo", uf="SP", cep="04634-042"),
    "sabesp": dict(logradouro="Rua Costa Carvalho", numero="300", complemento="", bairro="Pinheiros",
                   cidade="São Paulo", uf="SP", cep="05429-000"),
    "claro": dict(logradouro="Rua Henri Dunant", numero="780", complemento="", bairro="Santo Amaro",
                  cidade="São Paulo", uf="SP", cep="04709-110"),
}
AGENCIAS_SABESP = [
    dict(logradouro="Avenida do Estado", numero="561", complemento="", bairro="Ponte Pequena",
         cidade="São Paulo", uf="SP", cep="01107-000"),
    dict(logradouro="Rua Nicolau Gagliardi", numero="313", complemento="", bairro="Pinheiros",
         cidade="São Paulo", uf="SP", cep="05429-010"),
]


def fmt_cep(n: int) -> str:
    s = f"{n:08d}"
    return f"{s[:5]}-{s[5:]}"


def endereco_aleatorio(rng: random.Random, ufs: set[str]) -> dict:
    opcoes = [l for l in LOGRADOUROS if l[4] in ufs]
    tipo, nome, bairro, cidade, uf, (c0, c1) = rng.choice(opcoes)
    comp = rng.choice(["", "", "", f"Apto {rng.randint(1, 24)}{rng.randint(1, 4)}",
                       f"Casa {rng.randint(1, 6)}", f"Bloco {rng.choice('ABCD')} Apto {rng.randint(11, 98)}",
                       "Fundos"])
    return dict(logradouro=f"{tipo} {nome}", numero=str(rng.randint(10, 3999)), complemento=comp,
                bairro=bairro, cidade=cidade, uf=uf, cep=fmt_cep(rng.randint(c0, c1)))


def abreviar(logradouro: str) -> str:
    tipo, _, resto = logradouro.partition(" ")
    return f"{ABREV_TIPO.get(tipo, tipo)} {resto}"


def nome_aleatorio(rng: random.Random) -> str:
    return f"{rng.choice(NOMES)} {rng.choice(SOBRENOMES)} {rng.choice(SOBRENOMES)}"


def uc(rng: random.Random, n: int) -> str:
    return "".join(str(rng.randint(0, 9)) for _ in range(n))


# --------------------------------------------------------------------------
# Desenho das faturas (A4 a ~150 dpi: 1240 x 1754)
# --------------------------------------------------------------------------
W, H = 1240, 1754


def _marca_dagua(img: Image.Image) -> None:
    camada = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    d.text((W // 2, H - 40), "DOCUMENTO SINTÉTICO - SEM VALOR - GERADO PARA TESTES",
           font=fonte(18, True), fill=(180, 0, 0, 200), anchor="mm")
    img.alpha_composite(camada)


def _tabela_consumo(d: ImageDraw.ImageDraw, x: int, y: int, rng: random.Random, unidade: str,
                    cor: tuple) -> None:
    d.text((x, y), f"Histórico de consumo ({unidade})", font=fonte(22, True), fill=cor)
    meses = ["JUN", "JUL", "AGO", "SET", "OUT", "NOV"]
    for i, m in enumerate(meses):
        v = rng.randint(80, 420) if unidade == "kWh" else rng.randint(6, 30)
        alt = int(v / (420 if unidade == "kWh" else 30) * 160)
        bx = x + i * 80
        d.rectangle([bx, y + 220 - alt, bx + 45, y + 220], fill=cor)
        d.text((bx + 22, y + 235), m, font=fonte(18), fill="black", anchor="mm")
        d.text((bx + 22, y + 215 - alt), str(v), font=fonte(16), fill="black", anchor="mb")


def _codigo_barras(d: ImageDraw.ImageDraw, x: int, y: int, rng: random.Random, larg: int = 900) -> None:
    cx = x
    while cx < x + larg:
        w = rng.choice([2, 2, 3, 4, 6])
        if rng.random() < 0.55:
            d.rectangle([cx, y, cx + w, y + 90], fill="black")
        cx += w
    linha = " ".join(uc(rng, 11) + "-" + str(rng.randint(0, 9)) for _ in range(4))
    d.text((x, y + 100), linha, font=fonte(20), fill="black")


def desenhar_enel(cli: dict, rng: random.Random) -> Image.Image:
    img = Image.new("RGBA", (W, H), "white")
    d = ImageDraw.Draw(img)
    roxo, verde = (90, 30, 140), (0, 140, 120)
    d.rectangle([0, 0, W, 150], fill=roxo)
    d.text((60, 45), "enel", font=fonte(72, True), fill="white")
    d.text((W - 60, 50), "CONTA DE ENERGIA ELÉTRICA", font=fonte(30, True), fill="white", anchor="ra")
    d.text((W - 60, 95), "Enel Distribuição São Paulo", font=fonte(22), fill="white", anchor="ra")

    y = 200
    d.text((60, y), "DADOS DO CLIENTE", font=fonte(26, True), fill=roxo)
    d.line([60, y + 38, W - 60, y + 38], fill=roxo, width=3)
    y += 60
    d.text((60, y), cli["nome"].upper(), font=fonte(28, True), fill="black")
    y += 55
    d.text((60, y), "ENDEREÇO DA UNIDADE CONSUMIDORA", font=fonte(22, True), fill=verde)
    e = cli["endereco"]
    l1 = f"{e['logradouro'].upper()}, {e['numero']}" + (f" {e['complemento'].upper()}" if e["complemento"] else "")
    d.text((60, y + 38), l1, font=fonte(28), fill="black")
    d.text((60, y + 78), e["bairro"].upper(), font=fonte(28), fill="black")
    d.text((60, y + 118), f"{e['cep']} {e['cidade'].upper()} {e['uf']}", font=fonte(28), fill="black")

    # caixa lateral
    d.rectangle([800, 250, W - 60, 470], outline=roxo, width=3)
    d.text((820, 265), "Nº DA INSTALAÇÃO", font=fonte(20, True), fill=roxo)
    d.text((820, 295), uc(rng, 10), font=fonte(28, True), fill="black")
    d.text((820, 345), "VENCIMENTO", font=fonte(20, True), fill=roxo)
    d.text((820, 375), f"{rng.randint(1, 28):02d}/12/2026", font=fonte(28, True), fill="black")
    d.text((820, 420), f"TOTAL R$ {rng.randint(60, 480)},{rng.randint(10, 99)}", font=fonte(26, True), fill="black")

    y = 560
    d.rectangle([60, y, W - 60, y + 120], fill=(240, 236, 248))
    d.text((80, y + 20), f"Classe: Residencial  |  Tensão: 127/220 V  |  Leitura anterior: {rng.randint(1000, 9000)}",
           font=fonte(22), fill="black")
    d.text((80, y + 60), f"Leitura atual: {rng.randint(9000, 9999)}  |  Consumo faturado: {rng.randint(80, 420)} kWh",
           font=fonte(22), fill="black")
    _tabela_consumo(d, 60, 740, rng, "kWh", roxo)
    d.text((620, 760), "Bandeira tarifária: VERDE", font=fonte(22, True), fill=verde)
    d.text((620, 800), "Tributos: ICMS, PIS, COFINS", font=fonte(20), fill="black")
    d.text((620, 830), "Iluminação pública (COSIP)", font=fonte(20), fill="black")

    y = 1080
    d.line([60, y, W - 60, y], fill=(150, 150, 150), width=2)
    d.text((60, y + 20), "Atendimento: 0800 72 72 196  |  www.enel.com.br", font=fonte(20), fill="black")
    s = SEDES["enel"]
    d.text((60, y + 55), f"Enel Distribuição São Paulo - {s['logradouro']}, {s['numero']} - {s['bairro']}",
           font=fonte(20), fill="black")
    d.text((60, y + 85), f"{s['cidade']} - {s['uf']} - CEP {s['cep']} - CNPJ 61.695.227/0001-93",
           font=fonte(20), fill="black")
    _codigo_barras(d, 60, 1300, rng)
    _marca_dagua(img)
    return img


def desenhar_sabesp(cli: dict, rng: random.Random) -> Image.Image:
    img = Image.new("RGBA", (W, H), "white")
    d = ImageDraw.Draw(img)
    azul, azul_claro = (0, 82, 155), (225, 238, 250)
    d.rectangle([0, 0, W, 160], fill=azul_claro)
    d.text((60, 40), "SABESP", font=fonte(70, True), fill=azul)
    d.text((W - 60, 45), "Conta de Água e Esgoto", font=fonte(30, True), fill=azul, anchor="ra")
    d.text((W - 60, 95), f"Fornecimento: {rng.randint(1, 28):02d}/11/2026", font=fonte(22), fill="black", anchor="ra")

    # Agência (distrator) antes do endereço do imóvel
    ag = rng.choice(AGENCIAS_SABESP)
    d.text((60, 200), "Agência de atendimento:", font=fonte(20, True), fill=azul)
    d.text((60, 228), f"{abreviar(ag['logradouro'])}, {ag['numero']} - {ag['bairro']} - {ag['cidade']}/{ag['uf']} - CEP {ag['cep']}",
           font=fonte(20), fill="black")

    y = 300
    d.rounded_rectangle([60, y, W - 60, y + 260], radius=18, outline=azul, width=3)
    d.text((85, y + 20), "Cliente:", font=fonte(22, True), fill=azul)
    d.text((200, y + 18), cli["nome"], font=fonte(26), fill="black")
    d.text((85, y + 70), "Endereço do Imóvel:", font=fonte(22, True), fill=azul)
    e = cli["endereco"]
    l1 = f"{abreviar(e['logradouro'])}, {e['numero']}" + (f" - {e['complemento']}" if e["complemento"] else "")
    d.text((85, y + 108), f"{l1} - {e['bairro']}", font=fonte(28), fill="black")
    d.text((85, y + 150), f"{e['cidade']} - {e['uf']} - CEP {e['cep']}", font=fonte(28), fill="black")
    d.text((85, y + 205), f"RGI: {uc(rng, 10)}-{rng.randint(0, 9)}    Hidrômetro: Y{uc(rng, 8)}",
           font=fonte(22), fill="black")

    y = 620
    d.text((60, y), f"Consumo do mês: {rng.randint(6, 30)} m³", font=fonte(26, True), fill=azul)
    d.text((60, y + 45), f"Água: R$ {rng.randint(30, 150)},{rng.randint(10, 99)}   Esgoto: R$ {rng.randint(30, 150)},{rng.randint(10, 99)}",
           font=fonte(24), fill="black")
    _tabela_consumo(d, 60, 760, rng, "m³", azul)
    d.rectangle([700, 760, W - 60, 960], fill=azul_claro)
    d.text((720, 780), "VENCIMENTO", font=fonte(22, True), fill=azul)
    d.text((720, 815), f"{rng.randint(1, 28):02d}/12/2026", font=fonte(34, True), fill="black")
    d.text((720, 875), "TOTAL A PAGAR", font=fonte(22, True), fill=azul)
    d.text((720, 905), f"R$ {rng.randint(60, 300)},{rng.randint(10, 99)}", font=fonte(34, True), fill="black")

    y = 1100
    s = SEDES["sabesp"]
    d.text((60, y), "Cia. de Saneamento Básico do Estado de São Paulo - SABESP", font=fonte(20, True), fill="black")
    d.text((60, y + 32), f"{abreviar(s['logradouro'])}, {s['numero']} - {s['bairro']} - {s['cidade']}/{s['uf']} - CEP {s['cep']}",
           font=fonte(20), fill="black")
    d.text((60, y + 64), "CNPJ 43.776.517/0001-80  |  Atendimento 0800 055 0195", font=fonte(20), fill="black")
    _codigo_barras(d, 60, 1300, rng)
    _marca_dagua(img)
    return img


def desenhar_claro(cli: dict, rng: random.Random) -> Image.Image:
    img = Image.new("RGBA", (W, H), "white")
    d = ImageDraw.Draw(img)
    verm = (218, 41, 28)
    d.rectangle([0, 0, W, 140], fill=verm)
    d.text((60, 30), "claro", font=fonte(76, True), fill="white")
    d.text((W - 60, 50), "Fatura Claro Residencial", font=fonte(30, True), fill="white", anchor="ra")
    d.text((W - 60, 92), "Internet + TV + Fone", font=fonte(22), fill="white", anchor="ra")

    d.text((60, 180), f"Olá, {cli['nome'].split()[0]}!", font=fonte(30, True), fill="black")
    d.text((60, 225), f"Contrato: {uc(rng, 9)}   Vencimento: {rng.randint(1, 28):02d}/12/2026",
           font=fonte(22), fill="black")

    e = cli["endereco"]
    cob = cli["cobranca"]
    # Endereço de cobrança aparece ANTES (topo), instalação depois: distrator forte
    y = 290
    for titulo, end in (("Endereço de Cobrança", cob), ("Endereço de Instalação", e)):
        d.rectangle([60, y, W - 60, y + 175], outline=verm, width=3)
        d.text((80, y + 15), titulo, font=fonte(22, True), fill=verm)
        l1 = f"{end['logradouro']}, {end['numero']}" + (f", {end['complemento']}" if end["complemento"] else "")
        d.text((80, y + 55), l1, font=fonte(28), fill="black")
        d.text((80, y + 95), f"{end['bairro']} - {end['cidade']}/{end['uf']}", font=fonte(28), fill="black")
        d.text((80, y + 135), f"CEP: {end['cep']}", font=fonte(26), fill="black")
        y += 200

    y = 720
    d.text((60, y), "Resumo da fatura", font=fonte(26, True), fill=verm)
    itens = [("Claro Internet 500 Mega", rng.randint(80, 120)), ("Claro TV+ Box", rng.randint(60, 110)),
             ("Fone ilimitado", rng.randint(20, 50)), ("Descontos", -rng.randint(5, 30))]
    for i, (n, v) in enumerate(itens):
        d.text((60, y + 50 + i * 40), n, font=fonte(24), fill="black")
        d.text((W - 60, y + 50 + i * 40), f"R$ {v},{rng.randint(10, 99)}", font=fonte(24), fill="black", anchor="ra")
    d.line([60, y + 220, W - 60, y + 220], fill="black", width=2)
    d.text((60, y + 235), "TOTAL", font=fonte(28, True), fill="black")
    d.text((W - 60, y + 235), f"R$ {rng.randint(150, 320)},{rng.randint(10, 99)}", font=fonte(28, True),
           fill="black", anchor="ra")

    y = 1100
    s = SEDES["claro"]
    d.text((60, y), f"Claro S.A. - {s['logradouro']}, {s['numero']} - {s['bairro']}", font=fonte(20), fill="black")
    d.text((60, y + 30), f"{s['cidade']}/{s['uf']} - CEP {s['cep']} - CNPJ 40.432.544/0001-47",
           font=fonte(20), fill="black")
    d.text((60, y + 60), "Central de relacionamento: *525 ou 10621", font=fonte(20), fill="black")
    _codigo_barras(d, 60, 1300, rng)
    _marca_dagua(img)
    return img


DESENHOS = {"enel": desenhar_enel, "sabesp": desenhar_sabesp, "claro": desenhar_claro}


# --------------------------------------------------------------------------
# Simulação de "foto de celular"
# --------------------------------------------------------------------------
NIVEIS = {
    #            margem do quadro, deslocamento de cantos, rotação, desfoque, ruído, jpeg
    "facil":   dict(escala=(0.80, 0.88), jitter=0.03, rot=4, blur=(0.0, 0.6), ruido=4, jpeg=(85, 95), sombra=0.15),
    "medio":   dict(escala=(0.72, 0.84), jitter=0.07, rot=10, blur=(0.4, 1.0), ruido=8, jpeg=(70, 88), sombra=0.30),
    "dificil": dict(escala=(0.65, 0.80), jitter=0.11, rot=18, blur=(0.8, 1.5), ruido=12, jpeg=(55, 75), sombra=0.45),
}


def _fundo(rng: np.random.Generator, h: int, w: int) -> np.ndarray:
    base = rng.integers(40, 140, size=3).astype(np.float32)
    ruido = cv2.GaussianBlur(rng.normal(0, 25, (h // 8, w // 8)).astype(np.float32), (0, 0), 3)
    ruido = cv2.resize(ruido, (w, h))
    listras = (np.sin(np.linspace(0, rng.uniform(10, 40), w))[None, :] * rng.uniform(5, 15)).astype(np.float32)
    fundo = base[None, None, :] + (ruido + listras)[..., None]
    return np.clip(fundo, 0, 255).astype(np.uint8)


def simular_foto(plana: np.ndarray, nivel: str, rng: np.random.Generator) -> tuple[np.ndarray, list]:
    p = NIVEIS[nivel]
    FH, FW = 1600, 1200  # foto retrato 4:3
    h, w = plana.shape[:2]
    esc = rng.uniform(*p["escala"])
    alvo_h = FH * esc
    alvo_w = alvo_h * w / h
    if alvo_w > FW * 0.95:
        alvo_w = FW * 0.95
        alvo_h = alvo_w * h / w
    cx, cy = FW / 2 + rng.uniform(-40, 40), FH / 2 + rng.uniform(-40, 40)
    cantos = np.array([[-alvo_w / 2, -alvo_h / 2], [alvo_w / 2, -alvo_h / 2],
                       [alvo_w / 2, alvo_h / 2], [-alvo_w / 2, alvo_h / 2]], dtype=np.float32)
    ang = np.deg2rad(rng.uniform(-p["rot"], p["rot"]))
    R = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]], dtype=np.float32)
    cantos = cantos @ R.T
    cantos += rng.uniform(-p["jitter"], p["jitter"], cantos.shape).astype(np.float32) * np.array([alvo_w, alvo_h], np.float32)
    cantos += np.array([cx, cy], np.float32)
    cantos[:, 0] = np.clip(cantos[:, 0], 5, FW - 5)
    cantos[:, 1] = np.clip(cantos[:, 1], 5, FH - 5)

    origem = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(origem, cantos)
    papel = cv2.warpPerspective(plana, M, (FW, FH), flags=cv2.INTER_AREA)
    mascara = cv2.warpPerspective(np.full((h, w), 255, np.uint8), M, (FW, FH))
    foto = _fundo(rng, FH, FW)
    foto[mascara > 0] = papel[mascara > 0]

    # iluminação irregular + sombra
    yy, xx = np.mgrid[0:FH, 0:FW].astype(np.float32)
    gx, gy = rng.uniform(-1, 1, 2)
    grad = 1 - p["sombra"] * ((gx * (xx / FW - .5) + gy * (yy / FH - .5)) + .5).clip(0, 1)
    foto = (foto.astype(np.float32) * grad[..., None])
    if rng.random() < 0.5:  # sombra de mão/celular
        sx, sy = rng.uniform(0, FW), rng.uniform(0, FH)
        sombra = np.exp(-(((xx - sx) / 350) ** 2 + ((yy - sy) / 350) ** 2))
        foto *= (1 - 0.35 * sombra)[..., None]
    foto = np.clip(foto, 0, 255).astype(np.uint8)

    s = rng.uniform(*p["blur"])
    if s > 0.05:
        foto = cv2.GaussianBlur(foto, (0, 0), s)
    foto = np.clip(foto.astype(np.float32) + rng.normal(0, p["ruido"], foto.shape), 0, 255).astype(np.uint8)
    q = int(rng.integers(*p["jpeg"]))
    ok, buf = cv2.imencode(".jpg", foto, [cv2.IMWRITE_JPEG_QUALITY, q])
    foto = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    return foto, cantos.round(1).tolist()


# --------------------------------------------------------------------------
def gerar(por_empresa: int, seed: int, saida: Path) -> list[dict]:
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    (saida / "planas").mkdir(parents=True, exist_ok=True)
    (saida / "fotos").mkdir(parents=True, exist_ok=True)
    gabarito = []
    niveis = ["facil", "medio", "dificil"]
    for empresa, desenhar in DESENHOS.items():
        for i in range(por_empresa):
            ufs = UF_POR_EMPRESA[empresa]
            end = endereco_aleatorio(rng, ufs)
            cli = dict(nome=nome_aleatorio(rng), endereco=end)
            distratores = [SEDES[empresa]]
            if empresa == "claro":
                cli["cobranca"] = endereco_aleatorio(rng, ufs) if rng.random() < 0.6 else dict(end)
                if cli["cobranca"] != end:
                    distratores.append(cli["cobranca"])
            img = desenhar(cli, rng).convert("RGB")
            plana = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            ident = f"{empresa}_{i:03d}"
            nivel = niveis[i % 3]
            foto, cantos = simular_foto(plana, nivel, nrng)
            cv2.imwrite(str(saida / "planas" / f"{ident}.png"), plana)
            cv2.imwrite(str(saida / "fotos" / f"{ident}.jpg"), foto)
            gabarito.append(dict(id=ident, empresa=empresa, nivel=nivel, foto=f"fotos/{ident}.jpg",
                                 plana=f"planas/{ident}.png", cantos=cantos, endereco=end,
                                 distratores=distratores))
    (saida / "gabarito.json").write_text(json.dumps(gabarito, ensure_ascii=False, indent=2), encoding="utf-8")
    return gabarito


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--por-empresa", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--saida", type=Path, default=RAIZ / "dados" / "teste")
    a = ap.parse_args()
    g = gerar(a.por_empresa, a.seed, a.saida)
    print(f"{len(g)} faturas geradas em {a.saida}")
