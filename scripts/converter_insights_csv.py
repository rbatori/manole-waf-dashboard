#!/usr/bin/env python3  
"""  
converter_insights_csv.py  
Converte CSV exportado do CloudWatch Log Insights para waf_logs.csv  
"""  
import csv  
import os  
import glob  
  
INPUT_DIR = "/opt/manole-waf-dashboard/data/"  
OUTPUT = "/opt/manole-waf-dashboard/data/waf_logs.csv"  
  
# Ajuste aqui o nome da sua Web ACL  
WEB_ACL = "WEBACL-ALB"  
  
rows = []  
for fpath in sorted(glob.glob(os.path.join(INPUT_DIR, "logs-insights-*.csv"))):  
    print(f"Processando: {fpath}")  
    with open(fpath, newline="") as f:  
        reader = csv.DictReader(f)  
        for row in reader:  
            ts = row.get("@timestamp", "")  
            regra = row.get("regra", "")  
            acao = row.get("acao", "")  
            ip = row.get("ip_origem", "")  
            pais = row.get("pais", "")  
            metodo = row.get("metodo", "")  
            uri = row.get("uri", "")  
  
            rows.append([ts, WEB_ACL, regra, acao, ip, uri, pais, metodo, 0, ""])  
  
with open(OUTPUT, "w", newline="") as f:  
    w = csv.writer(f)  
    w.writerow(["timestamp", "web_acl", "regra", "acao", "source_ip", "uri", "country", "http_method", "status_code", "user_agent"])  
    w.writerows(rows)  
  
print(f"\nGerado {OUTPUT} com {len(rows)} linhas")
