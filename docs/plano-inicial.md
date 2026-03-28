# PLANO INIICAL — DASHBOARD DE SEGURANÇA AWS WAF (MANOLE)

## 1. Objetivo

Estabelecer um plano inicial, viável e de baixo impacto operacional, para criação de um dashboard de segurança do AWS WAF da Manole, com foco em visibilidade executiva e acompanhamento do nível de proteção dos sites atualmente publicados.

O dashboard deverá, no mínimo:

1. Consolidar o inventário dos sites protegidos pelo AWS WAF.
2. Identificar quais regras estão em modo monitoramento (`COUNT`) e quais estão em modo bloqueio (`BLOCK`).
3. Exibir gráficos e indicadores em Grafana para apoio à diretoria e à área técnica.
4. Operar dentro da restrição atual de coleta manual de dados via console web da AWS.

---

## 2. Premissas e restrições

### 2.1 Premissas

- A Manole possui sites protegidos por AWS WAF.
- Há acesso à console web da AWS para consulta dos Web ACLs, regras e logs.
- Existe um servidor Linux disponível para hospedar a solução local de consolidação e visualização.
- O objetivo inicial é gerar visibilidade gerencial, mesmo que o processo de coleta ainda seja parcialmente manual.

### 2.2 Restrições atuais

- Não há acesso ao AWS CLI.
- Não há permissão para exportar logs do WAF para S3.
- Os dados precisarão ser obtidos manualmente pela console web da AWS.
- A infraestrutura disponível é limitada e deve ser considerada no dimensionamento da solução.

---

## 3. Infraestrutura disponível e impacto no desenho

### 3.1 Ambiente disponível

| Componente | Versão / Capacidade |
|---|---|
| OS | Ubuntu 18.04 LTS |
| Docker | 18.06.0-ce |
| docker-compose | 1.29.2 |
| Apache | 2.4.29 |
| GPU | Não disponível (CPU-only) |
| CPU | 2 vCPU |
| Memória RAM | 3.9 GB |
| Swap | 2.0 GB |

### 3.2 Implicações técnicas

A infraestrutura disponível é suficiente para um projeto inicial de dashboard, porém com algumas limitações relevantes:

- O servidor possui apenas 2 vCPU e 3.9 GB de RAM.
- Soluções mais pesadas, como Elasticsearch/OpenSearch, podem consumir memória excessiva e degradar o servidor.
- O uso de containers deve ser conservador.
- O armazenamento de longo prazo de grandes volumes de logs locais não é recomendado nesta fase.
- O desenho deve priorizar leveza, simplicidade operacional e facilidade de manutenção.

### 3.3 Diretriz de arquitetura decorrente

Diante desse cenário, a recomendação para a versão inicial é:

- **Não utilizar Elasticsearch/OpenSearch nesta fase inicial**.
- Utilizar uma base leve, como **SQLite** ou arquivos **CSV normalizados**.
- Utilizar **Grafana** como camada de visualização.
- Implementar ingestão por script simples em Python.
- Manter retenção de dados controlada, com sumarização periódica.

---

## 4. Arquitetura proposta para a versão inicial

A arquitetura recomendada para o cenário atual é a seguinte:

```text
Console AWS (consulta manual)
        ↓
Exportação / download manual dos dados
        ↓
Arquivos locais JSON / CSV
        ↓
Script de normalização em Python
        ↓
Base local leve (SQLite)
        ↓
Grafana
```

### 4.1 Justificativa

Esse modelo foi escolhido porque:

- funciona sem AWS CLI;
- funciona sem integração com S3;
- é compatível com a capacidade do servidor atual;
- reduz consumo de CPU e memória;
- permite evolução futura para arquitetura automatizada.

---

## 5. Escopo mínimo do dashboard

O dashboard deve contemplar, no mínimo, duas frentes:

### 5.1 Inventário de proteção

- Relação dos sites protegidos por AWS WAF.
- Identificação do Web ACL associado a cada site.
- Relação das regras por Web ACL.
- Identificação de regras em:
  - modo monitoramento (`COUNT`);
  - modo bloqueio (`BLOCK`).

### 5.2 Indicadores gráficos em Grafana

- Total de eventos analisados no período.
- Total de eventos bloqueados.
- Total de eventos apenas monitorados.
- Distribuição por ação (`ALLOW`, `BLOCK`, `COUNT`).
- Regras que mais geraram eventos.
- Sites com maior volume de eventos.
- Evolução temporal dos eventos.

---

## 6. Etapa 1 — Inventário dos sites e regras

### 6.1 Objetivo

Construir a base inicial de governança do WAF, identificando com precisão o que está protegido e como está configurado.

### 6.2 Coleta manual na console AWS

Para cada Web ACL, levantar:

- Nome do Web ACL
- Ambiente ou contexto de uso
- Recurso associado:
  - CloudFront
  - Application Load Balancer
  - API Gateway
  - outro, se aplicável
- Nome do site ou aplicação protegida
- Lista de regras
- Tipo da regra:
  - Managed Rule
  - Custom Rule
  - Rate-based Rule
- Ação configurada para cada regra:
  - `BLOCK`
  - `COUNT`
  - `ALLOW`, quando aplicável

### 6.3 Estrutura recomendada do inventário

| Site | Recurso AWS | Web ACL | Regra | Tipo da Regra | Modo | Observação |
|---|---|---|---|---|---|---|
| site1.manole.com.br | CloudFront | waf-site1 | AWS-AWSManagedRulesSQLiRuleSet | Managed | BLOCK | Ativa |
| site1.manole.com.br | CloudFront | waf-site1 | AWS-AWSManagedRulesCommonRuleSet | Managed | COUNT | Em avaliação |

### 6.4 Indicadores derivados do inventário

A partir dessa base, gerar:

- quantidade total de sites protegidos;
- quantidade total de Web ACLs;
- quantidade total de regras;
- percentual de regras em bloqueio;
- percentual de regras em monitoramento;
- identificação de lacunas de proteção.

---

## 7. Etapa 2 — Coleta manual dos dados operacionais

### 7.1 Cenário de coleta

Como não há integração automatizada disponível neste momento, a coleta deverá ser feita manualmente pela console web.

### 7.2 Fontes de dados a coletar

A coleta deve priorizar:

1. **Configuração dos Web ACLs e regras**, para inventário.
2. **Dados operacionais e logs visualizados na console**, para indicadores.
3. **Métricas resumidas por período**, quando disponíveis na interface.

### 7.3 Procedimento operacional sugerido

Periodicidade recomendada inicial: **semanal**.

Fluxo:

1. Acessar a console AWS.
2. Abrir cada Web ACL relevante.
3. Registrar a configuração atual das regras.
4. Consultar os eventos ou logs disponíveis na interface web.
5. Exportar ou copiar os dados manualmente para arquivos padronizados.
6. Salvar localmente em diretório organizado por data.

### 7.4 Estrutura de diretórios sugerida

```text
/opt/waf-dashboard/
├── input/
│   ├── inventario/
│   └── logs/
├── processed/
├── db/
├── scripts/
└── exports/
```

Exemplo de uso:

```text
/opt/waf-dashboard/input/inventario/2026-03-28-webacl-inventario.csv
/opt/waf-dashboard/input/logs/2026-03-28-waf-eventos.json
```

### 7.5 Observação importante

Como a coleta é manual, este dashboard deve ser tratado inicialmente como um **painel gerencial de acompanhamento periódico**, e não como plataforma de monitoramento em tempo real.

---

## 8. Etapa 3 — Normalização e consolidação dos dados

### 8.1 Objetivo

Transformar dados coletados manualmente em formato consistente para consulta no Grafana.

### 8.2 Tecnologia recomendada

- Python 3 para scripts de processamento
- SQLite como base local

### 8.3 Justificativa do SQLite

O SQLite é indicado neste cenário porque:

- consome poucos recursos;
- não exige serviço pesado adicional;
- é simples de manter;
- atende ao volume inicial esperado;
- funciona bem para dashboards leves e históricos resumidos.

### 8.4 Dados a normalizar

Campos recomendados para eventos do WAF:

- data_hora
- site
- web_acl
- regra
- tipo_regra
- acao
- ip_origem
- pais
- uri
- metodo_http
- observacao_coleta

Campos recomendados para inventário:

- data_referencia
- site
- recurso_aws
- web_acl
- regra
- tipo_regra
- modo
- observacao

### 8.5 Resultado esperado

Ao final do processamento, deve existir:

- uma tabela de inventário;
- uma tabela de eventos;
- eventualmente uma tabela agregada diária para melhor desempenho.

---

## 9. Etapa 4 — Camada de visualização com Grafana

### 9.1 Papel do Grafana

O Grafana será utilizado como camada de visualização para:

- construir painéis executivos;
- demonstrar tendência de eventos;
- exibir cobertura de proteção;
- facilitar leitura pela diretoria.

### 9.2 Observação sobre compatibilidade

Devido ao ambiente antigo:

- deve-se escolher uma versão de Grafana compatível e estável;
- deve-se evitar plugins excessivos;
- a instalação deve priorizar imagens leves e bem suportadas.

### 9.3 Recomendação prática

Subir apenas os serviços estritamente necessários:

- Grafana
- Eventual container auxiliar para rotina de processamento, se necessário

Evitar containers adicionais pesados nesta fase.

---

## 10. Etapa 5 — Dashboards mínimos recomendados

## 10.1 Dashboard 1 — Visão executiva de proteção

Objetivo: apresentar uma leitura simples para diretoria.

Indicadores:

- total de sites protegidos;
- total de Web ACLs monitorados;
- total de regras em bloqueio;
- total de regras em monitoramento;
- percentual de regras em bloqueio;
- percentual de regras em monitoramento.

Gráficos sugeridos:

- gráfico de barras: regras por modo (`BLOCK` x `COUNT`);
- tabela: inventário por site;
- indicador numérico: cobertura total.

---

## 10.2 Dashboard 2 — Efetividade operacional do WAF

Objetivo: mostrar o comportamento do WAF no período.

Indicadores:

- total de eventos analisados;
- total de bloqueios;
- total de eventos apenas monitorados;
- top regras com maior volume de acionamento;
- top sites com mais eventos.

Gráficos sugeridos:

- série temporal de eventos por dia;
- pizza ou barra por ação (`BLOCK`, `COUNT`, `ALLOW`);
- tabela com top regras;
- tabela com top origens ou países, se disponível.

---

## 10.3 Dashboard 3 — Risco e oportunidades de endurecimento

Objetivo: evidenciar onde há gap de proteção.

Indicadores:

- regras em `COUNT` com volume elevado;
- sites com baixo percentual de regras em bloqueio;
- regras mais acionadas ainda não promovidas para bloqueio.

Gráficos sugeridos:

- tabela de priorização;
- heatmap simples por site e por regra;
- ranking de ajustes recomendados.

---

## 11. Indicadores-chave para a diretoria

Os indicadores mais relevantes para leitura executiva devem ser:

### 11.1 Indicadores de cobertura

- Quantidade de sites protegidos
- Quantidade de Web ACLs ativos
- Percentual de regras em bloqueio
- Percentual de regras em monitoramento

### 11.2 Indicadores de efetividade

- Quantidade total de eventos observados
- Quantidade total de eventos bloqueados
- Taxa de bloqueio no período
- Regras mais efetivas

### 11.3 Indicadores de risco

- Regras críticas ainda em `COUNT`
- Sites com proteção parcial
- Tendência de crescimento de eventos suspeitos

---

## 12. Plano operacional de implantação

## 12.1 Fase 1 — Estruturação

Atividades:

- definir layout do inventário;
- definir modelo de coleta manual;
- criar diretórios locais;
- preparar banco SQLite;
- instalar Grafana;
- criar script inicial de ingestão.

Entregáveis:

- base inicial de inventário;
- ambiente local preparado;
- primeiro ciclo de ingestão funcional.

## 12.2 Fase 2 — Construção dos dashboards

Atividades:

- modelar tabelas;
- importar dados de inventário;
- importar eventos históricos disponíveis;
- criar painéis no Grafana;
- validar leitura executiva e técnica.

Entregáveis:

- dashboard executivo;
- dashboard operacional;
- dashboard de risco.

## 12.3 Fase 3 — Operação recorrente

Atividades:

- instituir rotina semanal de coleta;
- executar ingestão;
- revisar indicadores;
- registrar recomendações de ajuste de regras.

Entregáveis:

- histórico progressivo;
- acompanhamento contínuo;
- insumos para decisão gerencial.

---

## 13. Recomendações específicas para a infraestrutura atual

Dado o servidor disponível, recomenda-se:

1. **Não utilizar stack ELK/OpenSearch nesta fase**.
2. **Não manter grande volume bruto de logs por longos períodos**.
3. **Preferir retenção curta de dados detalhados**, por exemplo 30 a 60 dias.
4. **Gerar agregações diárias ou semanais** para retenção mais longa.
5. **Monitorar consumo de memória dos containers**.
6. **Executar processamento fora do horário de maior uso**, se o servidor também hospedar outros serviços.
7. **Evitar concorrência com serviços já críticos da máquina**.

---

## 14. Riscos do modelo inicial

Os principais riscos e limitações desta versão são:

- dependência de coleta manual;
- possibilidade de atraso na atualização dos dashboards;
- menor granularidade dos dados, dependendo do que a console permitir exportar;
- risco de inconsistência humana na coleta;
- impossibilidade de monitoramento em tempo real.

Esses riscos não inviabilizam o projeto, mas devem ser formalmente reconhecidos como limitações da fase inicial.

---

## 15. Evolução futura recomendada

Quando houver ampliação de permissões ou infraestrutura, recomenda-se evoluir para:

- coleta automatizada por S3;
- integração por AWS CLI ou API;
- pipeline automatizado de ingestão;
- base analítica mais robusta;
- alertas automáticos;
- integração com SIEM.

---

## 16. Conclusão

Considerando as restrições atuais de acesso à AWS e a capacidade limitada da infraestrutura disponível, é plenamente viável implantar uma **versão inicial** do dashboard de segurança do AWS WAF da Manole.

A estratégia recomendada é pragmática:

- coleta manual controlada;
- processamento leve local;
- armazenamento simples;
- visualização executiva em Grafana.

Esse modelo já permite entregar valor para a diretoria, criando visibilidade sobre:

- quais sites estão protegidos;
- quais regras realmente bloqueiam;
- quais regras ainda estão apenas monitorando;
- onde existem lacunas de endurecimento da proteção.

Embora não seja uma solução em tempo real, a abordagem proposta é adequada para iniciar governança, gerar evidências de proteção e apoiar decisões de melhoria contínua.
