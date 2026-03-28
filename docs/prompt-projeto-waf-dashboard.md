# Projeto: Dashboard de Indicadores de Proteção AWS WAF - Manole

## Contexto

A Manole possui sites protegidos pelo AWS WAF. Preciso gerar indicadores de proteção do WAF para que a diretoria tenha visibilidade do nível de proteção. O projeto está no repositório `manole-waf-dashboard`.

---

## Infraestrutura Disponível

| Componente       | Versão           |
|------------------|------------------|
| OS               | Ubuntu 18.04 LTS |
| Docker           | 18.06.0-ce       |
| docker-compose   | 1.29.2           |
| Apache           | 2.4.29           |
| CPU              | 2x Intel Xeon E5-2686 v4 @ 2.30GHz |
| RAM              | 3.9 GB           |
| GPU              | Não disponível   |
| Servidor         | root@ip-172-30-0-60 |

---

## Restrições

- Sem acesso ao AWS CLI (apenas Console Web da AWS)
- Sem permissão para exportar logs para S3 (download manual dos dados pelo console)
- Coleta de dados é manual (sampled requests do console, máximo 3h por vez)

---

## Objetivo

1. **Inventário dos sites** atualmente protegidos pelo WAF, com quais regras estão em modo **Monitor (Count)** e quais estão em modo **Bloqueio (Block)**
2. **Dashboard Grafana** com gráficos visuais para a diretoria

---

## Arquitetura da Solução

```
Console AWS WAF (manual) → Download CSV → Script Python (ingestão) → SQLite → Grafana (Docker)
```

- Grafana 9.5 via Docker com plugin `frser-sqlite-datasource`
- Script Python para ingerir CSVs no SQLite
- Processo de atualização manual (1x por dia útil)

---

## Estrutura de Arquivos do Projeto

```
manole-waf-dashboard/
├── docs/
│   └── plano-inicial.md              (já existe - atualize se necessário)
├── docker-compose.yml
├── atualizar.sh
├── data/
│   ├── inventario_sites.csv           (template com dados de exemplo)
│   └── waf_logs.csv                   (template com dados de exemplo)
├── scripts/
│   └── ingest_data.py
└── grafana/
    ├── provisioning/
    │   ├── datasources/
    │   │   └── sqlite.yml
    │   └── dashboards/
    │       └── dashboards.yml
    └── dashboards/
        └── waf-manole-dashboard.json
```

---

## Tarefas de Implementação

### Tarefa 1 — Analisar o plano existente

Leia o arquivo `docs/plano-inicial.md` no repositório `manole-waf-dashboard`. Ele contém o plano detalhado elaborado previamente. Analise e verifique se precisa de ajustes ou melhorias.

### Tarefa 2 — docker-compose.yml

Criar `docker-compose.yml` na raiz do repositório:

- Grafana 9.5.20 na porta 3000
- Plugin `frser-sqlite-datasource` instalado via variável de ambiente `GF_INSTALL_PLUGINS`
- Credenciais: admin / Manole@WAF2026
- Volumes mapeando:
  - `./grafana/provisioning` → `/etc/grafana/provisioning`
  - `./grafana/dashboards` → `/var/lib/grafana/dashboards`
  - `./data` → `/var/lib/grafana/data-waf`
- Restart policy: `unless-stopped`

### Tarefa 3 — Script de ingestão (scripts/ingest_data.py)

Criar `scripts/ingest_data.py` em Python 3:

- Lê os CSVs de `data/inventario_sites.csv` e `data/waf_logs.csv`
- Ingere no banco SQLite em `data/waf_dashboard.db`
- Três tabelas:
  - `inventario_sites`: web_acl, site, recurso_tipo, regiao, regra, tipo_regra, acao, data_coleta
  - `waf_logs`: timestamp, web_acl, regra, acao, source_ip, uri, country, http_method, status_code, data_ingestao
  - `resumo_diario`: data, web_acl, total_requests, total_blocked, total_counted, total_allowed
- O inventário é reimportado a cada execução (DELETE + INSERT)
- Os logs evitam duplicatas (verificar timestamp + source_ip + uri antes de inserir)
- Gera resumo diário automaticamente após importação

### Tarefa 4 — Provisioning do Grafana

**`grafana/provisioning/datasources/sqlite.yml`:**
- Datasource tipo `frser-sqlite-datasource`
- Path: `/var/lib/grafana/data-waf/waf_dashboard.db`
- Nome: `WAF-SQLite`
- Default: true

**`grafana/provisioning/dashboards/dashboards.yml`:**
- Provider tipo file
- Path: `/var/lib/grafana/dashboards`
- Folder: `WAF Manole`

### Tarefa 5 — Dashboard Grafana (grafana/dashboards/waf-manole-dashboard.json)

Dashboard JSON com **9 painéis**:

| # | Painel | Tipo | Query SQL |
|---|--------|------|-----------|
| 1 | Inventário de Sites Protegidos | Tabela | `SELECT DISTINCT site, web_acl, recurso_tipo, regiao FROM inventario_sites` |
| 2 | Regras por Modo: Bloqueio vs Monitor | Tabela (com cores) | `SELECT site, web_acl, regra, tipo_regra, acao FROM inventario_sites` — mapear Block→🛡️ BLOQUEIO (verde), Count→👁️ MONITOR (amarelo) |
| 3 | Proporção Bloqueio/Monitor | Pizza | `SELECT acao, COUNT(*) FROM inventario_sites GROUP BY acao` |
| 4 | % Cobertura de Proteção por Site | Gauge | `SELECT site, ROUND(100.0 * SUM(CASE WHEN acao='Block' THEN 1 ELSE 0 END) / COUNT(*), 1) FROM inventario_sites GROUP BY site` — thresholds: 0=vermelho, 50=amarelo, 80=verde |
| 5 | Requests Bloqueados vs Monitorados por dia | Barras | `SELECT data, total_blocked, total_counted FROM resumo_diario` |
| 6 | Top 10 IPs Bloqueados | Tabela | `SELECT source_ip, country, COUNT(*) FROM waf_logs WHERE acao='BLOCK' GROUP BY source_ip ORDER BY COUNT(*) DESC LIMIT 10` |
| 7 | Top 10 URIs Atacadas | Tabela | `SELECT uri, COUNT(*), bloqueados, monitorados FROM waf_logs GROUP BY uri ORDER BY COUNT(*) DESC LIMIT 10` |
| 8 | Ataques por País de Origem | Pizza | `SELECT country, COUNT(*) FROM waf_logs WHERE acao='BLOCK' GROUP BY country LIMIT 15` |
| 9 | Regras Mais Acionadas | Barras | `SELECT regra, bloqueios, monitoramentos FROM waf_logs GROUP BY regra` |

### Tarefa 6 — Templates CSV com dados de exemplo

**`data/inventario_sites.csv`:**
```csv
web_acl,site,recurso_tipo,regiao,regra,tipo_regra,acao
ACL-Manole-Prod,www.manole.com.br,CloudFront,us-east-1,AWS-AWSManagedRulesCommonRuleSet,Managed,Block
ACL-Manole-Prod,www.manole.com.br,CloudFront,us-east-1,AWS-AWSManagedRulesSQLiRuleSet,Managed,Count
ACL-Manole-Prod,www.manole.com.br,CloudFront,us-east-1,RateLimitRule,Rate-based,Block
ACL-Manole-Loja,loja.manole.com.br,ALB,sa-east-1,AWS-AWSManagedRulesKnownBadInputsRuleSet,Managed,Block
ACL-Manole-Loja,loja.manole.com.br,ALB,sa-east-1,AWS-AWSManagedRulesBotControlRuleSet,Managed,Count
```

**`data/waf_logs.csv`:**
```csv
timestamp,web_acl,regra,acao,source_ip,uri,country,http_method,status_code
2026-03-28T10:15:00Z,ACL-Manole-Prod,AWS-AWSManagedRulesCommonRuleSet,BLOCK,203.0.113.50,/admin,CN,GET,403
2026-03-28T10:16:00Z,ACL-Manole-Prod,AWS-AWSManagedRulesSQLiRuleSet,COUNT,198.51.100.23,/search?q=1' OR 1=1,US,GET,200
2026-03-28T10:17:00Z,ACL-Manole-Loja,RateLimitRule,BLOCK,192.0.2.100,/api/login,BR,POST,403
```

### Tarefa 7 — Script de conveniência (atualizar.sh)

Criar `atualizar.sh` na raiz:
```bash
#!/bin/bash
echo "=== Atualizando dados WAF Manole ==="
echo "[1/2] Ingerindo dados..."
cd /root/waf-dashboard
python3 scripts/ingest_data.py
echo "[2/2] Verificando Grafana..."
docker ps | grep grafana-waf || docker-compose up -d
echo "=== Concluido! Acesse http://$(hostname -I | awk '{print $1}'):3000 ==="
```
Tornar executável com `chmod +x atualizar.sh`.

### Tarefa 8 — Atualizar docs/plano-inicial.md

Atualizar o arquivo `docs/plano-inicial.md` com qualquer alteração feita durante a implementação. Incluir seção de indicadores-chave para a diretoria:

| Indicador | Descrição | Meta Sugerida |
|-----------|-----------|---------------|
| % Regras em Bloqueio | Percentual de regras ativas em modo Block | > 80% |
| Total de Ataques Bloqueados | Quantidade de requests bloqueados no período | Quanto maior, melhor |
| Sites Protegidos | Quantidade de sites cobertos pelo WAF | 100% dos sites públicos |
| Regras em Monitor | Regras ainda em modo Count | Migrar para Block após validação |
| Top Origens de Ataque | Países/IPs com mais tentativas | Avaliar geo-blocking |

### Tarefa 9 — Commit e Push

Fazer commit de todos os arquivos e push para o repositório `manole-waf-dashboard`.
