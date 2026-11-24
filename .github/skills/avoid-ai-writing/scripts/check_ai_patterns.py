#!/usr/bin/env python3
"""Audit a Markdown/plain-text document for signs of AI-generated writing.

Implements the heuristics described in the accompanying ``SKILL.md``:

* occurrences of the forbidden (synthetic) lexicon;
* em-dashes used as parentheticals;
* inline bold text inside paragraphs;
* ASCII-art boxes made of ``+``/``-``/``|`` characters;
* GitHub Flavored Markdown alert blocks (``> [!NOTE]`` …).

The tool prints one finding per occurrence (file:line:col) and a summary
with an overall **AI contamination index**. Exit code 1 signals that the
index exceeds ``--max``, so the tool can gate a CI job.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Forbidden (synthetic) lexicon: term -> natural alternative.
AI_LEXICON: dict[str, str] = {
    'crucial': 'determinante / significativo',
    'pivotal': 'central / decisivo',
    'vital': 'essencial',
    'seamless': 'integrado / contínuo',
    'robust': 'estável / consistente',
    'showcases': 'demonstra',
    'boasts': 'oferece / apresenta',
    'delve': 'analisar / investigar',
    'tapestry': 'conjunto / estrutura',
    'mosaic': 'arranjo / configuração',
    'imperativo notar': 'nota-se que',
    'imperativo observar': 'constata-se que',
    'desempenha um papel fundamental': 'governa / regula / determina',
    'desempenham um papel': 'atuam / regem',
    'nesse cenário': 'sob essa condição',
    'nesse contexto': 'para tal regime',
    'notavelmente': 'sobressai por',
    'em suma': 'os resultados evidenciam',
    'em conclusão': 'a análise demonstra',
    'diante do exposto': 'portanto',
    'é importante notar que': 'nota-se que',
    'it is important to note': 'note that',
    'plays a key role': 'governs / regulates',
    'a testament to': 'evidencia',
}

_EM_DASH_RE = re.compile(r'—')
_INLINE_BOLD_RE = re.compile(r'\*\*[^*\n]+\*\*')
_GFM_ALERT_RE = re.compile(
    r'^\s*>\s*\[!(NOTE|WARNING|IMPORTANT|TIP|CAUTION)\]',
    re.IGNORECASE | re.MULTILINE,
)
# A line made only of box-drawing characters, with at least one non-dash
# glyph so that legitimate Markdown separators (---) are not flagged.
_ASCII_ART_LINE_RE = re.compile(r'^\s*[+\-|=<>^v·•]*[+|<>^v·•][+\-|=<>^v·•]*\s*$')


def _report(
    lines: list[str],
) -> tuple[list[tuple[int, int, str, str]], int, int, int]:
    """Scan lines and return (findings, ascii_lines, bold_chars, em_dashes)."""
    findings: list[tuple[int, int, str, str]] = []
    ascii_lines = 0
    bold_chars = 0
    em_dashes = 0

    for lineno, line in enumerate(lines, 1):
        for m in _EM_DASH_RE.finditer(line):
            em_dashes += 1
            findings.append((lineno, m.start() + 1, 'travessão (—)', line.strip()))
        for m in _INLINE_BOLD_RE.finditer(line):
            bold_chars += len(m.group(0))
            findings.append((lineno, m.start() + 1, 'negrito inline', m.group(0)))
        for m in _GFM_ALERT_RE.finditer(line):
            findings.append((lineno, m.start() + 1, 'alerta GFM', m.group(0).strip()))
        if _ASCII_ART_LINE_RE.match(line) and not re.match(r'^\s*-{3,}\s*$', line):
            ascii_lines += 1
            findings.append((lineno, 1, 'caixa ASCII', line.strip()))
        for term, alternative in AI_LEXICON.items():
            for m in re.finditer(re.escape(term), line, re.IGNORECASE):
                findings.append(
                    (
                        lineno,
                        m.start() + 1,
                        f'léxico "{term}" → "{alternative}"',
                        line.strip(),
                    )
                )

    return findings, ascii_lines, bold_chars, em_dashes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('document', type=Path, help='Markdown/plain-text file to audit')
    parser.add_argument(
        '--max',
        type=int,
        default=10,
        help='maximum tolerated contamination index (default 10)',
    )
    args = parser.parse_args(argv)

    if not args.document.exists():
        print(f'ERRO: arquivo não encontrado: {args.document}', file=sys.stderr)
        return 2

    lines = args.document.read_text(encoding='utf-8').splitlines()
    findings, ascii_lines, bold_chars, em_dashes = _report(lines)

    for lineno, col, kind, snippet in findings:
        print(f'{args.document.name}:{lineno}:{col}: {kind}')
        print(f'    {snippet[:120]}')

    # Weighted index: lexicon/dashes/alerts = 1, bold = 1 per occurrence,
    # ASCII boxes = 3 each. Normalised to a 0-100 scale for readability.
    lexicon_hits = sum(1 for f in findings if f[2].startswith('léxico'))
    bold_occurrences = sum(1 for f in findings if f[2] == 'negrito inline')
    alert_occurrences = sum(1 for f in findings if f[2] == 'alerta GFM')
    index = lexicon_hits + em_dashes + bold_occurrences + alert_occurrences + 3 * ascii_lines

    print()
    print('Resumo da auditoria:')
    print(f'  ocorrências de léxico de IA : {lexicon_hits}')
    print(f'  travessões (—)               : {em_dashes}')
    print(f'  negritos inline              : {bold_occurrences}')
    print(f'  alertas GFM                  : {alert_occurrences}')
    print(f'  caixas ASCII                 : {ascii_lines}')
    print(f'  Índice de contaminação       : {index}')

    if index > args.max:
        print(f'[FALHA] índice {index} acima do limite {args.max}.', file=sys.stderr)
        return 1
    print(f'[OK] índice {index} dentro do limite {args.max}.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
