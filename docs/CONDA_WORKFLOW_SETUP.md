# Conda Workflow Setup — Lessons Learned

Configuração do workflow `publish-conda.yml` para publicar pacotes no
[Anaconda.org](https://anaconda.org/prof_reginaldo_leao).

---

## Arquivo final: `.github/workflows/publish-conda.yml`

```yaml
name: Publish to Anaconda

on:
  push:
    tags:
      - "v*"

jobs:
  build-conda:
    name: Build — ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
    defaults:
      run:
        shell: bash
    steps:
      - uses: actions/checkout@v4

      - name: Setup miniconda
        uses: conda-incubator/setup-miniconda@v3
        with:
          auto-update-conda: true
          channels: conda-forge
          activate-environment: base

      - name: Install conda-build
        shell: bash -el {0}
        run: |
          conda install -y -c conda-forge conda-build
          conda build --version

      - name: Build conda package
        shell: bash -el {0}
        run: conda build conda.recipe/ --output-folder ./build

      - name: Upload build artifact
        uses: actions/upload-artifact@v4
        with:
          name: conda-package-${{ matrix.os }}
          path: ./build/noarch/*.conda

  publish:
    needs: build-conda
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Download build artifact
        uses: actions/download-artifact@v4
        with:
          name: conda-package-ubuntu-latest
          path: ./dist

      - name: Publish to Anaconda.org
        uses: anaconda/actions/upload-package@v0.3.1
        with:
          token: ${{ secrets.ANACONDA_ORG_TOKEN }}
          channel: prof_reginaldo_leao
          packages: ./dist/*.conda
```

---

## Problemas enfrentados e soluções

### 1. `conda build` não encontrado
**Erro:** `conda: error: argument COMMAND: invalid choice: 'build'`

**Causa:** O pacote `conda-build` não vem junto com o `conda`. Precisa ser instalado separadamente.

**Solução:** Instalar explicitamente com canal `conda-forge`:
```yaml
- name: Install conda-build
  shell: bash -el {0}
  run: |
    conda install -y -c conda-forge conda-build
    conda build --version
```
Também adicionar `activate-environment: base` no `setup-miniconda`.

---

### 2. Action `anaconda/actions@v0` não encontrada
**Erro:** `Unable to resolve action 'anaconda/actions@v0', unable to find version 'v0'`

**Causa:** Path incorreto e tag inexistente.

**Solução:** Usar o path completo com tag específica:
```yaml
uses: anaconda/actions/upload-package@v0.3.1   # ✅ correto
#  anaconda/actions@v0                           # ❌ errado (faltou /upload-package)
#  anaconda/actions/upload-package@v0            # ❌ errado (tag v0 não existe)
```

Tags disponíveis: `v0.1.0`, `v0.1.1`, `v0.2.0`, `v0.2.1`, `v0.2.2`, `v0.2.3`, `v0.3.0`, `v0.3.1`

---

### 3. `--user` não é opção válida no `anaconda upload`
**Erro:** `No such option: --user`

**Causa:** O CLI `anaconda` (anaconda-client) não aceita `--user` — o usuário é identificado pelo token.

**Solução:** Remover `--user` e usar apenas `anaconda upload ./dist/*.conda`.  
(Mais tarde substituído pela action oficial, que usa `channel:` em vez de `--user`.)

---

### 4. Token não resolvido (401 Unauthorized)
**Erro:** `Unauthorized: ('Authorization header was not given', 401)`

**Causas identificadas:**
- Secret estava em **Environment secrets**, não em **Repository secrets**.  
  → Environment secrets só são acessíveis se o job declarar `environment:`.
- Token gerado no Anaconda.org estava expirado/inválido.

**Solução:**
1. Mover o secret `ANACONDA_ORG_TOKEN` para **Repository secrets**  
   (Settings → Secrets and variables → Actions → Repository secrets)
2. Gerar novo token em: **https://anaconda.org/prof_reginaldo_leao/settings/access**

---

### 5. Evitar disparar workflow do PyPI durante testes
**Problema:** Ambos os workflows (`publish-pypi.yml` e `publish-conda.yml`) disparam com tags `v*`.  
Correções no workflow do conda exigiam vários pushes de tag, republicando indevidamente no PyPI.

**Solução:** Durante os testes, renomear temporariamente o workflow do PyPI:
```bash
mv .github/workflows/publish-pypi.yml .github/workflows/_publish-pypi.yml
```
Depois restaurar. (Os arquivos foram renomeados permanentemente para `publish-pypi.yml` e `publish-conda.yml`.)

---

## Checklist para configurar do zero

1. [ ] Criar token em https://anaconda.org/prof_reginaldo_leao/settings/access (Allow uploads)
2. [ ] Adicionar token como **Repository secret** `ANACONDA_ORG_TOKEN` no GitHub
3. [ ] Garantir `activate-environment: base` no `setup-miniconda`
4. [ ] Instalar `conda-build` com `-c conda-forge` explícito
5. [ ] Usar `anaconda/actions/upload-package@v0.3.1` (não `@v0`)
6. [ ] `channel:` = username do Anaconda.org (`prof_reginaldo_leao`)
7. [ ] Versão no `conda.recipe/meta.yaml` sincronizada com `pyglenn/__init__.py`
