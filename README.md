# Pipeline de dados · alerta de enchente e calor por endereço

GS 2026.2 CitizenTech · **Big Data Architecture & Data Integration** (Profa. Ana Machado) · FIAP 4ESPR

Pipeline orquestrado no **Apache Airflow** que vai do dado bruto do **INMET** e do **Cemaden** até a tabela
de **risco por CEP** e a **fila de alertas** que o MVP usa para avisar o cidadão por WhatsApp/SMS.

```
INMET (estações, avisos) ─┐
Cemaden (pluviômetros) ───┤   BRONZE        SILVER          GOLD                 ┌─> MVP (SQLite): risco_por_cep, fila_alertas
Cadastros do MVP (SQLite) ┼─> JSON bruto ─> Parquet limpo ─> risco por CEP ─> QA ┤
Tabela CEP / BrasilAPI ───┘                                 fila de alertas      └─> Data warehouse (Postgres) -> Power BI
```

## Entrega

| Item | Link |
|---|---|
| Vídeo do pipeline rodando | https://youtu.be/LH2OI6K8ZRc |
| PDF: arquitetura e dicionário de dados | [`docs/GS_BigData_Pipeline.pdf`](docs/GS_BigData_Pipeline.pdf) |
| Prints de uma execução | [`docs/prints/`](docs/prints/) |
| DAG do Airflow | [`dags/alerta_enchente_calor.py`](dags/alerta_enchente_calor.py) |
| MVP no ar | https://alerta-enchente-calor.onrender.com |

**Integrantes:** Kaio Vinicius Meireles Alves (RM553282) · Lucas Alves de Souza (RM553956) ·
Henrique Rafael Gomes (RM553945) · Guilherme Fernandes de Freitas (RM554323) ·
João Pedro Chizzolini de Freitas (RM553172)

## Como rodar (um comando)

Pré-requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/) aberto.

```bash
docker compose up -d
```

1. Espere ~2 minutos e abra **http://localhost:8080** (usuário `admin`, senha `admin`).
2. A DAG **`alerta_enchente_calor`** já vem ligada e roda sozinha a cada hora. Para rodar agora, clique no ▶ (Trigger DAG).
3. Em ~10 segundos todas as 15 tasks ficam verdes.

Parar: `docker compose down` (os dados ficam). Apagar tudo e começar do zero: `docker compose down -v` e apagar `dados/lake` e `dados/mvp`.

> No Linux, antes do primeiro `up`, rode `echo AIRFLOW_UID=$(id -u) > .env` para os arquivos gerados ficarem no seu usuário.

### Onde ver o resultado

| O quê | Onde |
|---|---|
| Tabela que o MVP lê | `dados/mvp/cadastros.sqlite3` → tabelas `risco_por_cep` e `fila_alertas` |
| Mesmo dado em planilha | `dados/lake/gold/risco_por_cep/atual.csv`, `dados/lake/gold/fila_alertas/atual.csv` |
| Camadas do data lake | `dados/lake/bronze`, `silver`, `gold` (particionadas por `dt=AAAA-MM-DD/HHMM`) |
| Relatório de qualidade | `dados/lake/gold/qualidade/` e log da task `checar_qualidade` |
| Data warehouse (BI) | Postgres em `localhost:5432`, banco `citizentech`, usuário `airflow`, senha `gs2026pg`, schema `dw` |

Consultas de exemplo:

```bash
# risco por região (DW)
docker compose exec postgres psql -U airflow -d citizentech -c \
  "select regiao, chuva_24h_mm, temp_max_24h_c, situacao from dw.fato_risco_regiao
   where referencia_utc = (select max(referencia_utc) from dw.fato_risco_regiao) order by nivel_geral desc;"
```

```sql
-- o que o MVP faz para saber o risco de um cadastro (SQLite)
SELECT r.situacao, r.motivo_enchente, r.motivo_calor
FROM cadastros c JOIN risco_por_cep r ON r.cep = replace(c.cep, '-', '')
WHERE c.id = :id;

-- o que o disparador de WhatsApp/SMS lê
SELECT f.id_alerta, f.canal, c.contato, f.mensagem
FROM fila_alertas f JOIN cadastros c ON c.id = f.id_cadastro
WHERE f.status = 'pendente';
```

## Fontes e modo offline

| Fonte | Endpoint | Precisa de |
|---|---|---|
| INMET estações | `apitempo.inmet.gov.br/estacoes/T` | nada |
| INMET observações horárias | `apitempo.inmet.gov.br/token/estacao/...` | token gratuito do INMET (`INMET_TOKEN`) |
| INMET avisos | `apiprevmet3.inmet.gov.br/avisos/ativos` | nada |
| Cemaden pluviômetros | `sjc.salvar.cemaden.gov.br/.../getJson2.php?uf=SP` | nada |
| Coordenada do CEP | `brasilapi.com.br/api/cep/v2/{cep}` | nada |
| Cadastros | SQLite do MVP | — |

`PIPELINE_MODO` (no `.env`, ver `.env.example`):

* `auto` (padrão): tenta a fonte real; se falhar, usa a **amostra local** em `dados/amostra/` (mesmo formato da API).
* `offline`: só amostra. Use na apresentação se a internet estiver ruim.
* `online`: só fonte real; a task falha se a fonte cair.

Toda tabela tem a coluna `origem` (`api`, `amostra` ou `mvp_sqlite`) dizendo de onde o dado veio.
A amostra é um cenário de fim de tarde quente com temporal na Zona Leste, Guarulhos e Franco da Rocha;
os horários são deslocados para a hora da execução para a demo se comportar como dado ao vivo.
Para regenerar: `python scripts/gerar_amostra.py`.

## Integração com o MVP (API de cadastro)

O pipeline lê a tabela `cadastros` do mesmo SQLite que a API de cadastro do MVP (`visao-enderecos/api/app.py`) grava.
MVP publicado em https://alerta-enchente-calor.onrender.com.
Para apontar para o banco real da API, no `.env`:

```
MVP_DADOS_DIR=../visao-enderecos/dados
```

Sem cadastros no banco, o pipeline usa `dados/amostra/cadastros_exemplo.json`. Para encher o banco do MVP com
os cadastros de exemplo (mesmo esquema da API) e ver a integração funcionando: `python scripts/popular_cadastros_mvp.py`.

**LGPD:** o telefone nunca entra no data lake. A extração lê só id e endereço; o disparador busca o contato pelo id.

## Sem Docker

```bash
pip install -r requirements.txt
python scripts/rodar_local.py      # roda o pipeline inteiro uma vez (sem o DW)
pytest                             # 7 testes: regras, qualidade, idempotência, integração com o SQLite
```

## Estrutura

```
docker-compose.yaml          Airflow 2.10 (webserver + scheduler, LocalExecutor) + Postgres
dags/
  alerta_enchente_calor.py   a DAG (task groups bronze/silver, gold, qualidade, publicação)
  citizentech/
    config.py                variáveis de ambiente
    fontes.py                extração -> bronze (com fallback para amostra)
    transformacao.py         bronze -> silver (limpeza, tipagem, geocodificação do CEP)
    risco.py                 regras de risco e fila de alertas (gold)
    qualidade.py             12 regras de qualidade (erro bloqueia publicação)
    carga.py                 publicação no MVP (SQLite) e no DW (Postgres)
    etapas.py                etapas gold e execução completa sem Airflow
dados/amostra/               amostra offline no formato das APIs + tabela CEP -> região
scripts/                     gerar_amostra, popular_cadastros_mvp, rodar_local
sql/init_dw.sql              cria o banco do data warehouse
tests/                       pytest
docs/                        PDF, diagrama, prints e scripts que geram o PDF
ROTEIRO_GRAVACAO.md          passo a passo para gravar o vídeo/prints da entrega
```
