"""Monta o PDF de entrega da disciplina Applied Computer Vision.

Uso:
    python docs/gerar_figuras.py
    python docs/gerar_pdf.py --repo https://github.com/<usuario>/<repo> --integrantes "Nome (RM), ..."
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

RAIZ = Path(__file__).resolve().parents[1]
FIG = RAIZ / "docs" / "figuras"
AZUL = colors.HexColor("#1f5fa8")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=15, textColor=AZUL, spaceBefore=10, spaceAfter=6)
H2 = ParagraphStyle("h2", parent=ss["Heading2"], fontSize=12, textColor=AZUL, spaceBefore=8, spaceAfter=4)
P = ParagraphStyle("p", parent=ss["BodyText"], fontSize=10, leading=14, spaceAfter=5)
PEQ = ParagraphStyle("peq", parent=P, fontSize=8.5, leading=11)
CEL = ParagraphStyle("cel", parent=P, fontSize=8.5, leading=10.5, spaceAfter=0)
CAPA = ParagraphStyle("capa", parent=P, alignment=TA_CENTER, fontSize=12, leading=18)


def pct(v):
    return "-" if v is None else f"{v * 100:.1f}%"


def tabela(dados, larguras, cabecalho=True):
    linhas = [[Paragraph(str(c), CEL) for c in l] for l in dados]
    t = Table(linhas, colWidths=larguras, repeatRows=1 if cabecalho else 0)
    estilo = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c2cc")),
              ("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if cabecalho:
        estilo += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e6eef8"))]
    t.setStyle(TableStyle(estilo))
    return t


def img(nome, largura):
    from PIL import Image as PImage
    caminho = FIG / nome
    w, h = PImage.open(caminho).size
    return Image(str(caminho), width=largura, height=largura * h / w)


def link(url, texto=None):
    if not url or "preencher" in url:
        return "<i>(preencher)</i>"
    return f'<link href="{url}" color="blue"><u>{texto or url}</u></link>'


def montar(args):
    met = json.loads((RAIZ / "resultados" / "teste" / "metricas.json").read_text(encoding="utf-8"))
    dev_p = RAIZ / "resultados" / "desenvolvimento" / "metricas.json"
    dev = json.loads(dev_p.read_text(encoding="utf-8")) if dev_p.exists() else None
    c, s, pl = met["completo"]["geral"], met.get("sem_perspectiva", {}).get("geral"), met.get("plana", {}).get("geral")
    W = A4[0] - 4 * cm
    el = []

    # ---------------- Capa
    el += [Spacer(1, 3 * cm),
           Paragraph("<b>Extração Automática de Endereços</b>", ParagraphStyle("t", parent=CAPA, fontSize=22, leading=28)),
           Spacer(1, 0.4 * cm),
           Paragraph("Componente <b>Visão</b> do MVP CitizenTech<br/>Alerta de enchente e calor por endereço", CAPA),
           Spacer(1, 1.2 * cm),
           Paragraph("Global Solution 2026.2 · FIAP · Engenharia de Software 4º ano (4ESPR)<br/>"
                     "Applied Computer Vision · Prof. Wilians Douglas Conde Souza", CAPA),
           Spacer(1, 1.2 * cm),
           Paragraph(f"<b>Integrantes:</b> {args.integrantes}", CAPA),
           Spacer(1, 0.6 * cm),
           Paragraph(f"<b>Repositório:</b> {link(args.repo)}", CAPA),
           Paragraph(f"<b>MVP:</b> {link(args.mvp)}", CAPA),
           Paragraph("<i>A tela de cadastro com leitura da conta é a página inicial do MVP. Hospedagem gratuita: "
                     "o primeiro acesso pode levar cerca de 1 minuto para o servidor acordar.</i>",
                     ParagraphStyle("nota", parent=CAPA, fontSize=9, leading=12)) if "preencher" not in args.mvp else Spacer(1, 0),
           Spacer(1, 2 * cm),
           tabela([["Resultado no conjunto de teste (90 fotos)", "Valor"],
                   ["Endereço 100% correto (7 campos)", pct(c["endereco_exato"])],
                   ["Erro de caractere (CER) do endereço", pct(c["cer_medio"])],
                   ["Empresa identificada corretamente", pct(c["classificacao_acuracia"])],
                   ["Documento localizado (IoU >= 0,90)", pct(c.get("deteccao_sucesso_iou90"))],
                   ["Devolveu endereço de cobrança/agência/sede", pct(c["taxa_distrator"])],
                   ["Tempo médio por foto (CPU, 1 núcleo)", f"{c['tempo_medio_ms'] / 1000:.1f} s"]],
                  [W * 0.7, W * 0.3]),
           PageBreak()]

    # ---------------- 1. Papel no MVP
    el += [Paragraph("1. O problema e o papel da visão no MVP", H1),
           Paragraph("O MVP avisa por WhatsApp/SMS quem mora numa área com risco de alagamento ou calor extremo, "
                     "a partir dos avisos da Defesa Civil, do INMET e do Cemaden. Para o alerta ser útil, o sistema "
                     "precisa saber <b>onde a pessoa mora</b> com precisão de CEP e bairro. Digitar endereço no celular "
                     "é lento e cheio de erro, principalmente para idosos e pessoas com pouca familiaridade digital.", P),
           Paragraph("Este componente resolve o cadastro: o cidadão fotografa uma conta de consumo, o comprovante de "
                     "residência mais comum no Brasil, e o sistema preenche o endereço. O fluxo é:", P),
           tabela([["Etapa", "O que acontece", "Quem decide"],
                   ["1. Foto", "Cidadão fotografa conta de luz (Enel), água (Sabesp) ou internet (Claro)", "Cidadão"],
                   ["2. Leitura", "Pipeline de visão devolve endereço, empresa, confiança e campos duvidosos", "Sistema"],
                   ["3. Confirmação", "Tela mostra o trecho da conta e o formulário preenchido; campos duvidosos "
                                      "ficam destacados", "Cidadão (pessoa no circuito)"],
                   ["4. Cadastro", "Endereço confirmado + canal + consentimento são gravados", "Sistema"],
                   ["5. Alertas", "Serviço de alertas cruza CEP/bairro/cidade com as áreas de risco", "Sistema"]],
                  [W * 0.16, W * 0.6, W * 0.24]),
           Spacer(1, 6),
           Paragraph("A leitura nunca é gravada sem confirmação: um endereço errado faria a pessoa receber alertas "
                     "do lugar errado, então a decisão final é sempre do cidadão.", P)]

    # ---------------- 2. Dados
    el += [Paragraph("2. Documentos sintéticos com gabarito", H1),
           Paragraph("Para não usar dados pessoais reais, todos os documentos foram <b>gerados</b> por "
                     "<font face='Courier'>gerador/gerar_faturas.py</font>. Cada fatura imita a estrutura de uma conta "
                     "real (blocos, rótulos, tabelas, código de barras), traz a marca 'DOCUMENTO SINTÉTICO - SEM VALOR' "
                     "e, de propósito, contém <b>endereços concorrentes</b>:", P),
           tabela([["Empresa", "Endereço correto (rótulo)", "Distratores na mesma fatura"],
                   ["Enel", "ENDEREÇO DA UNIDADE CONSUMIDORA (maiúsculas, CEP antes da cidade)", "Sede no rodapé, com CNPJ"],
                   ["Sabesp", "Endereço do Imóvel (abreviações R., Av.)", "Agência de atendimento no topo; sede no rodapé"],
                   ["Claro", "Endereço de Instalação", "Endereço de Cobrança logo acima (diferente em 60% dos casos); sede"]],
                  [W * 0.14, W * 0.48, W * 0.38]),
           Spacer(1, 6),
           Paragraph("Cada fatura vira uma <b>foto de celular simulada</b>: perspectiva e rotação aleatórias (até 18°), "
                     "fundo texturizado, iluminação irregular, sombra, desfoque, ruído e compressão JPEG, em três níveis "
                     "(fácil, médio, difícil). O gabarito (<font face='Courier'>gabarito.json</font>) guarda a empresa, "
                     "os 7 campos do endereço correto, os distratores e os 4 cantos do papel na foto.", P),
           Paragraph(f"Foram gerados dois conjuntos independentes: <b>desenvolvimento</b> (60 fotos, semente 42), usado "
                     f"para ajustar o pipeline, e <b>teste</b> (90 fotos, semente 2026), usado só para as métricas "
                     f"finais. Os nomes de rua são reais, mas números, complementos, CEPs e pessoas são sorteados.", P),
           img("exemplos.png", W),
           PageBreak()]

    # ---------------- 3. Pipeline
    el += [Paragraph("3. Pipeline e técnicas", H1),
           img("etapas.png", W),
           Spacer(1, 6),
           tabela([["Etapa", "Técnica", "Por que"],
                   ["Localizar o documento", "Duas segmentações concorrentes: (a) distância de cor (Lab) ao fundo estimado "
                    "pela moldura da foto; (b) GrabCut com a moldura como fundo certo e o centro como documento. "
                    "Contorno externo, envoltória convexa e approxPolyDP para obter 4 cantos.",
                    "A máscara de 'papel branco' cortava cabeçalhos coloridos; o GrabCut aprende as cores do fundo e "
                    "do documento e resiste a fundos parecidos com o cabeçalho."],
                   ["Escolher o melhor quadrilátero", "Nota = suporte de bordas (Canny ao longo dos 4 lados) x retangularidade "
                    "x fração do lado de fora que parece fundo; penaliza quadriláteros que deixam parte do objeto de fora.",
                    "Torna a escolha objetiva e explicável; evitou cortes do cabeçalho."],
                   ["Corrigir perspectiva", "Homografia (getPerspectiveTransform + warpPerspective) para A4 a 150 dpi "
                    "(1240 x 1754), com margem de 2,5%.", "Linhas de texto ficam retas e com altura constante; a margem "
                    "evita perder a 1ª letra das linhas."],
                   ["Corrigir orientação", "OSD do Tesseract (detecção de orientação do texto) + giro de 90/180/270°; "
                    "se a leitura falhar, testa os outros giros. No servidor, a foto é aberta respeitando a "
                    "rotação EXIF gravada pelo celular.", "Fotos tiradas com o celular deitado ou de cabeça para baixo."],
                   ["Pré-processar", "Non-Local Means (ruído) -> normalização de iluminação (divisão pelo fundo "
                    "estimado por fechamento morfológico) -> CLAHE. Binarização Otsu e ampliação 1,6x como 2ª e 3ª tentativa.",
                    "Remover o ruído antes do CLAHE subiu o acerto de 87% para 93% no desenvolvimento."],
                   ["OCR", "Tesseract 5 (LSTM, idioma por), psm 4; palavras agrupadas em linhas com caixa e confiança; "
                    "linhas com grande vão horizontal são separadas (colunas).", "Precisamos da posição de cada linha "
                    "para montar blocos de endereço."],
                   ["Identificar a empresa", "Palavras-chave no texto (peso 0,7) + matiz dominante do cabeçalho (peso 0,3).",
                    "Duas evidências independentes: funciona mesmo se o logotipo não for lido."],
                   ["Separar o endereço certo", "Cada CEP encontrado vira um candidato; o bloco é montado subindo pelas "
                    "linhas da mesma coluna até um rótulo. Regras pontuam o bloco: rótulo do imóvel (+3), rótulo de "
                    "cobrança/agência (-3), CNPJ/razão social (-4), endereço válido (+1). Nada é devolvido se o melhor "
                    "candidato for negativo.", "Decisão auditável: a API devolve todos os candidatos com nota e motivo."],
                   ["Interpretar e validar", "Regex para CEP (com correção O->0, S->5...), UF, número, complemento; "
                    "expansão de abreviações; checagem CEP x UF pelas faixas dos Correios; campos duvidosos marcados.",
                    "Pega erros de OCR que parecem plausíveis (ex.: CEP de SP com UF RJ)."]],
                  [W * 0.18, W * 0.5, W * 0.32]),
           PageBreak()]

    # ---------------- 4. Resultados
    el += [Paragraph("4. Métricas", H1),
           Paragraph("Todas as métricas abaixo são do <b>conjunto de teste</b> (90 fotos nunca usadas no ajuste). "
                     "Um endereço só conta como correto se os 7 campos baterem com o gabarito (comparação sem acento e "
                     "sem diferença de maiúsculas). O CER é a distância de edição entre o endereço lido e o gabarito, "
                     "dividida pelo tamanho do gabarito.", P)]
    linhas = [["Métrica", "Sem correção de perspectiva", "Pipeline completo", "Fatura escaneada (teto)"]]
    def g(d, k):
        return pct(d[k]) if d and d.get(k) is not None else "-"
    for nome, k in (("Endereço 100% correto", "endereco_exato"), ("CER médio", "cer_medio"),
                    ("Empresa correta", "classificacao_acuracia"), ("Endereço válido (CEP x UF etc.)", "validos"),
                    ("Devolveu distrator", "taxa_distrator")):
        linhas.append([nome, g(s, k), g(c, k), g(pl, k)])
    linhas.append(["Tempo médio", *(f"{d['tempo_medio_ms'] / 1000:.1f} s" if d else "-" for d in (s, c, pl))])
    el += [tabela(linhas, [W * 0.31, W * 0.23, W * 0.23, W * 0.23]), Spacer(1, 6),
           KeepTogether([img("ablacao.png", W * 0.7), Paragraph(
               "Estudo de ablação: a mesma foto vai direto para o OCR (sem detectar nem retificar), passa pelo pipeline "
               "completo, ou é substituída pela fatura plana (o melhor caso possível).", PEQ)]),
           img("campos.png", W * 0.75)]

    linhas = [["Recorte", "N", "Endereço exato", "CER", "Empresa", "IoU médio"]]
    for grupo, chaves in (("por_empresa", ("enel", "sabesp", "claro")), ("por_nivel", ("facil", "medio", "dificil"))):
        for k in chaves:
            d = met["completo"][grupo][k]
            linhas.append([k.capitalize().replace("Facil", "Fácil").replace("Medio", "Médio").replace("Dificil", "Difícil"),
                           d["n"], pct(d["endereco_exato"]), pct(d["cer_medio"]), pct(d["classificacao_acuracia"]),
                           f"{d.get('deteccao_iou_medio', 0):.3f}"])
    el += [Paragraph("Por empresa e por nível de dificuldade (pipeline completo)", H2),
           tabela(linhas, [W * 0.2, W * 0.1, W * 0.2, W * 0.15, W * 0.15, W * 0.2])]

    mc = met["completo"]["matriz_confusao"]
    colunas = ["enel", "sabesp", "claro", "nenhuma"]
    linhas = [["Real \\ Previsto", *colunas]] + [[r, *[mc[r].get(cn, 0) for cn in colunas]] for r in ("enel", "sabesp", "claro")]
    el += [Paragraph("Matriz de confusão da classificação de empresa", H2),
           tabela(linhas, [W * 0.24] + [W * 0.19] * 4),
           Paragraph("Confiança e revisão", H2),
           Paragraph(f"O pipeline calcula uma confiança (OCR x validação x margem para o 2º candidato). Com o limiar de "
                     f"0,75, <b>{pct(c['cobertura_confiavel'])}</b> das fotos saem marcadas como confiáveis e, nelas, o "
                     f"acerto é de <b>{pct(c['acuracia_quando_confiavel'])}</b>; nas marcadas para revisão o acerto cai "
                     f"para {pct(c['acuracia_quando_revisar'])}. Ou seja, a confiança aponta onde o cidadão deve olhar.", P)]
    if dev:
        d = dev["completo"]["geral"]
        el.append(Paragraph(f"Para comparação, no conjunto de desenvolvimento o acerto exato foi "
                            f"{pct(d['endereco_exato'])} (CER {pct(d['cer_medio'])}).", PEQ))
    el.append(PageBreak())

    # ---------------- 5. Integração
    el += [Paragraph("5. Uso do endereço no MVP (integração)", H1),
           Paragraph("O componente roda como uma API FastAPI empacotada em Docker (com Tesseract) e está publicado dentro do "
                     "MVP, no Render. A tela de cadastro do MVP consome a API:", P),
           tabela([["Rota", "Função"],
                   ["POST /api/v1/enderecos/extrair", "Recebe a foto; devolve empresa, endereço, confiança, campos a revisar, "
                    "candidatos com motivos e o recorte do documento onde o endereço foi lido."],
                   ["POST /api/v1/enderecos/validar", "Valida um endereço digitado (entrada manual)."],
                   ["POST /api/v1/cadastros", "Grava o endereço confirmado, canal (WhatsApp/SMS), consentimento, origem "
                    "(ocr/manual) e quais campos o cidadão corrigiu."],
                   ["GET /api/v1/metricas", "Taxa de endereços aceitos sem correção e correções por campo (métrica de uso real)."],
                   ["DELETE /api/v1/cadastros/{id}", "Exclusão a pedido do titular (LGPD)."]],
                  [W * 0.38, W * 0.62]),
           Spacer(1, 6)]
    if (FIG / "tela.png").exists():
        el += [img("tela.png", W * 0.45),
               Paragraph("Tela de confirmação: campos lidos já preenchidos, trecho da conta para conferência e campos "
                         "duvidosos destacados em amarelo.", PEQ)]
    el += [Paragraph("Decisões de design da integração", H2),
           Paragraph("• <b>Pessoa no circuito:</b> nada é cadastrado sem o clique em 'Confirmar'. "
                     "• <b>Plano B:</b> se a foto falhar ou não houver conexão boa, o cidadão digita o endereço "
                     "(mesma validação). • <b>Acessível:</b> rótulos em todos os campos, foco visível, navegação por "
                     "teclado, mensagens em região <i>aria-live</i>, alto contraste e tema escuro. "
                     "• <b>Leve:</b> a foto é reduzida para 2000 px no servidor; a resposta tem poucos KB.", P)]

    # ---------------- 6. Testes
    el += [PageBreak(), Paragraph("6. Testes automatizados", H1),
           Paragraph("29 testes com pytest (<font face='Courier'>pytest -q</font>), todos passando:", P),
           tabela([["Arquivo", "O que cobre"],
                   ["tests/test_endereco.py", "Interpretação dos 3 formatos de fatura, ruído de OCR (R-, O no CEP, lixo de "
                    "outra coluna), rua com número no nome, CEP x UF, campos faltando, nº de hidrômetro que não pode virar CEP."],
                   ["tests/test_pipeline.py", "Ordenação de cantos, detecção (IoU > 0,90) nas 3 empresas, retificação em A4, "
                    "foto sem documento, ponta a ponta (empresa, CEP, logradouro, número), foto girada 90/180/270° e imagem sem conta que não pode "
                    "inventar endereço."],
                   ["tests/test_api.py", "Health check, consentimento obrigatório, CEP de outro estado, cadastro + métricas + "
                    "exclusão, arquivo que não é imagem, rotação EXIF do celular, extração a partir de uma foto."],
                   ["avaliacao/avaliar.py", "Avaliação em lote contra o gabarito: métricas por campo, empresa, nível, "
                    "ablação e matriz de confusão (resultados/*.json e .csv)."]],
                  [W * 0.3, W * 0.7])]

    # ---------------- 7. Limitações
    el += [Paragraph("7. Limitações e próximos passos", H1),
           Paragraph("• <b>Dados sintéticos:</b> as faturas imitam a estrutura das reais, mas contas verdadeiras têm mais "
                     "variação (versões de layout, papel amassado, reflexo, foto parcial). Próximo passo: coletar, com "
                     "consentimento, fotos reais anonimizadas para validar. "
                     "• <b>Endereço de cobrança:</b> na Claro, quando o rótulo 'Endereço de Cobrança' sai ilegível, o "
                     "sistema pode devolver esse endereço no lugar do de instalação. "
                     "• <b>Fotos muito degradadas:</b> os erros restantes vêm do OCR em fotos difíceis (letras trocadas no "
                     "bairro e no complemento). A tela de confirmação existe para isso. "
                     "• <b>Layout fixo por empresa:</b> os rótulos de cada empresa estão em listas; uma nova empresa exige "
                     "incluir seus rótulos (a parte genérica, por CEP, continua funcionando). "
                     "• <b>Endereços sem CEP legível</b> caem num modo mais fraco (bloco abaixo do rótulo). "
                     "• <b>Velocidade:</b> cerca de 4 s por foto em CPU; aceitável num cadastro único, e pode cair "
                     "com OCR só na região do endereço. • <b>Próximo passo de dados:</b> confirmar o CEP numa base "
                     "oficial (ViaCEP/Correios) e georreferenciar o endereço para cruzar com polígonos de risco.", P)]

    # ---------------- 8. LGPD
    el += [Paragraph("8. LGPD e IA responsável", H1),
           Paragraph("• Nenhum dado pessoal real no desenvolvimento nem nos testes. • A foto é processada em memória e "
                     "descartada; valores da conta, nome e número de cliente não são guardados. • Só ficam o endereço "
                     "confirmado e o celular, com consentimento explícito e finalidade única (alertas); o contato aparece "
                     "mascarado nas respostas; exclusão disponível pela API. • A decisão é explicável (candidatos, notas e "
                     "motivos) e sempre confirmada por uma pessoa. • O sistema prefere não responder a responder errado: "
                     "blocos reconhecidos como endereço da empresa, agência ou cobrança são descartados. Quando o OCR não "
                     f"consegue ler o rótulo, isso ainda escapa ({pct(c['taxa_distrator'])} das fotos de teste), e é mais um "
                     "motivo para a confirmação obrigatória.", P)]

    def rodape(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(2 * cm, 1.2 * cm, "GS 2026.2 · CitizenTech · Applied Computer Vision · Extração Automática de Endereços")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, str(doc.page))
        canvas.restoreState()

    saida = Path(args.saida)
    SimpleDocTemplate(str(saida), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                      bottomMargin=1.8 * cm, title="Extração Automática de Endereços - GS CitizenTech",
                      author="Equipe GS 4ESPR").build(el, onFirstPage=rodape, onLaterPages=rodape)
    print("PDF gerado em", saida)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="https://github.com/LucasSouza-Engineer/GS-APPLIED")
    ap.add_argument("--mvp", default="https://alerta-enchente-calor.onrender.com")
    ap.add_argument("--integrantes", default="(preencher: nome e RM de cada integrante)")
    ap.add_argument("--saida", default=str(RAIZ / "docs" / "GS_Visao_Extracao_Enderecos.pdf"))
    montar(ap.parse_args())
