# 📊 PLANO V2 — DASHBOARD DE SEGURANÇA AWS WAF (MANOLE)

## 🎯 OBJETIVO

Criar um dashboard executivo no Grafana para demonstrar o nível de proteção dos sites protegidos pelo AWS WAF, incluindo:

- Inventário dos sites protegidos
- Status das regras (monitor vs bloqueio)
- Indicadores de ataque e efetividade
- Visão clara para diretoria

---

## ⚠️ RESTRIÇÕES DO AMBIENTE

- Sem acesso ao AWS CLI
- Sem permissão para exportar logs para S3
- Coleta de dados exclusivamente via console web AWS
- Infra local disponível com Docker

---

## 🧱 ARQUITETURA PROPOSTA

Console AWS (download manual)
        ↓
Arquivos JSON (logs do WAF)
        ↓
Script de normalização (Python ou Bash)
        ↓
Banco local (Elasticsearch ou SQLite)
        ↓
Grafana

---

## 📌 ETAPA 1 — INVENTÁRIO DOS SITES E REGRAS

### Coleta manual (console AWS)

Para cada WebACL:

- Nome do WebACL
- Recurso associado:
  - CloudFront / ALB / API Gateway
- Lista de regras
- Ação de cada regra:
  - ALLOW
  - BLOCK
  - COUNT (modo monitor)

---

### 📋 Modelo de inventário

| Site | Tipo | WebACL | Regra | Modo | Tipo |
|------|------|--------|-------|------|------|
| site1 | CloudFront | waf-prod | SQLi | BLOCK | Managed |
| site1 | CloudFront | waf-prod | XSS | COUNT | Managed |

---

### 🎯 Indicadores derivados

- % de regras em BLOCK
- % de regras em COUNT (risco)
- Sites sem proteção WAF

---

## 📦 ETAPA 2 — COLETA MANUAL DOS LOGS

### Caminho no console:

AWS WAF → WebACL → Logging → Visualizar logs

---

### Procedimento:

1. Filtrar por período (ex: últimas 24h)
2. Exportar/download dos logs (JSON)
3. Salvar localmente em:

