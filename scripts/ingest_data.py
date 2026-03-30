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
    cursor.execute("""  
        CREATE INDEX IF NOT EXISTS idx_waf_logs_timestamp ON waf_logs(timestamp)  
    """)  
    cursor.execute("""  
        CREATE INDEX IF NOT EXISTS idx_waf_logs_acao ON waf_logs(acao)  
    """)  
    cursor.execute("""  
        CREATE INDEX IF NOT EXISTS idx_waf_logs_dedup ON waf_logs(timestamp, source_ip, uri)  
    """)  
    cursor.execute("""  
        CREATE INDEX IF NOT EXISTS idx_resumo_diario_data ON resumo_diario(data)  
    """)  
  
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
  
    # Limpa e recalcula todo o resumo  
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
    regras_block = cursor.execute(  
        "SELECT COUNT(*) FROM inventario_sites WHERE UPPER(acao) = 'BLOCK'"  
    ).fetchone()[0]  
    regras_count = cursor.execute(  
        "SELECT COUNT(*) FROM inventario_sites WHERE UPPER(acao) = 'COUNT'"  
    ).fetchone()[0]  
    total_logs = cursor.execute("SELECT COUNT(*) FROM waf_logs").fetchone()[0]  
    total_blocked = cursor.execute(  
        "SELECT COUNT(*) FROM waf_logs WHERE UPPER(acao) = 'BLOCK'"  
    ).fetchone()[0]  
  
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
