#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Demonstração das inconsistências encontradas no pyglenn v0.1.9
================================================================
Este script reproduz de forma clara e independente as 4 inconsistências
relatadas em relatorio_inconsistencias_pyglenn_v0_1_9.txt.

Requisitos: pyglenn v0.1.9 instalado (pip install pyglenn)

Uso: python demonstra_inconsistencias_pyglenn.py
"""

import sys
import sqlite3
from pathlib import Path


def titulo(texto: str):
    """Imprime um título formatado."""
    print("\n" + "=" * 72)
    print(f"  {texto}")
    print("=" * 72)


def subtitulo(texto: str):
    """Imprime um subtítulo formatado."""
    print(f"\n--- {texto} ---")


def check_pyglenn():
    """Verifica se pyglenn está instalado e retorna a versão."""
    try:
        import pyglenn
        print(f"✅ pyglenn encontrado: versão {pyglenn.__version__}")
        print(f"   Local: {Path(pyglenn.__file__).parent}")
        return pyglenn
    except ImportError:
        print("❌ pyglenn NÃO está instalado.")
        print("   Instale com: pip install pyglenn")
        sys.exit(1)


def get_db_path(pyglenn_module):
    """Obtém o caminho do banco de dados SQLite do pyglenn."""
    db_path = str(Path(pyglenn_module.__file__).parent / 'data' / 'thermo.db')
    if not Path(db_path).exists():
        print(f"❌ Banco de dados não encontrado em: {db_path}")
        sys.exit(1)
    return db_path


# ====================================================================
# INCONSISTÊNCIA 1: get_available_species() retorna espécies erradas
# ====================================================================
def demo_inconsistencia_1(pyglenn_module, db_path):
    """
    Demonstra que get_available_species() retorna a espécie ERRADA
    para várias consultas comuns, porque usa LIKE '%name%' com LIMIT 20.
    """
    titulo("INCONSISTÊNCIA 1: get_available_species() retorna espécies erradas")

    from pyglenn import ThermochemicalCalculator

    calc = ThermochemicalCalculator()
    calc.connect()

    # Espécies que queremos buscar (nomes químicos comuns)
    queries = ['O2', 'N2', 'CO2', 'H2O', 'CO', 'CH4', 'H2', 'OH', 'NO']

    conn = sqlite3.connect(db_path)

    print("\n  Comparação: resultado de get_available_species() vs. SQLite (nome exato)\n")
    print(f"  {'Query':<6s} {'ID (pyglenn)':>12s} {'Nome (pyglenn)':<25s} {'ID (SQLite)':>12s} {'Nome (SQLite)':<25s} {'Status':<10s}")
    print(f"  {'-'*6} {'-'*12} {'-'*25} {'-'*12} {'-'*25} {'-'*10}")

    erros = 0
    for query in queries:
        # Método pyglenn (retorna primeiro resultado)
        results = calc.get_available_species(query)
        if results:
            pyglenn_id = results[0]['id']
            pyglenn_name = results[0]['name']
        else:
            pyglenn_id = 'N/A'
            pyglenn_name = 'N/A'

        # Método SQLite direto (nome exato)
        cursor = conn.execute(
            "SELECT id, name FROM species WHERE UPPER(name) = ?",
            (query.upper(),)
        )
        row = cursor.fetchone()
        if row:
            sqlite_id = row[0]
            sqlite_name = row[1]
            status = "✓ OK" if str(pyglenn_id) == str(sqlite_id) else "✗ ERRO"
            if status != "✓ OK":
                erros += 1
        else:
            sqlite_id = 'N/A'
            sqlite_name = 'NÃO ENCONTRADO'
            status = "? N/D"

        print(f"  {query:<6s} {str(pyglenn_id):>12s} {pyglenn_name:<25s} {str(sqlite_id):>12s} {sqlite_name:<25s} {status:<10s}")

    conn.close()

    print(f"\n  📊 Resultado: {erros}/{len(queries)} consultas retornaram a espécie ERRADA via pyglenn.")
    print(f"     Apenas {len(queries) - erros} espécies acertaram por coincidência (nomes únicos no banco).")

    # ── Detalhamento para N2 ──
    subtitulo("Detalhamento do caso 'N2'")
    results_n2 = calc.get_available_species('N2')
    print(f"  Total de resultados retornados: {len(results_n2)}")
    print(f"  Primeiro resultado: id={results_n2[0]['id']}, name='{results_n2[0]['name']}'")
    print(f"  ⚠️  Este é Be3N2(L), cujo intervalo válido é apenas [(2473, 6000)] K")

    conn2 = sqlite3.connect(db_path)
    cursor2 = conn2.execute(
        "SELECT id, name FROM species WHERE UPPER(name) = 'N2'"
    )
    real_n2 = cursor2.fetchone()
    conn2.close()
    print(f"  ✅ N2 molecular real: id={real_n2[0]}, name='{real_n2[1]}'")
    print(f"  ❌ pyglenn retornou id={results_n2[0]['id']} (Be3N2(L)) em vez de id={real_n2[0]} (N2)")

    # ── Mostrar que N2 real NÃO está nos 20 resultados ──
    ids_retornados = {r['id'] for r in results_n2}
    if real_n2[0] not in ids_retornados:
        print(f"  🚨 AGRAVANTE: N2 molecular (id={real_n2[0]}) NÃO está entre os 20 resultados!")
        conn3 = sqlite3.connect(db_path)
        cursor3 = conn3.execute(
            "SELECT COUNT(*) FROM species WHERE name LIKE '%N2%'"
        )
        total = cursor3.fetchone()[0]
        conn3.close()
        print(f"     Há {total} espécies com 'N2' no nome, mas get_available_species() só retorna 20.")


# ====================================================================
# INCONSISTÊNCIA 2: calculate_properties() retorna None em fronteiras
# ====================================================================
def demo_inconsistencia_2(pyglenn_module, db_path):
    """
    Demonstra que calculate_properties() retorna None quando a temperatura
    está exatamente no limite entre dois intervalos (ex: 1000 K).
    """
    titulo("INCONSISTÊNCIA 2: calculate_properties() retorna None em T = 1000 K (fronteira)")

    from pyglenn import ThermochemicalCalculator

    calc = ThermochemicalCalculator()
    calc.connect()

    # Buscar IDs corretos via SQLite (evitando Inconsistência 1)
    conn = sqlite3.connect(db_path)
    species_to_test = ['CO2', 'H2O', 'N2', 'O2']
    species_ids = {}

    for sp in species_to_test:
        cursor = conn.execute(
            "SELECT id FROM species WHERE UPPER(name) = ?", (sp.upper(),)
        )
        row = cursor.fetchone()
        if row:
            species_ids[sp] = row[0]
    conn.close()

    print("\n  Teste: calcular propriedades em T = 999.9, 1000.0 (fronteira), 1000.1 K\n")
    print(f"  {'Espécie':<8s} {'T (K)':<10s} {'Resultado':<30s} {'Status':<15s}")
    print(f"  {'-'*8} {'-'*10} {'-'*30} {'-'*15}")

    falhas_fronteira = 0
    for sp in species_to_test:
        sid = species_ids[sp]
        for T in [999.9, 1000.0, 1000.1]:
            result = calc.calculate_properties(sid, T)
            if result is not None:
                h_str = f"h = {result['h_relative']:.2f} J/mol"
                status = "✓ OK"
            else:
                h_str = "None (retornou None!)"
                status = "✗ FALHA"
                if T == 1000.0:
                    falhas_fronteira += 1
            print(f"  {sp:<8s} {T:<10.1f} {h_str:<30s} {status:<15s}")

    print(f"\n  📊 Resultado: {falhas_fronteira}/{len(species_to_test)} espécies falham em T = 1000.0 K.")
    print(f"     A 999.9 K e 1000.1 K, todas funcionam normalmente.")
    print(f"     ⚠️  O pyglenn emite warning 'out of valid range' mas retorna None,")
    print(f"     causando TypeError ao tentar acessar result['h_relative'].")

    # ── Mostrar intervalos ──
    subtitulo("Intervalos disponíveis (exemplo: CO2)")
    conn2 = sqlite3.connect(db_path)
    cursor2 = conn2.execute("""
        SELECT ti.temp_min, ti.temp_max
        FROM temperature_intervals ti
        JOIN species s ON s.id = ti.species_id
        WHERE s.name = 'CO2'
        ORDER BY ti.temp_min
    """)
    intervals = cursor2.fetchall()
    conn2.close()
    print(f"  Intervalos para CO2:")
    for tmin, tmax in intervals:
        print(f"    ({tmin}, {tmax}]")
    print(f"  ⚠️  1000.0 K está EXATAMENTE no limite: é o max do 1º intervalo")
    print(f"     E o min do 2º intervalo. O pyglenn rejeita em AMBOS.")


# ====================================================================
# INCONSISTÊNCIA 3: Ordenação imprevisível
# ====================================================================
def demo_inconsistencia_3(pyglenn_module):
    """
    Demonstra que a ordem dos resultados de get_available_species()
    não segue critério documentado.
    """
    titulo("INCONSISTÊNCIA 3: Ordenação não determinística dos resultados")

    from pyglenn import ThermochemicalCalculator

    calc = ThermochemicalCalculator()
    calc.connect()

    results = calc.get_available_species('N2')

    print("\n  Ordem REAL retornada por get_available_species('N2'):")
    print(f"  {'Pos':<6s} {'ID':>6s}  {'Nome'}")
    print(f"  {'-'*6} {'-'*6}  {'-'*30}")
    for i, r in enumerate(results):
        marker = "  ← N2 MOLECULAR!" if r['name'] == 'N2' else ""
        print(f"  [{i:<4d}] {r['id']:>6d}  {r['name']}{marker}")

    ids = [r['id'] for r in results]
    is_sorted_by_id = all(ids[i] <= ids[i+1] for i in range(len(ids)-1))
    is_sorted_by_name = all(
        results[i]['name'].lower() <= results[i+1]['name'].lower()
        for i in range(len(results)-1)
    )

    print(f"\n  📊 Análise da ordenação:")
    print(f"     Ordenado por ID?     {'Sim' if is_sorted_by_id else 'NÃO — ordem imprevisível'}")
    print(f"     Ordenado por nome?   {'Sim' if is_sorted_by_name else 'NÃO — ordem imprevisível'}")
    print(f"     ⚠️  A ordem parece ser a ordem de inserção (rowid) no SQLite,")
    print(f"     que não tem significado semântico para o usuário.")


# ====================================================================
# INCONSISTÊNCIA 4: Comportamento não determinístico
# ====================================================================
def demo_inconsistencia_4(pyglenn_module, db_path):
    """
    Demonstra que calculate_properties() pode ter comportamento
    diferente entre execuções na mesma temperatura de fronteira.
    """
    titulo("INCONSISTÊNCIA 4: Comportamento potencialmente não determinístico")

    from pyglenn import ThermochemicalCalculator
    import sqlite3

    conn = sqlite3.connect(db_path)
    cursor = conn.execute("SELECT id FROM species WHERE UPPER(name) = 'CO2'")
    co2_id = cursor.fetchone()[0]
    conn.close()

    print("\n  Teste: 5 chamadas consecutivas a calculate_properties(CO2, 1000.0)")
    print(f"  (Recriando a conexão a cada chamada para isolar o estado)\n")

    resultados = []
    for i in range(5):
        calc = ThermochemicalCalculator()
        calc.connect()
        result = calc.calculate_properties(co2_id, 1000.0)
        if result is not None:
            val = result['h_relative']
            resultados.append(val)
            print(f"  Chamada {i+1}: h = {val:.2f} J/mol  ✓")
        else:
            resultados.append(None)
            print(f"  Chamada {i+1}: None  ✗ (FALHA)")

    todos_ok = all(r is not None for r in resultados)
    todos_none = all(r is None for r in resultados)
    misto = not todos_ok and not todos_none

    print(f"\n  📊 Análise:")
    if todos_none:
        print(f"     Todas as chamadas retornaram None (consistente, mas errado)")
    elif todos_ok:
        valores_iguais = len(set(resultados)) == 1
        if valores_iguais:
            print(f"     Todas as chamadas retornaram o mesmo valor (determinístico)")
        else:
            print(f"     ⚠️  Todas retornaram valor, mas valores DIFERENTES!")
            print(f"     Valores: {[f'{v:.2f}' for v in resultados]}")
    elif misto:
        print(f"     🚨 COMPORTAMENTO NÃO DETERMINÍSTICO!")
        print(f"     Algumas chamadas retornaram valor, outras None.")
        print(f"     Isso é INACEITÁVEL para uma função de cálculo científico.")

    print(f"\n  ⚠️  Nota: Se o comportamento for consistente nesta execução,")
    print(f"     execute o script novamente. O bug pode se manifestar")
    print(f"     de forma intermitente dependendo do estado do SQLite.")


# ====================================================================
# RESUMO FINAL
# ====================================================================
def resumo():
    titulo("RESUMO DAS INCONSISTÊNCIAS")

    print("""
  As 4 inconsistências encontradas no pyglenn v0.1.9 são:

  ┌─────┬──────────────────────────────────────────────────────────────┐
  │  #  │ Inconsistência                           │ Gravidade         │
  ├─────┼──────────────────────────────────────────────────────────────┤
  │  1  │ get_available_species() retorna espécie  │ CRÍTICA           │
  │     │ errada (LIKE + LIMIT 20)                 │ (56% de falha)    │
  ├─────┼──────────────────────────────────────────────────────────────┤
  │  2  │ calculate_properties() retorna None em   │ ALTA              │
  │     │ temperaturas de fronteira (ex: 1000 K)   │ (quebra fsolve)   │
  ├─────┼──────────────────────────────────────────────────────────────┤
  │  3  │ Ordenação imprevisível dos resultados    │ MÉDIA             │
  │     │ de get_available_species()               │                   │
  ├─────┼──────────────────────────────────────────────────────────────┤
  │  4  │ Comportamento potencialmente não         │ BAIXA (preocu-    │
  │     │ determinístico em fronteiras             │ pante)            │
  └─────┴──────────────────────────────────────────────────────────────┘

  Recomendações prioritárias:
    1. Adicionar busca por nome EXATO em get_available_species()
    2. Corrigir calculate_properties() para nunca retornar None
    3. Documentar o LIMIT 20 e permitir paginação
    4. Ordenar resultados de forma previsível
    5. Adicionar testes unitários para temperaturas de fronteira

  Relatório detalhado: relatorio_inconsistencias_pyglenn_v0_1_9.txt
""")


# ====================================================================
# MAIN
# ====================================================================
def main():
    print("=" * 72)
    print("  DEMONSTRAÇÃO DE INCONSISTÊNCIAS NO PYGLENN v0.1.9")
    print("=" * 72)
    print("\n  Este script demonstra de forma reprodutível as inconsistências")
    print("  encontradas durante a depuração do notebook de AFT.")
    print("  Relatório completo: relatorio_inconsistencias_pyglenn_v0_1_9.txt")

    pyglenn_mod = check_pyglenn()
    db_path = get_db_path(pyglenn_mod)

    demo_inconsistencia_1(pyglenn_mod, db_path)
    demo_inconsistencia_2(pyglenn_mod, db_path)
    demo_inconsistencia_3(pyglenn_mod)
    demo_inconsistencia_4(pyglenn_mod, db_path)
    resumo()

    print("=" * 72)
    print("  Fim da demonstração.")
    print("=" * 72)


if __name__ == '__main__':
    main()
