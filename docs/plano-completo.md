# Plano de Dashboard de Indicadores de Proteção AWS WAF - Manole

## 1. Visão Geral

**Objetivo:** Gerar indicadores visuais de proteção do AWS WAF para dar visibilidade à diretoria da Manole sobre o nível de proteção dos sites.

**Repositório:** `manole-waf-dashboard`
**Servidor:** `root@ip-172-30-0-60` — `/opt/manole-waf-dashboard/`

**Infraestrutura disponível:**

| Componente       | Versão          |
|------------------|-----------------|
| OS               | Ubuntu 18.04 LTS |
| Docker           | 18.06.0-ce      |
| docker-compose   | 1.29.2          |
| Apache           | 2.4.29          |
| CPU              | 2x Intel Xeon E5-2686 v4 @ 2.30GHz |
| RAM              | 3.9 GB          |
| GPU              | Não disponível  |

**Restrições:**
- Sem acesso ao AWS CLI (apenas Console Web da AWS)
- Sem permissão para exportar logs para S3
- Dados do WAF obtidos manualmente via Console Web (sampled requests, máximo 3h por vez)

---

## 2. Arquitetura da Solução

```
Console AWS WAF (manual)
        │
        ▼
  Download CSV (logs + inventário)
        │
        ▼
  Script de Ingestão (Python 3 — stdlib only, sem dependências externas)
        │
        ▼
  SQLite (banco local leve — data/waf_dashboard.db)
        │
        ▼
  Grafana 9.5.20 (via Docker)
  Plugin: frser-sqlite-datasource v4.0.1
        │
        ▼
  Dashboard com 9 painéis
```

---

## 3. Estrutura de Arquivos

```
/opt/manole-waf-dashboard/
├── docs/
│   └── plano-completo.md              (este documento)
├── docker-compose.yml                 (Grafana via Docker)
├── atualizar.sh                       (script de conveniência)
├── data/
│   ├── inventario_sites.csv           (inventário dos sites e regras WAF)
│   ├── waf_logs.csv                   (logs de requests do WAF)
│   └── waf_dashboard.db              (banco SQLite — gerado pelo script)
├── scripts/
│   └── ingest_data.py                 (ingestão CSV → SQLite)
└── grafana/
    ├── provisioning/
    │   ├── datasources/
    │   │   └── sqlite.yml             (datasource SQLite automático)
    │   └── dashboards/
    │       └── dashboards.yml         (carregamento automático de dashboards)
    └── dashboards/
        └── waf-manole-dashboard.json  (dashboard com 9 painéis)
```

---

## 4. Etapa 1 — Coleta de Dados (Manual)

### 4.1 Inventário de Sites e Regras

1. Acesse **AWS Console > WAF & Shield > Web ACLs**
2. Para cada Web ACL, anote:
   - Nome da Web ACL
   - Recurso associado (CloudFront ou ALB) → este é o "site protegido"
   - Região
3. Para cada Web ACL, clique em **Rules** e anote:
   - Nome da regra
   - Ação: **Block** (bloqueio) ou **Count** (monitor/contagem)
   - Tipo: Managed Rule Group, Rate-based, Custom, etc.

> **Ação "Count" = Modo Monitor** (detecta mas não bloqueia)
> **Ação "Block" = Modo Bloqueio** (bloqueia efetivamente)

### 4.2 Modelo do CSV de Inventário

Arquivo: `data/inventario_sites.csv`

```csv
web_acl,site,recurso_tipo,regiao,regra,tipo_regra,acao
ACL-Manole-Prod,www.manole.com.br,CloudFront,us-east-1,AWS-AWSManagedRulesCommonRuleSet,Managed,Block
ACL-Manole-Prod,www.manole.com.br,CloudFront,us-east-1,AWS-AWSManagedRulesSQLiRuleSet,Managed,Count
ACL-Manole-Prod,www.manole.com.br,CloudFront,us-east-1,RateLimitRule,Rate-based,Block
ACL-Manole-Loja,loja.manole.com.br,ALB,sa-east-1,AWS-AWSManagedRulesKnownBadInputsRuleSet,Managed,Block
ACL-Manole-Loja,loja.manole.com.br,ALB,sa-east-1,AWS-AWSManagedRulesBotControlRuleSet,Managed,Count
```

### 4.3 Coleta de Logs do WAF

1. No Console AWS: **WAF & Shield > Web ACLs > [sua ACL] > Logging and metrics**
2. Em **Sampled requests**, selecione o período (máximo 3h no console)
3. Copie os dados para o CSV

Arquivo: `data/waf_logs.csv`

```csv
timestamp,web_acl,regra,acao,source_ip,uri,country,http_method,status_code
2026-03-28T10:15:00Z,ACL-Manole-Prod,AWS-AWSManagedRulesCommonRuleSet,BLOCK,203.0.113.50,/admin,CN,GET,403
2026-03-28T10:16:00Z,ACL-Manole-Prod,AWS-AWSManagedRulesSQLiRuleSet,COUNT,198.51.100.23,/search?q=1' OR 1=1,US,GET,200
2026-03-28T10:17:00Z,ACL-Manole-Loja,RateLimitRule,BLOCK,192.0.2.100,/api/login,BR,POST,403
```

---

## 5. Etapa 2 — docker-compose.yml

Arquivo: `docker-compose.yml`

```yaml
version: '3'

services:
  grafana:
    image: grafana/grafana:9.5.20
    container_name: grafana-waf
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=Manole@WAF2026
      - GF_INSTALL_PLUGINS=frser-sqlite-datasource
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning
      - ./grafana/dashboards:/var/lib/grafana/dashboards
      - ./data:/var/lib/grafana/data-waf
      - grafana-storage:/var/lib/grafana
    restart: unless-stopped

volumes:
  grafana-storage:
```

**Credenciais de acesso ao Grafana:**
- URL: `http://<IP-DO-SERVIDOR>:3000`
- Usuário: `admin`
- Senha: `Manole@WAF2026`

---

## 6. Etapa 3 — Script de Ingestão

Arquivo: `scripts/ingest_data.py`

**Dependências:** Nenhuma externa. Usa apenas biblioteca padrão do Python 3 (`sqlite3`, `csv`, `os`, `datetime`).

**Pré-requisito no servidor:**
```bash
apt-get update && apt-get install -y python3 sqlite3
```

```python
#!/usr/bin/env python3
"""
ingest_data.py - Script de ingestão de dados do AWS WAF para SQLite.
Lê os CSVs de data/ e ingere no banco waf_dashboard.db.
Executar sempre que novos dados forem baixados do console AWS.

Uso:
    python3 scripts/ingest_data.py
"""

import sqlite3
import csv
import os
from datetime import datetime

# Caminhos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "waf_dashboard.db")
DATA_DIR = os.path.join(BASE_DIR, "data")


def create_tables(conn):
    """Cria as tabelas no SQLite se não existirem."""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventario_sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            web_acl TEXT NOT NULL,
            site TEXT NOT NULL,
            recurso_tipo TEXT,
            regiao TEXT,
            regra TEXT NOT NULL,
            tipo_regra TEXT,
            acao TEXT NOT NULL,
            data_coleta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS waf_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            web_acl TEXT,
            regra TEXT,
            acao TEXT,
            source_ip TEXT,
            uri TEXT,
            country TEXT,
            http_method TEXT,
            status_code INTEGER,
            data_ingestao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resumo_diario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            web_acl TEXT,
            total_requests INTEGER DEFAULT 0,
            total_blocked INTEGER DEFAULT 0,
            total_counted INTEGER DEFAULT 0,
            total_allowed INTEGER DEFAULT 0,
            UNIQUE(data, web_acl)
        )
    """)

    # Índices para performance nas queries do Grafana
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_waf_logs_timestamp ON waf_logs(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_waf_logs_acao ON waf_logs(acao)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_waf_logs_dedup ON waf_logs(timestamp, source_ip, uri)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resumo_diario_data ON resumo_diario(data)")

    conn.commit()
    print("[OK] Tabelas e indices criados/verificados.")


def import_inventario(conn):
    """Importa o inventário de sites e regras do CSV.
    Reimporta completamente a cada execução (DELETE + INSERT).
    """
    filepath = os.path.join(DATA_DIR, "inventario_sites.csv")
    if not os.path.exists(filepath):
        print(f"[AVISO] Arquivo {filepath} nao encontrado. Pulando inventario.")
        return 0

    cursor = conn.cursor()
    cursor.execute("DELETE FROM inventario_sites")

    count = 0
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
                INSERT INTO inventario_sites
                    (web_acl, site, recurso_tipo, regiao, regra, tipo_regra, acao)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                row.get('web_acl', '').strip(),
                row.get('site', '').strip(),
                row.get('recurso_tipo', '').strip(),
                row.get('regiao', '').strip(),
                row.get('regra', '').strip(),
                row.get('tipo_regra', '').strip(),
                row.get('acao', '').strip(),
            ))
            count += 1

    conn.commit()
    print(f"[OK] Inventario importado: {count} registros.")
    return count


def import_logs(conn):
    """Importa logs do WAF do CSV.
    Evita duplicatas verificando timestamp + source_ip + uri.
    """
    filepath = os.path.join(DATA_DIR, "waf_logs.csv")
    if not os.path.exists(filepath):
        print(f"[AVISO] Arquivo {filepath} nao encontrado. Pulando logs.")
        return 0

    cursor = conn.cursor()
    inseridos = 0
    duplicados = 0

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = row.get('timestamp', '').strip()
            ip = row.get('source_ip', '').strip()
            uri = row.get('uri', '').strip()

            # Verifica duplicata
            cursor.execute("""
                SELECT COUNT(*) FROM waf_logs
                WHERE timestamp = ? AND source_ip = ? AND uri = ?
            """, (ts, ip, uri))

            if cursor.fetchone()[0] > 0:
                duplicados += 1
                continue

            status = row.get('status_code', '0').strip()
            try:
                status = int(status)
            except ValueError:
                status = 0

            cursor.execute("""
                INSERT INTO waf_logs
                    (timestamp, web_acl, regra, acao, source_ip, uri, country, http_method, status_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ts,
                row.get('web_acl', '').strip(),
                row.get('regra', '').strip(),
                row.get('acao', '').strip(),
                ip,
                uri,
                row.get('country', '').strip(),
                row.get('http_method', '').strip(),
                status,
            ))
            inseridos += 1

    conn.commit()
    print(f"[OK] Logs importados: {inseridos} novos, {duplicados} duplicados ignorados.")
    return inseridos


def gerar_resumo_diario(conn):
    """Gera/atualiza a tabela de resumo diário a partir dos logs."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM resumo_diario")

    cursor.execute("""
        INSERT INTO resumo_diario (data, web_acl, total_requests, total_blocked, total_counted, total_allowed)
        SELECT
            DATE(timestamp) AS data,
            web_acl,
            COUNT(*) AS total_requests,
            SUM(CASE WHEN UPPER(acao) = 'BLOCK' THEN 1 ELSE 0 END) AS total_blocked,
            SUM(CASE WHEN UPPER(acao) = 'COUNT' THEN 1 ELSE 0 END) AS total_counted,
            SUM(CASE WHEN UPPER(acao) = 'ALLOW' THEN 1 ELSE 0 END) AS total_allowed
        FROM waf_logs
        WHERE timestamp IS NOT NULL AND timestamp != ''
        GROUP BY DATE(timestamp), web_acl
    """)

    total = cursor.execute("SELECT COUNT(*) FROM resumo_diario").fetchone()[0]
    conn.commit()
    print(f"[OK] Resumo diario gerado: {total} registros.")


def print_stats(conn):
    """Imprime estatísticas do banco para validação."""
    cursor = conn.cursor()
    sites = cursor.execute("SELECT COUNT(DISTINCT site) FROM inventario_sites").fetchone()[0]
    regras_block = cursor.execute("SELECT COUNT(*) FROM inventario_sites WHERE UPPER(acao) = 'BLOCK'").fetchone()[0]
    regras_count = cursor.execute("SELECT COUNT(*) FROM inventario_sites WHERE UPPER(acao) = 'COUNT'").fetchone()[0]
    total_logs = cursor.execute("SELECT COUNT(*) FROM waf_logs").fetchone()[0]
    total_blocked = cursor.execute("SELECT COUNT(*) FROM waf_logs WHERE UPPER(acao) = 'BLOCK'").fetchone()[0]

    print("")
    print("=" * 50)
    print("  RESUMO DO BANCO DE DADOS")
    print("=" * 50)
    print(f"  Sites protegidos:       {sites}")
    print(f"  Regras em BLOQUEIO:     {regras_block}")
    print(f"  Regras em MONITOR:      {regras_count}")
    print(f"  Total de logs:          {total_logs}")
    print(f"  Total bloqueados:       {total_blocked}")
    print(f"  Banco de dados:         {DB_PATH}")
    print("=" * 50)


if __name__ == "__main__":
    print(f"[INICIO] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"[INFO] Banco: {DB_PATH}")
    print(f"[INFO] Dados: {DATA_DIR}")
    print("")

    os.makedirs(DATA_DIR, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    try:
        create_tables(conn)
        import_inventario(conn)
        import_logs(conn)
        gerar_resumo_diario(conn)
        print_stats(conn)
    finally:
        conn.close()

    print("")
    print("[CONCLUIDO] Ingestao finalizada com sucesso.")
```

---

## 7. Etapa 4 — Provisioning do Grafana

### 7.1 Datasource SQLite

Arquivo: `grafana/provisioning/datasources/sqlite.yml`

```yaml
apiVersion: 1

datasources:
  - name: WAF-SQLite
    uid: WAF-SQLite
    type: frser-sqlite-datasource
    access: proxy
    jsonData:
      path: /var/lib/grafana/data-waf/waf_dashboard.db
    isDefault: true
    editable: true
```

> **IMPORTANTE:** O campo `uid: WAF-SQLite` é obrigatório. Sem ele, o Grafana gera um UID aleatório e os painéis do dashboard não encontram o datasource — ficam vazios sem erro visível.

### 7.2 Provider de Dashboards

Arquivo: `grafana/provisioning/dashboards/dashboards.yml`

```yaml
apiVersion: 1

providers:
  - name: 'WAF Dashboards'
    orgId: 1
    folder: 'WAF Manole'
    type: file
    disableDeletion: false
    editable: true
    options:
      path: /var/lib/grafana/dashboards
      foldersFromFilesStructure: false
```

---

## 8. Etapa 5 — Dashboard Grafana (9 painéis)

Arquivo: `grafana/dashboards/waf-manole-dashboard.json`

### IMPORTANTE — Formato dos Targets para o plugin frser-sqlite-datasource v4.0.1

O plugin SQLite **NÃO** usa o formato padrão do Grafana (`rawSql` + `format`). O formato correto exige **todos** estes campos em cada target:

```json
{
  "rawQueryText": "SELECT ...",
  "queryText": "SELECT ...",
  "refId": "A",
  "queryType": "table",
  "timeColumns": ["time", "ts"]
}
```

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| `queryText` | Sim | SQL que o plugin executa |
| `rawQueryText` | Sim | SQL original (usado internamente) |
| `queryType` | Sim | Sempre `"table"` |
| `timeColumns` | Sim | `["time", "ts"]` — colunas de tempo padrão |

> Se usar `rawSql` + `format: "table"` (formato MySQL/PostgreSQL), os painéis ficam vazios sem erro visível. O Explore funciona porque a UI envia no formato correto automaticamente.

### Dashboard JSON completo

```json
{
  "id": null,
  "uid": "waf-manole-main",
  "title": "WAF Manole - Indicadores de Protecao",
  "tags": ["waf", "seguranca", "manole"],
  "timezone": "browser",
  "refresh": "",
  "schemaVersion": 38,
  "editable": true,
  "panels": [
    {
      "id": 1,
      "title": "Inventario de Sites Protegidos",
      "description": "Lista de todos os sites atualmente protegidos pelo AWS WAF",
      "type": "table",
      "gridPos": { "h": 6, "w": 24, "x": 0, "y": 0 },
      "datasource": { "type": "frser-sqlite-datasource", "uid": "WAF-SQLite" },
      "targets": [
        {
          "rawQueryText": "SELECT DISTINCT site AS 'Site', web_acl AS 'Web ACL', recurso_tipo AS 'Tipo Recurso', regiao AS 'Regiao', data_coleta AS 'Ultima Coleta' FROM inventario_sites ORDER BY site",
          "queryText": "SELECT DISTINCT site AS 'Site', web_acl AS 'Web ACL', recurso_tipo AS 'Tipo Recurso', regiao AS 'Regiao', data_coleta AS 'Ultima Coleta' FROM inventario_sites ORDER BY site",
          "refId": "A",
          "queryType": "table",
          "timeColumns": ["time", "ts"]
        }
      ],
      "fieldConfig": {
        "defaults": {
          "custom": { "align": "left", "cellOptions": { "type": "auto" }, "filterable": true }
        },
        "overrides": []
      }
    },
    {
      "id": 2,
      "title": "Regras por Modo: Bloqueio vs Monitor",
      "description": "Detalhamento de cada regra WAF e seu modo de operacao (Block ou Count)",
      "type": "table",
      "gridPos": { "h": 10, "w": 24, "x": 0, "y": 6 },
      "datasource": { "type": "frser-sqlite-datasource", "uid": "WAF-SQLite" },
      "targets": [
        {
          "rawQueryText": "SELECT site AS 'Site', web_acl AS 'Web ACL', regra AS 'Regra', tipo_regra AS 'Tipo', CASE WHEN UPPER(acao) = 'BLOCK' THEN 'BLOQUEIO' WHEN UPPER(acao) = 'COUNT' THEN 'MONITOR' ELSE acao END AS 'Modo' FROM inventario_sites ORDER BY site, acao",
          "queryText": "SELECT site AS 'Site', web_acl AS 'Web ACL', regra AS 'Regra', tipo_regra AS 'Tipo', CASE WHEN UPPER(acao) = 'BLOCK' THEN 'BLOQUEIO' WHEN UPPER(acao) = 'COUNT' THEN 'MONITOR' ELSE acao END AS 'Modo' FROM inventario_sites ORDER BY site, acao",
          "refId": "A",
          "queryType": "table",
          "timeColumns": ["time", "ts"]
        }
      ],
      "fieldConfig": {
        "defaults": {
          "custom": { "align": "left", "cellOptions": { "type": "auto" }, "filterable": true }
        },
        "overrides": [
          {
            "matcher": { "id": "byName", "options": "Modo" },
            "properties": [
              { "id": "custom.cellOptions", "value": { "type": "color-text" } },
              {
                "id": "mappings",
                "value": [
                  {
                    "type": "value",
                    "options": {
                      "BLOQUEIO": { "text": "BLOQUEIO", "color": "green" },
                      "MONITOR": { "text": "MONITOR", "color": "yellow" }
                    }
                  }
                ]
              }
            ]
          }
        ]
      }
    },
    {
      "id": 3,
      "title": "Resumo: Regras em Bloqueio vs Monitor",
      "description": "Proporcao de regras em modo Block versus Count",
      "type": "piechart",
      "gridPos": { "h": 10, "w": 12, "x": 0, "y": 16 },
      "datasource": { "type": "frser-sqlite-datasource", "uid": "WAF-SQLite" },
      "targets": [
        {
          "rawQueryText": "SELECT CASE WHEN UPPER(acao) = 'BLOCK' THEN 'Bloqueio' ELSE 'Monitor' END AS modo, COUNT(*) AS total FROM inventario_sites GROUP BY modo",
          "queryText": "SELECT CASE WHEN UPPER(acao) = 'BLOCK' THEN 'Bloqueio' ELSE 'Monitor' END AS modo, COUNT(*) AS total FROM inventario_sites GROUP BY modo",
          "refId": "A",
          "queryType": "table",
          "timeColumns": ["time", "ts"]
        }
      ],
      "options": {
        "legend": { "displayMode": "table", "placement": "right", "values": ["value", "percent"] },
        "pieType": "pie",
        "reduceOptions": { "calcs": ["lastNotNull"], "fields": "", "values": true },
        "tooltip": { "mode": "single" }
      },
      "fieldConfig": {
        "overrides": [
          { "matcher": { "id": "byName", "options": "Bloqueio" }, "properties": [{ "id": "color", "value": { "fixedColor": "green", "mode": "fixed" } }] },
          { "matcher": { "id": "byName", "options": "Monitor" }, "properties": [{ "id": "color", "value": { "fixedColor": "yellow", "mode": "fixed" } }] }
        ]
      }
    },
    {
      "id": 4,
      "title": "Cobertura de Protecao por Site (% regras em bloqueio)",
      "description": "Percentual de regras em modo Block por site. Meta: acima de 80%",
      "type": "gauge",
      "gridPos": { "h": 10, "w": 12, "x": 12, "y": 16 },
      "datasource": { "type": "frser-sqlite-datasource", "uid": "WAF-SQLite" },
      "targets": [
        {
          "rawQueryText": "SELECT site AS 'Site', ROUND(100.0 * SUM(CASE WHEN UPPER(acao) = 'BLOCK' THEN 1 ELSE 0 END) / COUNT(*), 1) AS 'Cobertura' FROM inventario_sites GROUP BY site",
          "queryText": "SELECT site AS 'Site', ROUND(100.0 * SUM(CASE WHEN UPPER(acao) = 'BLOCK' THEN 1 ELSE 0 END) / COUNT(*), 1) AS 'Cobertura' FROM inventario_sites GROUP BY site",
          "refId": "A",
          "queryType": "table",
          "timeColumns": ["time", "ts"]
        }
      ],
      "fieldConfig": {
        "defaults": {
          "min": 0, "max": 100, "unit": "percent",
          "thresholds": {
            "mode": "absolute",
            "steps": [
              { "value": null, "color": "red" },
              { "value": 50, "color": "yellow" },
              { "value": 80, "color": "green" }
            ]
          }
        }
      },
      "options": {
        "reduceOptions": { "calcs": ["lastNotNull"], "fields": "/^Cobertura$/", "values": true },
        "showThresholdLabels": false,
        "showThresholdMarkers": true
      }
    },
    {
      "id": 5,
      "title": "Requests Bloqueados vs Monitorados (por dia)",
      "description": "Evolucao diaria de requests bloqueados e monitorados pelo WAF",
      "type": "barchart",
      "gridPos": { "h": 10, "w": 24, "x": 0, "y": 26 },
      "datasource": { "type": "frser-sqlite-datasource", "uid": "WAF-SQLite" },
      "targets": [
        {
          "rawQueryText": "SELECT data AS 'Data', total_blocked AS 'Bloqueados', total_counted AS 'Monitorados' FROM resumo_diario ORDER BY data",
          "queryText": "SELECT data AS 'Data', total_blocked AS 'Bloqueados', total_counted AS 'Monitorados' FROM resumo_diario ORDER BY data",
          "refId": "A",
          "queryType": "table",
          "timeColumns": ["time", "ts"]
        }
      ],
      "fieldConfig": {
        "defaults": {},
        "overrides": [
          { "matcher": { "id": "byName", "options": "Bloqueados" }, "properties": [{ "id": "color", "value": { "fixedColor": "red", "mode": "fixed" } }] },
          { "matcher": { "id": "byName", "options": "Monitorados" }, "properties": [{ "id": "color", "value": { "fixedColor": "orange", "mode": "fixed" } }] }
        ]
      },
      "options": {
