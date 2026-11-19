# Visão Computacional · Extração automática de endereço

Componente **Visão** do MVP CitizenTech *Alerta de enchente e calor por endereço*
(Global Solution FIAP 2026.2, Engenharia de Software 4º ano, disciplina **Applied Computer Vision**).

O cidadão fotografa uma conta de **luz (Enel)**, **água (Sabesp)** ou **internet (Claro)**.
O pipeline encontra o documento na foto, corrige a perspectiva, identifica a empresa,
lê o texto por OCR e separa o **endereço do imóvel** dos outros endereços da fatura
(cobrança, agência, sede da empresa). O endereço é validado e mostrado para o cidadão
**confirmar ou corrigir** antes de entrar no cadastro que define para onde vão os alertas.

## Ficha Técnica do MVP

| Item | Conteúdo |
|---|---|
| Produto | Alerta de enchente e calor por endereço (nome provisório) |
| Cidadão e território | Moradores de áreas de risco de alagamento e ilhas de calor, começando pela Grande São Paulo |
| Problema | Alertas da Defesa Civil e do INMET chegam genéricos, por município, e não dizem se a *sua rua* está em risco |
| Proposta de valor | Cadastro em 1 minuto com a foto de uma conta e alertas por WhatsApp/SMS só quando o risco é na sua região |
| Componente Visão | Leitura automática do endereço do comprovante (este repositório) |
| Fontes de dados | INMET, Cemaden, boletins da Defesa Civil; faturas sintéticas para testar a visão |
| Modelos de IA | Tesseract 5 (LSTM) para OCR + visão clássica (OpenCV): GrabCut, homografia, CLAHE |
| Repositório | https://github.com/LucasSouza-Engineer/GS-APPLIED |
| URL do MVP | https://alerta-enchente-calor.onrender.com (plano gratuito: o 1º acesso pode levar ~1 min) |
| Indicadores de impacto | % de cadastros concluídos; % de endereços aceitos sem correção; tempo de cadastro |
| ODS | 11 (cidades sustentáveis) e 13 (ação contra a mudança do clima) |

## Resultados (conjunto de teste separado, 90 fotos sintéticas)

| Métrica | Sem correção de perspectiva | **Pipeline completo** | Fatura escaneada (teto) |
|---|---|---|---|
| Endereço 100% correto (7 campos) | 41,1% | **86,7%** | 97,8% |
| Erro de caractere (CER) | 48,7% | **6,8%** | 0,0% |
| Empresa correta | 65,6% | **100%** | 100% |
| Documento localizado (IoU ≥ 0,90) | – | **97,8%** | – |
| Devolveu endereço de cobrança/sede | 2,2% | **3,3%** | 0% |

Quando o sistema se diz confiável (91% das fotos), acerta 93,9%; quando pede revisão, acerta 12,5%.
Detalhes em [`resultados/teste/metricas.json`](resultados/teste/metricas.json) e no PDF em `docs/`.
O conjunto de **desenvolvimento** (60 fotos, usado para ajustar) teve 93,3%; o de **teste** (90 fotos) não foi usado no ajuste.

## Como rodar

Pré-requisitos: Python 3.10+ e Tesseract com o idioma português.

```bash
# Ubuntu/Debian
sudo apt install tesseract-ocr tesseract-ocr-por
# macOS
brew install tesseract tesseract-lang
# Windows: instalador do UB Mannheim (marque "Portuguese") e adicione ao PATH
```

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# 1) gerar as faturas sintéticas
#    as fotos de teste já vêm em dados/teste; este comando recria também as versões
#    "escaneadas" (planas) e o conjunto de desenvolvimento (mesmas sementes = mesmos arquivos)
python gerador/gerar_faturas.py --por-empresa 30 --seed 2026 --saida dados/teste
python gerador/gerar_faturas.py --por-empresa 20 --seed 42 --saida dados/desenvolvimento

# 2) avaliar (métricas + estudo de ablação)
python avaliacao/avaliar.py --dados dados/teste --saida resultados/teste

# 3) testes automatizados
pytest -q

# 4) subir a API + tela de cadastro em http://localhost:8000
uvicorn api.app:app --reload
```

Com Docker (a mesma imagem serve para publicar em qualquer nuvem que rode contêiner):

```bash
docker build -t visao-enderecos .
docker run -p 8000:8000 visao-enderecos
```

## Como usar no código

```python
import cv2
from visao_enderecos import processar   # adicione src/ ao PYTHONPATH

r = processar(cv2.imread("conta.jpg"))
r.empresa          # 'enel' | 'sabesp' | 'claro' | None
r.endereco         # {'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'uf', 'cep'}
r.campos_revisar   # campos que o cidadão deve conferir
r.candidatos       # todos os endereços achados, com nota e motivo (decisão auditável)
```

## API

| Método | Rota | Para quê |
|---|---|---|
| `POST` | `/api/v1/enderecos/extrair` | recebe a foto (`multipart`, campo `arquivo`) e devolve endereço, confiança, campos a revisar e o trecho do documento lido |
| `POST` | `/api/v1/enderecos/validar` | valida um endereço digitado (CEP x UF, campos obrigatórios) |
| `POST` | `/api/v1/cadastros` | grava o endereço **confirmado pelo cidadão**, o canal (WhatsApp/SMS) e o consentimento |
| `GET` | `/api/v1/cadastros/{id}` | consulta (contato mascarado) |
| `DELETE` | `/api/v1/cadastros/{id}` | exclusão a pedido do titular (LGPD) |
| `GET` | `/api/v1/metricas` | % de endereços aceitos sem correção e correções por campo |
| `GET` | `/api/v1/saude` | health check para o monitoramento |

Documentação interativa em `/docs` (Swagger).

## Estrutura

```
src/visao_enderecos/
  documento.py         detecção do documento (GrabCut + cor de fundo) e homografia
  preprocessamento.py  ruído (NLM), iluminação, CLAHE, binarização
  ocr.py               Tesseract -> linhas com posição e confiança
  classificador.py     empresa por palavras-chave + cor do cabeçalho
  extrator.py          escolhe o endereço do imóvel entre os candidatos (regras explicáveis)
  endereco.py          interpretação, normalização e validação (CEP x UF)
  pipeline.py          orquestra tudo e calcula a confiança
api/                   FastAPI + tela de confirmação (HTML acessível)
gerador/               gerador de faturas e fotos sintéticas com gabarito
avaliacao/             métricas e ablação
tests/                 pytest
dados/teste/           90 fotos sintéticas de teste + gabarito.json
docs/                  PDF de entrega
```

## Privacidade (LGPD)

* Nenhum dado pessoal real: todas as faturas de teste são geradas e marcadas como sintéticas.
* A foto é processada em memória e descartada; não guardamos imagem nem valores da conta.
* Só o endereço confirmado e o contato são gravados, com consentimento explícito, e podem ser excluídos pela API.
