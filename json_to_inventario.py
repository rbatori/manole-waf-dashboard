#!/usr/bin/env python3  
"""  
Converte JSON exportado do AWS WAF Console (WAFv2) para inventario_sites.csv.  
  
Uso:  
  python3 json_to_inventario.py <webacl.json> [--regiao us-east-1] [--sites site1:tipo1,site2:tipo2]  
  
Exemplo:  
  python3 json_to_inventario.py ManoleACL.json \  
    --regiao Global \  
    --sites "d1234abc.cloudfront.net:CloudFront,meu-alb.us-east-1.elb.amazonaws.com:ALB"  
"""  
import json  
import csv  
import sys  
import argparse  
import os  
  
OUTPUT = "/opt/manole-waf-dashboard/data/inventario_sites.csv"  
  
  
def detectar_tipo_regra(rule):  
    """Detecta o tipo da regra com base no Statement."""  
    stmt = rule.get("Statement", {})  
  
    if "ManagedRuleGroupStatement" in stmt:  
        return "Managed"  
    if "RateBasedStatement" in stmt:  
        return "Rate-based"  
    if "RuleGroupReferenceStatement" in stmt:  
        return "Group"  
    # Tudo o resto é Custom (IPSet, Regex, GeoMatch, ByteMatch, etc.)  
    return "Custom"  
  
  
def detectar_acao(rule):  
    """Detecta a ação da regra (Action ou OverrideAction para managed/groups)."""  
    # Regras managed/group usam OverrideAction  
    override = rule.get("OverrideAction", {})  
    if override:  
        if "None" in override:  
            return "Block"  # usa a ação padrão do grupo (geralmente Block)  
        if "Count" in override:  
            return "Count"  
  
    # Regras custom/rate-based usam Action  
    action = rule.get("Action", {})  
    if "Block" in action:  
        return "Block"  
    if "Allow" in action:  
        return "Allow"  
    if "Count" in action:  
        return "Count"  
    if "Captcha" in action:  
        return "CAPTCHA"  
    if "Challenge" in action:  
        return "Challenge"  
  
    return "Unknown"  
  
  
def extrair_nome_regra(rule):  
    """Extrai nome legível da regra."""  
    nome = rule.get("Name", "")  
    stmt = rule.get("Statement", {})  
  
    # Para managed rules, inclui vendor + nome do grupo  
    if "ManagedRuleGroupStatement" in stmt:  
        mg = stmt["ManagedRuleGroupStatement"]  
        vendor = mg.get("VendorName", "AWS")  
        group_name = mg.get("Name", nome)  
        return f"{vendor}-{group_name}"  
  
    # Para rule group references  
    if "RuleGroupReferenceStatement" in stmt:  
        arn = stmt["RuleGroupReferenceStatement"].get("ARN", "")  
        # Extrai nome do ARN: ...rulegroup/NomeDoGrupo/id  
        parts = arn.split("/")  
        if len(parts) >= 2:  
            return f"RuleGroup-{parts[-2]}"  
  
    return nome  
  
  
def expandir_regras_managed(rule):  
    """  
    Se o managed rule group tem ExcludedRules, lista as sub-regras excluídas  
    como linhas separadas com ação Count.  
    """  
    stmt = rule.get("Statement", {})  
    if "ManagedRuleGroupStatement" not in stmt:  
        return []  
  
    mg = stmt["ManagedRuleGroupStatement"]  
    excluded = mg.get("ExcludedRules", [])  
    vendor = mg.get("VendorName", "AWS")  
    group_name = mg.get("Name", "")  
  
    sub_regras = []  
    for exc in excluded:  
        sub_regras.append({  
            "regra": f"{vendor}-{group_name}/{exc['Name']}",  
            "tipo_regra": "Managed (excluded)",  
            "acao": "Count"  
        })  
    return sub_regras  
  
  
def processar_json(json_path, regiao, sites):  
    """Processa o JSON e retorna lista de linhas para o CSV."""  
    with open(json_path, "r") as f:  
        data = json.load(f)  
  
    # O JSON pode ter o WebACL dentro de uma chave "WebACL" ou ser direto  
    if "WebACL" in data:  
        acl = data["WebACL"]  
    elif "Name" in data and "Rules" in data:  
        acl = data  
    else:  
        # Tenta a primeira chave que tenha "Rules"  
        for key in data:  
            if isinstance(data[key], dict) and "Rules" in data[key]:  
                acl = data[key]  
                break  
        else:  
            print("ERRO: Formato de JSON não reconhecido.")  
            sys.exit(1)  
  
    web_acl_name = acl.get("Name", os.path.splitext(os.path.basename(json_path))[0])  
    rules = acl.get("Rules", [])  
  
    # Se não informou sites, usa placeholder  
    if not sites:  
        sites = [("(preencher_site)", "(preencher_tipo)")]  
        print("AVISO: Nenhum site informado. Use --sites para associar recursos.")  
        print("       As linhas terão '(preencher_site)' como placeholder.\n")  
  
    rows = []  
    for rule in rules:  
        nome_regra = extrair_nome_regra(rule)  
        tipo_regra = detectar_tipo_regra(rule)  
        acao = detectar_acao(rule)  
  
        for site, recurso_tipo in sites:  
            rows.append([web_acl_name, site, recurso_tipo, regiao, nome_regra, tipo_regra, acao])  
  
        # Expande sub-regras excluídas de managed groups  
        for sub in expandir_regras_managed(rule):  
            for site, recurso_tipo in sites:  
                rows.append([  
                    web_acl_name, site, recurso_tipo, regiao,  
                    sub["regra"], sub["tipo_regra"], sub["acao"]  
                ])  
  
    return rows  
  
  
def main():  
    parser = argparse.ArgumentParser(description="Converte JSON do WAF Console para inventario_sites.csv")  
    parser.add_argument("json_files", nargs="+", help="Arquivo(s) JSON exportado(s) do WAF Console")  
    parser.add_argument("--regiao", default="us-east-1", help="Região (ex: us-east-1, Global)")  
    parser.add_argument("--sites", default="",  
                        help="Sites associados no formato 'site1:tipo1,site2:tipo2' "  
                             "(ex: 'd123.cloudfront.net:CloudFront,meu-alb:ALB')")  
    parser.add_argument("--output", default=OUTPUT, help=f"Caminho do CSV de saída (default: {OUTPUT})")  
    parser.add_argument("--append", action="store_true", help="Adiciona ao CSV existente em vez de sobrescrever")  
  
    args = parser.parse_args()  
  
    # Parse sites  
    sites = []  
    if args.sites:  
        for pair in args.sites.split(","):  
            parts = pair.strip().split(":")  
            if len(parts) == 2:  
                sites.append((parts[0].strip(), parts[1].strip()))  
            else:  
                print(f"AVISO: Formato inválido para site '{pair}'. Use 'site:tipo'.")  
  
    # Processa cada JSON  
    all_rows = []  
    for json_path in args.json_files:  
        print(f"Processando: {json_path}")  
        rows = processar_json(json_path, args.regiao, sites)  
        all_rows.extend(rows)  
        print(f"  → {len(rows)} linhas extraídas")  
  
    # Escreve CSV  
    mode = "a" if args.append else "w"  
    write_header = not args.append or not os.path.exists(args.output)  
  
    os.makedirs(os.path.dirname(args.output), exist_ok=True)  
    with open(args.output, mode, newline="") as f:  
        w = csv.writer(f)  
        if write_header:  
            w.writerow(["web_acl", "site", "recurso_tipo", "regiao", "regra", "tipo_regra", "acao"])  
        w.writerows(all_rows)  
  
    print(f"\nCSV gerado: {args.output} ({len(all_rows)} linhas)")  
  
  
if __name__ == "__main__":  
    main()
